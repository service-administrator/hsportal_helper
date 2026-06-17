from typing import Any

from fastapi import APIRouter

from backend.hsportal.storage import load_dataset
from backend.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
    build_recommendations,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
def recommend_programs(request: RecommendationRequest) -> RecommendationResponse:
    dataset: dict[str, Any] = load_dataset()
    return build_recommendations(
        request,
        dataset.get("programs", []),
        include_needs_review=request.include_needs_review,
        include_unavailable=request.include_unavailable,
        limit=request.limit,
    )
