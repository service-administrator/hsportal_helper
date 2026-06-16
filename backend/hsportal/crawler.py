from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

from backend.hsportal.constants import (
    ALL_PROGRAMS_LIST_URL,
    BASE_URL,
    PROGRAM_DATA_SCHEMA_VERSION,
    PROGRAM_INCLUDED_STATUS_CODES,
    PROGRAM_STATUS_FILTER,
    PROGRAM_STATUS_FILTER_LABEL,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)
from backend.hsportal.parser import merge_list_update, parse_detail_page, parse_list_page
from backend.hsportal.storage import (
    empty_dataset,
    load_dataset,
    now_iso,
    programs_by_id,
    save_dataset,
)

logger = logging.getLogger(__name__)


class CrawlCancelled(Exception):
    """Raised when the application asks the crawler to stop."""


class HsportalCrawler:
    def __init__(self, stop_event: threading.Event | None = None) -> None:
        self.stop_event = stop_event or threading.Event()
        self.client = httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def stop(self) -> None:
        self.stop_event.set()
        self.close()

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            logger.debug("HS Portal crawler client was already closed.", exc_info=True)

    def __enter__(self) -> HsportalCrawler:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ensure_program_data(
        self,
        *,
        force: bool = False,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        dataset = load_dataset()
        if not dataset.get("programs"):
            logger.info("No saved HS Portal data found. Starting full crawl.")
            return self.crawl_full(max_pages=max_pages)
        if self.should_recrawl_for_policy(dataset):
            logger.info("Saved HS Portal data does not match current crawl policy.")
            return self.crawl_full(max_pages=max_pages)
        if force:
            logger.info("Force refresh was requested. Starting incremental crawl.")
            return self.crawl_incremental(dataset, max_pages=max_pages)

        first_page = self.fetch_list_page(1)
        return self.crawl_if_cursor_changed(dataset, first_page=first_page, max_pages=max_pages)

    def should_recrawl_for_policy(self, dataset: dict[str, Any]) -> bool:
        info = dataset.get("info", {})
        return (
            info.get("schema_version") != PROGRAM_DATA_SCHEMA_VERSION
            or info.get("filter", {}).get("status") != PROGRAM_STATUS_FILTER
        )

    def crawl_if_cursor_changed(
        self,
        dataset: dict[str, Any],
        *,
        first_page: dict[str, Any],
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        cursor_id = str(
            dataset.get("info", {})
            .get("cursor", {})
            .get("last_checked_program_id")
            or ""
        )
        latest = first_page["programs"][0] if first_page["programs"] else None
        latest_id = str(latest["id"]) if latest else ""

        if latest_id and latest_id != cursor_id:
            logger.info(
                "HS Portal cursor changed. latest=%s saved_cursor=%s",
                latest_id,
                cursor_id or "empty",
            )
            return self.crawl_incremental(
                dataset,
                max_pages=max_pages,
                first_page=first_page,
            )

        logger.info(
            "HS Portal cursor is unchanged. Refreshing first-page list fields only. cursor=%s",
            cursor_id or "empty",
        )
        return self.refresh_from_listings(
            dataset,
            first_page["programs"],
            first_page["total_count"],
            first_page["page_total"],
        )

    def crawl_full(self, *, max_pages: int | None = None) -> dict[str, Any]:
        self.check_cancelled()
        dataset = empty_dataset()
        listings, site_total_count, page_total = self.fetch_all_listings(max_pages=max_pages)
        logger.info(
            "Full crawl collected %s listings from %s total site programs across %s pages.",
            len(listings),
            site_total_count,
            page_total,
        )
        programs = []
        for index, listing in enumerate(listings, start=1):
            self.check_cancelled()
            logger.info(
                "Fetching detail %s/%s: %s",
                index,
                len(listings),
                listing.get("title") or listing.get("id"),
            )
            detail = self.fetch_detail(listing)
            detail["last_seen_at"] = now_iso()
            programs.append(detail)

        self.finish_dataset(dataset, programs, site_total_count, page_total)
        save_dataset(dataset)
        logger.info("Full crawl saved %s HS Portal programs.", len(programs))
        return dataset

    def crawl_incremental(
        self,
        dataset: dict[str, Any],
        *,
        max_pages: int | None = None,
        first_page: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.check_cancelled()
        existing = programs_by_id(dataset)
        cursor = dataset.get("info", {}).get("cursor", {})
        cursor_id = str(cursor.get("last_checked_program_id") or "")
        listings, site_total_count, page_total = self.fetch_until_cursor(
            cursor_id,
            max_pages=max_pages,
            first_page=first_page,
        )
        logger.info(
            "Incremental crawl checked %s listings before cursor=%s.",
            len(listings),
            cursor_id or "empty",
        )
        leading_programs: list[dict[str, Any]] = []
        new_count = 0

        for listing in listings:
            self.check_cancelled()
            program_id = str(listing["id"])
            if program_id in existing:
                existing[program_id] = merge_list_update(existing[program_id], listing)
                existing[program_id]["last_seen_at"] = now_iso()
                leading_programs.append(existing[program_id])
                continue
            logger.info("Fetching new program detail: %s", listing.get("title") or program_id)
            detail = self.fetch_detail(listing)
            detail["last_seen_at"] = now_iso()
            leading_programs.append(detail)
            new_count += 1

        leading_ids = {str(program["id"]) for program in leading_programs}
        merged = leading_programs + [
            existing[str(program["id"])]
            for program in dataset.get("programs", [])
            if str(program.get("id")) not in leading_ids
        ]
        self.finish_dataset(dataset, merged, site_total_count, page_total)
        save_dataset(dataset)
        logger.info(
            "Incremental crawl saved %s programs. new=%s updated=%s",
            len(merged),
            new_count,
            max(len(listings) - new_count, 0),
        )
        return dataset

    def refresh_existing_from_list(self, *, max_pages: int | None = None) -> dict[str, Any]:
        self.check_cancelled()
        dataset = load_dataset()
        listings, site_total_count, page_total = self.fetch_all_listings(
            max_pages=max_pages,
            include_details=False,
        )
        return self.refresh_from_listings(dataset, listings, site_total_count, page_total)

    def refresh_from_listings(
        self,
        dataset: dict[str, Any],
        listings: list[dict[str, Any]],
        site_total_count: int,
        page_total: int,
    ) -> dict[str, Any]:
        existing = programs_by_id(dataset)
        updated_count = 0
        for listing in listings:
            program_id = str(listing["id"])
            if program_id not in existing:
                continue
            existing[program_id] = merge_list_update(existing[program_id], listing)
            existing[program_id]["last_seen_at"] = now_iso()
            updated_count += 1

        dataset["programs"] = [
            existing[str(program["id"])] for program in dataset.get("programs", [])
        ]
        self.finish_dataset(
            dataset,
            dataset["programs"],
            site_total_count,
            page_total,
            update_cursor=False,
        )
        save_dataset(dataset)
        logger.info("Refreshed %s existing HS Portal programs from list pages.", updated_count)
        return dataset

    def fetch_all_listings(
        self,
        *,
        max_pages: int | None = None,
        include_details: bool = True,
    ) -> tuple[list[dict[str, Any]], int, int]:
        first_page = self.fetch_list_page(1)
        total_count = first_page["total_count"]
        page_total = first_page["page_total"]
        limit = min(page_total, max_pages) if max_pages else page_total
        listings = list(first_page["programs"])
        if include_details:
            self.sleep()

        for page in range(2, limit + 1):
            self.check_cancelled()
            page_data = self.fetch_list_page(page)
            listings.extend(page_data["programs"])
            self.sleep()

        return listings, total_count, page_total

    def fetch_until_cursor(
        self,
        cursor_id: str,
        *,
        max_pages: int | None = None,
        first_page: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int, int]:
        first_page = first_page or self.fetch_list_page(1)
        total_count = first_page["total_count"]
        page_total = first_page["page_total"]
        limit = min(page_total, max_pages) if max_pages else page_total
        listings: list[dict[str, Any]] = []

        for page in range(1, limit + 1):
            self.check_cancelled()
            page_data = first_page if page == 1 else self.fetch_list_page(page)
            for listing in page_data["programs"]:
                if cursor_id and str(listing["id"]) == cursor_id:
                    return listings, total_count, page_total
                listings.append(listing)
            self.sleep()

        return listings, total_count, page_total

    def fetch_list_page(self, page: int) -> dict[str, Any]:
        self.check_cancelled()
        logger.info("Fetching HS Portal list page %s.", page)
        response = self.client.get(list_url(page))
        response.raise_for_status()
        self.check_cancelled()
        return parse_list_page(response.text)

    def fetch_detail(self, listing: dict[str, Any]) -> dict[str, Any]:
        self.check_cancelled()
        detail_url = (
            listing.get("url")
            or f"{BASE_URL}/ko/program/all/view/{listing['id']}/description"
        )
        response = self.client.get(detail_url)
        response.raise_for_status()
        self.check_cancelled()
        self.sleep()
        return parse_detail_page(response.text, listing)

    def finish_dataset(
        self,
        dataset: dict[str, Any],
        programs: list[dict[str, Any]],
        total_count: int,
        page_total: int,
        *,
        update_cursor: bool = True,
    ) -> None:
        newest = programs[0] if programs and update_cursor else None
        cursor = dataset.get("info", {}).get("cursor", {})
        dataset["programs"] = programs
        dataset["info"].update(
            {
                "site": "hsportal",
                "schema_version": PROGRAM_DATA_SCHEMA_VERSION,
                "base_url": BASE_URL,
                "list_url": ALL_PROGRAMS_LIST_URL,
                "crawled_at": now_iso(),
                "filter": {
                    "status": PROGRAM_STATUS_FILTER,
                    "label": PROGRAM_STATUS_FILTER_LABEL,
                    "included_statuses": PROGRAM_INCLUDED_STATUS_CODES,
                },
                "counts": {
                    "listed": total_count,
                    "saved": len(programs),
                    "pages": page_total,
                },
                "cursor": {
                    "last_checked_program_id": newest.get("id")
                    if newest
                    else cursor.get("last_checked_program_id"),
                    "last_checked_url": newest.get("url")
                    if newest
                    else cursor.get("last_checked_url"),
                },
                "parser_version": "hsportal_v1",
            }
        )

    def sleep(self) -> None:
        self.check_cancelled()
        if REQUEST_DELAY_SECONDS > 0 and self.stop_event.wait(REQUEST_DELAY_SECONDS):
            raise CrawlCancelled("HS Portal crawl was cancelled.")

    def check_cancelled(self) -> None:
        if self.stop_event.is_set():
            raise CrawlCancelled("HS Portal crawl was cancelled.")


def list_url(page: int) -> str:
    if page <= 1:
        return ALL_PROGRAMS_LIST_URL
    return (
        f"{BASE_URL}/ko/program/all/list/all/1/{page}"
        f"?status={PROGRAM_STATUS_FILTER}&sort=date"
    )
