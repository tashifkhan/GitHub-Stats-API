from typing import List, Optional
import os

from fastapi import Depends, HTTPException

from services.analytics_service import AnalyticsService
from services.pr_service import PRService

DEFAULT_EXCLUDED_LANGUAGES = ["Markdown", "JSON", "YAML", "XML"]


async def get_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")
    return token


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

    if exclude:
        return [lang.strip() for lang in exclude.split(",") if lang.strip()]

    return list(default or [])
