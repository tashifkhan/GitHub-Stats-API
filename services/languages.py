import asyncio
import base64
from datetime import datetime
import re
from typing import Dict, List, Optional, cast

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from models.analytics import LanguageData
from models.commits import CommitDetail
from models.profile import PinnedRepo
from models.pull_requests import OrganizationContribution, PullRequestDetail
from models.repositories import Contributor, ReleaseAsset, RepoDetail, RepoRelease
from models.stars import StarredList, StarsData

BASE_GITHUB_URL = "https://github.com"
GITHUB_API = "https://api.github.com"
STAR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def github_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def get_language_stats(
    username: str, token: str, excluded_languages: List[str]
) -> List[LanguageData]:
    async with httpx.AsyncClient() as client:
        repos_response = await client.get(
            f"https://api.github.com/users/{username}/repos",
            headers={"Authorization": f"Bearer {token}"},
        )

        if repos_response.status_code != 200:
            raise HTTPException(status_code=404, detail="User not found or API error")

        repos = repos_response.json()

        excluded_set = set(excluded_languages)
        language_totals: Dict[str, int] = {}
        language_urls = [
            repo.get("languages_url")
            for repo in repos
            if isinstance(repo, dict) and repo.get("languages_url")
        ]

        semaphore = asyncio.Semaphore(8)

        async def fetch_languages(url: str) -> Dict[str, int]:
            async with semaphore:
                lang_response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if lang_response.status_code != 200:
                    return {}
                data = lang_response.json()
                return data if isinstance(data, dict) else {}

        language_payloads = await asyncio.gather(
            *(fetch_languages(url) for url in language_urls)
        )

        for langs in language_payloads:
            for lang, bytes_used in langs.items():
                if lang in excluded_set:
                    continue
                language_totals[lang] = language_totals.get(lang, 0) + bytes_used

        total_bytes = sum(language_totals.values())
        if total_bytes == 0:
            return []

        language_stats = [
            LanguageData(name=name, percentage=round((bytes / total_bytes) * 100, 2))
            for name, bytes in language_totals.items()
        ]
        return sorted(language_stats, key=lambda x: x.percentage, reverse=True)
