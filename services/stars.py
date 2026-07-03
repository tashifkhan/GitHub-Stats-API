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


def _extract_url_from_description(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    match = re.search(r"(https?://[^\s]+)", description)
    return match.group(1) if match else None


async def get_user_stars_data(username: str, token: str) -> StarsData:
    """
    Get total stars and starred repositories for a user.

    Args:
        username: GitHub username
        token: GitHub API token

    Returns:
        StarsData with total stars and repository details
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
                return StarsData(total_stars=0, repositories=[])

            total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)

            # Get detailed repository information with stars
            repo_details = []
            for repo in repos:
                stars_count = repo.get("stargazers_count", 0)
                if stars_count > 0:  # Only include repositories with stars
                    homepage_url = repo.get("homepage")
                    live_url = None

                    if (
                        homepage_url
                        and isinstance(homepage_url, str)
                        and homepage_url.startswith(("http://", "https://"))
                    ):
                        live_url = homepage_url
                    else:
                        live_url = _extract_url_from_description(
                            repo.get("description")
                        )

                    repo_detail = {
                        "name": repo["name"],
                        "description": repo.get("description"),
                        "stars": stars_count,
                        "url": repo.get("html_url"),
                        "language": repo.get("language"),
                        "created_at": repo.get("created_at"),
                        "updated_at": repo.get("updated_at"),
                        "homepage": live_url,
                    }
                    repo_details.append(repo_detail)

            # Sort by stars (highest first)
            repo_details.sort(key=lambda x: x["stars"], reverse=True)

            return StarsData(total_stars=total_stars, repositories=repo_details)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            raise HTTPException(status_code=500, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching stars data: {str(e)}"
            )


async def fetch_star_lists(username: str) -> List[StarredList]:
    """Fetch all starred lists for a GitHub user (HTML scrape)."""

    url = f"{BASE_GITHUB_URL}/{username}?tab=stars"

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        resp = await client.get(
            url,
            headers=STAR_HEADERS,
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to fetch starred lists page: {resp.status_code}",
            )

        soup = BeautifulSoup(resp.text, "html.parser")

        star_lists: List[StarredList] = []

        container = soup.find(id="profile-lists-container")

        anchors = []
        if container:
            anchors = container.find_all("a", href=True)

        if not anchors:
            anchors = soup.select("div[jscontroller] ul li a")

        for item in anchors:
            href_attr = item.get("href")
            if not href_attr:
                continue

            href = href_attr if isinstance(href_attr, str) else str(href_attr)
            if not href.startswith(f"/stars/{username}/lists/"):
                continue

            list_url = BASE_GITHUB_URL + href
            name_tag = item.find("h3")
            list_name = (
                name_tag.get_text(strip=True)
                if name_tag and name_tag.get_text(strip=True)
                else item.get_text(strip=True)
            )
            if not list_name:
                continue

            desc_tag = item.select_one(".Truncate-text")
            description = None
            if desc_tag:
                raw_desc = desc_tag.get_text(" ", strip=True)
                description = raw_desc if raw_desc else None

            num_repos = None
            count_container = item.find(
                string=lambda t: isinstance(t, str) and "repositories" in t
            )
            if count_container:
                import re as _re

                m = _re.search(r"(\d+)", count_container)
                if m:
                    try:
                        num_repos = int(m.group(1))
                    except ValueError:
                        num_repos = None

            star_lists.append(
                StarredList(
                    name=list_name,
                    url=list_url,
                    description=description,
                    num_repos=num_repos,
                )
            )
        return star_lists


async def fetch_repos_from_star_list(list_url: str) -> List[str]:
    """Fetch repositories inside a starred list (HTML scrape)."""

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        resp = await client.get(
            list_url,
            headers=STAR_HEADERS,
        )

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Failed to fetch list page: {resp.status_code}",
            )

        soup = BeautifulSoup(resp.text, "html.parser")
        repos: List[str] = []

        # Match links of the form /owner/repo (exactly two path segments)
        repo_re = re.compile(r"^/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")

        for a_tag in soup.find_all("a", href=True):
            href_attr = a_tag.get("href")
            if href_attr is None:
                continue
            href_str = href_attr if isinstance(href_attr, str) else str(href_attr)
            m = repo_re.match(href_str)
            if m:
                repos.append(f"{m.group(1)}/{m.group(2)}")

        return sorted(set(repos))


async def get_user_starred_lists(
    username: str,
    include_repos: bool = False,
) -> List[StarredList]:
    """Public helper to get a user's starred lists optionally with repos."""
    lists = await fetch_star_lists(username)
    if include_repos and lists:

        async def enrich(star_list: StarredList) -> StarredList:
            try:
                repos = await fetch_repos_from_star_list(star_list.url)
                star_list.repositories = repos

            except HTTPException:
                star_list.repositories = []

            return star_list

        tasks = [enrich(lst) for lst in lists]
        lists = cast(List[StarredList], await asyncio.gather(*tasks))

    return lists
