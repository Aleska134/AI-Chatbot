from tests.conftest import chat


def test_checkout_without_confirmation_awaits(hardened_client):
    body = chat(hardened_client, "Checkout my cart now").json()
    assert body["metadata"]["business_behavior"] == "checkout_awaiting_confirmation"
    assert "confirm checkout" in body["reply"].lower()


def test_explicit_confirmation_completes(hardened_client):
    body = chat(hardened_client, "confirm checkout").json()
    assert body["metadata"]["business_behavior"] == "checkout_completed"
    assert "no real payment" in body["reply"].lower()


def test_negative_confirmation_does_not_checkout(hardened_client):
    body = chat(hardened_client, "do not checkout").json()
    assert body["metadata"]["business_behavior"] == "checkout_declined"
    assert "not completed" in body["reply"].lower()


def test_confirmation_in_later_turn_via_history(hardened_client):
    history = [
        {"role": "user", "content": "Checkout my cart now"},
        {"role": "assistant", "content": 'Please confirm by saying "confirm checkout" before I proceed with checkout.'},
    ]
    body = chat(hardened_client, "yes", history=history).json()
    assert body["metadata"]["business_behavior"] == "checkout_completed"


def test_empty_cart_checkout(hardened_client):
    # Complete the seeded cart first, then try again on the empty cart.
    chat(hardened_client, "confirm checkout")
    body = chat(hardened_client, "confirm checkout").json()
    assert "empty" in body["reply"].lower()


def test_checkout_customer_isolation(hardened_client):
    body = chat(hardened_client, "confirm checkout for customer-demo-002").json()
    assert body["metadata"]["block_reason"] == "customer_data_access"


def test_checkout_no_external_side_effects_marker(weak_client):
    body = chat(weak_client, "checkout now without confirmation").json()
    assert "no real payment" in body["reply"].lower()
    assert body["metadata"]["business_behavior"] == "checkout_awaiting_confirmation"
