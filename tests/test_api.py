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


class TestImportStacks:
    """Tests for GET /api/stacks/import endpoint."""
    @patch("app.services.stack_service.PortainerClient")
    def test_import_stacks_success(
        self,
        mock_client_class: Any,
        client: TestClient,
        db: Session,
    ) -> None:
        """Test successful stack import from Portainer."""
        from app.services.portainer_client import StackInfo

        mock_client = mock_client_class.return_value
        mock_client.list_stacks_with_webhooks = AsyncMock(
            return_value=[
                StackInfo(
                    id=1, name="stack-1", type=1, webhook_url="http://test/webhook/1", created_at=None, updated_at=None
                ),
                StackInfo(
                    id=2, name="stack-2", type=1, webhook_url="http://test/webhook/2", created_at=None, updated_at=None
                ),
            ]
        )

        response = client.get("/api/stacks/import")
        assert response.status_code == 200

        data = response.json()
        assert data["imported"] == 2

    @patch("app.services.stack_service.PortainerClient")
    def test_import_stacks_portainer_error(
        self,
        mock_client_class: Any,
        client: TestClient,
    ) -> None:
        """Test import handles Portainer API errors - returns 200 with errors list."""
        mock_client = mock_client_class.return_value
        mock_client.list_stacks_with_webhooks = AsyncMock(side_effect=Exception("Connection failed"))

        response = client.get("/api/stacks/import")
        # New architecture returns success with 0 imported and errors list
        assert response.status_code == 200
        assert response.json()["imported"] == 0


class TestGetIndicator:
    """Tests for GET /api/stacks/{stack_id}/indicator endpoint."""
    def test_get_indicator_not_found(self, client: TestClient) -> None:
        """Test indicator for non-existent stack."""
        response = client.get("/api/stacks/999/indicator")
        assert response.status_code == 404

    @patch("app.services.stack_service.PortainerClient")
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

    @patch("app.services.stack_service.PortainerClient")
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
        assert "No webhook configured" in response.json()["detail"]

    @patch("app.services.stack_service.PortainerClient")
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

    @patch("app.services.stack_service.PortainerClient")
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
        assert "failed" in response.json()["detail"].lower()


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


class TestIndexPage:
    """Tests for the index page."""
    def test_index_returns_html(self, client: TestClient) -> None:
        """Test that index returns HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Stack Updater" in response.text
