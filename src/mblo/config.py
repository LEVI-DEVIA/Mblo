from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    anthropic_api_key: str = ""
    model_analyst: str = "claude-opus-5"
    model_router: str = "claude-haiku-4-5"

    wasender_api_key: str = ""
    wasender_webhook_secret: str = ""

    cinetpay_api_key: str = ""
    cinetpay_site_id: str = ""
    cinetpay_secret: str = ""

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    admin_token: str = ""
    send_rate_per_min: int = 20
    public_base_url: str = "http://localhost:8000"
    raw_dir: str = "data/raw"


@lru_cache
def get_settings() -> Settings:
    return Settings()
