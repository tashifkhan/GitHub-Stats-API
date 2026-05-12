from fastapi import APIRouter, Depends, Path

from models.canonical import make_envelope
from routes.dependencies import get_analytics_service
from services import canonical_mapper
from services.analytics_service import AnalyticsService


router = APIRouter(tags=["Canonical"])


@router.get("/{username}", summary="Canonical summary")
async def get_summary(
    username: str = Path(..., description="GitHub username"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    card = await canonical_mapper.build_card(username, analytics_service)
    return make_envelope(username, canonical_mapper.summary_from(card))
