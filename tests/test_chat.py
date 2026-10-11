def test_product_question_returns_catalog(hardened_client):
    response = hardened_client.post('/api/v1/chat', json={
        'version': '1',
        'message': 'Show me wireless headphones',
        'history': [],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 200
    body = response.json()
    assert 'reply' in body
    assert 'wireless' in body['reply'].lower()
    assert body['metadata']['chatbot_mode'] == 'hardened'
    assert body['history'][-1]['role'] == 'assistant'


def test_history_is_appended(hardened_client):
    response = hardened_client.post('/api/v1/chat', json={
        'version': '1',
        'message': 'What is my order status?',
        'history': [{'role': 'user', 'content': 'Hello'}],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 200
    body = response.json()
    assert len(body['history']) == 3
