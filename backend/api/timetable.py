import asyncio
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.config import is_dev_environment
from llm.exceptions import (
    ImagePayloadError,
    LLMConfigurationError,
    LLMRequestError,
    LLMResponseParseError,
    LLMResponseValidationError,
)
from llm.schemas import TimetableExtractionResult
from llm.tasks.timetable import extract_timetable_from_image_bytes

router = APIRouter(prefix="/timetable", tags=["timetable"])


@router.post("/extract", response_model=TimetableExtractionResult)
async def extract_timetable(
    file: Annotated[UploadFile, File(...)],
) -> TimetableExtractionResult:
    image_bytes = await file.read()

    try:
        return await asyncio.to_thread(
            extract_timetable_from_image_bytes,
            image_bytes,
            content_type=file.content_type,
            log_image_debug=is_dev_environment(),
        )
    except ImagePayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (LLMRequestError, LLMResponseParseError, LLMResponseValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
