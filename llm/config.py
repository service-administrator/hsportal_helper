from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    app_env: str = "dev"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3-vl-flash"
    qwen_enable_thinking: bool = False
    qwen_thinking_budget: int | None = Field(default=None, ge=1)
    llm_max_image_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
