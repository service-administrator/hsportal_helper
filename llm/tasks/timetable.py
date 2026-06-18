import logging
from typing import Any

from llm.config import get_llm_settings
from llm.media import ImagePayload, prepare_image_data_url
from llm.schemas import TimetableExtractionResult
from llm.service import LLMService
from llm.tasks.base import LLMJSONTask, VisionImage
from util.image_processing import NORMALIZED_IMAGE_MAX_EDGE, inspect_image

logger = logging.getLogger(__name__)

TIMETABLE_SYSTEM_INSTRUCTION = """
You are an OCR and timetable parsing assistant for a Korean university service.
Extract only information that is visible in the timetable image.
Return only one valid JSON object. Do not include markdown, comments, or prose.
If a class name or time is unreadable, skip that class and add a Korean warning.
""".strip()

TIMETABLE_PROMPT = """
Analyze the attached timetable image and return JSON in exactly this shape:

{
  "courses": [
    {
      "course_name": "자료구조",
      "day_of_week": "MON",
      "start_time": "09:00",
      "end_time": "10:30"
    }
  ],
  "warnings": []
}

Rules:
- Return JSON only.
- day_of_week must be one of MON, TUE, WED, THU, FRI, SAT, SUN.
- start_time and end_time must use 24-hour HH:MM format.
- Split classes by each visible day/time block.
- If one class appears multiple times in a week, create one object per day/time block.
- If the start and end of a block fall exactly in the middle of the time axis, it represents a 30-minute block.
- If the boundaries of a block are ambiguous, it indicates a consecutive class session.
- Do not guess invisible classes.
- Do not include location, instructor, confidence, or any fields not shown in the JSON shape.
""".strip()


def build_timetable_extraction_task(image_data_url: str) -> LLMJSONTask[TimetableExtractionResult]:
    return LLMJSONTask(
        name="timetable_extraction",
        system_instruction=TIMETABLE_SYSTEM_INSTRUCTION,
        prompt=TIMETABLE_PROMPT,
        response_model=TimetableExtractionResult,
        images=(VisionImage(data_url=image_data_url),),
        max_tokens=3000,
        response_format={"type": "json_object"},
        extra_body=_build_timetable_extra_body(),
    )


def _build_timetable_extra_body() -> dict[str, Any]:
    settings = get_llm_settings()
    extra_body: dict[str, Any] = {
        "enable_thinking": settings.qwen_enable_thinking,
        "vl_high_resolution_images": True,
    }
    if settings.qwen_thinking_budget is not None:
        extra_body["thinking_budget"] = settings.qwen_thinking_budget
    return extra_body


def extract_timetable_from_image_bytes(
    image_bytes: bytes,
    *,
    content_type: str | None = None,
    service: LLMService | None = None,
    log_image_debug: bool = False,
) -> TimetableExtractionResult:
    """Internal helper for backend code. This is intentionally not exposed as an API route."""
    image_payload = prepare_image_data_url(image_bytes, content_type=content_type)
    if log_image_debug:
        _log_image_debug(image_bytes, image_payload)

    task = build_timetable_extraction_task(image_payload.data_url)
    return (service or LLMService()).run_json_task(task)


def _log_image_debug(image_bytes: bytes, image_payload: ImagePayload) -> None:
    original_image = inspect_image(image_bytes)
    logger.info(
        "Timetable VLM image normalized: "
        "original=%s %sx%s %s bytes, normalized=%s %sx%s %s bytes, max_edge=%s.",
        original_image.mime_type,
        original_image.width,
        original_image.height,
        len(image_bytes),
        image_payload.mime_type,
        image_payload.width,
        image_payload.height,
        image_payload.size_bytes,
        NORMALIZED_IMAGE_MAX_EDGE,
    )
