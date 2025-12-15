"""Portainer API Client.

Clean, straightforward client for interacting with Portainer's REST API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StackInfo:
    """Represents a Portainer stack with essential information."""

    id: int
    name: str
    stack_type: int | None
    webhook_url: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @property
    def has_webhook(self) -> bool:
        return bool(self.webhook_url)


def parse_timestamp(unix_timestamp: Any) -> datetime | None:
    """Convert Unix timestamp to datetime. Returns None if invalid."""
    if unix_timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(int(unix_timestamp), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


class PortainerClient:
    """Client for Portainer API interactions."""

    DEFAULT_TIMEOUT = 30.0

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool | None = None,
        cloudflare_client_id: str | None = None,
        cloudflare_client_secret: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.portainer_url).rstrip("/")
        self.api_key = api_key or settings.portainer_api_key
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.verify_ssl

        # Build headers for API requests
        self.api_headers = self._build_api_headers(
            api_key=self.api_key,
            cf_client_id=cloudflare_client_id or settings.cf_access_client_id,
            cf_client_secret=cloudflare_client_secret or settings.cf_access_client_secret,
        )

        # Webhook requests only need Cloudflare headers (no API key)
        self.webhook_headers = self._build_cloudflare_headers(
            cf_client_id=cloudflare_client_id or settings.cf_access_client_id,
            cf_client_secret=cloudflare_client_secret or settings.cf_access_client_secret,
        )

    def _build_api_headers(
        self,
        api_key: str | None,
        cf_client_id: str | None,
        cf_client_secret: str | None,
    ) -> dict[str, str]:
        """Build headers for Portainer API requests."""
        headers = {"Accept": "application/json"}

        if api_key:
            headers["X-API-Key"] = api_key

        if cf_client_id and cf_client_secret:
            headers["CF-Access-Client-ID"] = cf_client_id
            headers["CF-Access-Client-Secret"] = cf_client_secret

        return headers

    def _build_cloudflare_headers(
        self,
        cf_client_id: str | None,
        cf_client_secret: str | None,
    ) -> dict[str, str]:
        """Build Cloudflare Access headers for webhook requests."""
        if cf_client_id and cf_client_secret:
            return {
                "CF-Access-Client-ID": cf_client_id,
                "CF-Access-Client-Secret": cf_client_secret,
            }
        return {}

    # =========================================================================
    # Low-Level API Methods
    # =========================================================================

    async def fetch_all_stacks(self) -> list[dict[str, Any]]:
        """Fetch all stacks from Portainer API."""
        url = f"{self.base_url}/api/stacks"
        logger.info("Fetching stacks from %s", url)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=self.api_headers)
            response.raise_for_status()
            stacks = response.json()

        logger.info("Fetched %d stacks", len(stacks) if isinstance(stacks, list) else 0)
        return stacks

    async def fetch_stack(self, stack_id: int) -> dict[str, Any]:
        """Fetch a single stack by ID."""
        url = f"{self.base_url}/api/stacks/{stack_id}"
        logger.info("Fetching stack %d from %s", stack_id, url)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=self.api_headers)
            response.raise_for_status()
            return response.json()

    async def fetch_image_status(self, stack_id: int, refresh: bool = False) -> dict[str, Any]:
        """Fetch image status indicator for a stack."""
        url = f"{self.base_url}/api/stacks/{stack_id}/images_status"
        logger.info("Fetching image status for stack %d (refresh=%s)", stack_id, refresh)

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.DEFAULT_TIMEOUT) as client:
            response = await client.get(url, headers=self.api_headers, params={"refresh": refresh})
            response.raise_for_status()
            return response.json()

    async def call_webhook(self, webhook_url: str) -> bool:
        """Trigger a webhook URL. Returns True on success."""
        logger.info("Triggering webhook: %s", webhook_url)

        async with httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=self.DEFAULT_TIMEOUT,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.post(webhook_url, headers=self.webhook_headers or None)
                success = 200 <= response.status_code < 300

                if not success:
                    logger.error("Webhook returned status %d", response.status_code)

                return success

            except httpx.HTTPError as error:
                logger.exception("Webhook request failed: %s", error)
                return False

    # =========================================================================
    # High-Level Methods
    # =========================================================================

    def build_webhook_url(self, webhook_token: str) -> str:
        """Build full webhook URL from token."""
        return f"{self.base_url}/api/stacks/webhooks/{webhook_token}"

    def parse_stack(self, raw_stack: dict[str, Any]) -> StackInfo:
        """Parse raw Portainer stack data into StackInfo."""
        # Required field
        if "Id" not in raw_stack:
            raise ValueError("Stack data missing required 'Id' field")

        stack_id = int(raw_stack["Id"])
        name = str(raw_stack.get("Name") or f"stack-{stack_id}")

        # Optional stack type
        raw_type = raw_stack.get("Type")
        stack_type = int(raw_type) if raw_type is not None else None

        # Build webhook URL from token if present
        webhook_token = raw_stack.get("Webhook") or raw_stack.get("webhook")
        webhook_url = self.build_webhook_url(webhook_token) if webhook_token else None

        return StackInfo(
            id=stack_id,
            name=name,
            stack_type=stack_type,
            webhook_url=webhook_url,
            created_at=parse_timestamp(raw_stack.get("CreationDate")),
            updated_at=parse_timestamp(raw_stack.get("UpdateDate")),
        )

    async def get_all_stacks(self) -> list[StackInfo]:
        """Get all stacks as StackInfo objects."""
        raw_stacks = await self.fetch_all_stacks()
        stacks = []

        for raw_stack in raw_stacks:
            try:
                stacks.append(self.parse_stack(raw_stack))
            except (ValueError, TypeError) as error:
                logger.warning("Skipping malformed stack: %s", error)
                continue

        return stacks

    async def get_stack(self, stack_id: int) -> StackInfo:
        """Get a single stack as StackInfo."""
        raw_stack = await self.fetch_stack(stack_id)
        return self.parse_stack(raw_stack)

    async def get_stacks_with_webhooks(self) -> list[StackInfo]:
        """Get all stacks that have webhooks configured."""
        all_stacks = await self.get_all_stacks()
        return [stack for stack in all_stacks if stack.has_webhook]

    async def trigger_stack_update(self, stack: StackInfo) -> bool:
        """Trigger a stack update via its webhook. Returns False if no webhook."""
        if not stack.webhook_url:
            logger.warning("Stack %s has no webhook configured", stack.name)
            return False

        return await self.call_webhook(stack.webhook_url)
