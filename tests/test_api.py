"""Tests for API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.stack import Stack


class TestListStacks:
    """Tests for GET /api/stacks endpoint."""
    def test_list_stacks_empty(self, client: TestClient) -> None:
        """Test listing stacks when database is empty."""
        response = client.get("/api/stacks")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_stacks_with_data(self, client: TestClient, db: Session) -> None:
        """Test listing stacks with existing data."""
        # Create test stacks
        stack1 = Stack(
            id=1,
            name="alpha-stack",
            webhook_url="http://test/webhook/1",
            image_status="updated",
        )
        stack2 = Stack(
            id=2,
            name="beta-stack",
            webhook_url="http://test/webhook/2",
            image_status="outdated",
        )
        db.add(stack1)
        db.add(stack2)
        db.commit()

        response = client.get("/api/stacks")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        # Should be sorted by name
        assert data[0]["name"] == "alpha-stack"
        assert data[1]["name"] == "beta-stack"

    def test_list_stacks_returns_all_fields(self, client: TestClient, db: Session) -> None:
        """Test that list stacks returns all expected fields."""
        now = datetime.now(timezone.utc)
        stack = Stack(
            id=1,
            name="test-stack",
            webhook_url="http://test/webhook/1",
            image_status="updated",
            image_message="All good",
            image_last_checked=now,
            auto_update_enabled=True,
            is_outdated=False,
        )
        db.add(stack)
        db.commit()

        response = client.get("/api/stacks")
        assert response.status_code == 200

        data = response.json()[0]
        assert "id" in data
        assert "name" in data
        assert "webhook_url" in data
        assert "image_status" in data
        assert "image_message" in data
        assert "image_last_checked" in data
        assert "auto_update_enabled" in data
        assert "is_outdated" in data


class TestImportStacks:
    """Tests for GET /api/stacks/import endpoint."""
    @patch("app.api.routes.PortainerClient")
    def test_import_stacks_success(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
        sample_portainer_stacks: list[dict],
        sample_image_indicator: dict,
    ) -> None:
        """Test successful stack import from Portainer."""
        mock_client = mock_client_class.return_value
        mock_client.list_stacks = AsyncMock(return_value=sample_portainer_stacks)
        mock_client.get_stack_image_indicator = AsyncMock(return_value=sample_image_indicator)
        mock_client.extract_webhook_url.side_effect = lambda s: (
            f"http://test/webhook/{s['Webhook']}" if s.get("Webhook") else None
        )

        response = client.get("/api/stacks/import")
        assert response.status_code == 200

        data = response.json()
        # Should import 2 stacks (the one without webhook is skipped)
        assert data["imported"] == 2

    @patch("app.api.routes.PortainerClient")
    def test_import_stacks_portainer_error(
        self,
        mock_client_class: Any,
        client: TestClient,
    ) -> None:
        """Test import handles Portainer API errors."""
        mock_client = mock_client_class.return_value
        mock_client.list_stacks = AsyncMock(side_effect=Exception("Connection failed"))

        response = client.get("/api/stacks/import")
        assert response.status_code == 502
        assert "Failed to fetch stacks" in response.json()["detail"]

    @patch("app.api.routes.PortainerClient")
    def test_import_stacks_skips_existing(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
        sample_portainer_stacks: list[dict],
        sample_image_indicator: dict,
    ) -> None:
        """Test import doesn't duplicate existing stacks."""
        # Pre-create one stack
        existing = Stack(id=1, name="existing", webhook_url="http://old/webhook")
        db.add(existing)
        db.commit()

        mock_client = mock_client_class.return_value
        mock_client.list_stacks = AsyncMock(return_value=sample_portainer_stacks)
        mock_client.get_stack_image_indicator = AsyncMock(return_value=sample_image_indicator)
        mock_client.extract_webhook_url.side_effect = lambda s: (
            f"http://test/webhook/{s['Webhook']}" if s.get("Webhook") else None
        )

        response = client.get("/api/stacks/import")
        assert response.status_code == 200

        # Only 1 new stack imported (id=2), id=1 already exists, id=3 has no webhook
        data = response.json()
        assert data["imported"] == 1


class TestGetIndicator:
    """Tests for GET /api/stacks/{stack_id}/indicator endpoint."""
    def test_get_indicator_not_found(self, client: TestClient) -> None:
        """Test indicator for non-existent stack."""
        response = client.get("/api/stacks/999/indicator")
        assert response.status_code == 404

    @patch("app.api.routes.PortainerClient")
    def test_get_indicator_success(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
        sample_image_indicator: dict,
    ) -> None:
        """Test successful indicator fetch."""
        stack = Stack(id=1, name="test", webhook_url="http://test/webhook")
        db.add(stack)
        db.commit()

        mock_client = mock_client_class.return_value
        mock_client.get_stack_image_indicator = AsyncMock(return_value=sample_image_indicator)

        response = client.get("/api/stacks/1/indicator")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["status"] == "updated"
        assert data["message"] == "All images are up to date"

    @patch("app.api.routes.PortainerClient")
    def test_get_indicator_with_refresh(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
        sample_image_indicator: dict,
    ) -> None:
        """Test indicator fetch with refresh=true."""
        stack = Stack(id=1, name="test", webhook_url="http://test/webhook")
        db.add(stack)
        db.commit()

        mock_client = mock_client_class.return_value
        mock_client.get_stack_image_indicator = AsyncMock(return_value=sample_image_indicator)

        response = client.get("/api/stacks/1/indicator?refresh=true")
        assert response.status_code == 200

        # Verify refresh=True was passed
        mock_client.get_stack_image_indicator.assert_called_once_with(1, refresh=True)


class TestTriggerUpdate:
    """Tests for POST /api/stacks/{stack_id}/update endpoint."""
    def test_update_not_found(self, client: TestClient) -> None:
        """Test update for non-existent stack."""
        response = client.post("/api/stacks/999/update")
        assert response.status_code == 404

    def test_update_no_webhook(self, client: TestClient, db: Session) -> None:
        """Test update for stack without webhook."""
        stack = Stack(id=1, name="no-webhook", webhook_url=None)
        db.add(stack)
        db.commit()

        response = client.post("/api/stacks/1/update")
        assert response.status_code == 400
        assert "Webhook URL not configured" in response.json()["detail"]

    @patch("app.api.routes.PortainerClient")
    def test_update_success(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
        sample_image_indicator: dict,
    ) -> None:
        """Test successful stack update."""
        stack = Stack(id=1, name="test", webhook_url="http://test/webhook")
        db.add(stack)
        db.commit()

        mock_client = mock_client_class.return_value
        mock_client.trigger_webhook = AsyncMock(return_value=True)
        mock_client.get_stack_image_indicator = AsyncMock(return_value=sample_image_indicator)

        response = client.post("/api/stacks/1/update")
        assert response.status_code == 200
        assert response.json()["updated"] is True

    @patch("app.api.routes.PortainerClient")
    def test_update_webhook_fails(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
    ) -> None:
        """Test update when webhook call fails."""
        stack = Stack(id=1, name="test", webhook_url="http://test/webhook")
        db.add(stack)
        db.commit()

        mock_client = mock_client_class.return_value
        mock_client.trigger_webhook = AsyncMock(return_value=False)

        response = client.post("/api/stacks/1/update")
        assert response.status_code == 502
        assert "Webhook call failed" in response.json()["detail"]


class TestSetAutoUpdate:
    """Tests for POST /api/stacks/{stack_id}/auto-update endpoint."""
    def test_auto_update_not_found(self, client: TestClient) -> None:
        """Test auto-update for non-existent stack."""
        response = client.post("/api/stacks/999/auto-update?enabled=true")
        assert response.status_code == 404

    def test_auto_update_enable(self, client: TestClient, db: Session) -> None:
        """Test enabling auto-update."""
        stack = Stack(id=1, name="test", webhook_url="http://test/webhook", auto_update_enabled=False)
        db.add(stack)
        db.commit()

        response = client.post("/api/stacks/1/auto-update?enabled=true")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 1
        assert data["auto_update_enabled"] is True

    def test_auto_update_disable(self, client: TestClient, db: Session) -> None:
        """Test disabling auto-update."""
        stack = Stack(id=1, name="test", webhook_url="http://test/webhook", auto_update_enabled=True)
        db.add(stack)
        db.commit()

        response = client.post("/api/stacks/1/auto-update?enabled=false")
        assert response.status_code == 200

        data = response.json()
        assert data["auto_update_enabled"] is False


class TestCheckNow:
    """Tests for POST /api/stacks/{stack_id}/check-now endpoint."""
    def test_check_now_not_found(self, client: TestClient) -> None:
        """Test check-now for non-existent stack."""
        response = client.post("/api/stacks/999/check-now")
        assert response.status_code == 404

    def test_check_now_marks_outdated(self, client: TestClient, db: Session) -> None:
        """Test check-now marks stack as outdated when old."""
        # Stack with very old last_updated_at
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        stack = Stack(
            id=1,
            name="old-stack",
            webhook_url="http://test/webhook",
            last_updated_at=old_time,
            is_outdated=False,
        )
        db.add(stack)
        db.commit()

        response = client.post("/api/stacks/1/check-now")
        assert response.status_code == 200

        data = response.json()
        assert data["is_outdated"] is True

    def test_check_now_recent_not_outdated(self, client: TestClient, db: Session) -> None:
        """Test check-now doesn't mark recent stack as outdated."""
        # Stack updated just now
        stack = Stack(
            id=1,
            name="fresh-stack",
            webhook_url="http://test/webhook",
            last_updated_at=datetime.now(timezone.utc),
            is_outdated=True,
        )
        db.add(stack)
        db.commit()

        response = client.post("/api/stacks/1/check-now")
        assert response.status_code == 200

        data = response.json()
        assert data["is_outdated"] is False


class TestIndexPage:
    """Tests for the index page."""
    def test_index_returns_html(self, client: TestClient) -> None:
        """Test that index returns HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Stack Updater" in response.text
