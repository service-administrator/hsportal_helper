from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3-vl-flash"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
