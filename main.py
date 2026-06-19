import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from backend.api.heartbeat import router as heartbeat_router
from backend.api.hsportal import router as hsportal_router
from backend.api.recommendations import router as recommendations_router
from backend.api.timetable import router as timetable_router
from backend.config import get_backend_settings
from backend.hsportal.crawler import CrawlCancelled, HsportalCrawler
from util.logging_config import configure_logging

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_PUBLIC_DIR = BASE_DIR / "frontend" / "public"
logger = logging.getLogger(__name__)


def local_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def local_future_iso(seconds: float) -> str:
    return (
        datetime.now(timezone.utc).astimezone() + timedelta(seconds=seconds)
    ).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_backend_settings()
    app.state.hsportal_crawl_status = {
        "status": "scheduled",
        "message": "HS Portal program data crawl is scheduled.",
        "interval_hours": settings.hsportal_crawl_interval_hours,
    }
    app.state.hsportal_crawler = None
    app.state.hsportal_crawl_stop_event = asyncio.Event()
    app.state.hsportal_crawl_task = asyncio.create_task(
        run_hsportal_crawl_loop(app, settings.hsportal_crawl_interval_hours)
    )
    logger.info(
        "HS Portal program data crawl loop scheduled in background. interval_hours=%s",
        settings.hsportal_crawl_interval_hours,
    )

    yield

    stop_event: asyncio.Event | None = getattr(app.state, "hsportal_crawl_stop_event", None)
    if stop_event:
        stop_event.set()

    crawler: HsportalCrawler | None = getattr(app.state, "hsportal_crawler", None)
    if crawler:
        crawler.stop()
        logger.info("Requested HS Portal crawler shutdown.")

    crawl_task: asyncio.Task | None = getattr(app.state, "hsportal_crawl_task", None)
    if crawl_task and not crawl_task.done():
        try:
            await asyncio.wait_for(asyncio.shield(crawl_task), timeout=5)
        except asyncio.TimeoutError:
            crawl_task.cancel()
            with suppress(asyncio.CancelledError):
                await crawl_task
            logger.info("Cancelled pending HS Portal program data preparation task.")


async def run_hsportal_crawl_loop(app: FastAPI, interval_hours: float) -> None:
    interval_seconds = interval_hours * 60 * 60
    stop_event: asyncio.Event = app.state.hsportal_crawl_stop_event
    logger.info("[HS Portal] Scheduled crawl loop started.")

    try:
        while not stop_event.is_set():
            crawler = HsportalCrawler()
            app.state.hsportal_crawler = crawler
            await prepare_hsportal_program_data(
                app,
                crawler,
                interval_hours=interval_hours,
            )

            if stop_event.is_set() or crawler.stop_event.is_set():
                break

            next_run_at = local_future_iso(interval_seconds)
            app.state.hsportal_crawl_status = {
                **app.state.hsportal_crawl_status,
                "next_run_at": next_run_at,
                "interval_hours": interval_hours,
            }
            logger.info(
                "[HS Portal] Next scheduled crawl will run at %s. interval_hours=%s",
                next_run_at,
                interval_hours,
            )

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue
    finally:
        app.state.hsportal_crawler = None
        logger.info("[HS Portal] Scheduled crawl loop stopped.")


async def prepare_hsportal_program_data(
    app: FastAPI,
    crawler: HsportalCrawler,
    *,
    interval_hours: float | None = None,
) -> None:
    started_at = local_now_iso()
    app.state.hsportal_crawl_status = {
        "status": "running",
        "message": "HS Portal program data crawl is running in background.",
        "last_started_at": started_at,
        "interval_hours": interval_hours,
    }
    try:
        logger.info("Preparing HS Portal program data in background.")
        await asyncio.to_thread(crawler.ensure_program_data)
    except asyncio.CancelledError:
        app.state.hsportal_crawl_status = {
            "status": "cancelled",
            "message": "HS Portal program data crawl was cancelled.",
            "last_started_at": started_at,
            "last_finished_at": local_now_iso(),
            "interval_hours": interval_hours,
        }
        raise
    except CrawlCancelled:
        app.state.hsportal_crawl_status = {
            "status": "cancelled",
            "message": "HS Portal program data crawl was cancelled.",
            "last_started_at": started_at,
            "last_finished_at": local_now_iso(),
            "interval_hours": interval_hours,
        }
        logger.info("HS Portal program data crawl was cancelled.")
    except Exception:
        if crawler.stop_event.is_set():
            app.state.hsportal_crawl_status = {
                "status": "cancelled",
                "message": "HS Portal program data crawl was cancelled.",
                "last_started_at": started_at,
                "last_finished_at": local_now_iso(),
                "interval_hours": interval_hours,
            }
            logger.info("HS Portal program data crawl stopped during shutdown.")
            return
        app.state.hsportal_crawl_status = {
            "status": "failed",
            "message": "Failed to prepare HS Portal program data.",
            "last_started_at": started_at,
            "last_finished_at": local_now_iso(),
            "interval_hours": interval_hours,
        }
        logger.exception("Failed to prepare HS Portal program data.")
    else:
        app.state.hsportal_crawl_status = {
            "status": "ready",
            "message": "HS Portal program data is ready.",
            "last_started_at": started_at,
            "last_finished_at": local_now_iso(),
            "interval_hours": interval_hours,
        }
        logger.info("HS Portal program data is ready.")
    finally:
        crawler.close()


def create_app() -> FastAPI:
    settings = get_backend_settings()
    configure_logging(settings.log_level)
    logger.info(
        "Starting %s in %s environment.",
        settings.app_name,
        settings.app_env,
    )
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.include_router(heartbeat_router, prefix="/api")
    app.include_router(hsportal_router, prefix="/api")
    app.include_router(recommendations_router, prefix="/api")
    app.include_router(timetable_router, prefix="/api")

    @app.middleware("http")
    async def log_http_requests(request: Request, call_next):
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (perf_counter() - started_at) * 1000
            logger.exception(
                "%s %s -> failed %.1fms",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (perf_counter() - started_at) * 1000
        logger.info(
            "%s %s -> %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # Root entrypoint composes backend API and frontend static files.
    app.mount("/", StaticFiles(directory=FRONTEND_PUBLIC_DIR, html=True), name="frontend")
    return app


app = create_app()
