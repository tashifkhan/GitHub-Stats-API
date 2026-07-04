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
from models.repositories import Contributor, OriginalRepo, ReleaseAsset, RepoDetail, RepoRelease
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


def _repo_summary(repo: Optional[Dict]) -> Optional[OriginalRepo]:
    if not isinstance(repo, dict):
        return None

    owner = repo.get("owner")
    owner_login = owner.get("login") if isinstance(owner, dict) else None
    name = repo.get("name")
    full_name = repo.get("full_name")
    url = repo.get("html_url")

    if not all(isinstance(value, str) and value for value in (name, full_name, owner_login, url)):
        return None

    return OriginalRepo(name=name, full_name=full_name, owner=owner_login, url=url)


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


async def fetch_repo_details(
    client: httpx.AsyncClient, repo: Dict, token: str
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

    num_commits = await _get_commit_count(client, owner, repo_name, token)
    stars_count = repo.get("stargazers_count", 0)
    forks_count = repo.get("forks_count", repo.get("forks", 0)) or 0
    is_fork = bool(repo.get("fork"))
    original_repo = _repo_summary(repo.get("source") or repo.get("parent")) if is_fork else None

    await asyncio.gather(
        get_readme(), get_languages(), get_contributors(), get_releases()
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

    return RepoDetail(
        title=repo_name,
        description=description,
        live_website_url=live_url,
        languages=languages_list,
        num_commits=num_commits,
        stars=stars_count,
        forks=forks_count,
        is_fork=is_fork,
        original_repo=original_repo,
        readme=readme_content_markdown,
        contributors=contributors_list,
        releases=releases_list,
    )


async def get_repo_details(username: str, token: str) -> List[RepoDetail]:
    """
    Get detailed information for all public repositories of a user.

    Args:
        username: GitHub username
        token: GitHub API token

    Returns:
        List of repository details
    """
    async with httpx.AsyncClient() as client:
        # Get user's repositories
        repos_url = f"{GITHUB_API}/users/{username}/repos?per_page=100&sort=updated"
        try:
            response = await client.get(repos_url, headers=github_headers(token))
            if response.status_code != 200:
                raise HTTPException(
                    status_code=404, detail="User not found or API error"
                )

            repos = response.json()
            if not repos:
                return []

            # Fetch details for each repository concurrently
            repo_details_tasks = [
                fetch_repo_details(client, repo, token) for repo in repos
            ]
            repo_details = await asyncio.gather(
                *repo_details_tasks, return_exceptions=True
            )

            # Filter out None values and exceptions
            valid_repo_details: List[RepoDetail] = [
                cast(RepoDetail, detail)
                for detail in repo_details
                if detail is not None and not isinstance(detail, Exception)
            ]

            return valid_repo_details

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            raise HTTPException(status_code=500, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching repository details: {str(e)}"
            )
