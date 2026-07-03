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


def github_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def get_user_pull_requests(username: str, token: str) -> List[PullRequestDetail]:
    """
    Fetch all pull requests created by the user within repositories they own.
    The state field will be 'merged' if merged, 'closed' if closed but not merged, or 'open' if still open.

    Uses the GitHub Search API (one query, paginated) instead of iterating every
    owned repository individually and paginating each one's /pulls endpoint —
    that N+1 approach could take 30+ seconds for users with many repos and would
    routinely blow past serverless function time limits.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        pull_requests: List[PullRequestDetail] = []
        per_page = 100
        page = 1
        try:
            checked_user = False
            while True:
                search_url = (
                    f"{GITHUB_API}/search/issues"
                    f"?q=type:pr+author:{username}+user:{username}"
                    f"&per_page={per_page}&page={page}"
                )
                resp = await client.get(search_url, headers=github_headers(token))
                if resp.status_code != 200:
                    if not checked_user:
                        user_resp = await client.get(
                            f"{GITHUB_API}/users/{username}",
                            headers=github_headers(token),
                        )
                        if user_resp.status_code == 404:
                            raise HTTPException(
                                status_code=404, detail="User not found"
                            )
                    raise HTTPException(status_code=502, detail="GitHub API error")
                checked_user = True
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                for pr in items:
                    repo_url = pr.get("repository_url", "")
                    repo_name = repo_url.rsplit("/", 1)[-1] if repo_url else ""
                    merged_at = pr.get("pull_request", {}).get("merged_at")
                    closed_at = pr.get("closed_at")
                    if merged_at:
                        pr_state = "merged"
                    elif closed_at:
                        pr_state = "closed"
                    else:
                        pr_state = pr.get("state", "open")
                    pull_requests.append(
                        PullRequestDetail(
                            repo=repo_name,
                            number=pr.get("number", 0),
                            title=pr.get("title", ""),
                            state=pr_state,
                            created_at=pr.get("created_at", ""),
                            updated_at=pr.get("updated_at", ""),
                            closed_at=closed_at,
                            merged_at=merged_at,
                            user=username,
                            url=pr.get("html_url", ""),
                            body=pr.get("body"),
                        )
                    )
                if len(items) < per_page:
                    break
                page += 1
            return pull_requests
        except HTTPException:
            raise
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=502, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching pull requests: {str(e) or type(e).__name__}",
            )


async def get_organization_contributions(
    username: str, token: str, orgs: Optional[List[str]] = None
) -> List[OrganizationContribution]:
    """
    Find all organizations where the user has contributed (via merged PRs), regardless of membership.
    Uses the GitHub Search API to find all merged PRs by the user, then groups repos by organization.
    """
    async with httpx.AsyncClient() as client:
        per_page = 100
        page = 1
        org_repo_map = {}
        org_meta_map = {}
        while True:
            search_url = f"{GITHUB_API}/search/issues?q=type:pr+author:{username}+is:merged&per_page={per_page}&page={page}"
            resp = await client.get(search_url, headers=github_headers(token))
            if resp.status_code != 200:
                break
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for pr in items:
                repo_url = pr.get("repository_url")
                if not repo_url:
                    continue
                # repo_url: https://api.github.com/repos/{org}/{repo}
                parts = repo_url.split("/")
                if len(parts) < 2:
                    continue
                org_login = parts[-2]
                repo_name = parts[-1]
                if org_login not in org_repo_map:
                    org_repo_map[org_login] = set()
                org_repo_map[org_login].add(repo_name)
                if org_login not in org_meta_map:
                    # Fetch org meta (id, avatar_url)
                    org_api_url = f"{GITHUB_API}/orgs/{org_login}"
                    org_resp = await client.get(
                        org_api_url, headers=github_headers(token)
                    )
                    if org_resp.status_code == 200:
                        org_data = org_resp.json()
                        org_meta_map[org_login] = {
                            "id": org_data.get("id", 0),
                            "avatar_url": org_data.get("avatar_url", ""),
                        }
                    else:
                        org_meta_map[org_login] = {"id": 0, "avatar_url": ""}
            if len(items) < per_page:
                break
            page += 1
        org_contributions = []
        for org_login, repos in org_repo_map.items():
            meta = org_meta_map.get(org_login, {"id": 0, "avatar_url": ""})
            org_contributions.append(
                OrganizationContribution(
                    org=org_login,
                    org_id=meta["id"],
                    org_url=f"https://github.com/{org_login}",
                    org_avatar_url=meta["avatar_url"],
                    repos=sorted(list(repos)),
                )
            )
        return org_contributions


async def _search_count(query: str, token: str) -> int:
    """Return total_count from GitHub search API for a given query string."""
    url = f"{GITHUB_API}/search/issues?q={query}&per_page=1"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers=github_headers(token))
            if resp.status_code == 200:
                return resp.json().get("total_count", 0)
        except Exception:
            pass
    return 0


async def get_user_pr_count(username: str, token: str) -> int:
    """Count all PRs authored by the user across all public repos."""
    return await _search_count(f"type:pr+author:{username}", token)


async def get_user_issue_count(username: str, token: str) -> int:
    """Count all issues opened by the user across all public repos."""
    return await _search_count(f"type:issue+author:{username}", token)


async def get_user_review_count(username: str, token: str) -> int:
    """Count PRs reviewed by the user across all public repos."""
    return await _search_count(f"type:pr+reviewed-by:{username}", token)
