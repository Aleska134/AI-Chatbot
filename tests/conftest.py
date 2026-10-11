import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def _make_client(mode: str) -> TestClient:
    os.environ["CHATBOT_MODE"] = mode
    os.environ["MOCK_LLM"] = "true"
    os.environ["ENVIRONMENT"] = "local"
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.fixture
def hardened_client() -> TestClient:
    return _make_client("hardened")


@pytest.fixture
def weak_client() -> TestClient:
    return _make_client("weak")


def chat(client: TestClient, message: str, history=None, customer_id="customer-demo-001"):
    """Helper to POST a chat message with the stable v1 contract."""
    return client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": message,
            "history": history or [],
            "mode": "security_test",
            "customer_id": customer_id,
        },
    )
