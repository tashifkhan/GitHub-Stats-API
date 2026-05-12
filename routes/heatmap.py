from fastapi import APIRouter, Depends, Path, Query

from models.canonical import make_envelope
from routes.dependencies import get_analytics_service
from services import canonical_mapper
from services.analytics_service import AnalyticsService
from services.heatmap_window import window_heatmap


router = APIRouter(tags=["Canonical"])


@router.get("/{username}/heatmap", summary="Canonical contribution heatmap")
async def get_heatmap(
    username: str = Path(..., description="GitHub username"),
    view: str = Query("all", description="all | last_365 | year"),
    year: int | None = Query(None, description="Required when view=year"),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    contrib = await analytics_service.get_user_contributions(username, None)
    contributions = contrib.get("contributions") or {}
    data = canonical_mapper.heatmap_from(
        contributions,
        contrib.get("longestStreak", 0),
        contrib.get("currentStreak", 0),
    )
    # GitHub fetches every year since account creation (keyed by year), so those
    # keys are the authoritative availableYears list.
    years = sorted((int(y) for y in contributions.keys()), reverse=True)
    data = window_heatmap(data, view, year, available_years=years or None)
    return make_envelope(username, data)
