import pytest

from app.config import ConfigurationError, Settings, get_settings
from app.domain import MAX_DISCOUNT_PERCENT


def test_default_discount_is_ten():
    assert MAX_DISCOUNT_PERCENT == 10


def test_valid_modes_accepted():
    assert Settings(CHATBOT_MODE="hardened").mode.value == "hardened"
    assert Settings(CHATBOT_MODE="weak").mode.value == "weak"


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        Settings(CHATBOT_MODE="turbo")


def test_discount_must_be_bounded_positive():
    with pytest.raises(ValueError):
        Settings(DISCOUNT_MAX_PERCENT=0)
    with pytest.raises(ValueError):
        Settings(DISCOUNT_MAX_PERCENT=200)


def test_environment_must_be_non_empty():
    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="   ")


def test_get_settings_wraps_errors(monkeypatch):
    monkeypatch.setenv("CHATBOT_MODE", "invalid-mode")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError):
        get_settings()
    monkeypatch.setenv("CHATBOT_MODE", "hardened")
    get_settings.cache_clear()
