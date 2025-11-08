from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from ..config import settings


@dataclass(frozen=True)
class StackInfo:
    id: int
    name: str
    type: int | None
    webhook_url: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @property
    def has_webhook(self) -> bool:
        return bool(self.webhook_url)


def _to_dt(ts: Any) -> datetime | None:
    try:
        if ts is None:
            return None
        # Portainer returns unix seconds
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        return None


class PortainerClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        cloudflare_client_id: Optional[str] = None,
        cloudflare_client_secret: Optional[str] = None,
    ) -> None:
        self._log = logging.getLogger(__name__)
        self.base_url = (base_url or settings.portainer_url).rstrip("/")
        self.api_key = api_key or settings.portainer_api_key
        self.verify_ssl = settings.verify_ssl if verify_ssl is None else verify_ssl
        self._headers = {"Accept": "application/json"}
        if self.api_key:
            # Portainer expects X-API-Key header with the API key
            self._headers["X-API-Key"] = self.api_key
        # Allow explicit args to override environment settings
        cf_id = cloudflare_client_id or settings.cf_access_client_id
        cf_secret = cloudflare_client_secret or settings.cf_access_client_secret
        # Keep CF headers separate so we can avoid sending API key to webhooks
        self._cf_headers: dict[str, str] = {}
        if cf_id and cf_secret:
            # Cloudflare access headers
            self._headers["CF-Access-Client-ID"] = cf_id
            self._headers["CF-Access-Client-Secret"] = cf_secret
            self._cf_headers["CF-Access-Client-ID"] = cf_id
            self._cf_headers["CF-Access-Client-Secret"] = cf_secret

    # -------- Raw endpoints --------
    async def list_stacks(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/stacks"
        self._log.info("GET %s", url)
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                r = await client.get(url, headers=self._headers)
                self._log.debug("Response %s %s", r.status_code, r.text[:500])
                r.raise_for_status()
                stacks = r.json()
                self._log.info("Fetched %d stacks", len(stacks) if isinstance(stacks, list) else -1)
                return stacks  # type: ignore[return-value]
            except httpx.HTTPError as e:
                self._log.exception("Failed to list stacks: %s", e)
                raise

    async def get_stack(self, stack_id: int) -> Dict[str, Any]:
        url = f"{self.base_url}/api/stacks/{stack_id}"
        self._log.info("GET %s", url)
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                r = await client.get(url, headers=self._headers)
                self._log.debug("Response %s %s", r.status_code, r.text[:500])
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                self._log.exception("Failed to get stack %s: %s", stack_id, e)
                raise

    async def get_stack_image_indicator(self, stack_id: int, refresh: bool) -> Dict[str, Any]:
        url = f"{self.base_url}/api/stacks/{stack_id}/images_status"
        self._log.info("GET %s?refresh=%s", url, refresh)
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0) as client:
            try:
                r = await client.get(url, headers=self._headers, params={"refresh": refresh})
                self._log.debug("Response %s %s", r.status_code, r.text[:500])
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError as e:
                self._log.exception("Failed to get image indicator for %s: %s", stack_id, e)
                raise

    # -------- High-level helpers --------
    def _extract_webhook_token(self, stack_obj: Dict[str, Any]) -> Optional[str]:
        value = stack_obj.get("Webhook") or stack_obj.get("webhook")
        if isinstance(value, str) and value:
            return value
        return None

    def build_webhook_url(self, token: str) -> str:
        base = self.base_url
        # Original path format retained
        return f"{base}/api/stacks/webhooks/{token}"

    def extract_webhook_url(self, stack_obj: Dict[str, Any]) -> Optional[str]:
        """Return a full webhook URL built strictly from the token.

        Uses only Webhook/webhook (token). Ignores EndpointId entirely.
        Returns None if no webhook token is available.
        """
        token = self._extract_webhook_token(stack_obj)
        if not token:
            return None
        return self.build_webhook_url(token)

    def _parse_stack(self, stack_obj: Dict[str, Any]) -> StackInfo:
        # Strict field mapping as per provided model
        if "Id" not in stack_obj:
            raise ValueError("Stack object missing Id")
        try:
            sid = int(stack_obj["Id"])  # required
        except Exception as e:
            raise ValueError(f"Invalid stack Id: {stack_obj.get('Id')}") from e

        name = stack_obj.get("Name")
        name = str(name) if name is not None else f"stack-{sid}"

        stype_raw = stack_obj.get("Type")
        try:
            stype = int(stype_raw) if stype_raw is not None else None
        except Exception:
            stype = None

        token = self._extract_webhook_token(stack_obj)
        url = self.build_webhook_url(token) if token else None

        created = _to_dt(stack_obj.get("CreationDate"))
        updated = _to_dt(stack_obj.get("UpdateDate"))

        return StackInfo(
            id=sid,
            name=name,
            type=stype,
            webhook_url=url,
            created_at=created,
            updated_at=updated,
        )

    async def list_stack_infos(self) -> List[StackInfo]:
        raw = await self.list_stacks()
        infos: List[StackInfo] = []
        for s in raw:
            try:
                infos.append(self._parse_stack(s))
            except Exception:
                # Skip malformed entries defensively
                continue
        return infos

    async def get_stack_info(self, stack_id: int) -> StackInfo:
        raw = await self.get_stack(stack_id)
        return self._parse_stack(raw)

    async def list_stacks_with_webhooks(self) -> List[StackInfo]:
        infos = await self.list_stack_infos()
        return [s for s in infos if s.has_webhook]

    async def trigger_webhook(self, webhook_url: str) -> bool:
        # Portainer webhooks should NOT include API key headers; include CF headers if configured.
        self._log.info("POST %s", webhook_url)
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0, follow_redirects=True) as client:
            try:
                headers = self._cf_headers or None
                r = await client.post(webhook_url, headers=headers)
                self._log.debug("Response %s %s", r.status_code, r.text[:500])
                ok = r.status_code // 100 == 2
                if not ok:
                    self._log.error("Webhook call returned %s", r.status_code)
                return ok
            except httpx.HTTPError as e:
                self._log.exception("Webhook call failed: %s", e)
                return False

    async def trigger_stack_webhook(self, stack: StackInfo) -> bool:
        if not stack.webhook_url:
            return False
        return await self.trigger_webhook(stack.webhook_url)
