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


async def get_all_commits_for_repo_async(
    client: httpx.AsyncClient, owner: str, repo_name: str, username: str, token: str
) -> List[CommitDetail]:
    commits_data: List[CommitDetail] = []
    page = 1
    per_page = 100
    while True:
        commits_url = (
            f"{GITHUB_API}/repos/{owner}/{repo_name}/commits"
            f"?author={username}&per_page={per_page}&page={page}"
        )
        try:
            resp = await client.get(commits_url, headers=github_headers(token))
            if resp.status_code != 200:
                break
            page_commits = resp.json()
            if not page_commits:
                break

            for commit_item in page_commits:
                commit_details = commit_item.get("commit", {})
                author_details = commit_details.get("author", {})
                commits_data.append(
                    CommitDetail(
                        repo=repo_name,
                        message=commit_details.get("message"),
                        timestamp=author_details.get("date"),
                        sha=commit_item.get("sha"),
                        url=commit_item.get("html_url"),
                    )
                )

            if len(page_commits) < per_page:
                break
            page += 1
        except Exception:
            break
    return commits_data


async def get_all_commits(username: str, token: str) -> List[CommitDetail]:
    """
    Get all commits made by a user across their owned repositories.

    Args:
        username: GitHub username
        token: GitHub API token

    Returns:
        List of commit details sorted by timestamp (most recent first)
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

            # Get commits for each repository concurrently
            commits_tasks = [
                get_all_commits_for_repo_async(
                    client, username, repo["name"], username, token
                )
                for repo in repos
            ]
            all_commits_lists = await asyncio.gather(
                *commits_tasks, return_exceptions=True
            )

            # Flatten and filter out exceptions
            all_commits = []
            for commits_list in all_commits_lists:
                if isinstance(commits_list, list):
                    all_commits.extend(commits_list)

            # Sort by timestamp (most recent first)
            all_commits.sort(key=lambda x: x.timestamp or "", reverse=True)

            return all_commits

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            raise HTTPException(status_code=500, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching commits: {str(e)}"
            )
