from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models.stack import Stack
from ..realtime import broadcast_staleness_payload


async def status_refresher():
    # Periodically evaluate staleness heuristics
    log = logging.getLogger(__name__)
    while True:
        try:
            with SessionLocal() as db:  # type: ignore[call-arg]
                _refresh_statuses(db)
            log.debug("Staleness refresh completed")
        except Exception:
            # Best-effort background job; avoid crashing
            log.exception("Background status refresher failed")
        await asyncio.sleep(settings.refresh_interval_seconds)


def _refresh_statuses(db: Session) -> None:
    now = datetime.now(timezone.utc)
    rows = db.query(Stack).all()
    threshold = timedelta(seconds=settings.outdated_after_seconds)
    for row in rows:
        row.last_status_check = now
        is_outdated = True
        if row.last_updated_at:
            # Ensure timezone-aware comparison (SQLite stores naive datetimes)
            last_updated = row.last_updated_at
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)
            is_outdated = now - last_updated > threshold
        row.is_outdated = is_outdated
    db.commit()
    # Snapshot payload BEFORE session/context ends to avoid detached access.
    payload = [{"id": r.id, "is_outdated": r.is_outdated} for r in rows]
    try:
        asyncio.create_task(broadcast_staleness_payload(payload))
    except Exception:
        pass
