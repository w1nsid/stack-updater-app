"""
Background Tasks - Periodic jobs for stack management.

This module handles:
- Periodic indicator refresh from Portainer
- Auto-update execution for outdated stacks
"""
from __future__ import annotations

import asyncio
import logging

from ..config import settings
from ..db import SessionLocal
from ..realtime import broadcast_stacks_update
from ..services.stack_service import StackService


async def indicator_refresh_task():
    """
    Periodically refresh image indicators from Portainer API.

    This runs at the configured refresh interval and updates all stacks'
    image status by querying Portainer's image indicator API.
    """
    log = logging.getLogger(__name__)
    log.info("Starting indicator refresh background task (interval=%ds)", settings.refresh_interval_seconds)

    while True:
        try:
            await asyncio.sleep(settings.refresh_interval_seconds)

            log.debug("Running periodic indicator refresh")

            with SessionLocal() as db:
                service = StackService(db)

                # Refresh all indicators (without forcing Portainer to re-check)
                result = await service.refresh_all_indicators(force_refresh=False)

                log.debug(
                    "Indicator refresh completed: total=%d, success=%d, errors=%d", result["total"], result["success"],
                    result["errors"]
                )

                # Broadcast updated stacks to connected clients
                try:
                    stacks = service.get_all_stacks()
                    await broadcast_stacks_update([s.to_dict() for s in stacks])
                except Exception:
                    pass

        except Exception:
            log.exception("Background indicator refresh failed")


async def auto_update_task():
    """
    Periodically run auto-updates for outdated stacks.

    This checks for stacks that have auto_update_enabled=True and
    image_status='outdated', then triggers their webhooks.
    """
    log = logging.getLogger(__name__)
    # Run auto-update check every 12 hours
    auto_update_interval = 43200
    log.info("Starting auto-update background task (interval=%ds)", auto_update_interval)

    while True:
        try:
            await asyncio.sleep(auto_update_interval)

            log.debug("Running periodic auto-update check")

            with SessionLocal() as db:
                service = StackService(db)

                # Get stacks eligible for auto-update
                eligible = service.get_auto_update_stacks()

                if eligible:
                    log.info("Found %d stacks eligible for auto-update", len(eligible))
                    result = await service.run_auto_updates()
                    log.info("Auto-update completed: updated=%d, failed=%d", result["updated"], result["failed"])

                    # Broadcast updated stacks
                    try:
                        stacks = service.get_all_stacks()
                        await broadcast_stacks_update([s.to_dict() for s in stacks])
                    except Exception:
                        pass

        except Exception:
            log.exception("Background auto-update task failed")
