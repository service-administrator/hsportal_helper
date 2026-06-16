import logging
from io import BytesIO

from PIL import Image

from llm.media import prepare_image_data_url
from llm.schemas import CourseSlot, TimetableExtractionResult
from llm.service import _parse_json_payload
from llm.tasks.timetable import extract_timetable_from_image_bytes
from util.image_processing import normalize_image_for_vlm


def test_prepare_image_data_url_normalizes_png_to_webp() -> None:
    payload = prepare_image_data_url(_make_png_bytes(), content_type="image/png")

    assert payload.mime_type == "image/webp"
    assert payload.width == 1
    assert payload.height == 1
    assert payload.data_url.startswith("data:image/webp;base64,")


def test_normalize_image_for_vlm_limits_max_edge() -> None:
    normalized = normalize_image_for_vlm(_make_png_bytes(size=(3000, 1500)))

    assert normalized.mime_type == "image/webp"
    assert normalized.width == 2000
    assert normalized.height == 1000


def test_course_slot_normalizes_weekday_and_time() -> None:
    slot = CourseSlot(
        course_name="자료구조",
        day_of_week="월요일",
        start_time="9:00",
        end_time="10시 30분",
    )

    assert slot.day_of_week == "MON"
    assert slot.start_time == "09:00"
    assert slot.end_time == "10:30"


def test_parse_json_payload_accepts_markdown_fenced_json() -> None:
    payload = _parse_json_payload(
        '```json\n{"courses": [], "warnings": ["글자가 흐립니다."]}\n```',
        task_name="test",
    )
    result = TimetableExtractionResult.model_validate(payload)

    assert result.courses == []
    assert result.warnings == ["글자가 흐립니다."]


def test_extract_timetable_logs_image_debug_when_enabled(caplog) -> None:
    caplog.set_level(logging.INFO, logger="llm.tasks.timetable")

    result = extract_timetable_from_image_bytes(
        _make_png_bytes(),
        content_type="image/png",
        service=_FakeLLMService(),
        log_image_debug=True,
    )

    assert result == TimetableExtractionResult(courses=[], warnings=[])
    assert "Timetable VLM image normalized" in caplog.text
    assert "original=image/png" in caplog.text
    assert "normalized=image/webp" in caplog.text


class _FakeLLMService:
    def run_json_task(self, task):
        return TimetableExtractionResult(courses=[], warnings=[])


def _make_png_bytes(size: tuple[int, int] = (1, 1)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()
