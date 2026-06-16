from openai import OpenAI

from llm.config import get_llm_settings


def get_qwen_client() -> OpenAI:
    settings = get_llm_settings()
    if not settings.qwen_api_key:
        raise RuntimeError("QWEN_API_KEY is not configured. Copy .env.example to .env first.")

    return OpenAI(
        api_key=settings.qwen_api_key,
        base_url=settings.qwen_base_url,
    )


def get_qwen_model_name() -> str:
    return get_llm_settings().qwen_model

