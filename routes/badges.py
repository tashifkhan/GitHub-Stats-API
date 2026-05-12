from fastapi import APIRouter, Depends, Path

from models.canonical import make_envelope
from routes.dependencies import get_analytics_service
from services import canonical_mapper
from services.analytics_service import AnalyticsService


router = APIRouter(tags=["Canonical"])


@router.get("/{username}/badges", summary="Canonical badges (GitHub profile achievements)")
async def get_badges(
    username: str = Path(..., description="GitHub username"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    achievements = await analytics_service.get_user_achievements(username)
    return make_envelope(username, canonical_mapper.badges_from(achievements))
