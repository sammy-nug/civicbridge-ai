"""Application settings, read from environment variables or backend/.env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    llm_provider: str = "none"
    llm_model: str = ""
    llm_timeout_seconds: float = 60
    request_deadline_seconds: float = 100  # Below the frontend's 120-second timeout.
    max_concurrent_llm_calls: int = 8
    llm_daily_request_limit: int = 0  # Across all users, per process. 0 means no cap.
    gemini_api_key: str = ""
    openai_compatible_base_url: str = ""
    openai_compatible_api_key: str = ""

    embedding_backend: str = "onnx"

    retrieval_top_k: int = 6
    similarity_threshold: float = 0.45
    max_context_chars: int = 6000

    allowed_origins: str = "http://localhost:5173"
    rate_limit_per_minute: int = 20
    rate_limit_per_day: int = 30  # Chat and verify requests per client. 0 means no limit.
    trust_proxy_headers: bool = False
    trusted_proxy_hops: int = 1  # How many proxies in front of the app add to X-Forwarded-For.

    data_dir: Path = BACKEND_DIR / "data"
    processed_dir: Path = REPO_ROOT / "knowledge_base" / "processed_documents"

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
