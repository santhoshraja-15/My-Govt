"""Application configuration using pydantic-settings."""
from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_ENV: str = "development"
    APP_LOG_LEVEL: str = "INFO"
    APP_DEBUG: bool = True
    APP_CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"

    # PostgreSQL
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "mygovt"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "changeme"
    MYGOVT_APP_PASSWORD: str = "changeme_app"

    # Neo4j
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changeme_neo4j"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "changeme_minio"
    MINIO_BUCKET_EVIDENCE: str = "mygovt-evidence"
    MINIO_BUCKET_DOCUMENTS: str = "mygovt-documents"

    # JWT
    JWT_SECRET_KEY: str = "change_me_very_long_random_secret_at_least_64_chars_for_security"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    LLM_PROVIDER: str = "none"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.1

    # Embedding
    EMBEDDING_PROVIDER: str = "local"
    # English 1024-d model; multilingual retrieval is not required. Changing model or dimension means
    # changing the vector(1024) columns deliberately (see docs); vectors are never truncated or padded.
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    EMBEDDING_API_KEY: str = ""        # only for EMBEDDING_PROVIDER=openai; set via environment
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 32

    # AI Pipeline
    TRUST_THRESHOLD: float = 0.70
    CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.60
    HYBRID_WEIGHT_SEMANTIC: float = 0.35
    HYBRID_WEIGHT_KEYWORD: float = 0.25
    HYBRID_WEIGHT_GRAPH: float = 0.15
    HYBRID_WEIGHT_RELIABILITY: float = 0.15
    HYBRID_WEIGHT_FRESHNESS: float = 0.10
    MAX_RETRIEVAL_CHUNKS: int = 50
    # A vector hit with no keyword match must reach this cosine similarity to count as evidence; otherwise
    # nearest-neighbour search would return something for ANY question and the assistant could never abstain.
    # NOT calibrated against real queries yet - tune with an evaluation set before relying on it.
    RETRIEVAL_MIN_SIMILARITY: float = 0.6
    MAX_CONTEXT_TOKENS: int = 6000

    # Abuse protection (per client IP, per process)
    RATE_LIMIT_LOGIN_PER_MIN: int = 10
    RATE_LIMIT_REGISTER_PER_HOUR: int = 5
    RATE_LIMIT_CHAT_PER_MIN: int = 30

    # Features
    FEATURE_VOICE: bool = False
    FEATURE_GRAPH: bool = True
    FEATURE_VECTOR_SEARCH: bool = True

    @model_validator(mode="after")
    def _reject_insecure_production_defaults(self):
        """Refuse to start in production with placeholder secrets."""
        if self.APP_ENV.lower() == "production":
            bad = [
                name for name, val in (
                    ("JWT_SECRET_KEY", self.JWT_SECRET_KEY),
                    ("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD),
                    ("NEO4J_PASSWORD", self.NEO4J_PASSWORD),
                    ("MINIO_SECRET_KEY", self.MINIO_SECRET_KEY),
                ) if val.lower().startswith(("change", "minioadmin")) or len(val) < 8
            ]
            if len(self.JWT_SECRET_KEY) < 32 and "JWT_SECRET_KEY" not in bad:
                bad.append("JWT_SECRET_KEY")
            if bad:
                raise ValueError("Insecure placeholder secrets in production: " + ", ".join(bad))
        return self

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def APP_CORS_ORIGINS_LIST(self) -> List[str]:
        return [o.strip() for o in self.APP_CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
