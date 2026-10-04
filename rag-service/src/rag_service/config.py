from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://rag:rag_local_dev@localhost:55432/rag"
    aws_profile: str | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_backend: Literal["auto", "bedrock", "ollama"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_embedding_model: str | None = "qwen3-embedding:0.6b"
    ollama_embedding_context_length: int = Field(default=2048, ge=512, le=32768)
    ollama_default_embedding_model: str = "qwen3-embedding:0.6b"
    ollama_chat_model: str = "qwen2.5:3b"
    ollama_chat_num_gpu: int = Field(default=-1, ge=-1)
    ollama_chat_timeout: int = Field(default=120, ge=1, le=600)
    ollama_timeout: int = Field(default=120, ge=1, le=600)
    ollama_pull_timeout: int = Field(default=1800, ge=1, le=7200)
    embedding_circuit_seconds: int = Field(default=60, ge=0, le=3600)
    ollama_shadow_enabled: bool = True
    chunk_size_chars: int = Field(default=2000, ge=100, le=6000)
    chunk_overlap_chars: int = Field(default=200, ge=0)
    max_pdf_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=300, gt=0)
    max_chunks: int = Field(default=1000, gt=0)
    db_connect_timeout: int = Field(default=3, ge=1, le=30)
    bedrock_read_timeout: int = Field(default=30, ge=1, le=120)

    @model_validator(mode="after")
    def validate_overlap(self) -> "Settings":
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("CHUNK_OVERLAP_CHARS debe ser menor que CHUNK_SIZE_CHARS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
