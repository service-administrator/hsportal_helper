from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.hsportal.storage import load_dataset

router = APIRouter(prefix="/hsportal", tags=["hsportal"])


@router.get("/programs")
def list_programs() -> dict[str, Any]:
    return load_dataset()


@router.get("/info")
def get_hsportal_info() -> dict[str, Any]:
    return load_dataset()["info"]


@router.get("/crawl-status")
def get_crawl_status(request: Request) -> dict[str, Any]:
    return getattr(
        request.app.state,
        "hsportal_crawl_status",
        {
            "status": "unknown",
            "message": "HS Portal crawl status is not available.",
        },
    )


@router.get("/programs/{program_id}")
def get_program(program_id: str) -> dict[str, Any]:
    for program in load_dataset()["programs"]:
        if str(program.get("id")) == program_id:
            return program
    raise HTTPException(status_code=404, detail="Program not found.")
