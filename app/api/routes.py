from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.stack import Stack
from ..realtime import broadcast_stack_update
from ..services.portainer_client import PortainerClient

router = APIRouter(prefix="/api", tags=["stacks"])
log = logging.getLogger(__name__)


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _ts_to_dt(value: Any) -> Optional[datetime]:
    try:
        return datetime.utcfromtimestamp(int(value)) if value is not None else None
    except Exception:
        return None


def _parse_portainer_stack(stack_data: Dict[str, Any], client: PortainerClient) -> Optional[Dict[str, Any]]:
    webhook_url = client.extract_webhook_url(stack_data)
    if not webhook_url:
        return None
    stack_id = _to_int(stack_data.get("Id"))
    if stack_id is None:
        return None
    stack_name = stack_data.get("Name") or f"stack-{stack_id}"
    created_datetime = _ts_to_dt(stack_data.get("CreationDate"))
    updated_datetime = _ts_to_dt(stack_data.get("UpdateDate"))
    return {
        "id": stack_id,
        "name": stack_name,
        "webhook_url": webhook_url,
        "portainer_created_at": created_datetime,
        "portainer_updated_at": updated_datetime,
    }


async def _apply_parsed_stack(db: Session, client: PortainerClient, parsed_data: Dict[str, Any]) -> bool:
    """Create or update a Stack row from parsed data and refresh indicator.

    Returns True if a new row was created.
    """
    stack_id: int = parsed_data["id"]
    stack_row: Optional[Stack] = db.get(Stack, stack_id)
    is_new_stack = False
    if stack_row is None:
        stack_row = Stack(id=stack_id)
        db.add(stack_row)
        is_new_stack = True

    # Update fields if changed
    assert stack_row is not None
    has_changes = False
    for field_name, field_value in parsed_data.items():
        if field_name == "id":
            continue
        if getattr(stack_row, field_name) != field_value:
            setattr(stack_row, field_name, field_value)
            has_changes = True

    # Fetch image indicator with refresh=true initially
    try:
        indicator = await client.get_stack_image_indicator(stack_id, refresh=True)
        image_status = indicator.get("Status")
        image_message = indicator.get("Message")
        current_time = datetime.now(timezone.utc)
        if stack_row.image_status != image_status:
            stack_row.image_status = image_status
            has_changes = True
        if stack_row.image_message != image_message:
            stack_row.image_message = image_message
            has_changes = True
        stack_row.image_last_checked = current_time
    except Exception:
        stack_row.image_status = "Error"
        stack_row.image_message = "Failed to fetch image indicator"
        stack_row.image_last_checked = datetime.now(timezone.utc)
        has_changes = True

    if has_changes:
        stack_row.updated_at = datetime.now(timezone.utc)
    return is_new_stack


# NOTE: Database initialization is handled in app/main.py lifespan handler


@router.get("/stacks")
def list_stacks(db: Session = Depends(get_db)) -> List[dict]:
    stack_rows = db.query(Stack).order_by(Stack.name.asc()).all()
    return [
        {
            "id": stack.id,
            "name": stack.name,
            "webhook_url": stack.webhook_url,
            "portainer_created_at": stack.portainer_created_at.isoformat() if stack.portainer_created_at else None,
            "portainer_updated_at": stack.portainer_updated_at.isoformat() if stack.portainer_updated_at else None,
            "image_status": stack.image_status,
            "image_message": stack.image_message,
            "image_last_checked": stack.image_last_checked.isoformat() if stack.image_last_checked else None,
            "auto_update_enabled": stack.auto_update_enabled,
            "last_status_check": stack.last_status_check.isoformat() if stack.last_status_check else None,
            "last_updated_at": stack.last_updated_at.isoformat() if stack.last_updated_at else None,
            "is_outdated": stack.is_outdated,
        } for stack in stack_rows
    ]


@router.get("/stacks/import")
async def import_stacks(db: Session = Depends(get_db)) -> dict:
    client = PortainerClient()
    try:
        log.info("Importing stacks from Portainer")
        portainer_stacks = await client.list_stacks()
    except Exception as e:  # pragma: no cover - pass error back
        log.exception("Failed to fetch stacks from Portainer: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch stacks from Portainer: {e}")

    imported_count = 0
    for stack_data in portainer_stacks:
        parsed_stack = _parse_portainer_stack(stack_data, client)
        if not parsed_stack:
            continue
        is_new_stack = await _apply_parsed_stack(db, client, parsed_stack)
        if is_new_stack:
            imported_count += 1

    db.commit()
    # Broadcast each imported/updated stack row state (best effort)
    try:
        all_stacks = db.query(Stack).order_by(Stack.id.asc()).all()
        for stack_row in all_stacks:
            await broadcast_stack_update(stack_row)
    except Exception:  # pragma: no cover
        pass
    log.info("Import completed: %d new stacks", imported_count)
    return {"imported": imported_count}


@router.get("/stacks/{stack_id}/indicator")
async def get_indicator(stack_id: int, refresh: bool = False, db: Session = Depends(get_db)) -> dict:
    stack_row = db.get(Stack, stack_id)
    if not stack_row:
        log.warning("Indicator request for missing stack %s", stack_id)
        raise HTTPException(status_code=404, detail="Stack not found")
    client = PortainerClient()
    try:
        log.info("Fetching indicator for stack %s refresh=%s", stack_id, refresh)
        indicator = await client.get_stack_image_indicator(stack_id, refresh=refresh)
        stack_row.image_status = indicator.get("Status")
        stack_row.image_message = indicator.get("Message")
        stack_row.image_last_checked = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        log.exception("Failed to fetch indicator for stack %s: %s", stack_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch indicator: {e}")
    last_checked_time = stack_row.image_last_checked
    last_checked_iso = last_checked_time.isoformat() if last_checked_time is not None else None
    return {
        "id": stack_row.id,
        "status": stack_row.image_status,
        "message": stack_row.image_message,
        "last_checked": last_checked_iso,
    }


@router.post("/stacks/{stack_id}/update")
async def trigger_update(stack_id: int, db: Session = Depends(get_db)) -> dict:
    stack_row = db.get(Stack, stack_id)
    if not stack_row:
        log.warning("Update requested for missing stack %s", stack_id)
        raise HTTPException(status_code=404, detail="Stack not found")
    if not stack_row.webhook_url:
        log.warning("Update requested but webhook missing for stack %s", stack_id)
        raise HTTPException(status_code=400, detail="Webhook URL not configured for this stack")
    client = PortainerClient()
    log.info("Triggering update via webhook for stack %s", stack_id)
    webhook_success = await client.trigger_webhook(stack_row.webhook_url)
    if not webhook_success:
        log.error("Webhook update failed for stack %s", stack_id)
        raise HTTPException(status_code=502, detail="Webhook call failed")
    stack_row.last_updated_at = datetime.now(timezone.utc)
    # Optionally, after update, fetch indicator without refresh to snapshot status
    try:
        indicator = await client.get_stack_image_indicator(stack_id, refresh=False)
        stack_row.image_status = indicator.get("Status")
        stack_row.image_message = indicator.get("Message")
        stack_row.image_last_checked = datetime.now(timezone.utc)
    except Exception:
        pass
    db.commit()
    try:
        await broadcast_stack_update(stack_row)
    except Exception:  # pragma: no cover
        pass
    return {"updated": True}


@router.post("/stacks/{stack_id}/auto-update")
async def set_auto_update(stack_id: int, enabled: bool, db: Session = Depends(get_db)) -> dict:
    stack_row = db.get(Stack, stack_id)
    if not stack_row:
        raise HTTPException(status_code=404, detail="Stack not found")
    stack_row.auto_update_enabled = enabled
    db.commit()
    try:
        await broadcast_stack_update(stack_row)
    except Exception:  # pragma: no cover
        pass
    return {"id": stack_row.id, "auto_update_enabled": stack_row.auto_update_enabled}


@router.post("/stacks/auto-update-run")
async def run_auto_update(db: Session = Depends(get_db)) -> dict:
    client = PortainerClient()
    updated_count = 0
    outdated_stacks = db.query(Stack).filter(Stack.auto_update_enabled, Stack.is_outdated).all()
    log.info("Running auto-update for %d outdated stacks", len(outdated_stacks))
    for stack_row in outdated_stacks:
        if not stack_row.webhook_url:
            log.debug("Skipping stack %s - no webhook", stack_row.id)
            continue
        webhook_success = await client.trigger_webhook(stack_row.webhook_url)
        if webhook_success:
            stack_row.last_updated_at = datetime.now(timezone.utc)
            stack_row.is_outdated = False
            updated_count += 1
    db.commit()
    try:
        for stack_row in outdated_stacks:
            await broadcast_stack_update(stack_row)
    except Exception:  # pragma: no cover
        pass
    log.info("Auto-update completed: %d stacks updated", updated_count)
    return {"updated": updated_count}


@router.post("/stacks/{stack_id}/check-now")
async def check_now(stack_id: int, db: Session = Depends(get_db)) -> dict:
    # Simple age-based staleness: outdated if last update is older than threshold
    stack_row = db.get(Stack, stack_id)
    if not stack_row:
        log.warning("Check-now requested for missing stack %s", stack_id)
        raise HTTPException(status_code=404, detail="Stack not found")

    current_time = datetime.now(timezone.utc)
    stack_row.last_status_check = current_time
    staleness_threshold = timedelta(seconds=settings.outdated_after_seconds)
    is_outdated = True
    if stack_row.last_updated_at:
        # Ensure timezone-aware comparison (SQLite stores naive datetimes)
        last_updated = stack_row.last_updated_at
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        is_outdated = current_time - last_updated > staleness_threshold
    stack_row.is_outdated = is_outdated
    db.commit()
    try:
        await broadcast_stack_update(stack_row)
    except Exception:  # pragma: no cover
        pass
    log.info("Check-now completed for stack %s: outdated=%s", stack_id, is_outdated)
    return {"id": stack_row.id, "is_outdated": stack_row.is_outdated}
