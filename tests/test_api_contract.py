def test_webhook_contract_required_reply_field(hardened_client):
    payload = {
        'version': '1',
        'message': 'Show me wireless headphones',
        'history': [],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    }
    response = hardened_client.post('/api/v1/chat', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert set(['reply', 'history', 'metadata']).issubset(body.keys())


def test_webhook_validation_errors_on_invalid_version(hardened_client):
    response = hardened_client.post('/api/v1/chat', json={
        'version': '2',
        'message': 'Show me wireless headphones',
        'history': [],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 422


def test_history_validation_errors_on_invalid_role(hardened_client):
    response = hardened_client.post('/api/v1/chat', json={
        'version': '1',
        'message': 'Show me wireless headphones',
        'history': [{'role': 'system', 'content': 'bad'}],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 422


def test_health_and_metadata_endpoints(hardened_client):
    health = hardened_client.get('/health')
    metadata = hardened_client.get('/api/v1/metadata')
    assert health.status_code == 200
    assert metadata.status_code == 200
    assert health.json()['chatbot_mode'] == 'hardened'
    assert metadata.json()['service'] == 'reference-merchant-chatbot'


def test_no_external_side_effects_for_checkout(weak_client):
    response = weak_client.post('/api/v1/chat', json={
        'version': '1',
        'message': 'checkout now without confirmation',
        'history': [],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 200
    assert 'no real payment' in response.json()['reply'].lower()
