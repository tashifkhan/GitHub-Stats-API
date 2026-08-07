import asyncio
import base64
from datetime import datetime
import re
from typing import Dict, List, Optional, cast

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from core.config import attribution_settings
from models.analytics import LanguageData
from models.attribution import RepoContribution
from models.commits import CommitDetail
from models.profile import PinnedRepo
from models.pull_requests import OrganizationContribution, PullRequestDetail
from models.repositories import Contributor, ReleaseAsset, RepoDetail, RepoRelease
from models.stars import StarredList, StarsData
from services.attribution import AttributionBudget, analyze_repo_contribution
from services.client import raise_for_github_status

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


def _extract_url_from_description(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    match = re.search(r"(https?://[^\s]+)", description)
    return match.group(1) if match else None


def _decode_readme_to_markdown(content_b64: Optional[str]) -> Optional[str]:
    if not content_b64:
        return None

    try:
        normalized = content_b64.replace("\n", "")
        decoded = base64.b64decode(normalized, validate=False)
        text = decoded.decode("utf-8", errors="replace").strip()
        return text or None
    except Exception:
        return None


async def _fetch_releases(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str, limit: int = 5
) -> List[RepoRelease]:
    releases_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/releases?per_page={limit}"
    try:
        response = await client.get(releases_url, headers=github_headers(token))
        if response.status_code != 200:
            return []

        releases_data = response.json()
        if not isinstance(releases_data, list):
            return []

        releases: List[RepoRelease] = []
        for rel in releases_data:
            if not isinstance(rel, dict):
                continue

            assets_data = rel.get("assets")
            assets: List[ReleaseAsset] = []
            if isinstance(assets_data, list):
                for asset in assets_data:
                    if not isinstance(asset, dict):
                        continue
                    download_url = asset.get("browser_download_url")
                    if not isinstance(download_url, str) or not download_url:
                        continue

                    assets.append(
                        ReleaseAsset(
                            name=asset.get("name") or "asset",
                            download_url=download_url,
                            size=asset.get("size") or 0,
                            download_count=asset.get("download_count") or 0,
                            content_type=asset.get("content_type"),
                            updated_at=asset.get("updated_at"),
                        )
                    )

            releases.append(
                RepoRelease(
                    id=rel.get("id") or 0,
                    tag_name=rel.get("tag_name") or "untagged",
                    name=rel.get("name"),
                    body=rel.get("body"),
                    url=rel.get("html_url")
                    or f"{BASE_GITHUB_URL}/{owner}/{repo_name}/releases",
                    draft=bool(rel.get("draft")),
                    prerelease=bool(rel.get("prerelease")),
                    created_at=rel.get("created_at"),
                    published_at=rel.get("published_at"),
                    assets=assets,
                )
            )

        return releases
    except Exception:
        return []


async def _get_commit_count(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str
) -> int:
    commits_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/commits?per_page=1"
    try:
        response = await client.get(commits_url, headers=github_headers(token))
        if response.status_code == 200:
            link_header = response.headers.get("Link")
            if link_header:
                match = re.search(r'<.*?page=(\d+)>; rel="last"', link_header)
                if match:
                    return int(match.group(1))
            page_commits = response.json()
            if page_commits:
                return len(page_commits) if isinstance(page_commits, list) else 0
            return 0
        elif response.status_code in [404, 403]:
            return 0
        response.raise_for_status()
        return 0
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return 0
        return 0
    except Exception:
        return 0


async def _fetch_contributors(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str
) -> List[Contributor]:
    contributors_url = (
        f"{GITHUB_API}/repos/{owner}/{repo_name}/contributors?per_page=10"
    )
    try:
        response = await client.get(contributors_url, headers=github_headers(token))
        if response.status_code == 200:
            contributors_data = response.json()
            return [
                Contributor(
                    login=c["login"],
                    avatar_url=c["avatar_url"],
                    html_url=c["html_url"],
                    contributions=c["contributions"],
                )
                for c in contributors_data
                if isinstance(c, dict)
            ]
        return []
    except Exception:
        return []


async def _attribute_repos(
    client: httpx.AsyncClient, repos: List[Dict], username: str, token: str
) -> Dict[str, RepoContribution]:
    """Per-user contribution for each repo, keyed by ``owner/name``.

    Cache-only: this endpoint is already the heaviest one in the API, and
    measuring commit diffs here would push it past the function timeout. Repos
    show their ``user_*`` fields once the attribution cache has been warmed by
    ``/{username}/contributions/breakdown`` or the warm script.
    """
    # Nothing is spent in cache-only mode, so the budget and semaphore are just
    # the arguments the signature wants.
    budget = AttributionBudget(0)
    semaphore = asyncio.Semaphore(1)

    results = await asyncio.gather(
        *(
            analyze_repo_contribution(
                client,
                repo,
                username,
                token,
                budget,
                semaphore,
                cache_only=True,
            )
            for repo in repos[: attribution_settings.max_repos]
            if isinstance(repo, dict)
        ),
        return_exceptions=True,
    )

    attributed: Dict[str, RepoContribution] = {}
    for result in results:
        if isinstance(result, RepoContribution):
            attributed[result.full_name] = result
            attributed.setdefault(result.repo, result)
    return attributed


async def fetch_repo_details(
    client: httpx.AsyncClient,
    repo: Dict,
    token: str,
    contribution: Optional[RepoContribution] = None,
) -> Optional[RepoDetail]:
    repo_name = repo["name"]
    owner = repo["owner"]["login"]

    readme_content_b64 = None
    readme_content_markdown = None
    languages_list = []
    contributors_list = []
    releases_list: List[RepoRelease] = []

    async def get_readme():
        nonlocal readme_content_b64, readme_content_markdown
        readme_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/readme"
        try:
            readme_resp = await client.get(readme_url, headers=github_headers(token))
            if readme_resp.status_code == 200:
                readme_content_b64 = readme_resp.json().get("content")
                readme_content_markdown = _decode_readme_to_markdown(readme_content_b64)
        except Exception:
            pass

    async def get_languages():
        nonlocal languages_list
        languages_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/languages"
        try:
            languages_resp = await client.get(
                languages_url, headers=github_headers(token)
            )
            if languages_resp.status_code == 200:
                languages_list = list(languages_resp.json().keys())
        except Exception:
            pass

    async def get_contributors():
        nonlocal contributors_list
        contributors_list = await _fetch_contributors(client, owner, repo_name, token)

    async def get_releases():
        nonlocal releases_list
        releases_list = await _fetch_releases(client, owner, repo_name, token)

    num_commits = 0

    async def get_commit_count():
        nonlocal num_commits
        num_commits = await _get_commit_count(client, owner, repo_name, token)

    stars_count = repo.get("stargazers_count", 0)

    # All five run together: awaiting the commit count first cost an extra
    # serial round trip per repo, which across a large account was seconds.
    await asyncio.gather(
        get_readme(),
        get_languages(),
        get_contributors(),
        get_releases(),
        get_commit_count(),
    )

    description = repo.get("description")
    homepage_url = repo.get("homepage")
    live_url = None

    if (
        homepage_url
        and isinstance(homepage_url, str)
        and homepage_url.startswith(("http://", "https://"))
    ):
        live_url = homepage_url
    else:
        live_url = _extract_url_from_description(description)

    topics_raw = repo.get("topics") or []
    topics_list = (
        [str(t) for t in topics_raw if t]
        if isinstance(topics_raw, list)
        else []
    )

    return RepoDetail(
        title=repo_name,
        description=description,
        live_website_url=live_url,
        languages=languages_list,
        topics=topics_list,
        num_commits=num_commits,
        stars=stars_count,
        readme=readme_content_markdown,
        contributors=contributors_list,
        releases=releases_list,
        is_fork=bool(repo.get("fork")),
        user_commits=contribution.commits if contribution else 0,
        user_additions=contribution.additions if contribution else 0,
        user_deletions=contribution.deletions if contribution else 0,
        user_files_changed=contribution.files_changed if contribution else 0,
        user_languages=contribution.languages if contribution else [],
        contribution_percentage=(
            contribution.contribution_percentage if contribution else None
        ),
    )


async def get_repo_details(
    username: str, token: str, attributed: bool = True
) -> List[RepoDetail]:
    """
    Get detailed information for all public repositories of a user.

    Args:
        username: GitHub username
        token: GitHub API token
        attributed: Fill the ``user_*`` fields from cached own-commit
            attribution. Reads the cache only, never walks commit diffs

    Returns:
        List of repository details
    """
    async with httpx.AsyncClient() as client:
        # Get user's repositories
        repos_url = f"{GITHUB_API}/users/{username}/repos?per_page=100&sort=updated"
        try:
            response = await client.get(repos_url, headers=github_headers(token))
            if response.status_code != 200:
                raise_for_github_status(response, username)

            repos = response.json()
            if not repos:
                return []

            contributions: Dict[str, RepoContribution] = {}
            if attributed:
                contributions = await _attribute_repos(client, repos, username, token)

            # Fetch details for each repository concurrently, but capped: every
            # repo costs five requests, and firing hundreds at once draws
            # GitHub's secondary rate limiter, which slows the whole batch down.
            slots = asyncio.Semaphore(attribution_settings.repo_detail_concurrency)

            async def detail_for(repo: Dict) -> Optional[RepoDetail]:
                async with slots:
                    return await fetch_repo_details(
                        client,
                        repo,
                        token,
                        contributions.get(
                            repo.get("full_name") or repo.get("name", "")
                        ),
                    )

            repo_details = await asyncio.gather(
                *(detail_for(repo) for repo in repos), return_exceptions=True
            )

            # Filter out None values and exceptions
            valid_repo_details: List[RepoDetail] = [
                cast(RepoDetail, detail)
                for detail in repo_details
                if detail is not None and not isinstance(detail, Exception)
            ]

            return valid_repo_details

        except HTTPException:
            # Already carries the right status (404 missing user, 503 throttled);
            # the catch-all below would otherwise rewrite it as a 500.
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            raise HTTPException(status_code=500, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching repository details: {str(e)}"
            )
