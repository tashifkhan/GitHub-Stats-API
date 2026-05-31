"""Canonical unified endpoints shared across all stats services.

Adds the cross-platform endpoints for GitHub: ``/{username}/profile``,
``/{username}/heatmap`` (alias of ``/contributions``), ``/{username}/contests``,
``/{username}/rating``, ``/{username}/badges`` and the aggregated
``/{username}/card``. The existing ``/{username}/stats`` and
``/{username}/contributions`` routes already carry the unified envelope
additively. Contests / rating / badges are empty (GitHub is the development
category).
"""

from fastapi import APIRouter, Depends, Path

from modules.unified import UnifiedBadges, UnifiedContests, UnifiedRating, make_envelope
from routes.dependencies import get_analytics_service
from services import unified_mapper
from services.analytics_service import AnalyticsService

unified_router = APIRouter()


@unified_router.get("/{username}/profile", tags=["Unified"], summary="Unified profile")
async def unified_profile(
    username: str = Path(..., description="GitHub username"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    user = await analytics_service.get_user_profile(username)
    return make_envelope(username, unified_mapper.profile_from(user, username))


@unified_router.get("/{username}/heatmap", tags=["Unified"], summary="Unified contribution heatmap")
async def unified_heatmap(
    username: str = Path(..., description="GitHub username"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    contrib = await analytics_service.get_user_contributions(username, None)
    data = unified_mapper.heatmap_from(
        contrib.get("contributions"),
        contrib.get("longestStreak", 0),
        contrib.get("currentStreak", 0),
    )
    return make_envelope(username, data)


@unified_router.get("/{username}/contests", tags=["Unified"], summary="Unified contests (empty for GitHub)")
async def unified_contests(username: str = Path(..., description="GitHub username")):
    return make_envelope(username, UnifiedContests())


@unified_router.get("/{username}/rating", tags=["Unified"], summary="Unified rating (empty for GitHub)")
async def unified_rating(username: str = Path(..., description="GitHub username")):
    return make_envelope(username, UnifiedRating())


@unified_router.get("/{username}/badges", tags=["Unified"], summary="Unified badges (empty for GitHub)")
async def unified_badges(username: str = Path(..., description="GitHub username")):
    return make_envelope(username, UnifiedBadges())


@unified_router.get("/{username}/card", tags=["Unified"], summary="Aggregated unified profile card")
async def unified_card(
    username: str = Path(..., description="GitHub username"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    card = await unified_mapper.build_card(username, analytics_service)
    return make_envelope(username, card)
