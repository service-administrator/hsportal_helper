from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import recommendations
from backend.api.recommendations import router
from backend.recommendation import ScheduleKind, build_recommendations, classify_schedule_kind
from llm.schemas import TimetableExtractionResult


def test_recommends_fixed_session_when_it_does_not_conflict() -> None:
    result = build_recommendations(
        TimetableExtractionResult(courses=[_course("FRI", "09:00", "10:30")]),
        [
            _program(
                "1",
                schedules=[
                    _schedule(
                        "2026-06-26T14:00:00+09:00",
                        "2026-06-26T16:00:00+09:00",
                    )
                ],
            )
        ],
    )

    item = result.recommendations[0]

    assert item.availability == "available"
    assert item.schedule_kind == ScheduleKind.FIXED_SESSION
    assert item.conflicts == []


def test_marks_fixed_session_unavailable_when_it_conflicts() -> None:
    result = build_recommendations(
        TimetableExtractionResult(courses=[_course("FRI", "15:00", "16:30")]),
        [
            _program(
                "1",
                schedules=[
                    _schedule(
                        "2026-06-26T14:00:00+09:00",
                        "2026-06-26T16:00:00+09:00",
                    )
                ],
            )
        ],
        include_unavailable=True,
    )

    item = result.recommendations[0]

    assert item.availability == "unavailable"
    assert item.conflicts[0].course_name == "자료구조"


def test_checks_timetable_when_multiple_schedules_each_end_on_same_day() -> None:
    result = build_recommendations(
        TimetableExtractionResult(courses=[_course("WED", "14:00", "15:30")]),
        [
            _program(
                "multi-day-same-day-sessions",
                schedules=[
                    _schedule(
                        "2026-07-22T13:00:00+09:00",
                        "2026-07-22T16:00:00+09:00",
                    ),
                    _schedule(
                        "2026-07-23T13:00:00+09:00",
                        "2026-07-23T16:00:00+09:00",
                    ),
                    _schedule(
                        "2026-07-24T13:00:00+09:00",
                        "2026-07-24T16:00:00+09:00",
                    ),
                ],
            )
        ],
        include_unavailable=True,
    )

    item = result.recommendations[0]

    assert item.schedule_kind == ScheduleKind.SAME_DAY
    assert item.availability == "unavailable"
    assert item.conflicts[0].program_start_at == "2026-07-22T13:00:00+09:00"


def test_classifies_online_submission_and_flexible_programs() -> None:
    online = _program(
        "online",
        category={"main": "상담·심리지원", "sub": "특강·워크숍"},
        schedules=[
            _schedule(
                "2026-05-18T00:00:00+09:00",
                "2026-12-31T23:45:00+09:00",
                "온라인",
            )
        ],
        description="e-class 온라인 교육 동영상 수강",
    )
    submission = _program(
        "contest",
        category={"main": "학습역량강화", "sub": "공모전·대회"},
        description="작품 제출 후 심사하는 경진대회",
    )
    flexible = _program(
        "counsel",
        category={"main": "상담·심리지원", "sub": "상담·검사"},
        description="1:1 상담 희망 일시를 선택하고 개별 조율",
    )

    assert classify_schedule_kind(online) == ScheduleKind.ASYNC_ONLINE
    assert classify_schedule_kind(submission) == ScheduleKind.SUBMISSION
    assert classify_schedule_kind(flexible) == ScheduleKind.FLEXIBLE


def test_same_day_field_experience_is_not_classified_as_long_term() -> None:
    program = _program(
        "showcase",
        category={"main": "전공역량강화", "sub": "현장체험활동"},
        schedules=[
            _schedule(
                "2026-06-20T16:00:00+09:00",
                "2026-06-20T18:00:00+09:00",
                "낙산관 대극장",
            )
        ],
        description="예술학부 프로젝트 쇼케이스 관람",
    )

    assert classify_schedule_kind(program) == ScheduleKind.FIXED_SESSION


def test_long_range_field_experience_can_still_be_long_term() -> None:
    program = _program(
        "internship",
        category={"main": "진로·취업지원", "sub": "현장체험활동"},
        schedules=[
            _schedule(
                "2026-01-01T00:00:00+09:00",
                "2026-06-30T00:00:00+09:00",
                "학생별 실습기업",
            )
        ],
        description="기업별 2개월 또는 4개월 현장실습 프로젝트",
    )

    assert classify_schedule_kind(program) == ScheduleKind.LONG_TERM


def test_recommendations_api_uses_saved_programs(monkeypatch) -> None:
    monkeypatch.setattr(
        recommendations,
        "load_dataset",
        lambda: {
            "programs": [
                _program(
                    "1",
                    schedules=[
                        _schedule(
                            "2026-06-26T14:00:00+09:00",
                            "2026-06-26T16:00:00+09:00",
                        )
                    ],
                )
            ]
        },
    )
    client = TestClient(_make_app())

    response = client.post(
        "/api/recommendations",
        json={
            "courses": [
                {
                    "course_name": "자료구조",
                    "day_of_week": "FRI",
                    "start_time": "09:00",
                    "end_time": "10:30",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["available"] == 1
    assert payload["recommendations"][0]["availability"] == "available"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


def _course(day: str, start: str, end: str) -> dict[str, str]:
    return {
        "course_name": "자료구조",
        "day_of_week": day,
        "start_time": start,
        "end_time": end,
    }


def _program(
    program_id: str,
    *,
    category: dict[str, str] | None = None,
    schedules: list[dict[str, str]] | None = None,
    description: str = "",
) -> dict:
    return {
        "id": program_id,
        "title": f"프로그램 {program_id}",
        "url": f"https://example.test/programs/{program_id}",
        "status": {
            "code": "open",
            "label": "접수중",
            "accepting": True,
        },
        "points": 10,
        "type": "개인",
        "category": category or {"main": "학습역량강화", "sub": "특강·워크숍"},
        "participants": {
            "current": 0,
            "capacity": None,
            "is_unlimited": True,
        },
        "schedules": schedules or [],
        "content": {
            "summary": "",
            "description_text": description,
        },
    }


def _schedule(start_at: str, end_at: str, location: str = "상상관") -> dict[str, str]:
    return {
        "start_at": start_at,
        "end_at": end_at,
        "location": location,
    }
