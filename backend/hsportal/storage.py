import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.hsportal.constants import (
    BASE_URL,
    DATA_FILE,
    PROGRAM_DATA_SCHEMA_VERSION,
    PROGRAM_INCLUDED_STATUS_CODES,
    PROGRAM_STATUS_FILTER,
    PROGRAM_STATUS_FILTER_LABEL,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def empty_dataset() -> dict[str, Any]:
    return {
        "info": {
            "site": "hsportal",
            "schema_version": PROGRAM_DATA_SCHEMA_VERSION,
            "base_url": BASE_URL,
            "list_url": "",
            "crawled_at": None,
            "filter": {
                "status": PROGRAM_STATUS_FILTER,
                "label": PROGRAM_STATUS_FILTER_LABEL,
                "included_statuses": PROGRAM_INCLUDED_STATUS_CODES,
            },
            "counts": {
                "listed": 0,
                "saved": 0,
                "pages": 0,
            },
            "cursor": {
                "last_checked_program_id": None,
                "last_checked_url": None,
            },
            "parser_version": "hsportal_v1",
        },
        "programs": [],
    }


def load_dataset(path: Path = DATA_FILE) -> dict[str, Any]:
    if not path.exists():
        return empty_dataset()

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    base = empty_dataset()
    base["info"].update(data.get("info", {}))
    base["programs"] = data.get("programs", [])
    base["info"] = normalize_info(base["info"], len(base["programs"]))
    return base


def save_dataset(data: dict[str, Any], path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = deepcopy(data)
    normalized.setdefault("info", {})
    normalized.setdefault("programs", [])
    normalized["info"] = normalize_info(normalized["info"], len(normalized["programs"]))

    with path.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, ensure_ascii=False, indent=2)


def programs_by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(program["id"]): program
        for program in data.get("programs", [])
        if program.get("id")
    }


def normalize_info(info: dict[str, Any], saved_count: int) -> dict[str, Any]:
    normalized = empty_dataset()["info"]
    normalized.update(
        {
            key: value
            for key, value in info.items()
            if key
            not in {
                "total_count",
                "site_total_count",
                "page_total",
                "program_count",
                "status_filter",
                "status_filter_label",
                "included_status_codes",
                "refresh_after_hours",
            }
        }
    )
    if info and "schema_version" not in info:
        normalized["schema_version"] = None

    filter_info = info.get("filter", {})
    normalized["filter"] = {
        "status": filter_info.get("status", info.get("status_filter", PROGRAM_STATUS_FILTER)),
        "label": filter_info.get(
            "label",
            info.get("status_filter_label", PROGRAM_STATUS_FILTER_LABEL),
        ),
        "included_statuses": filter_info.get(
            "included_statuses",
            info.get("included_status_codes", PROGRAM_INCLUDED_STATUS_CODES),
        ),
    }

    counts = info.get("counts", {})
    normalized["counts"] = {
        "listed": counts.get("listed", info.get("site_total_count", info.get("total_count", 0))),
        "saved": saved_count,
        "pages": counts.get("pages", info.get("page_total", 0)),
    }
    return normalized
