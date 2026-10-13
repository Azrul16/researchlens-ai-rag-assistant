from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ROOT = BACKEND_ROOT.parent if BACKEND_ROOT.name == "backend" else BACKEND_ROOT


class Settings(BaseSettings):
    """Validated runtime configuration; credentials stay on the backend."""

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = f"sqlite+aiosqlite:///{(ROOT / 'data/researchlens.db').as_posix()}"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = Field(default=25, ge=1, le=100)
    chunk_size: int = Field(default=900, ge=50)
    chunk_overlap: int = Field(default=120, ge=0)
    upload_dir: Path = ROOT / "data/uploads"
    vector_index_dir: Path = ROOT / "data/vector_indexes"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_revision: str | None = None
    retrieval_top_k: int = Field(default=8, ge=1, le=50)
    final_context_k: int = Field(default=5, ge=1, le=20)
    retrieval_score_threshold: float = Field(default=0.3, ge=-1, le=1)
    enable_reranker: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    chat_history_messages: int = Field(default=8, ge=0, le=30)
    context_token_budget: int = Field(default=12000, ge=2000, le=64000)
    groq_model: str = "qwen/qwen3.8-27b"
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: float = Field(default=90, ge=5, le=300)
    ai_requests_per_minute: int = Field(default=20, ge=1, le=1000)
    api_token: SecretStr = SecretStr("")
    max_pdf_pages: int = Field(default=500, ge=1, le=2000)
    llm_provider: Literal["groq", "gemini"] = "groq"
    groq_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def valid_overlap(self):
        if not self.embedding_revision:
            self.embedding_revision = None
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.final_context_k > self.retrieval_top_k:
            raise ValueError("FINAL_CONTEXT_K must not exceed RETRIEVAL_TOP_K")
        if self.app_env == "production" and not self.api_token.get_secret_value():
            raise ValueError("Production requires API_TOKEN for authenticated access")
        if not self.upload_dir.is_absolute():
            self.upload_dir = (ROOT / self.upload_dir).resolve()
        if not self.vector_index_dir.is_absolute():
            self.vector_index_dir = (ROOT / self.vector_index_dir).resolve()
        url = make_url(self.database_url)
        if url.get_backend_name() == "sqlite" and url.database not in {None, ":memory:"}:
            path = Path(url.database)
            if not path.is_absolute():
                self.database_url = url.set(
                    database=(ROOT / path).resolve().as_posix()
                ).render_as_string()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
