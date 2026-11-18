from typing import List, Optional

from fastapi import Depends, HTTPException

from core.token_pool import NoTokenAvailable, get_token_pool
from services.analytics_service import AnalyticsService
from services.pr_service import PRService
from services.language_distribution import DEFAULT_EXCLUDED_LANGUAGES


async def get_github_token() -> str:
    pool = get_token_pool()
    if not pool.configured:
        raise HTTPException(status_code=500, detail="GitHub token not configured")
    try:
        return pool.acquire()
    except NoTokenAvailable as exc:
        raise HTTPException(
            status_code=503,
            detail="GitHub API rate limit exceeded, please retry shortly",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


async def get_analytics_service(
    token: str = Depends(get_github_token),
) -> AnalyticsService:
    return AnalyticsService(token=token)


async def get_pr_service(token: str = Depends(get_github_token)) -> PRService:
    return PRService(token=token)


def parse_excluded_languages(
    exclude: Optional[str] = None,
    excluded: Optional[List[str]] = None,
    default: Optional[List[str]] = None,
) -> List[str]:
    if excluded is not None:
        return [lang.strip() for lang in excluded if lang and lang.strip()]

    if exclude is not None:
        return [lang.strip() for lang in exclude.split(",") if lang.strip()]

    return list(default or [])
