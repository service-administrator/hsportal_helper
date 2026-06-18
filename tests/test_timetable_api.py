import logging
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.api import timetable
from backend.api.timetable import router
from backend.config import get_backend_settings
from llm.exceptions import LLMRequestError
from llm.schemas import TimetableExtractionResult


def test_extract_timetable_returns_vlm_json_and_logs_debug_in_dev(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    get_backend_settings.cache_clear()

    def fake_extract(
        image_bytes: bytes,
        *,
        content_type: str | None = None,
        log_image_debug: bool = False,
    ):
        assert image_bytes
        assert content_type == "image/png"
        assert log_image_debug is True
        return TimetableExtractionResult(
            courses=[
                {
                    "course_name": "자료구조",
                    "day_of_week": "MON",
                    "start_time": "09:00",
                    "end_time": "10:30",
                }
            ],
            warnings=[],
        )

    monkeypatch.setattr(
        timetable,
        "extract_timetable_from_image_bytes",
        fake_extract,
    )
    client = TestClient(_make_app())

    response = client.post(
        "/api/timetable/extract",
        files={"file": ("timetable.png", _make_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "courses": [
            {
                "course_name": "자료구조",
                "day_of_week": "MON",
                "start_time": "09:00",
                "end_time": "10:30",
            }
        ],
        "warnings": [],
    }


def test_extract_timetable_disables_debug_logging_in_prod(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    get_backend_settings.cache_clear()

    def fake_extract(
        image_bytes: bytes,
        *,
        content_type: str | None = None,
        log_image_debug: bool = False,
    ):
        assert image_bytes
        assert content_type == "image/png"
        assert log_image_debug is False
        return TimetableExtractionResult(courses=[], warnings=[])

    monkeypatch.setattr(
        timetable,
        "extract_timetable_from_image_bytes",
        fake_extract,
    )
    client = TestClient(_make_app())

    response = client.post(
        "/api/timetable/extract",
        files={"file": ("timetable.png", _make_png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "courses": [],
        "warnings": [],
    }


def test_extract_timetable_rejects_invalid_image() -> None:
    client = TestClient(_make_app())

    response = client.post(
        "/api/timetable/extract",
        files={"file": ("not-image.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400


def test_extract_timetable_logs_llm_processing_error(monkeypatch, caplog) -> None:
    def fake_extract(
        image_bytes: bytes,
        *,
        content_type: str | None = None,
        log_image_debug: bool = False,
    ):
        raise LLMRequestError(
            "LLM API request failed for task 'timetable_extraction': "
            "status_code=401 code=invalid_api_key message=Invalid API-key provided."
        )

    monkeypatch.setattr(
        timetable,
        "extract_timetable_from_image_bytes",
        fake_extract,
    )
    caplog.set_level(logging.ERROR, logger="backend.api.timetable")
    client = TestClient(_make_app())

    response = client.post(
        "/api/timetable/extract",
        files={"file": ("timetable.png", _make_png_bytes(), "image/png")},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "LLM API request failed for task 'timetable_extraction': "
        "status_code=401 code=invalid_api_key message=Invalid API-key provided."
    }
    assert "Timetable extraction failed during LLM processing" in caplog.text
    assert "timetable.png" in caplog.text
    assert "Traceback" not in caplog.text


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def _make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()
