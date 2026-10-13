from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings from the environment and .env. Nothing is required to start the app."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    mongodb_uri: SecretStr = SecretStr("")
    mongodb_db_name: str = "building_with_rag"
    mongodb_test_db_name: str = "building_with_rag_test"
    voyage_api_key: SecretStr = SecretStr("")
    capstone_api_key: SecretStr = SecretStr("")
    webui_demo_caller_id: str = "demo-public"
    generation_api_base_url: str = ""
    generation_api_key: SecretStr = SecretStr("")
    generation_model_name: str = "gpt-4o-mini"
    rerank_api_base_url: str = "https://api.voyageai.com/v1"
    rerank_api_key: SecretStr = SecretStr("")
    rerank_model_name: str = "rerank-2.5"
    rerank_request_timeout_seconds: float = 30
    rerank_candidate_limit: int = 20
    rerank_send_limit: int = 10
    rerank_return_limit: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
