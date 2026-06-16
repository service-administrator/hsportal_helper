from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_PUBLIC_DIR = BASE_DIR / "frontend" / "public"


class BackendSettings(BaseSettings):
    app_name: str = "hsportal-helper"
    app_env: str = "local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_backend_settings() -> BackendSettings:
    return BackendSettings()
