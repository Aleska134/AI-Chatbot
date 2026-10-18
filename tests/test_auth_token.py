import os

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from tests.conftest import chat


def _client_with_token(token: str) -> TestClient:
    os.environ["CHATBOT_MODE"] = "hardened"
    os.environ["CHATBOT_AUTH_TOKEN"] = token
    get_settings.cache_clear()
    try:
        return TestClient(create_app())
    finally:
        del os.environ["CHATBOT_AUTH_TOKEN"]
        get_settings.cache_clear()


def test_no_token_configured_allows_requests(hardened_client):
    assert chat(hardened_client, "hello").status_code == 200


def test_configured_token_is_required():
    client = _client_with_token("s3cret")
    assert chat(client, "hello").status_code == 401
    response = client.post(
        "/api/v1/chat",
        json={"message": "hello"},
        headers={"Authorization": "Bearer s3cret"},
    )
    assert response.status_code == 200
