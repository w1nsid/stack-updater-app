from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import Base, engine, get_db
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


def _parse_portainer_stack(s: Dict[str, Any], client: PortainerClient) -> Optional[Dict[str, Any]]:
    webhook_url = client.extract_webhook_url(s)
    if not webhook_url:
        return None
    sid = _to_int(s.get("Id"))
    if sid is None:
        return None
    name = s.get("Name") or f"stack-{sid}"
    stype = _to_int(s.get("Type"))
    created_dt = _ts_to_dt(s.get("CreationDate"))
    updated_dt = _ts_to_dt(s.get("UpdateDate"))
    return {
        "id": sid,
        "name": name,
        "webhook_url": webhook_url,
        "type": stype,
        "portainer_created_at": created_dt,
        "portainer_updated_at": updated_dt,
    }


async def _apply_parsed_stack(db: Session, client: PortainerClient, parsed: Dict[str, Any]) -> bool:
    """Create or update a Stack row from parsed data and refresh indicator.

    Returns True if a new row was created.
    """
    sid: int = parsed["id"]
    row: Optional[Stack] = db.get(Stack, sid)
    created = False
    if row is None:
        row = Stack(id=sid)
        db.add(row)
        created = True

    # Update fields if changed
    assert row is not None
    changed = False
    for field, value in parsed.items():
        if field == "id":
            continue
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed = True

    # Fetch image indicator with refresh=true initially
    try:
        indicator = await client.get_stack_image_indicator(sid, refresh=True)
        status = indicator.get("Status")
        message = indicator.get("Message")
        now = datetime.utcnow()
        if row.image_status != status:
            row.image_status = status
            changed = True
        if row.image_message != message:
            row.image_message = message
            changed = True
        row.image_last_checked = now
    except Exception:
        row.image_status = "Error"
        row.image_message = "Failed to fetch image indicator"
        row.image_last_checked = datetime.utcnow()
        changed = True

    if changed:
        row.updated_at = datetime.utcnow()
    return created


@router.on_event("startup")
def _init_db() -> None:
    Base.metadata.create_all(bind=engine)


@router.get("/stacks")
def list_stacks(db: Session = Depends(get_db)) -> List[dict]:
    rows = db.query(Stack).order_by(Stack.name.asc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "webhook_url": s.webhook_url,
            "type": s.type,
            "portainer_created_at": s.portainer_created_at.isoformat() if s.portainer_created_at else None,
            "portainer_updated_at": s.portainer_updated_at.isoformat() if s.portainer_updated_at else None,
            "image_status": s.image_status,
            "image_message": s.image_message,
            "image_last_checked": s.image_last_checked.isoformat() if s.image_last_checked else None,
            "auto_update_enabled": s.auto_update_enabled,
            "last_status_check": s.last_status_check.isoformat() if s.last_status_check else None,
            "last_updated_at": s.last_updated_at.isoformat() if s.last_updated_at else None,
            "is_outdated": s.is_outdated,
        } for s in rows
    ]


@router.get("/stacks/import")
async def import_stacks(db: Session = Depends(get_db)) -> dict:
    client = PortainerClient()
    try:
        log.info("Importing stacks from Portainer")
        stacks = await client.list_stacks()
    except Exception as e:  # pragma: no cover - pass error back
        log.exception("Failed to fetch stacks from Portainer: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch stacks from Portainer: {e}")

    imported = 0
    for s in stacks:
        parsed = _parse_portainer_stack(s, client)
        if not parsed:
            continue
        created = await _apply_parsed_stack(db, client, parsed)
        if created:
            imported += 1

    db.commit()
    # Broadcast each imported/updated stack row state (best effort)
    try:
        rows = db.query(Stack).order_by(Stack.id.asc()).all()
        for s in rows:
            await broadcast_stack_update(s)
    except Exception:  # pragma: no cover
        pass
    log.info("Import completed: %d new stacks", imported)
    return {"imported": imported}


@router.get("/stacks/{stack_id}/indicator")
async def get_indicator(stack_id: int, refresh: bool = False, db: Session = Depends(get_db)) -> dict:
    row = db.get(Stack, stack_id)
    if not row:
        log.warning("Indicator request for missing stack %s", stack_id)
        raise HTTPException(status_code=404, detail="Stack not found")
    client = PortainerClient()
    try:
        log.info("Fetching indicator for stack %s refresh=%s", stack_id, refresh)
        indicator = await client.get_stack_image_indicator(stack_id, refresh=refresh)
        row.image_status = indicator.get("Status")
        row.image_message = indicator.get("Message")
        row.image_last_checked = datetime.utcnow()
        db.commit()
    except Exception as e:
        log.exception("Failed to fetch indicator for stack %s: %s", stack_id, e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch indicator: {e}")
    lc = row.image_last_checked
    last_checked = lc.isoformat() if lc is not None else None
    return {"id": row.id, "status": row.image_status, "message": row.image_message, "last_checked": last_checked}


@router.post("/stacks/{stack_id}/update")
async def trigger_update(stack_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Stack, stack_id)
    if not row:
        log.warning("Update requested for missing stack %s", stack_id)
        raise HTTPException(status_code=404, detail="Stack not found")
    if not row.webhook_url:
        log.warning("Update requested but webhook missing for stack %s", stack_id)
        raise HTTPException(status_code=400, detail="Webhook URL not configured for this stack")
    client = PortainerClient()
    log.info("Triggering update via webhook for stack %s", stack_id)
    ok = await client.trigger_webhook(row.webhook_url)
    if not ok:
        log.error("Webhook update failed for stack %s", stack_id)
        raise HTTPException(status_code=502, detail="Webhook call failed")
    row.last_updated_at = datetime.utcnow()
    # Optionally, after update, fetch indicator without refresh to snapshot status
    try:
        indicator = await client.get_stack_image_indicator(stack_id, refresh=False)
        row.image_status = indicator.get("Status")
        row.image_message = indicator.get("Message")
        row.image_last_checked = datetime.utcnow()
    except Exception:
        pass
    db.commit()
    try:
        await broadcast_stack_update(row)
    except Exception:  # pragma: no cover
        pass
    return {"updated": True}


@router.post("/stacks/{stack_id}/auto-update")
async def set_auto_update(stack_id: int, enabled: bool, db: Session = Depends(get_db)) -> dict:
    row = db.get(Stack, stack_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stack not found")
    row.auto_update_enabled = enabled
    db.commit()
    try:
        await broadcast_stack_update(row)
    except Exception:  # pragma: no cover
        pass
    return {"id": row.id, "auto_update_enabled": row.auto_update_enabled}


@router.post("/stacks/auto-update-run")
async def run_auto_update(db: Session = Depends(get_db)) -> dict:
    client = PortainerClient()
    updated = 0
    rows = db.query(Stack).filter(Stack.auto_update_enabled == True, Stack.is_outdated == True).all()  # noqa: E712
    log.info("Running auto-update for %d outdated stacks", len(rows))
    for row in rows:
        if not row.webhook_url:
            log.debug("Skipping stack %s - no webhook", row.id)
            continue
        ok = await client.trigger_webhook(row.webhook_url)
        if ok:
            row.last_updated_at = datetime.utcnow()
            row.is_outdated = False
            updated += 1
    db.commit()
    try:
        for r in rows:
            await broadcast_stack_update(r)
    except Exception:  # pragma: no cover
        pass
    log.info("Auto-update completed: %d stacks updated", updated)
    return {"updated": updated}


@router.post("/stacks/{stack_id}/check-now")
async def check_now(stack_id: int, db: Session = Depends(get_db)) -> dict:
    # Simple age-based staleness: outdated if last update is older than threshold
    row = db.get(Stack, stack_id)
    if not row:
        log.warning("Check-now requested for missing stack %s", stack_id)
        raise HTTPException(status_code=404, detail="Stack not found")

    now = datetime.utcnow()
    row.last_status_check = now
    threshold = timedelta(seconds=settings.outdated_after_seconds)
    is_outdated = True
    if row.last_updated_at:
        is_outdated = now - row.last_updated_at > threshold
    row.is_outdated = is_outdated
    db.commit()
    try:
        await broadcast_stack_update(row)
    except Exception:  # pragma: no cover
        pass
    log.info("Check-now completed for stack %s: outdated=%s", stack_id, is_outdated)
    return {"id": row.id, "is_outdated": row.is_outdated}
