"""Pytest configuration and fixtures for Stack Updater tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment variables before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["PORTAINER_URL"] = "http://test-portainer:9000"
os.environ["PORTAINER_API_KEY"] = "test-api-key"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.db import Base, get_db
from app.main import app

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_stack_data() -> dict[str, Any]:
    """Sample Portainer stack data for testing."""
    return {
        "Id": 1,
        "Name": "test-stack",
        "Type": 2,
        "Webhook": "abc123-webhook-token",
        "CreationDate": 1700000000,
        "UpdateDate": 1700100000,
    }


@pytest.fixture
def sample_portainer_stacks() -> list[dict[str, Any]]:
    """Sample list of Portainer stacks."""
    return [
        {
            "Id": 1,
            "Name": "web-app",
            "Type": 2,
            "Webhook": "token-1",
            "CreationDate": 1700000000,
            "UpdateDate": 1700100000,
        },
        {
            "Id": 2,
            "Name": "api-service",
            "Type": 2,
            "Webhook": "token-2",
            "CreationDate": 1700000000,
            "UpdateDate": 1700200000,
        },
        {
            "Id": 3,
            "Name": "no-webhook-stack",
            "Type": 2,
            "Webhook": None,  # No webhook configured
            "CreationDate": 1700000000,
            "UpdateDate": 1700300000,
        },
    ]


@pytest.fixture
def sample_image_indicator() -> dict[str, Any]:
    """Sample Portainer image indicator response."""
    return {
        "Status": "updated",
        "Message": "All images are up to date",
    }
