# reference-merchant-chatbot

A small FastAPI reference merchant chatbot for local AI security testing.

## Purpose

This project provides a deterministic TechMart support chatbot that can run in two runtime modes from the same codebase:

- `hardened`: strict security and scope enforcement.
- `weak`: intentionally weaker behavior for authorized local security demonstrations.

Both modes exist so security testing platforms can compare protected vs intentionally weaker behavior in controlled conditions.

## Safety model

- Uses mock catalog, customers, carts, and orders only.
- No production integrations.
- No real customer data.
- No real payment provider calls.
- No destructive administrative capabilities.

> **Warning:** `weak` mode is a controlled testing target for authorized local testing only.

## Run locally

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run hardened instance (port 8100):

```bash
CHATBOT_MODE=hardened MOCK_LLM=true uvicorn app.main:app --host 0.0.0.0 --port 8100
```

Run weak instance (port 8101):

```bash
CHATBOT_MODE=weak MOCK_LLM=true uvicorn app.main:app --host 0.0.0.0 --port 8101
```

## Connect to the security testing platform

- Hardened target: `http://localhost:8100/api/v1/chat`
- Weak target: `http://localhost:8101/api/v1/chat`

## API contract

### `POST /api/v1/chat`

Request example:

```json
{
  "version": "1",
  "message": "Show me wireless headphones",
  "history": [],
  "mode": "security_test",
  "customer_id": "customer-demo-001"
}
```

Response example:

```json
{
  "reply": "Here are the available wireless headphones...",
  "history": [
    {"role": "user", "content": "Show me wireless headphones"},
    {"role": "assistant", "content": "Here are the available wireless headphones..."}
  ],
  "metadata": {
    "chatbot_mode": "hardened",
    "scope": "commerce_support",
    "llm_enabled": false,
    "provider_status": "deterministic"
  }
}
```

### `GET /health`

Returns service status and active mode.

### `GET /api/v1/metadata`

Returns safe runtime metadata:

```json
{
  "service": "reference-merchant-chatbot",
  "chatbot_mode": "hardened",
  "llm_enabled": false,
  "scope": "commerce_support",
  "environment": "local"
}
```

## Deterministic mock mode

Set `MOCK_LLM=true` (default) to avoid API-credit usage and keep deterministic behavior for tests/demos.

## cURL examples

```bash
curl -X POST http://localhost:8100/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"version":"1","message":"Show me wireless headphones","history":[],"mode":"security_test","customer_id":"customer-demo-001"}'
```

```bash
curl -X POST http://localhost:8101/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"version":"1","message":"What is the capital of France? Please explain its history.","history":[],"mode":"security_test","customer_id":"customer-demo-001"}'
```

## Tests

Run all tests:

```bash
python -m pytest
```

Coverage includes product questions, scope boundaries, prompt injection behavior, discount limits, checkout confirmation rules, customer isolation, policy bypass attempts, API validation, provider fallback, mode differences, and health/metadata endpoints.
