import re
from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Weekday = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

WEEKDAY_ALIASES = {
    "MON": "MON",
    "MONDAY": "MON",
    "월": "MON",
    "월요일": "MON",
    "TUE": "TUE",
    "TUESDAY": "TUE",
    "화": "TUE",
    "화요일": "TUE",
    "WED": "WED",
    "WEDNESDAY": "WED",
    "수": "WED",
    "수요일": "WED",
    "THU": "THU",
    "THURSDAY": "THU",
    "목": "THU",
    "목요일": "THU",
    "FRI": "FRI",
    "FRIDAY": "FRI",
    "금": "FRI",
    "금요일": "FRI",
    "SAT": "SAT",
    "SATURDAY": "SAT",
    "토": "SAT",
    "토요일": "SAT",
    "SUN": "SUN",
    "SUNDAY": "SUN",
    "일": "SUN",
    "일요일": "SUN",
}


class CourseSlot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    course_name: str = Field(min_length=1)
    day_of_week: Weekday
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("day_of_week", mode="before")
    @classmethod
    def normalize_weekday(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        return WEEKDAY_ALIASES.get(normalized, WEEKDAY_ALIASES.get(value.strip(), value))

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def normalize_time(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        text = value.strip()
        colon_match = re.fullmatch(r"(\d{1,2}):(\d{1,2})(?::\d{1,2})?", text)
        if colon_match:
            hour, minute = colon_match.groups()
            return f"{int(hour):02d}:{int(minute):02d}"

        korean_match = re.fullmatch(r"(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분?)?", text)
        if korean_match:
            hour, minute = korean_match.groups()
            return f"{int(hour):02d}:{int(minute or 0):02d}"

        return text

    @model_validator(mode="after")
    def validate_time_order(self) -> "CourseSlot":
        if _parse_hhmm(self.start_time) >= _parse_hhmm(self.end_time):
            raise ValueError("end_time must be later than start_time.")
        return self


class TimetableExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    courses: list[CourseSlot] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _parse_hhmm(value: str) -> time:
    hour_text, minute_text = value.split(":", maxsplit=1)
    return time(hour=int(hour_text), minute=int(minute_text))
