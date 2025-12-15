"""
API Routes - Thin controller layer.

Routes should only handle:
- HTTP request parsing
- Input validation  
- Calling service layer
- HTTP response formatting

All business logic is delegated to StackService.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..realtime import broadcast_stack_update, broadcast_stacks_update
from ..services.stack_service import StackService, get_stack_service

router = APIRouter(prefix="/api", tags=["stacks"])
log = logging.getLogger(__name__)


def _get_service(db: Session = Depends(get_db)) -> StackService:
    """Dependency injection for StackService."""
    return get_stack_service(db)


# -----------------------------------------------------------------------------
# Stack List Operations
# -----------------------------------------------------------------------------


@router.get("/stacks")
def list_stacks(service: StackService = Depends(_get_service)) -> list[dict]:
    """
    Get all stacks from local database.
    
    This returns cached data. Use /stacks/sync to refresh from Portainer.
    """
    stacks = service.get_all_stacks()
    return [s.to_dict() for s in stacks]


@router.post("/stacks/sync")
async def sync_stacks(remove_missing: bool = False, service: StackService = Depends(_get_service)) -> dict:
    """
    Sync stacks from Portainer API to local database.
    
    Args:
        remove_missing: If True, remove stacks that no longer exist in Portainer
    """
    log.info("Starting stack sync from Portainer (remove_missing=%s)", remove_missing)

    result = await service.sync_from_portainer(remove_missing=remove_missing)

    if result.errors:
        log.warning("Sync completed with errors: %s", result.errors)

    # Broadcast updated stacks to connected clients
    try:
        stacks = service.get_all_stacks()
        await broadcast_stacks_update([s.to_dict() for s in stacks])
    except Exception:
        pass

    return {
        "imported": result.imported,
        "updated": result.updated,
        "removed": result.removed,
        "errors": result.errors,
    }


# Legacy alias for backwards compatibility
@router.get("/stacks/import")
async def import_stacks(service: StackService = Depends(_get_service)) -> dict:
    """
    Import stacks from Portainer (legacy endpoint).
    
    Deprecated: Use POST /stacks/sync instead.
    """
    result = await service.sync_from_portainer()

    # Broadcast updated stacks
    try:
        stacks = service.get_all_stacks()
        await broadcast_stacks_update([s.to_dict() for s in stacks])
    except Exception:
        pass

    return {"imported": result.imported}


# -----------------------------------------------------------------------------
# Single Stack Operations
# -----------------------------------------------------------------------------


@router.get("/stacks/{stack_id}")
def get_stack(stack_id: int, service: StackService = Depends(_get_service)) -> dict:
    """Get a single stack by ID."""
    stack = service.get_stack(stack_id)
    if not stack:
        raise HTTPException(status_code=404, detail="Stack not found")
    return stack.to_dict()


@router.get("/stacks/{stack_id}/indicator")
async def get_indicator(stack_id: int, refresh: bool = False, service: StackService = Depends(_get_service)) -> dict:
    """
    Get image status indicator for a stack.
    
    Args:
        stack_id: The stack ID
        refresh: If True, ask Portainer to re-check images (slower but fresh)
    """
    log.info("Fetching indicator for stack %s (refresh=%s)", stack_id, refresh)

    result = await service.refresh_indicator(stack_id, force_refresh=refresh)

    if not result.success and result.message == "Stack not found":
        raise HTTPException(status_code=404, detail="Stack not found")

    # Broadcast update to connected clients
    if result.stack:
        try:
            await broadcast_stack_update(result.stack.to_dict())
        except Exception:
            pass

    if result.stack:
        return {
            "id": result.stack.id,
            "status": result.stack.image_status,
            "message": result.stack.image_message,
            "last_checked": result.stack.image_last_checked.isoformat() if result.stack.image_last_checked else None,
        }

    raise HTTPException(status_code=502, detail=f"Failed to fetch indicator: {result.message}")


@router.post("/stacks/{stack_id}/update")
async def trigger_update(stack_id: int, service: StackService = Depends(_get_service)) -> dict:
    """
    Trigger a stack update via webhook.
    
    This calls the Portainer webhook to pull and redeploy the stack.
    """
    log.info("Triggering update for stack %s", stack_id)

    result = await service.trigger_update(stack_id)

    if not result.success:
        if result.message == "Stack not found":
            raise HTTPException(status_code=404, detail="Stack not found")
        elif result.message == "No webhook configured for this stack":
            raise HTTPException(status_code=400, detail=result.message)
        else:
            raise HTTPException(status_code=502, detail=f"Update failed: {result.message}")

    # Broadcast update to connected clients
    if result.stack:
        try:
            await broadcast_stack_update(result.stack.to_dict())
        except Exception:
            pass

    return {"updated": True, "stack": result.stack.to_dict() if result.stack else None}


@router.post("/stacks/{stack_id}/auto-update")
async def set_auto_update(stack_id: int, enabled: bool, service: StackService = Depends(_get_service)) -> dict:
    """Enable or disable auto-update for a stack."""
    result = service.set_auto_update(stack_id, enabled)

    if not result.success:
        raise HTTPException(status_code=404, detail="Stack not found")

    # Broadcast update to connected clients
    if result.stack:
        try:
            await broadcast_stack_update(result.stack.to_dict())
        except Exception:
            pass

    return {
        "id": result.stack.id if result.stack else stack_id,
        "auto_update_enabled": enabled,
    }


# -----------------------------------------------------------------------------
# Bulk Operations
# -----------------------------------------------------------------------------


@router.post("/stacks/refresh-all")
async def refresh_all_indicators(force: bool = False, service: StackService = Depends(_get_service)) -> dict:
    """
    Refresh indicators for all stacks.
    
    Args:
        force: If True, ask Portainer to re-check all images (slower)
    """
    log.info("Refreshing all indicators (force=%s)", force)

    result = await service.refresh_all_indicators(force_refresh=force)

    # Broadcast updated stacks
    try:
        stacks = service.get_all_stacks()
        await broadcast_stacks_update([s.to_dict() for s in stacks])
    except Exception:
        pass

    return result


@router.post("/stacks/auto-update-run")
async def run_auto_update(service: StackService = Depends(_get_service)) -> dict:
    """
    Run auto-updates for all eligible stacks.
    
    This triggers updates for stacks that have:
    - auto_update_enabled = True
    - image_status = 'outdated'
    """
    log.info("Running auto-updates")

    result = await service.run_auto_updates()

    # Broadcast updated stacks
    try:
        stacks = service.get_all_stacks()
        await broadcast_stacks_update([s.to_dict() for s in stacks])
    except Exception:
        pass

    return {"updated": result["updated"], "failed": result["failed"]}
