from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Stack(Base):
    __tablename__ = "stacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Portainer Stack ID
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Optional Portainer metadata (not required for operation but useful to show)
    type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    portainer_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    portainer_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    auto_update_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Portainer image indicator cache
    image_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    last_status_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_outdated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
