"""Request/response contracts for the reference merchant chatbot.

The webhook contract (version, message, history, mode, customer_id -> reply,
history, metadata) is intentionally stable so the external security testing
platform keeps working. ``mode`` is validated but never changes the server
runtime mode.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.domain import SCOPE

# Conversation limits (history is never trusted blindly).
MAX_HISTORY_ENTRIES = 20
MAX_CONTENT_LENGTH = 2000
MAX_TOTAL_CONVERSATION_CHARS = 20000


class HistoryEntry(BaseModel):
    # Only user/assistant are allowed; system messages are rejected (422).
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)


class ChatRequest(BaseModel):
    version: str = Field(default="1")
    message: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    history: list[HistoryEntry] = Field(default_factory=list, max_length=MAX_HISTORY_ENTRIES)
    # Identifies the purpose of the request only; does not switch server mode.
    mode: Literal["security_test"] = Field(default="security_test")
    # Optional so the platform webhook (which omits it) keeps working.
    customer_id: str = Field(default="customer-demo-001")

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != "1":
            raise ValueError('version must be "1"')
        return value

    @field_validator("history")
    @classmethod
    def validate_total_size(cls, value: list[HistoryEntry]) -> list[HistoryEntry]:
        total = sum(len(entry.content) for entry in value)
        if total > MAX_TOTAL_CONVERSATION_CHARS:
            raise ValueError("conversation history exceeds the maximum allowed size")
        return value


class ChatMetadata(BaseModel):
    chatbot_mode: Literal["hardened", "weak"]
    scope: str = SCOPE
    llm_enabled: bool
    provider_status: str = "deterministic"
    security_outcome: Literal["allowed", "blocked", "resisted", "unavailable", "fallback"]
    block_reason: Optional[str] = None
    business_behavior: str = "not_tested"


class ChatResponse(BaseModel):
    reply: str
    history: list[HistoryEntry]
    metadata: ChatMetadata


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    chatbot_mode: Literal["hardened", "weak"]
    environment: str


class MetadataResponse(BaseModel):
    service: str
    chatbot_mode: Literal["hardened", "weak"]
    llm_enabled: bool
    scope: str = SCOPE
    environment: str
    discount_max_percent: int
    warning: Optional[str] = None
