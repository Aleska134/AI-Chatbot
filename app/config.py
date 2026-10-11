from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=False)

    service_name: str = 'reference-merchant-chatbot'
    chatbot_mode: str = Field(default='hardened', alias='CHATBOT_MODE')
    mock_llm: bool = Field(default=True, alias='MOCK_LLM')
    environment: str = Field(default='local', alias='ENVIRONMENT')
    discount_max_percent: int = Field(default=20, alias='DISCOUNT_MAX_PERCENT')


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.chatbot_mode not in {'hardened', 'weak'}:
        raise ValueError('CHATBOT_MODE must be either hardened or weak')
    return settings
