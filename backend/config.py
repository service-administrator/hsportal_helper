from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseSettings):
    app_name: str = "hsportal-helper"
    app_env: str = "dev"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_backend_settings() -> BackendSettings:
    return BackendSettings()


def is_dev_environment() -> bool:
    return get_backend_settings().app_env.strip().lower() == "dev"
