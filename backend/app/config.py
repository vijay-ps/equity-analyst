from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Google OAuth ─────────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/callback"

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://equity_user:equity_pass@localhost:5432/equity_db"
    database_url_sync: str = "postgresql+psycopg2://equity_user:equity_pass@localhost:5432/equity_db"

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ── Embeddings ───────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ── Ingestion ─────────────────────────────────────────────────────────────
    news_refresh_hours: int = 6
    max_article_tokens: int = 512
    chunk_overlap_tokens: int = 50

    # ── AWS ──────────────────────────────────────────────────────────────────
    aws_region: str = "ap-south-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
