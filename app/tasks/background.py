from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models.stack import Stack


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
    now = datetime.utcnow()
    rows = db.query(Stack).all()
    threshold = timedelta(seconds=settings.outdated_after_seconds)
    for row in rows:
        row.last_status_check = now
        is_outdated = True
        if row.last_updated_at:
            is_outdated = now - row.last_updated_at > threshold
        row.is_outdated = is_outdated
    db.commit()
