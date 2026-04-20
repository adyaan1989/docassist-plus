"""
Application settings — loaded from environment variables / .env
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── LLM ──────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini" # cost-optimised default
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 1024

    # ── Embeddings ───────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # ── Vector Store (Chroma — swappable to Pinecone/Weaviate) ──────────
    VECTOR_STORE_TYPE: str = "chroma" # "chroma" | "pinecone" | "qdrant"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "docassist"

    # ── Chunking ─────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K: int = 3   # retrieved chunks per query

    # ── Session / Redis ──────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL_SECONDS: int = 3600 # 1 hour

    # ── Caching ──────────────────────────────────────────────────────────
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300 # 5 min for query responses

    # ── Rate Limiting ────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60 # per minute

    # ── File Upload ──────────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt", ".docx", ".md", ".csv"]
    UPLOAD_DIR: str = "./uploads"

    # ── Intent / Emotion ─────────────────────────────────────────────────
    INTENT_CONFIDENCE_THRESHOLD: float = 0.6
    EMOTION_CONFIDENCE_THRESHOLD: float = 0.5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()