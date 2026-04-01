"""
AIS Core Configuration.
Reads from the local .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_KEY: str = "changeme"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    ENABLE_LLM_SYNTHESIS: bool = False

    NVIDIA_EMBED_API_KEY: str = ""
    NVIDIA_CHAT_API_KEY: str = ""
    NVIDIA_WHISPER_API_KEY: str = ""
    NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_EMBED_MODEL: str = "nvidia/llama-nemotron-embed-1b-v2"
    NVIDIA_CHAT_MODEL: str = "meta/llama-3.1-70b-instruct"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"

    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_GRPC_PORT: int = 50051

    DATABASE_URL: str = "postgresql+asyncpg://ais_user:ais_password@localhost:5432/ais_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    SWISSEPH_PATH: str = ""
    DEFAULT_AYANAMSA: int = 1
    DEFAULT_HOUSE_SYSTEM: str = "W"

    @property
    def nvidia_chat_api_key(self) -> str:
        return self.NVIDIA_CHAT_API_KEY or self.NVIDIA_EMBED_API_KEY

    @property
    def active_llm_provider(self) -> str:
        if self.ENABLE_LLM_SYNTHESIS and self.nvidia_chat_api_key:
            return "nvidia_nim"
        return "ollama"

    @property
    def active_llm_model(self) -> str:
        if self.ENABLE_LLM_SYNTHESIS and self.nvidia_chat_api_key:
            return self.NVIDIA_CHAT_MODEL
        return self.OLLAMA_MODEL

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()