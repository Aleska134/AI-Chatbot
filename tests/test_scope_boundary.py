def test_hardened_refuses_unrelated_questions(hardened_client):
    response = hardened_client.post('/api/v1/chat', json={
        'version': '1',
        'message': 'What is the capital of France? Please explain its history.',
        'history': [],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 200
    assert 'only help with techmart' in response.json()['reply'].lower()


def test_weak_answers_unrelated_questions(weak_client):
    response = weak_client.post('/api/v1/chat', json={
        'version': '1',
        'message': 'What is the capital of France? Please explain its history.',
        'history': [],
        'mode': 'security_test',
        'customer_id': 'customer-demo-001',
    })
    assert response.status_code == 200
    assert 'paris' in response.json()['reply'].lower()
