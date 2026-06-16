from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.heartbeat import router as heartbeat_router
from backend.config import FRONTEND_PUBLIC_DIR, get_backend_settings


def create_app() -> FastAPI:
    settings = get_backend_settings()
    app = FastAPI(title=settings.app_name)

    app.include_router(heartbeat_router, prefix="/api")

    # Static frontend files live in frontend/public according to the project split.
    # Keep this mount last so /api routes are matched before static files.
    app.mount("/", StaticFiles(directory=FRONTEND_PUBLIC_DIR, html=True), name="frontend")
    return app


app = create_app()

