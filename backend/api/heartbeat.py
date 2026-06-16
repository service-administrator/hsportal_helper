from datetime import datetime, timezone

from fastapi import APIRouter

from backend.config import get_backend_settings
from llm.qwen_client import get_qwen_model_name

router = APIRouter(tags=["system"])


@router.get("/heartbeat")
def heartbeat() -> dict[str, str]:
    settings = get_backend_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "llm_model": get_qwen_model_name(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

