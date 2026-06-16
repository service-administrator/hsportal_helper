import logging

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
If a field is unreadable, use null for optional fields and add a Korean warning.
""".strip()

TIMETABLE_PROMPT = """
Analyze the attached timetable image and return JSON in exactly this shape:

{
  "courses": [
    {
      "course_name": "강의명",
      "day_of_week": "MON",
      "start_time": "09:00",
      "end_time": "10:30",
      "location": "강의실 또는 null",
      "instructor": "교수명 또는 null",
      "confidence": 0.0
    }
  ],
  "warnings": []
}

Rules:
- JSON만 반환하세요.
- day_of_week must be one of MON, TUE, WED, THU, FRI, SAT, SUN.
- start_time and end_time must use 24-hour HH:MM format.
- Split classes by each visible day/time block.
- If one class appears multiple times in a week, create one object per day/time block.
- Do not guess invisible classes, locations, or instructors.
- confidence must be between 0 and 1.
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
        extra_body={"enable_thinking": False, "vl_high_resolution_images": True},
    )


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
