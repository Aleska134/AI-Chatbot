from typing import Literal
from pydantic import BaseModel, Field, field_validator


class HistoryEntry(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    version: str = Field(default='1')
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryEntry] = Field(default_factory=list)
    mode: str = Field(default='security_test')
    customer_id: str = Field(default='customer-demo-001')

    @field_validator('version')
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != '1':
            raise ValueError('version must be "1"')
        return value


class ChatMetadata(BaseModel):
    chatbot_mode: Literal['hardened', 'weak']
    scope: str = 'commerce_support'
    llm_enabled: bool
    provider_status: str = 'deterministic'


class ChatResponse(BaseModel):
    reply: str
    history: list[HistoryEntry]
    metadata: ChatMetadata


class HealthResponse(BaseModel):
    status: str = 'ok'
    service: str
    chatbot_mode: Literal['hardened', 'weak']
    environment: str


class MetadataResponse(BaseModel):
    service: str
    chatbot_mode: Literal['hardened', 'weak']
    llm_enabled: bool
    scope: str = 'commerce_support'
    environment: str
