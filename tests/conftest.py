import os
from functools import lru_cache

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import get_settings


@lru_cache
def _make_client(mode: str):
    os.environ['CHATBOT_MODE'] = mode
    os.environ['MOCK_LLM'] = 'true'
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.fixture
def hardened_client():
    return _make_client('hardened')


@pytest.fixture
def weak_client():
    return _make_client('weak')
