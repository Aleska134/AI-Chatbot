from tests.conftest import chat


def test_product_question_returns_catalog(hardened_client):
    response = chat(hardened_client, "Show me wireless headphones")
    assert response.status_code == 200
    body = response.json()
    assert "wireless" in body["reply"].lower()
    assert body["metadata"]["chatbot_mode"] == "hardened"
    assert body["metadata"]["business_behavior"] == "product_lookup"
    assert body["history"][-1]["role"] == "assistant"


def test_history_is_appended(hardened_client):
    response = chat(
        hardened_client,
        "What is my order status?",
        history=[{"role": "user", "content": "Hello"}],
    )
    assert response.status_code == 200
    assert len(response.json()["history"]) == 3


def test_catalog_contains_aligned_products(hardened_client):
    response = chat(hardened_client, "Show me the product catalog")
    assert response.status_code == 200
    reply = response.json()["reply"].lower()
    assert "laptop" in reply or "keyboard" in reply or "headphones" in reply
