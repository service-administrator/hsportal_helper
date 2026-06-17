from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm.schemas import CourseSlot, TimetableExtractionResult, Weekday


class ScheduleKind(str, Enum):
    FIXED_SESSION = "fixed_session"
    MULTI_SESSION = "multi_session"
    SELECTABLE_SESSION = "selectable_session"
    FLEXIBLE = "flexible"
    ASYNC_ONLINE = "async_online"
    SUBMISSION = "submission"
    LONG_TERM = "long_term"
    UNCERTAIN = "uncertain"


Availability = Literal["available", "needs_review", "unavailable"]
Confidence = Literal["high", "medium", "low"]


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

    availability: Availability
    confidence: Confidence
    reason: str

    if _is_full(program):
        availability = "unavailable"
        confidence = "high"
        reason = "정원이 마감되어 추천 대상에서 제외됩니다."
        warnings.append("현재 신청 인원이 정원 이상입니다.")
    elif conflicts and schedule_kind in {
        ScheduleKind.FIXED_SESSION,
        ScheduleKind.MULTI_SESSION,
    }:
        availability = "unavailable"
        confidence = "high"
        reason = "운영 시간이 수업 시간과 겹칩니다."
    elif schedule_kind == ScheduleKind.SELECTABLE_SESSION and conflicts:
        fixed_count = len(_fixed_schedule_items(program))
        if fixed_count and len(conflicts) >= fixed_count:
            availability = "unavailable"
            confidence = "medium"
            reason = "확인 가능한 모든 선택 일정이 수업 시간과 겹칩니다."
        else:
            availability = _available_if_accepting(program, warnings)
            confidence = "medium"
            reason = "일부 선택 일정은 수업 시간과 겹치지 않을 수 있습니다."
            warnings.append("분반 또는 주제별 세부 일정을 확인해야 합니다.")
    elif schedule_kind in {ScheduleKind.FIXED_SESSION, ScheduleKind.MULTI_SESSION}:
        availability = _available_if_accepting(program, warnings)
        confidence = "high"
        reason = "운영 시간이 수업 시간과 겹치지 않습니다."
    elif schedule_kind == ScheduleKind.ASYNC_ONLINE:
        availability = _available_if_accepting(program, warnings)
        confidence = "high"
        reason = "온라인 비동기형으로 시간표와 직접 충돌하지 않습니다."
    elif schedule_kind == ScheduleKind.SUBMISSION:
        availability = _available_if_accepting(program, warnings)
        confidence = "high"
        reason = "제출형 프로그램으로 수업 시간과 직접 충돌하지 않습니다."
    elif schedule_kind == ScheduleKind.FLEXIBLE:
        availability = "needs_review"
        confidence = "medium"
        reason = "상담 또는 멘토링형 프로그램으로 개별 일정 조율이 필요합니다."
        warnings.append("신청 후 실제 상담 가능 시간을 확인해야 합니다.")
    elif schedule_kind == ScheduleKind.LONG_TERM:
        availability = "needs_review"
        confidence = "medium"
        reason = "장기 참여형 프로그램이라 시간표만으로 가능 여부를 확정하기 어렵습니다."
        warnings.append("운영기간 전체가 실제 참석 시간을 의미하지 않을 수 있습니다.")
    else:
        availability = "needs_review"
        confidence = "low"
        reason = "일정 정보가 불명확해 상세 확인이 필요합니다."
        warnings.append("저장된 운영 일정만으로 실제 참석 시간을 확정할 수 없습니다.")

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
    category = program.get("category") or {}
    sub_category = str(category.get("sub") or "")
    text = _program_text(program)

    if _looks_like_submission(sub_category, text):
        return ScheduleKind.SUBMISSION
    if _looks_like_async_online(program, text):
        return ScheduleKind.ASYNC_ONLINE
    if _looks_like_flexible(sub_category, text):
        return ScheduleKind.FLEXIBLE
    if _looks_like_long_term(sub_category, text):
        return ScheduleKind.LONG_TERM

    fixed_items = _fixed_schedule_items(program)
    schedules = program.get("schedules") or []
    if fixed_items and len(fixed_items) == len(schedules):
        if _looks_like_selectable(program, text):
            return ScheduleKind.SELECTABLE_SESSION
        if len(fixed_items) > 1:
            return ScheduleKind.MULTI_SESSION
        return ScheduleKind.FIXED_SESSION

    if _looks_like_selectable(program, text):
        return ScheduleKind.SELECTABLE_SESSION
    if _has_long_range_schedule(program):
        return ScheduleKind.LONG_TERM
    return ScheduleKind.UNCERTAIN


def find_schedule_conflicts(
    program: dict[str, Any],
    courses: list[CourseSlot],
    schedule_kind: ScheduleKind,
) -> list[ScheduleConflict]:
    if schedule_kind not in {
        ScheduleKind.FIXED_SESSION,
        ScheduleKind.MULTI_SESSION,
        ScheduleKind.SELECTABLE_SESSION,
    }:
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
        ScheduleKind.FIXED_SESSION: 18.0,
        ScheduleKind.MULTI_SESSION: 14.0,
        ScheduleKind.SELECTABLE_SESSION: 10.0,
        ScheduleKind.ASYNC_ONLINE: 12.0,
        ScheduleKind.SUBMISSION: 12.0,
        ScheduleKind.FLEXIBLE: 6.0,
        ScheduleKind.LONG_TERM: 2.0,
        ScheduleKind.UNCERTAIN: 0.0,
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
        start_at = _parse_datetime(schedule.get("start_at"))
        end_at = _parse_datetime(schedule.get("end_at"))
        if start_at is None or end_at is None:
            continue
        duration_seconds = (end_at - start_at).total_seconds()
        if start_at.date() == end_at.date() and 0 < duration_seconds <= 12 * 3600:
            fixed_items.append(schedule)
    return fixed_items


def _has_long_range_schedule(program: dict[str, Any]) -> bool:
    for schedule in program.get("schedules") or []:
        start_at = _parse_datetime(schedule.get("start_at"))
        end_at = _parse_datetime(schedule.get("end_at"))
        if start_at is None or end_at is None:
            continue
        if (end_at - start_at).total_seconds() >= 24 * 3600:
            return True
    return False


def _looks_like_submission(sub_category: str, text: str) -> bool:
    return sub_category == "공모전·대회" or any(
        keyword in text
        for keyword in (
            "공모전",
            "경진대회",
            "제출",
            "과제물",
            "신청서 제출",
        )
    )


def _looks_like_async_online(program: dict[str, Any], text: str) -> bool:
    locations = " ".join(
        str(schedule.get("location") or "") for schedule in program.get("schedules") or []
    )
    contact_location = str((program.get("contact") or {}).get("location") or "")
    place_text = f"{locations} {contact_location}"
    return "온라인" in place_text and any(
        keyword in text
        for keyword in (
            "e-class",
            "동영상",
            "온라인 교육",
            "온라인 폭력예방교육",
            "비대면",
            "상시",
        )
    )


def _looks_like_flexible(sub_category: str, text: str) -> bool:
    if sub_category != "상담·검사":
        return False
    return any(
        keyword in text
        for keyword in (
            "1:1",
            "개별",
            "조율",
            "희망 일시",
            "원하는 시간",
            "날짜/시간 선택",
            "상담신청",
        )
    ) or "상담" in text


def _looks_like_long_term(sub_category: str, text: str) -> bool:
    if sub_category in {"봉사", "현장체험활동"} and any(
        keyword in text
        for keyword in (
            "현장실습",
            "봉사단",
            "언론사",
            "장기",
            "매주",
            "매일",
            "학기",
            "프로젝트",
        )
    ):
        return True
    return False


def _looks_like_selectable(program: dict[str, Any], text: str) -> bool:
    program_type = str(program.get("type") or "")
    return program_type == "주제별 상이" or any(
        keyword in text
        for keyword in (
            "분반",
            "주제별",
            "중복 선택",
            "선택 가능",
            "택1",
            "희망 주제",
        )
    )


def _is_full(program: dict[str, Any]) -> bool:
    participants = program.get("participants") or {}
    if participants.get("is_unlimited"):
        return False
    current = participants.get("current")
    capacity = participants.get("capacity")
    return isinstance(current, int) and isinstance(capacity, int) and current >= capacity


def _program_text(program: dict[str, Any]) -> str:
    content = program.get("content") or {}
    tags = " ".join(str(tag) for tag in program.get("tags") or [])
    return " ".join(
        str(value or "")
        for value in (
            program.get("title"),
            (program.get("category") or {}).get("main"),
            (program.get("category") or {}).get("sub"),
            tags,
            content.get("summary"),
            content.get("description_text"),
        )
    )


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
