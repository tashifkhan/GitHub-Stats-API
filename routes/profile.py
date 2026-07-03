import asyncio

from fastapi import APIRouter, Depends, Path

from models.canonical import make_envelope
from routes.dependencies import get_analytics_service
from services import canonical_mapper
from services.analytics_service import AnalyticsService


router = APIRouter(tags=["Canonical"])


@router.get("/{username}/profile", summary="Canonical profile")
async def get_profile(
    username: str = Path(..., description="GitHub username"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    user, social_accounts = await asyncio.gather(
        analytics_service.get_user_profile(username),
        analytics_service.get_user_social_accounts(username),
    )
    return make_envelope(
        username, canonical_mapper.profile_from(user, username, social_accounts)
    )
