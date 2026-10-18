"""HTTP routes. The webhook contract is preserved; metadata is enriched."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException

from app import commerce
from app.agent import MerchantAgent
from app.config import Settings
from app.domain import ChatbotMode
from app.schemas import (
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    HistoryEntry,
    MetadataResponse,
)

WEAK_MODE_WARNING = (
    "Weak mode is an intentionally less-protected local testing target."
)


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    agent = MerchantAgent(settings)

    @router.post("/api/v1/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        authorization: str | None = Header(default=None),
    ) -> ChatResponse:
        if settings.auth_token and not secrets.compare_digest(
            authorization or "", f"Bearer {settings.auth_token}"
        ):
            raise HTTPException(status_code=401, detail="Invalid or missing token.")
        # Deterministic customer validation: unknown ids are rejected safely.
        if not commerce.MockStore.is_known_customer(payload.customer_id):
            raise HTTPException(
                status_code=404,
                detail=f"Unknown customer_id '{payload.customer_id}'.",
            )

        result = agent.respond(
            message=payload.message,
            customer_id=payload.customer_id,
            history=payload.history,
        )
        updated_history = [
            *payload.history,
            HistoryEntry(role="user", content=payload.message),
            HistoryEntry(role="assistant", content=result.reply),
        ]
        return ChatResponse(
            reply=result.reply,
            history=updated_history,
            metadata=ChatMetadata(
                chatbot_mode=settings.chatbot_mode,
                llm_enabled=not settings.mock_llm,
                provider_status=result.provider_status,
                security_outcome=result.security_outcome.value,
                block_reason=(
                    result.block_reason.value if result.block_reason else None
                ),
                business_behavior=result.business_behavior.value,
            ),
        )

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            service=settings.service_name,
            chatbot_mode=settings.chatbot_mode,
            environment=settings.environment,
        )

    @router.get("/api/v1/metadata", response_model=MetadataResponse)
    def metadata() -> MetadataResponse:
        return MetadataResponse(
            service=settings.service_name,
            chatbot_mode=settings.chatbot_mode,
            llm_enabled=not settings.mock_llm,
            environment=settings.environment,
            discount_max_percent=settings.discount_max_percent,
            warning=(
                WEAK_MODE_WARNING if settings.mode is ChatbotMode.WEAK else None
            ),
        )

    return router
