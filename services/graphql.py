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


async def execute_graphql_query(query: str, token: str) -> Dict:
    async with httpx.AsyncClient() as client:
        response = await _execute_graphql_query_with_client(client, query, token)
        return response.json()


async def _execute_graphql_query_with_client(
    client: httpx.AsyncClient, query: str, token: str
) -> httpx.Response:
    return await client.post(
        "https://api.github.com/graphql",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
    )


async def build_contribution_graph_query(user: str, year: int) -> str:
    start = f"{year}-01-01T00:00:00Z"
    end = f"{year}-12-31T23:59:59Z"
    return f"""
    query {{
        user(login: "{user}") {{
            createdAt
            contributionsCollection(from: "{start}", to: "{end}") {{
                contributionYears
                contributionCalendar {{
                    weeks {{
                        contributionDays {{
                            contributionCount
                            date
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
