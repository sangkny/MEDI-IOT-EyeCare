# MEDI-IOT-EyeCare/config.py
"""
애플리케이션 설정 — pydantic-settings 기반
환경변수 또는 .env 파일에서 자동 로드
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 서비스 기본 정보 ───────────────────────────────────
    service_name: str = "MEDI-IOT-EyeCare"
    version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # ── 데이터베이스 ───────────────────────────────────────
    database_url: str = "postgresql+asyncpg://dev:dev@postgres:5432/mediiot"

    # ── Redis ──────────────────────────────────────────────
    redis_url: str = "redis://redis:6379"
    cache_ttl_sec: int = 300          # 진단 결과 캐시 5분

    # ── LLM Provider ───────────────────────────────────────
    llm_provider: str = "local"
    llm_default_role: str = "vision"
    local_base_url: str = "http://host.docker.internal:8000/v1"
    local_api_key: str = "lm-studio"
    local_fast_model: str = "google/gemma-4-e4b"
    local_heavy_model: str = "google/gemma-4-26b-a4b"
    local_vision_model: str = "google/gemma-4-26b-a4b"
    local_embed_model: str = "text-embedding-nomic-embed-text-v1.5"

    # ── 보안 ───────────────────────────────────────────────
    secret_key: str = "medi-iot-dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── 의료 설정 ──────────────────────────────────────────
    max_report_length: int = 2000     # 진단 보고서 최대 글자 수
    diagnosis_timeout_sec: int = 300  # LLM 진단 타임아웃
    pii_encryption_enabled: bool = True  # 환자 개인정보 암호화

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
