import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from backend.hsportal.constants import BASE_URL

STATUS_LABELS = {
    "OPEN": "접수중",
    "APPROACHING": "접수중",
    "APPROACH_CLOSING": "접수중",
    "SCHEDULED": "접수예정",
    "WAIT": "접수대기",
    "OPERATION": "운영중",
    "COMPLETED": "마감",
}

STATUS_CODES = {
    "OPEN": "open",
    "APPROACHING": "open",
    "APPROACH_CLOSING": "open",
    "SCHEDULED": "scheduled",
    "WAIT": "waiting",
    "OPERATION": "operation",
    "COMPLETED": "completed",
}


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def select_text(node: Tag | BeautifulSoup, selector: str) -> str:
    selected = node.select_one(selector)
    return clean_text(selected.get_text(" ", strip=True)) if selected else ""


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def absolute_url(value: str | None) -> str | None:
    if not value:
        return None
    return urljoin(BASE_URL, value)


def int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d[\d,]*", value)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    if not match:
        return None
    return float(match.group(0))


def parse_time_pair(container: Tag | None) -> tuple[str | None, str | None]:
    if not container:
        return None, None
    times = [time.get("datetime") for time in container.select("time[datetime]")]
    if len(times) < 2:
        return None, None
    return times[0], times[1]


def parse_total_count(soup: BeautifulSoup) -> int:
    sortbar = soup.select_one("div[data-role='sortbar'] label")
    return int_or_none(sortbar.get_text(" ", strip=True) if sortbar else None) or 0


def parse_page_total(soup: BeautifulSoup) -> int:
    pagination = soup.select_one("div[data-role='pagination'][data-total]")
    return int_or_none(pagination.get("data-total") if pagination else None) or 1


def parse_list_page(html: str) -> dict[str, Any]:
    soup = parse_html(html)
    return {
        "total_count": parse_total_count(soup),
        "page_total": parse_page_total(soup),
        "programs": [parse_list_item(item) for item in soup.select("div[data-role='item']")],
    }


def parse_list_item(item: Tag) -> dict[str, Any]:
    link = item.select_one("a[data-idx]")
    program_id = link.get("data-idx") if link else ""
    href = absolute_url(link.get("href") if link else None)
    status_class = next((class_name for class_name in item.get("class", []) if class_name), None)
    status_badge = select_text(item, "label b")
    title = select_text(item, ".content b.title")
    institution = select_text(item, "span.institution")
    department = select_text(item, "span.department")
    application_start_at, application_end_at = parse_period_by_label(item, "신청:")
    operation_start_at, operation_end_at = parse_period_by_label(item, "운영:")
    hit_text = select_text(item, "span.hit")

    return {
        "id": str(program_id),
        "url": f"{href}/description" if href and not href.endswith("/description") else href,
        "title": title,
        "status": parse_status(status_class, status_badge),
        "points": parse_points(item),
        "type": select_text(item, "span.type") or None,
        "application_period": {
            "start_at": application_start_at,
            "end_at": application_end_at,
        },
        "schedules": [
            {
                "start_at": operation_start_at,
                "end_at": operation_end_at,
                "location": None,
            }
        ]
        if operation_start_at and operation_end_at
        else [],
        "organization": {
            "name": institution,
            "department": department,
        },
        "participants": parse_participants(item.get_text(" ", strip=True)),
        "media": {
            "cover_image_url": parse_cover_image(item),
            "content_images": [],
        },
        "metrics": {
            "hits": int_or_none(hit_text),
        },
        "flags": {
            "is_talent_certified": item.select_one("span.certified") is not None,
            "is_recommended": item.select_one("label.recommend") is not None,
            "is_excellent": item.select_one("label.excellent") is not None,
        },
    }


def parse_points(item: Tag) -> int | None:
    point_icon = item.select_one("i.point")
    if not point_icon or not point_icon.parent:
        return None
    return int_or_none(point_icon.parent.get_text(" ", strip=True))


def parse_status(status_class: str | None, badge: str) -> dict[str, Any]:
    raw_code = status_class or ""
    normalized_code = STATUS_CODES.get(raw_code, raw_code.lower())
    label = STATUS_LABELS.get(raw_code, raw_code)
    display_badge = badge if badge and badge not in {label, "예정"} else None
    return {
        "code": normalized_code,
        "label": label,
        "badge": display_badge,
        "accepting": normalized_code in {"open", "waiting"},
    }


def parse_cover_image(item: Tag) -> str | None:
    cover = item.select_one(".cover")
    style = cover.get("style", "") if cover else ""
    match = re.search(r"url\((.*?)\)", style)
    if not match:
        return None
    return absolute_url(match.group(1).strip("\"'"))


def parse_period_by_label(item: Tag, label: str) -> tuple[str | None, str | None]:
    for layer in item.select("small.date_layer"):
        if label in layer.get_text(" ", strip=True):
            return parse_time_pair(layer)
    return None, None


def parse_participants(text: str) -> dict[str, Any]:
    compact = clean_text(text)
    current = capacity = max_apply = None
    is_unlimited = "무제한" in compact

    match = re.search(r"(\d[\d,]*)\s*명?\s*/\s*(무제한|\d[\d,]*)", compact)
    if match:
        current = int(match.group(1).replace(",", ""))
        if match.group(2) != "무제한":
            capacity = int(match.group(2).replace(",", ""))

    max_match = re.search(r"최대\s*(\d[\d,]*)\s*명", compact)
    if max_match:
        max_apply = int(max_match.group(1).replace(",", ""))

    return {
        "current": current,
        "capacity": capacity,
        "max_apply": max_apply,
        "is_unlimited": is_unlimited,
    }


def parse_detail_page(html: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    soup = parse_html(html)
    view = soup.select_one("[data-role='itemview']")
    fallback = fallback or {}
    program_id = str(view.get("data-pidx")) if view else str(fallback.get("id", ""))
    title = select_text(soup, "#ModuleEcoProgramView h4") or fallback.get("title", "")
    detail = {
        **fallback,
        "id": program_id,
        "url": f"{BASE_URL}/ko/program/all/view/{program_id}/description",
        "title": title,
    }

    header = parse_detail_header(soup)
    if header.get("points") is None and fallback.get("points") is not None:
        header.pop("points")
    detail.update(header)
    detail["schedules"] = parse_detail_schedules(soup, detail.get("contact", {}).get("location"))
    if not detail["schedules"]:
        detail["schedules"] = fallback.get("schedules", [])
    detail["content"] = parse_content(soup)
    fallback_cover = fallback.get("media", {}).get("cover_image_url")
    detail["media"] = {
        "cover_image_url": parse_cover_image(soup) or fallback_cover,
        "content_images": parse_content_images(soup),
    }
    detail["attachments"] = parse_attachments(soup)
    return detail


def parse_detail_header(soup: BeautifulSoup) -> dict[str, Any]:
    tags = [
        clean_text(tag.get_text(" ", strip=True)).lstrip("#")
        for tag in soup.select("li.tag a")
    ]
    header: dict[str, Any] = {
        "tags": tags,
        "target": {
            "audiences": split_values(find_info_value(soup, "모집대상")),
            "grades": [],
            "gender": None,
            "departments": split_values(find_info_value(soup, "학과")),
        },
        "category": parse_category(soup),
        "organization": parse_organization(soup),
        "contact": parse_contact(soup),
    }
    grades_gender = find_info_value(soup, "학년/성별")
    if grades_gender:
        parts = [clean_text(part) for part in grades_gender.split("/") if clean_text(part)]
        header["target"]["grades"] = split_values(parts[0]) if parts else []
        header["target"]["gender"] = parts[1] if len(parts) > 1 else None

    time_label = soup.select_one("#ModuleEcoProgramView label.time")
    time_text = time_label.get_text(" ", strip=True) if time_label else ""
    header["duration_hours"] = float_or_none(time_text)
    header["session_count"] = int_or_none(time_text.split("/")[-1] if "/" in time_text else None)
    header["points"] = int_or_none(select_text(soup, "#ModuleEcoProgramView label.point"))
    header["type"] = select_text(soup, "#ModuleEcoProgramView label.type") or None
    hit_text = select_text(soup, "#ModuleEcoProgramView label.hit")
    header["metrics"] = {
        "hits": int_or_none(hit_text),
    }
    return header


def find_info_value(soup: BeautifulSoup, label_text: str) -> str:
    for label in soup.select("#ModuleEcoProgramView .title li label"):
        if label_text in label.get_text(" ", strip=True):
            parent = label.find_parent("li")
            span = parent.select_one("span") if parent else None
            return clean_text(span.get_text(" ", strip=True)) if span else ""
    return ""


def split_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [clean_text(part) for part in re.split(r"[,/]", value) if clean_text(part)]


def parse_category(soup: BeautifulSoup) -> dict[str, str | None]:
    category = soup.select_one("#ModuleEcoProgramView .info .category")
    values = [clean_text(value) for value in category.stripped_strings] if category else []
    return {
        "main": values[0] if values else None,
        "sub": values[1] if len(values) > 1 else None,
    }


def parse_organization(soup: BeautifulSoup) -> dict[str, str | None]:
    link = soup.select_one("#ModuleEcoProgramView .info .department a")
    if not link:
        return {"name": None, "department": None}
    sub = link.select_one(".sub")
    department = clean_text(sub.get_text(" ", strip=True)) if sub else None
    if sub:
        sub.extract()
    return {
        "name": clean_text(link.get_text(" ", strip=True)),
        "department": department,
    }


def parse_contact(soup: BeautifulSoup) -> dict[str, str | None]:
    contact = {"email": None, "phone": None, "location": None}
    for row in soup.select("#ModuleEcoProgramView .info li div"):
        text = clean_text(row.get_text(" ", strip=True))
        if row.select_one(".fa-envelope"):
            contact["email"] = text
        elif row.select_one(".fa-phone"):
            contact["phone"] = text
        elif row.select_one(".fa-map-marker"):
            contact["location"] = text
    return contact


def parse_detail_schedules(soup: BeautifulSoup, location: str | None) -> list[dict[str, Any]]:
    schedules = []
    for row in soup.select("#ModuleEcoProgramTopicForm li.tbody"):
        title_area = row.select_one("span.title")
        start_at, end_at = parse_time_pair(title_area)
        if not start_at or not end_at:
            continue
        schedules.append(
            {
                "start_at": start_at,
                "end_at": end_at,
                "location": location,
            }
        )
    return schedules


def parse_content(soup: BeautifulSoup) -> dict[str, str | None]:
    content = soup.select_one("div.description [data-role='wysiwyg-content']")
    text = clean_text(content.get_text(" ", strip=True)) if content else ""
    return {
        "summary": text[:160] if text else None,
        "description_text": text,
    }


def parse_content_images(soup: BeautifulSoup) -> list[str]:
    images = []
    for image in soup.select("div.description [data-role='wysiwyg-content'] img[src]"):
        url = absolute_url(image.get("src"))
        if url:
            images.append(url)
    return images


def parse_attachments(soup: BeautifulSoup) -> list[dict[str, str | None]]:
    attachments = []
    for link in soup.select("div[data-module='attachment'] a[href]"):
        size = link.select_one(".size")
        size_text = clean_text(size.get_text(" ", strip=True)) if size else None
        if size:
            size.extract()
        file_name = clean_text(link.get_text(" ", strip=True))
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else None
        attachments.append(
            {
                "file_name": file_name,
                "url": absolute_url(link.get("href")),
                "extension": extension,
                "size_text": size_text,
            }
        )
    return attachments


def merge_list_update(existing: dict[str, Any], listing: dict[str, Any]) -> dict[str, Any]:
    updated = {**existing}
    for key in (
        "status",
        "points",
        "type",
        "application_period",
        "participants",
        "media",
        "metrics",
        "flags",
    ):
        if listing.get(key) not in (None, "", [], {}):
            updated[key] = listing[key]
    if listing.get("organization"):
        updated["organization"] = {
            **updated.get("organization", {}),
            **{key: value for key, value in listing["organization"].items() if value},
        }
    if listing.get("schedules"):
        # List pages are used only for low-cost freshness fields. Preserve detailed
        # schedules when they already exist because they may include per-session data.
        updated.setdefault("schedules", listing["schedules"])
    return updated
