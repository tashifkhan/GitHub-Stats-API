import asyncio
import base64
from datetime import datetime
import re
from typing import Dict, List, Optional, cast

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from core import cache
from core.jobs import enqueue
from models.analytics import LanguageData
from models.commits import CommitDetail
from models.profile import PinnedRepo
from models.pull_requests import OrganizationContribution, PullRequestDetail
from models.repositories import Contributor, ReleaseAsset, RepoDetail, RepoRelease
from models.stars import StarredList, StarsData
from services.attribution import get_user_contributions
from services.client import list_user_repositories
from services.client import github_headers as api_headers, raise_for_github_status
from services.language_distribution import language_distribution

BASE_GITHUB_URL = "https://github.com"
GITHUB_API = "https://api.github.com"
STAR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


# How long a complete attribution result exempts a user from queueing.
COMPLETE_MARKER_TTL_SECONDS = 6 * 60 * 60


def _complete_marker(username: str) -> str:
    return "gh:attr:complete:" + username.lower()


def github_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def get_language_stats(
    username: str, token: str, excluded_languages: List[str], include_forks: bool = True
) -> List[LanguageData]:
    async with httpx.AsyncClient() as client:
        repos, _ = await list_user_repositories(
            client, username, token, sort="updated", repo_type="all"
        )

        language_totals: Dict[str, int] = {}
        language_urls = [
            repo.get("languages_url")
            for repo in repos
            if isinstance(repo, dict) and repo.get("languages_url")
            and not repo.get("archived") and (include_forks or not repo.get("fork"))
        ]

        semaphore = asyncio.Semaphore(8)

        async def fetch_languages(url: str) -> Dict[str, int]:
            async with semaphore:
                lang_response = await client.get(
                    url,
                    headers=api_headers(token),
                )
                if lang_response.status_code == 404:
                    # A repo disappearing does not make its owner invalid.
                    raise HTTPException(status_code=502, detail="Repository language data unavailable")
                raise_for_github_status(lang_response, username)
                data = lang_response.json()
                if not isinstance(data, dict) or any(
                    not isinstance(value, int) or isinstance(value, bool) or value < 0
                    for value in data.values()
                ):
                    raise HTTPException(status_code=502, detail="Invalid GitHub language data")
                return data

        language_payloads = await asyncio.gather(
            *(fetch_languages(url) for url in language_urls)
        )

        for langs in language_payloads:
            for lang, bytes_used in langs.items():
                language_totals[lang] = language_totals.get(lang, 0) + bytes_used

        language_stats = [
            LanguageData(name=name, percentage=percentage)
            for name, _, percentage in language_distribution(language_totals, excluded_languages)
        ]
        return language_stats


async def get_attributed_language_stats(
    username: str,
    token: str,
    excluded_languages: List[str],
    include_forks: bool = True,
    deadline_seconds: Optional[float] = None,
    cache_only: bool = True,
) -> List[LanguageData]:
    """Language split weighted by the lines the user personally wrote.

    Unlike :func:`get_language_stats`, this ignores code written by other
    contributors and counts only the user's own commits, so a fork of a large
    upstream project contributes just the patches they authored.

    Public reads use cached measurements. An unfinished scan cannot establish
    a user's leading language, so only complete results become a ranking.
    The breakdown endpoint retains partial measurements for refresh progress.
    """
    # Queue before walking. Listing a large account's repos can use most of
    # the request budget, and a request cut off by the budget must still leave
    # the user queued for the scheduled worker (scripts/drain_attribution.py).
    # Users with a recent complete result skip the queue.
    marker = _complete_marker(username)
    queued = False if await cache.get_json(marker) else await enqueue("languages", username)
    stats = await get_user_contributions(
        username,
        token,
        excluded_languages=excluded_languages,
        include_forks=include_forks,
        include_repositories=False,
        deadline_seconds=deadline_seconds,
        cache_only=cache_only,
    )
    if stats.partial or stats.truncated or (stats.coverage < 1.0 and stats.repos_considered):
        # A pushed repo can make a once-complete user incomplete again.
        queued = queued or await enqueue("languages", username)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "language_attribution_pending",
                "message": "Complete authored-language measurements are not available yet.",
                "coverage": stats.coverage,
                "partial": stats.partial,
                "truncated": stats.truncated,
                "basis": "authored_additions",
                "refreshQueued": queued,
            },
            headers={"Cache-Control": "no-store"},
        )
    await cache.set_json(marker, {"complete": True}, COMPLETE_MARKER_TTL_SECONDS)
    return [
        LanguageData(name=language.name, percentage=language.percentage)
        for language in stats.languages
    ]
