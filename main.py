import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from backend.api.heartbeat import router as heartbeat_router
from backend.api.hsportal import router as hsportal_router
from backend.api.timetable import router as timetable_router
from backend.config import get_backend_settings
from backend.hsportal.crawler import CrawlCancelled, HsportalCrawler
from util.logging_config import configure_logging

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_PUBLIC_DIR = BASE_DIR / "frontend" / "public"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.hsportal_crawl_status = {
        "status": "scheduled",
        "message": "HS Portal program data crawl is scheduled.",
    }
    app.state.hsportal_crawler = HsportalCrawler()
    app.state.hsportal_crawl_task = asyncio.create_task(
        prepare_hsportal_program_data(app, app.state.hsportal_crawler)
    )
    logger.info("HS Portal program data preparation scheduled in background.")

    yield

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


async def prepare_hsportal_program_data(app: FastAPI, crawler: HsportalCrawler) -> None:
    app.state.hsportal_crawl_status = {
        "status": "running",
        "message": "HS Portal program data crawl is running in background.",
    }
    try:
        logger.info("Preparing HS Portal program data in background.")
        await asyncio.to_thread(crawler.ensure_program_data)
    except asyncio.CancelledError:
        app.state.hsportal_crawl_status = {
            "status": "cancelled",
            "message": "HS Portal program data crawl was cancelled.",
        }
        raise
    except CrawlCancelled:
        app.state.hsportal_crawl_status = {
            "status": "cancelled",
            "message": "HS Portal program data crawl was cancelled.",
        }
        logger.info("HS Portal program data crawl was cancelled.")
    except Exception:
        if crawler.stop_event.is_set():
            app.state.hsportal_crawl_status = {
                "status": "cancelled",
                "message": "HS Portal program data crawl was cancelled.",
            }
            logger.info("HS Portal program data crawl stopped during shutdown.")
            return
        app.state.hsportal_crawl_status = {
            "status": "failed",
            "message": "Failed to prepare HS Portal program data.",
        }
        logger.exception("Failed to prepare HS Portal program data.")
    else:
        app.state.hsportal_crawl_status = {
            "status": "ready",
            "message": "HS Portal program data is ready.",
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
