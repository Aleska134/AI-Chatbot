from fastapi import APIRouter

from app.agent import MerchantAgent
from app.config import Settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MetadataResponse,
    HistoryEntry,
    ChatMetadata,
)


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    agent = MerchantAgent(settings)

    @router.post('/api/v1/chat', response_model=ChatResponse)
    def chat(payload: ChatRequest) -> ChatResponse:
        result = agent.respond(payload.message, payload.customer_id)
        updated_history = [*payload.history, HistoryEntry(role='user', content=payload.message), HistoryEntry(role='assistant', content=result.reply)]
        return ChatResponse(
            reply=result.reply,
            history=updated_history,
            metadata=ChatMetadata(
                chatbot_mode=settings.chatbot_mode,
                llm_enabled=not settings.mock_llm,
                provider_status=result.provider_status,
            ),
        )

    @router.get('/health', response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            service=settings.service_name,
            chatbot_mode=settings.chatbot_mode,
            environment=settings.environment,
        )

    @router.get('/api/v1/metadata', response_model=MetadataResponse)
    def metadata() -> MetadataResponse:
        return MetadataResponse(
            service=settings.service_name,
            chatbot_mode=settings.chatbot_mode,
            llm_enabled=not settings.mock_llm,
            environment=settings.environment,
        )

    return router
