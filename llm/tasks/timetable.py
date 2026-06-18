import logging
from typing import Any

from llm.config import get_llm_settings
from llm.media import ImagePayload, prepare_image_data_url
from llm.schemas import TimetableExtractionResult
from llm.service import LLMService
from llm.tasks.base import LLMJSONTask, VisionImage
from util.image_processing import (
    NORMALIZED_IMAGE_MAX_EDGE,
    NORMALIZED_IMAGE_MIN_EDGE,
    inspect_image,
)

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
- Each course block spans either 1.5, 2, or 3 hourly time rows.
- Use this rule only to validate the final duration of a detected block, not to invent, split, extend, or shift block boundaries.
- The timetable is a grid.
- Use the visible horizontal and vertical grid lines to determine each class block.
- The index columns represent the horizontal day-of-week axis.
- The index rows represent the vertical time axis.
- Split classes into separate objects only by visible course block boundaries, not by each hourly time row.
- Use the day-of-week columns to determine the day, and use the time rows only to calculate the top and bottom times of each visible course block.
- start_time is determined by the top boundary of the class block.
- end_time is determined by the bottom boundary of the class block.
- Determine the top and bottom boundaries from the visible outer boundary of the course cell, not from the vertical position of the course text.
- Course text may appear only once inside a block and does not indicate the full height of the block.
- Empty-looking hourly rows do not necessarily indicate free time if a visible course block extends through them.
- If a block boundary lies exactly on an hour row, use HH:00.
- If a block starts or ends halfway between two hour rows, use HH:30.
- If one class appears multiple times in a week, create one object per day/time block.
- If different course blocks are vertically adjacent in the same day column and there is no visible empty gap between them, treat them as back-to-back consecutive class sessions.
- Do not insert a 30-minute gap between adjacent course blocks unless a visible empty space exists.
- If two different course blocks touch vertically, the first block's end_time must equal the next block's start_time.
- Still extract each distinct course as a separate object.
- Distinguish clearly between the course name and the classroom to extract only the course name.
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
        "original=%s %sx%s %s bytes, normalized=%s %sx%s %s bytes, "
        "min_edge=%s max_edge=%s.",
        original_image.mime_type,
        original_image.width,
        original_image.height,
        len(image_bytes),
        image_payload.mime_type,
        image_payload.width,
        image_payload.height,
        image_payload.size_bytes,
        NORMALIZED_IMAGE_MIN_EDGE,
        NORMALIZED_IMAGE_MAX_EDGE,
    )
