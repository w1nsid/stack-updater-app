"""Tests for Stack model and database operations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.stack import Stack


class TestStackModel:
    """Tests for the Stack model."""
    def test_create_stack(self, db: Session) -> None:
        """Test creating a new stack."""
        stack = Stack(
            id=1,
            name="test-stack",
            webhook_url="http://localhost/webhook/token",
        )
        db.add(stack)
        db.commit()

        retrieved = db.get(Stack, 1)
        assert retrieved is not None
        assert retrieved.name == "test-stack"
        assert retrieved.webhook_url == "http://localhost/webhook/token"

    def test_stack_defaults(self, db: Session) -> None:
        """Test stack default values."""
        stack = Stack(id=1, name="defaults-test")
        db.add(stack)
        db.commit()

        retrieved = db.get(Stack, 1)
        assert retrieved is not None
        assert retrieved.auto_update_enabled is False
        assert retrieved.webhook_url is None
        assert retrieved.image_status is None

    def test_stack_with_all_fields(self, db: Session) -> None:
        """Test stack with all fields populated."""
        now = datetime.now(timezone.utc)
        stack = Stack(
            id=42,
            name="full-stack",
            webhook_url="http://test/webhook",
            portainer_created_at=now,
            portainer_updated_at=now,
            auto_update_enabled=True,
            image_status="updated",
            image_message="All images up to date",
            image_last_checked=now,
            last_updated_at=now,
        )
        db.add(stack)
        db.commit()

        retrieved = db.get(Stack, 42)
        assert retrieved is not None
        assert retrieved.name == "full-stack"
        assert retrieved.auto_update_enabled is True
        assert retrieved.image_status == "updated"

    def test_update_stack(self, db: Session) -> None:
        """Test updating a stack."""
        stack = Stack(id=1, name="original", webhook_url="http://old/webhook")
        db.add(stack)
        db.commit()

        # Update the stack
        stack.name = "updated"
        stack.webhook_url = "http://new/webhook"
        stack.auto_update_enabled = True
        db.commit()

        retrieved = db.get(Stack, 1)
        assert retrieved is not None
        assert retrieved.name == "updated"
        assert retrieved.webhook_url == "http://new/webhook"
        assert retrieved.auto_update_enabled is True

    def test_delete_stack(self, db: Session) -> None:
        """Test deleting a stack."""
        stack = Stack(id=1, name="to-delete")
        db.add(stack)
        db.commit()

        db.delete(stack)
        db.commit()

        retrieved = db.get(Stack, 1)
        assert retrieved is None

    def test_query_stacks_by_status(self, db: Session) -> None:
        """Test querying stacks by image status."""
        stack1 = Stack(id=1, name="updated-stack", image_status="updated")
        stack2 = Stack(id=2, name="outdated-stack", image_status="outdated")
        stack3 = Stack(id=3, name="error-stack", image_status="error")
        db.add_all([stack1, stack2, stack3])
        db.commit()

        outdated = db.query(Stack).filter(Stack.image_status == "outdated").all()
        assert len(outdated) == 1
        assert outdated[0].name == "outdated-stack"

    def test_query_auto_update_enabled(self, db: Session) -> None:
        """Test querying stacks with auto-update enabled and outdated status."""
        stack1 = Stack(id=1, name="auto-enabled", auto_update_enabled=True, image_status="outdated")
        stack2 = Stack(id=2, name="auto-disabled", auto_update_enabled=False, image_status="outdated")
        stack3 = Stack(id=3, name="auto-enabled-fresh", auto_update_enabled=True, image_status="updated")
        db.add_all([stack1, stack2, stack3])
        db.commit()

        # Query for stacks that need auto-update
        needs_update = (
            db.query(Stack).filter(
                Stack.auto_update_enabled == True,  # noqa: E712
                Stack.image_status == "outdated",
            ).all()
        )

        assert len(needs_update) == 1
        assert needs_update[0].name == "auto-enabled"

    def test_stack_ordering(self, db: Session) -> None:
        """Test stack ordering by name."""
        stack_c = Stack(id=3, name="charlie")
        stack_a = Stack(id=1, name="alpha")
        stack_b = Stack(id=2, name="bravo")
        db.add_all([stack_c, stack_a, stack_b])
        db.commit()

        ordered = db.query(Stack).order_by(Stack.name.asc()).all()
        assert [s.name for s in ordered] == ["alpha", "bravo", "charlie"]
