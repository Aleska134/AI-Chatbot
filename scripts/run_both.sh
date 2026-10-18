#!/usr/bin/env bash
# Start the hardened (8100) and weak (8101) targets together. Ctrl+C stops both.
set -euo pipefail
trap 'kill 0' EXIT
CHATBOT_MODE=hardened MOCK_LLM=true uvicorn app.main:app --port 8100 &
CHATBOT_MODE=weak MOCK_LLM=true uvicorn app.main:app --port 8101 &
wait
