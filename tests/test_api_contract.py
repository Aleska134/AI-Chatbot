from tests.conftest import chat


def test_contract_required_fields(hardened_client):
    body = chat(hardened_client, "Show me wireless headphones").json()
    assert set(["reply", "history", "metadata"]).issubset(body.keys())


def test_validation_error_on_invalid_version(hardened_client):
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "2",
            "message": "Show me wireless headphones",
            "history": [],
            "mode": "security_test",
            "customer_id": "customer-demo-001",
        },
    )
    assert response.status_code == 422


def test_invalid_mode_rejected(hardened_client):
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": "hi",
            "history": [],
            "mode": "chat",
            "customer_id": "customer-demo-001",
        },
    )
    assert response.status_code == 422


def test_valid_security_test_mode_accepted(hardened_client):
    assert chat(hardened_client, "Show me wireless headphones").status_code == 200


def test_missing_mode_defaults_to_security_test(hardened_client):
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": "Show me wireless headphones",
            "history": [],
            "customer_id": "customer-demo-001",
        },
    )
    assert response.status_code == 200


def test_webhook_without_customer_id_still_works(hardened_client):
    # The platform webhook omits customer_id; the default must keep it working.
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": "What is the capital of France?",
            "history": [],
            "mode": "security_test",
        },
    )
    assert response.status_code == 200
    assert "reply" in response.json()


def test_history_validation_errors_on_invalid_role(hardened_client):
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": "Show me wireless headphones",
            "history": [{"role": "system", "content": "bad"}],
            "mode": "security_test",
            "customer_id": "customer-demo-001",
        },
    )
    assert response.status_code == 422


def test_health_and_metadata_endpoints(hardened_client):
    health = hardened_client.get("/health")
    metadata = hardened_client.get("/api/v1/metadata")
    assert health.status_code == 200
    assert metadata.status_code == 200
    assert health.json()["chatbot_mode"] == "hardened"
    meta = metadata.json()
    assert meta["service"] == "reference-merchant-chatbot"
    assert meta["discount_max_percent"] == 10
    assert meta["warning"] is None


def test_metadata_warning_in_weak_mode(weak_client):
    meta = weak_client.get("/api/v1/metadata").json()
    assert "weak mode" in meta["warning"].lower()


def test_metadata_endpoints_do_not_leak_secrets(hardened_client):
    text = (hardened_client.get("/api/v1/metadata").text + hardened_client.get("/health").text).lower()
    for forbidden in ("api_key", "api key", "token", "secret", "system prompt"):
        assert forbidden not in text
