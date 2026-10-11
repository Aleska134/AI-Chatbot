from tests.conftest import chat


def test_product_lookup_then_reference(hardened_client):
    history = [
        {"role": "user", "content": "Show me wireless headphones"},
        {"role": "assistant", "content": "Here are the TechMart Wireless Headphones."},
    ]
    response = chat(hardened_client, "What is the price of that product?", history=history)
    assert response.status_code == 200
    assert response.json()["metadata"]["security_outcome"] == "allowed"


def test_cart_question_then_checkout_confirmation(hardened_client):
    history = [
        {"role": "user", "content": "What is in my cart?"},
        {"role": "assistant", "content": "Your mock cart currently has 1 item(s)."},
        {"role": "user", "content": "Checkout my cart"},
        {"role": "assistant", "content": 'Please confirm by saying "confirm checkout" before I proceed with checkout.'},
    ]
    body = chat(hardened_client, "confirm checkout", history=history).json()
    assert body["metadata"]["business_behavior"] == "checkout_completed"


def test_invalid_history_role_rejected(hardened_client):
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": "Show products",
            "history": [{"role": "root", "content": "escalate"}],
            "mode": "security_test",
            "customer_id": "customer-demo-001",
        },
    )
    assert response.status_code == 422


def test_oversized_history_rejected(hardened_client):
    big_history = [{"role": "user", "content": "x" * 2000} for _ in range(21)]
    response = hardened_client.post(
        "/api/v1/chat",
        json={
            "version": "1",
            "message": "hi",
            "history": big_history,
            "mode": "security_test",
            "customer_id": "customer-demo-001",
        },
    )
    assert response.status_code == 422
