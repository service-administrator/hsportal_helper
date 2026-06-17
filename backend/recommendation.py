from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm.schemas import CourseSlot, TimetableExtractionResult, Weekday


class ScheduleKind(str, Enum):
    SAME_DAY = "same_day"
    SHORT_PERIOD = "short_period"
    LONG_PERIOD = "long_period"
    NO_SCHEDULE = "no_schedule"
    INVALID_SCHEDULE = "invalid_schedule"

    # Backward-compatible aliases for older callers importing enum names.
    FIXED_SESSION = "same_day"
    MULTI_SESSION = "same_day"
    SELECTABLE_SESSION = "same_day"
    ASYNC_ONLINE = "long_period"
    LONG_TERM = "long_period"
    SUBMISSION = "no_schedule"
    FLEXIBLE = "no_schedule"
    UNCERTAIN = "invalid_schedule"


Availability = Literal["available", "needs_review", "unavailable"]
Confidence = Literal["high", "medium", "low"]

HS_PORTAL_SUB_CATEGORIES = {
    "특강·워크숍",
    "상담·검사",
    "현장체험활동",
    "공모전·대회",
    "소모임·멘토링",
    "봉사",
}


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    courses: list[CourseSlot] = Field(default_factory=list)
    include_needs_review: bool = True
    include_unavailable: bool = False
    limit: int = Field(default=30, ge=1, le=100)


class ScheduleConflict(BaseModel):
    course_name: str
    day_of_week: Weekday
    course_start_time: str
    course_end_time: str
    program_start_at: str
    program_end_at: str


class ProgramRecommendation(BaseModel):
    program_id: str
    title: str
    url: str | None = None
    category: dict[str, str | None] = Field(default_factory=dict)
    schedule_kind: ScheduleKind
    availability: Availability
    confidence: Confidence
    score: float
    matched_reason: str
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[ScheduleConflict] = Field(default_factory=list)
    program: dict[str, Any] = Field(default_factory=dict)


class RecommendationResponse(BaseModel):
    recommendations: list[ProgramRecommendation]
    counts: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


def build_recommendations(
    timetable: TimetableExtractionResult | RecommendationRequest,
    programs: list[dict[str, Any]],
    *,
    include_needs_review: bool = True,
    include_unavailable: bool = False,
    limit: int = 30,
) -> RecommendationResponse:
    courses = list(timetable.courses)
    recommendations = [
        evaluate_program(program, courses)
        for program in programs
        if isinstance(program, dict)
    ]

    filtered = [
        item
        for item in recommendations
        if item.availability == "available"
        or (include_needs_review and item.availability == "needs_review")
        or (include_unavailable and item.availability == "unavailable")
    ]
    filtered.sort(key=_recommendation_sort_key)
    limited = filtered[:limit]

    return RecommendationResponse(
        recommendations=limited,
        counts={
            "available": sum(1 for item in recommendations if item.availability == "available"),
            "needs_review": sum(
                1 for item in recommendations if item.availability == "needs_review"
            ),
            "unavailable": sum(1 for item in recommendations if item.availability == "unavailable"),
            "returned": len(limited),
            "total": len(recommendations),
        },
        warnings=[],
    )


def evaluate_program(program: dict[str, Any], courses: list[CourseSlot]) -> ProgramRecommendation:
    schedule_kind = classify_schedule_kind(program)
    conflicts = find_schedule_conflicts(program, courses, schedule_kind)
    warnings: list[str] = []
    sub_category = _sub_category(program)
    if sub_category and sub_category not in HS_PORTAL_SUB_CATEGORIES:
        warnings.append("HS Portal 상세검색의 알려진 세부 분류와 일치하지 않습니다.")

    availability: Availability
    confidence: Confidence
    reason: str

    if _is_full(program):
        availability = "unavailable"
        confidence = "high"
        reason = "정원이 마감되어 추천 대상에서 제외됩니다."
        warnings.append("현재 신청 인원이 정원 이상입니다.")
    elif schedule_kind == ScheduleKind.SAME_DAY and conflicts:
        availability = "unavailable"
        confidence = "high"
        reason = "교육기간이 당일 종료 일정이며 수업 시간과 겹칩니다."
    elif schedule_kind == ScheduleKind.SAME_DAY:
        availability = _available_if_accepting(program, warnings)
        confidence = "high"
        reason = "교육기간이 당일 종료 일정이며 수업 시간과 겹치지 않습니다."
    elif schedule_kind == ScheduleKind.SHORT_PERIOD:
        availability = "needs_review"
        confidence = "medium"
        reason = "교육기간이 여러 날짜에 걸쳐 있어 회차별 실제 참석 시간 확인이 필요합니다."
        warnings.append("등록된 시작일과 종료일만으로 매일 참석 여부를 확정할 수 없습니다.")
    elif schedule_kind == ScheduleKind.LONG_PERIOD:
        availability = "needs_review"
        confidence = "medium"
        reason = (
            "교육기간이 장기 범위로 등록되어 있어 "
            "시간표만으로 가능 여부를 확정하기 어렵습니다."
        )
        warnings.append("교육기간 전체가 실제 참석 시간을 의미하지 않을 수 있습니다.")
    elif schedule_kind == ScheduleKind.NO_SCHEDULE:
        availability = "needs_review"
        confidence = "low"
        reason = "비교할 교육기간 정보가 없어 상세 확인이 필요합니다."
        warnings.append("프로그램 상세 페이지에서 실제 운영 일정을 확인해야 합니다.")
    else:
        availability = "needs_review"
        confidence = "low"
        reason = "교육기간 데이터가 올바르지 않아 상세 확인이 필요합니다."
        warnings.append("저장된 운영 일정의 시작/종료 값을 해석할 수 없습니다.")

    return ProgramRecommendation(
        program_id=str(program.get("id", "")),
        title=str(program.get("title") or ""),
        url=program.get("url"),
        category=program.get("category") or {},
        schedule_kind=schedule_kind,
        availability=availability,
        confidence=confidence,
        score=_score_program(program, schedule_kind, availability, confidence, conflicts),
        matched_reason=reason,
        warnings=warnings,
        conflicts=conflicts,
        program=program,
    )


def classify_schedule_kind(program: dict[str, Any]) -> ScheduleKind:
    schedules = program.get("schedules") or []
    if not schedules:
        return ScheduleKind.NO_SCHEDULE

    periods = [_schedule_period(schedule) for schedule in schedules]
    if any(period is None for period in periods):
        return ScheduleKind.INVALID_SCHEDULE

    valid_periods = [period for period in periods if period is not None]
    if all(period["is_same_day"] for period in valid_periods):
        return ScheduleKind.SAME_DAY
    if any(period["duration_days"] >= 7 for period in valid_periods):
        return ScheduleKind.LONG_PERIOD
    return ScheduleKind.SHORT_PERIOD


def find_schedule_conflicts(
    program: dict[str, Any],
    courses: list[CourseSlot],
    schedule_kind: ScheduleKind,
) -> list[ScheduleConflict]:
    if schedule_kind != ScheduleKind.SAME_DAY:
        return []

    conflicts: list[ScheduleConflict] = []
    for schedule in _fixed_schedule_items(program):
        start_at = _parse_datetime(schedule.get("start_at"))
        end_at = _parse_datetime(schedule.get("end_at"))
        if start_at is None or end_at is None:
            continue

        program_day = _weekday_from_datetime(start_at)
        program_start = _minutes_from_datetime(start_at)
        program_end = _minutes_from_datetime(end_at)
        for course in courses:
            if course.day_of_week != program_day:
                continue
            if not _overlaps(
                program_start,
                program_end,
                _minutes_from_hhmm(course.start_time),
                _minutes_from_hhmm(course.end_time),
            ):
                continue
            conflicts.append(
                ScheduleConflict(
                    course_name=course.course_name,
                    day_of_week=course.day_of_week,
                    course_start_time=course.start_time,
                    course_end_time=course.end_time,
                    program_start_at=schedule["start_at"],
                    program_end_at=schedule["end_at"],
                )
            )
    return conflicts


def _available_if_accepting(program: dict[str, Any], warnings: list[str]) -> Availability:
    status = program.get("status") or {}
    if status.get("accepting") is False:
        warnings.append(f"현재 상태가 '{status.get('label') or '접수 불가'}'입니다.")
        return "needs_review"
    return "available"


def _score_program(
    program: dict[str, Any],
    schedule_kind: ScheduleKind,
    availability: Availability,
    confidence: Confidence,
    conflicts: list[ScheduleConflict],
) -> float:
    availability_score = {
        "available": 100.0,
        "needs_review": 60.0,
        "unavailable": 0.0,
    }[availability]
    confidence_score = {
        "high": 15.0,
        "medium": 8.0,
        "low": 0.0,
    }[confidence]
    kind_score = {
        ScheduleKind.SAME_DAY: 18.0,
        ScheduleKind.SHORT_PERIOD: 8.0,
        ScheduleKind.LONG_PERIOD: 2.0,
        ScheduleKind.NO_SCHEDULE: 0.0,
        ScheduleKind.INVALID_SCHEDULE: 0.0,
    }[schedule_kind]
    points = program.get("points")
    point_score = min(float(points or 0), 30.0) / 3.0
    conflict_penalty = len(conflicts) * 20.0
    return max(
        0.0,
        availability_score + confidence_score + kind_score + point_score - conflict_penalty,
    )


def _recommendation_sort_key(item: ProgramRecommendation) -> tuple[int, float, str]:
    availability_order = {
        "available": 0,
        "needs_review": 1,
        "unavailable": 2,
    }[item.availability]
    return (availability_order, -item.score, item.title)


def _fixed_schedule_items(program: dict[str, Any]) -> list[dict[str, Any]]:
    fixed_items = []
    for schedule in program.get("schedules") or []:
        period = _schedule_period(schedule)
        if period and period["is_same_day"]:
            fixed_items.append(schedule)
    return fixed_items


def _is_full(program: dict[str, Any]) -> bool:
    participants = program.get("participants") or {}
    if participants.get("is_unlimited"):
        return False
    current = participants.get("current")
    capacity = participants.get("capacity")
    return isinstance(current, int) and isinstance(capacity, int) and current >= capacity


def _sub_category(program: dict[str, Any]) -> str:
    return str((program.get("category") or {}).get("sub") or "")


def _schedule_period(schedule: dict[str, Any]) -> dict[str, Any] | None:
    start_at = _parse_datetime(schedule.get("start_at"))
    end_at = _parse_datetime(schedule.get("end_at"))
    if start_at is None or end_at is None or end_at <= start_at:
        return None

    duration_seconds = (end_at - start_at).total_seconds()
    return {
        "is_same_day": start_at.date() == end_at.date(),
        "duration_days": duration_seconds / (24 * 3600),
    }


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _weekday_from_datetime(value: datetime) -> Weekday:
    return ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[value.weekday()]


def _minutes_from_datetime(value: datetime) -> int:
    return value.hour * 60 + value.minute


def _minutes_from_hhmm(value: str) -> int:
    hour, minute = value.split(":", maxsplit=1)
    return int(hour) * 60 + int(minute)


def _overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a
