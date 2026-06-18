import logging
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from llm.config import get_llm_settings
from llm.media import prepare_image_data_url
from llm.schemas import CourseSlot, TimetableExtractionResult
from llm.service import LLMService, _api_error_detail, _parse_json_payload
from llm.tasks.timetable import build_timetable_extraction_task, extract_timetable_from_image_bytes
from util.image_processing import normalize_image_for_vlm


def test_prepare_image_data_url_normalizes_png_to_webp() -> None:
    payload = prepare_image_data_url(_make_png_bytes(), content_type="image/png")

    assert payload.mime_type == "image/webp"
    assert payload.width == 1500
    assert payload.height == 1500
    assert payload.data_url.startswith("data:image/webp;base64,")


def test_normalize_image_for_vlm_limits_max_edge() -> None:
    normalized = normalize_image_for_vlm(_make_png_bytes(size=(3000, 1500)))

    assert normalized.mime_type == "image/webp"
    assert normalized.width == 2500
    assert normalized.height == 1250


def test_normalize_image_for_vlm_raises_low_resolution_edge() -> None:
    normalized = normalize_image_for_vlm(_make_png_bytes(size=(600, 300)))

    assert normalized.mime_type == "image/webp"
    assert normalized.width == 1500
    assert normalized.height == 750


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


def test_api_error_detail_extracts_provider_error_body() -> None:
    error = _FakeAPIError()

    assert _api_error_detail(error) == (
        "status_code=401 code=invalid_api_key request_id=req-123 "
        "message=Invalid API-key provided."
    )


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


def test_timetable_task_uses_reasoning_env_options(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_ENABLE_THINKING", "true")
    monkeypatch.setenv("QWEN_THINKING_BUDGET", "512")
    get_llm_settings.cache_clear()

    task = build_timetable_extraction_task("data:image/webp;base64,abc")

    assert task.extra_body == {
        "enable_thinking": True,
        "vl_high_resolution_images": True,
        "thinking_budget": 512,
    }
    get_llm_settings.cache_clear()


def test_llm_service_logs_full_api_response_in_dev(monkeypatch, caplog) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    get_llm_settings.cache_clear()
    caplog.set_level(logging.INFO, logger="llm.service")

    service = LLMService(client=_FakeOpenAIClient(), model="qwen-test")
    result = service.run_json_task(build_timetable_extraction_task("data:image/webp;base64,abc"))

    assert result == TimetableExtractionResult(courses=[], warnings=[])
    assert "LLM API response" in caplog.text
    assert "reasoning_content" in caplog.text
    assert "finish_reason" in caplog.text
    assert "prompt_tokens" in caplog.text
    assert '\\"courses\\": []' in caplog.text
    get_llm_settings.cache_clear()


class _FakeLLMService:
    def run_json_task(self, task):
        return TimetableExtractionResult(courses=[], warnings=[])


class _FakeChatCompletions:
    def create(self, **kwargs):
        return SimpleNamespace(
            id="chatcmpl-test",
            model="qwen-test",
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content='{"courses": [], "warnings": []}',
                        reasoning_content="looked at the timetable grid",
                    ),
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


class _FakeOpenAIClient:
    chat = SimpleNamespace(completions=_FakeChatCompletions())


class _FakeAPIError(Exception):
    status_code = 401
    request_id = None
    body = {
        "message": "Invalid API-key provided.",
        "id": "req-123",
        "type": "invalid_request_error",
        "code": "invalid_api_key",
    }


def _make_png_bytes(size: tuple[int, int] = (1, 1)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()
