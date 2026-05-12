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
from services.graphql import execute_graphql_query

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


async def get_user_pinned_repos(
    username: str, token: str, first: int = 6
) -> List[PinnedRepo]:
    """Fetch a user's pinned repositories via GitHub GraphQL API."""
    first = max(1, min(first, 6))  # GitHub UI limits to 6
    query = f"""
        query {{
            user(login: "{username}") {{
                pinnedItems(first: {first}, types: REPOSITORY) {{
                    edges {{
                        node {{
                            ... on Repository {{
                                name
                                description
                                url
                                stargazerCount
                                forkCount
                                primaryLanguage {{ name }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
    data = await execute_graphql_query(query, token)
    user = data.get("data", {}).get("user")
    if not user:
        raise HTTPException(status_code=404, detail="User not found or API error")
    edges = (
        user.get("pinnedItems", {}).get("edges", []) if user.get("pinnedItems") else []
    )
    pinned: List[PinnedRepo] = []
    for edge in edges:
        node = edge.get("node") or {}
        pinned.append(
            PinnedRepo(
                name=node.get("name") or "",
                description=node.get("description"),
                url=node.get("url") or "",
                stars=node.get("stargazerCount", 0),
                forks=node.get("forkCount", 0),
                primary_language=(
                    (node.get("primaryLanguage") or {}).get("name")
                    if node.get("primaryLanguage")
                    else None
                ),
            )
        )
    return pinned


async def get_user_profile(username: str, token: str) -> Dict:
    """Fetch a user's public profile from the GitHub REST API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/users/{username}",
            headers=github_headers(token),
        )
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"GitHub API error: {response.status_code}",
        )
    return response.json()


async def get_user_social_accounts(username: str, token: str) -> List[Dict]:
    """Fetch a user's linked social accounts (LinkedIn, Mastodon, etc.) from the GitHub REST API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API}/users/{username}/social_accounts",
            headers=github_headers(token),
        )
    if response.status_code >= 400:
        return []
    return response.json()
