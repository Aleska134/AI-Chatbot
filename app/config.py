"""Typed, validated runtime configuration.

Configuration is the single place that decides the server runtime mode. The
per-request ``mode`` field (``security_test``) never changes this; it only
labels the purpose of the request.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain import (
    MAX_DISCOUNT_PERCENT,
    SERVICE_NAME,
    ChatbotMode,
)


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is invalid at startup."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    service_name: str = SERVICE_NAME
    chatbot_mode: str = Field(default=ChatbotMode.HARDENED.value, alias="CHATBOT_MODE")
    mock_llm: bool = Field(default=True, alias="MOCK_LLM")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    discount_max_percent: int = Field(
        default=MAX_DISCOUNT_PERCENT, alias="DISCOUNT_MAX_PERCENT"
    )

    @field_validator("chatbot_mode")
    @classmethod
    def _validate_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        valid = {mode.value for mode in ChatbotMode}
        if normalized not in valid:
            raise ValueError(
                f"CHATBOT_MODE must be one of {sorted(valid)}, got '{value}'."
            )
        return normalized

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("ENVIRONMENT must be a non-empty value.")
        return value.strip()

    @field_validator("discount_max_percent")
    @classmethod
    def _validate_discount(cls, value: int) -> int:
        if value <= 0 or value > 100:
            raise ValueError(
                "DISCOUNT_MAX_PERCENT must be a positive integer between 1 and 100."
            )
        return value

    @property
    def mode(self) -> ChatbotMode:
        return ChatbotMode(self.chatbot_mode)

    @property
    def is_hardened(self) -> bool:
        return self.mode is ChatbotMode.HARDENED


@lru_cache
def get_settings() -> Settings:
    """Load and validate settings once. Fails clearly on invalid configuration."""
    try:
        return Settings()
    except Exception as error:  # noqa: BLE001 - re-raised as a clear startup error
        raise ConfigurationError(f"Invalid chatbot configuration: {error}") from error
