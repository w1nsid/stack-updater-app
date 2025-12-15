"""
Stack Service - Business logic layer for stack operations.

This service handles all business logic related to stacks:
- Syncing stacks from Portainer API to local database
- Fetching and updating image indicators
- Triggering stack updates via webhooks
- Auto-update logic

The web layer (routes) should only handle HTTP request/response concerns
and delegate all business logic to this service.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.stack import Stack
from .portainer_client import PortainerClient, StackInfo


class ImageStatus(str, Enum):
    """Standardized image status values."""
    UPDATED = "updated"
    OUTDATED = "outdated"
    PROCESSING = "processing"
    ERROR = "error"
    UNKNOWN = "unknown"

    @classmethod
    def from_portainer(cls, status: Optional[str]) -> "ImageStatus":
        """Convert Portainer status string to our standardized enum."""
        if not status:
            return cls.UNKNOWN
        normalized = status.strip().lower()
        mapping = {
            "updated": cls.UPDATED,
            "outdated": cls.OUTDATED,
            "processing": cls.PROCESSING,
            "preparing": cls.PROCESSING,
            "skipped": cls.UNKNOWN,
            "error": cls.ERROR,
        }
        return mapping.get(normalized, cls.UNKNOWN)


@dataclass
class StackDTO:
    """Data Transfer Object for Stack - used to pass stack data between layers."""
    id: int
    name: str
    webhook_url: Optional[str]
    image_status: Optional[str]
    image_message: Optional[str]
    image_last_checked: Optional[datetime]
    auto_update_enabled: bool
    last_updated_at: Optional[datetime]
    portainer_created_at: Optional[datetime]
    portainer_updated_at: Optional[datetime]

    @classmethod
    def from_model(cls, stack: Stack) -> "StackDTO":
        """Create DTO from SQLAlchemy model."""
        return cls(
            id=stack.id,
            name=stack.name,
            webhook_url=stack.webhook_url,
            image_status=stack.image_status,
            image_message=stack.image_message,
            image_last_checked=stack.image_last_checked,
            auto_update_enabled=stack.auto_update_enabled,
            last_updated_at=stack.last_updated_at,
            portainer_created_at=stack.portainer_created_at,
            portainer_updated_at=stack.portainer_updated_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "webhook_url": self.webhook_url,
            "image_status": self.image_status,
            "image_message": self.image_message,
            "image_last_checked": self.image_last_checked.isoformat() if self.image_last_checked else None,
            "auto_update_enabled": self.auto_update_enabled,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
            "portainer_created_at": self.portainer_created_at.isoformat() if self.portainer_created_at else None,
            "portainer_updated_at": self.portainer_updated_at.isoformat() if self.portainer_updated_at else None,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""
    imported: int
    updated: int
    removed: int
    errors: List[str]


@dataclass
class UpdateResult:
    """Result of an update operation."""
    success: bool
    message: str
    stack: Optional[StackDTO] = None


class StackService:
    """
    Service layer for stack operations.

    This class centralizes all business logic for:
    - Syncing stacks from Portainer
    - Managing stack indicators
    - Triggering updates
    - Auto-update logic
    """
    def __init__(self, db: Session, client: Optional[PortainerClient] = None):
        self._db = db
        self._client = client or PortainerClient()
        self._log = logging.getLogger(__name__)

    # -------------------------------------------------------------------------
    # Read Operations (from local database)
    # -------------------------------------------------------------------------

    def get_all_stacks(self) -> List[StackDTO]:
        """Get all stacks from local database."""
        stacks = self._db.query(Stack).order_by(Stack.name.asc()).all()
        return [StackDTO.from_model(s) for s in stacks]

    def get_stack(self, stack_id: int) -> Optional[StackDTO]:
        """Get a single stack by ID from local database."""
        stack = self._db.get(Stack, stack_id)
        return StackDTO.from_model(stack) if stack else None

    def get_auto_update_stacks(self) -> List[StackDTO]:
        """Get all stacks with auto-update enabled that are outdated."""
        stacks = self._db.query(Stack).filter(
            Stack.auto_update_enabled == True,  # noqa: E712
            Stack.image_status == ImageStatus.OUTDATED.value
        ).all()
        return [StackDTO.from_model(s) for s in stacks]

    # -------------------------------------------------------------------------
    # Sync Operations (Portainer -> Database)
    # -------------------------------------------------------------------------

    async def sync_from_portainer(self, remove_missing: bool = False) -> SyncResult:
        """
        Sync stacks from Portainer API to local database.

        Args:
            remove_missing: If True, remove stacks from DB that no longer exist in Portainer

        Returns:
            SyncResult with counts of imported, updated, removed stacks
        """
        result = SyncResult(imported=0, updated=0, removed=0, errors=[])

        try:
            portainer_stacks = await self._client.get_stacks_with_webhooks()
        except Exception as e:
            self._log.exception("Failed to fetch stacks from Portainer")
            result.errors.append(f"Failed to fetch stacks: {e}")
            return result

        portainer_ids = set()

        for stack_info in portainer_stacks:
            portainer_ids.add(stack_info.id)
            try:
                is_new = self._upsert_stack_from_portainer(stack_info)
                if is_new:
                    result.imported += 1
                else:
                    result.updated += 1
            except Exception as e:
                self._log.exception("Failed to sync stack %s", stack_info.id)
                result.errors.append(f"Failed to sync stack {stack_info.name}: {e}")

        # Optionally remove stacks that no longer exist in Portainer
        if remove_missing:
            existing_ids = {s.id for s in self._db.query(Stack.id).all()}
            to_remove = existing_ids - portainer_ids
            for stack_id in to_remove:
                stack = self._db.get(Stack, stack_id)
                if stack:
                    self._db.delete(stack)
                    result.removed += 1

        self._db.commit()
        self._log.info(
            "Sync completed: imported=%d, updated=%d, removed=%d, errors=%d", result.imported, result.updated,
            result.removed, len(result.errors)
        )
        return result

    def _upsert_stack_from_portainer(self, stack_info: StackInfo) -> bool:
        """
        Create or update a Stack row from Portainer data.

        Returns True if a new row was created, False if existing was updated.
        """
        stack = self._db.get(Stack, stack_info.id)
        is_new = stack is None

        if is_new:
            stack = Stack(id=stack_info.id)
            self._db.add(stack)

        # Update fields
        stack.name = stack_info.name
        stack.webhook_url = stack_info.webhook_url
        stack.portainer_created_at = stack_info.created_at
        stack.portainer_updated_at = stack_info.updated_at
        stack.updated_at = datetime.now(timezone.utc)

        return is_new

    # -------------------------------------------------------------------------
    # Indicator Operations (Image Status)
    # -------------------------------------------------------------------------

    async def refresh_indicator(self, stack_id: int, force_refresh: bool = False) -> UpdateResult:
        """
        Refresh the image indicator for a single stack from Portainer API.

        Args:
            stack_id: The stack ID
            force_refresh: If True, ask Portainer to re-check images (slower but fresh)

        Returns:
            UpdateResult with success status and updated stack data
        """
        stack = self._db.get(Stack, stack_id)
        if not stack:
            return UpdateResult(success=False, message="Stack not found")

        try:
            indicator = await self._client.fetch_image_status(stack_id, refresh=force_refresh)

            stack.image_status = indicator.get("Status")
            stack.image_message = indicator.get("Message")
            stack.image_last_checked = datetime.now(timezone.utc)
            stack.updated_at = datetime.now(timezone.utc)

            self._db.commit()

            return UpdateResult(success=True, message="Indicator refreshed", stack=StackDTO.from_model(stack))
        except Exception as e:
            self._log.exception("Failed to refresh indicator for stack %s", stack_id)

            # Update stack with error status
            stack.image_status = ImageStatus.ERROR.value
            stack.image_message = f"Failed to fetch indicator: {e}"
            stack.image_last_checked = datetime.now(timezone.utc)
            self._db.commit()

            return UpdateResult(success=False, message=str(e), stack=StackDTO.from_model(stack))

    async def refresh_all_indicators(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Refresh indicators for all stacks.

        Returns dict with success/failure counts.
        """
        stacks = self._db.query(Stack).all()
        success_count = 0
        error_count = 0

        for stack in stacks:
            result = await self.refresh_indicator(stack.id, force_refresh)
            if result.success:
                success_count += 1
            else:
                error_count += 1

        return {
            "total": len(stacks),
            "success": success_count,
            "errors": error_count,
        }

    # -------------------------------------------------------------------------
    # Update Operations (Trigger Webhooks)
    # -------------------------------------------------------------------------

    async def trigger_update(self, stack_id: int) -> UpdateResult:
        """
        Trigger a stack update via webhook.

        Returns UpdateResult with success status.
        """
        stack = self._db.get(Stack, stack_id)
        if not stack:
            return UpdateResult(success=False, message="Stack not found")

        if not stack.webhook_url:
            return UpdateResult(success=False, message="No webhook configured for this stack")

        try:
            success = await self._client.call_webhook(stack.webhook_url)

            if success:
                stack.last_updated_at = datetime.now(timezone.utc)
                stack.updated_at = datetime.now(timezone.utc)
                self._db.commit()

                # Refresh indicator after update (without force refresh for speed)
                await self.refresh_indicator(stack_id, force_refresh=False)

                # Re-fetch to get updated data
                updated_stack = self._db.get(Stack, stack_id)
                if updated_stack:
                    return UpdateResult(
                        success=True, message="Update triggered successfully", stack=StackDTO.from_model(updated_stack)
                    )
                return UpdateResult(success=True, message="Update triggered successfully")
            else:
                return UpdateResult(success=False, message="Webhook call failed")

        except Exception as e:
            self._log.exception("Failed to trigger update for stack %s", stack_id)
            return UpdateResult(success=False, message=str(e))

    async def run_auto_updates(self) -> Dict[str, Any]:
        """
        Run auto-updates for all eligible stacks (auto_update_enabled + outdated).

        Returns dict with counts of updated stacks.
        """
        stacks = self._db.query(Stack).filter(
            Stack.auto_update_enabled == True,  # noqa
            Stack.image_status == ImageStatus.OUTDATED.value  # noqa
        ).all()

        updated_count = 0
        failed_count = 0
        updated_stacks: List[StackDTO] = []

        for stack in stacks:
            result = await self.trigger_update(stack.id)
            if result.success:
                updated_count += 1
                if result.stack:
                    updated_stacks.append(result.stack)
            else:
                failed_count += 1

        self._log.info("Auto-update completed: %d updated, %d failed", updated_count, failed_count)

        return {
            "total": len(stacks),
            "updated": updated_count,
            "failed": failed_count,
            "stacks": [s.to_dict() for s in updated_stacks],
        }

    # -------------------------------------------------------------------------
    # Settings Operations
    # -------------------------------------------------------------------------

    def set_auto_update(self, stack_id: int, enabled: bool) -> UpdateResult:
        """Enable or disable auto-update for a stack."""
        stack = self._db.get(Stack, stack_id)
        if not stack:
            return UpdateResult(success=False, message="Stack not found")

        stack.auto_update_enabled = enabled
        stack.updated_at = datetime.now(timezone.utc)
        self._db.commit()

        return UpdateResult(
            success=True,
            message=f"Auto-update {'enabled' if enabled else 'disabled'}",
            stack=StackDTO.from_model(stack)
        )


# Convenience function to create service with dependency injection
def get_stack_service(db: Session, client: Optional[PortainerClient] = None) -> StackService:
    """Factory function to create StackService with proper dependencies."""
    return StackService(db, client)
