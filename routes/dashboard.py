import asyncio
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, List, Optional
import os
from services.github_service import *

dashboard_router = APIRouter()


@dashboard_router.get(
    "/{username}/stats",
    tags=["User Analytics"],
    summary="Get User's Complete Statistics",
    description="""
    Retrieves comprehensive GitHub statistics for a user, combining:
    
    - Top programming languages
    - Total contribution count
    - Longest contribution streak
    
    This endpoint provides a complete overview of a user's GitHub activity.
    """,
    responses={
        200: {
            "description": "Successfully retrieved user statistics",
            "content": {
                "application/json": {
                    "example": {
                        "topLanguages": [{"name": "Python", "percentage": 45}],
                        "totalCommits": 1234,
                        "currentStreak": 15,
                        "longestStreak": 30,
                    }
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_stats(
    username: str,
    exclude: Optional[str] = Query(
        None, description="Comma-separated list of languages to exclude"
    ),
):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    excluded_list = exclude.split(",") if exclude else []

    contribution_data, language_stats = await asyncio.gather(
        get_contribution_graphs(username, token),
        get_language_stats(username, token, excluded_list),
    )

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)
    current_streak = calculate_current_streak(contribution_data)

    return {
        "topLanguages": language_stats,
        "totalCommits": total_commits,
        "longestStreak": longest_streak,
        "currentStreak": current_streak,
    }


@dashboard_router.get(
    "/{username}/repos",
    response_model=List[RepoDetail],
    tags=["Dashboard Details"],
    summary="Get User's Repository Details",
    description="Retrieves detailed information for each of the user's public repositories, including README, languages, and commit count.",
    responses={
        200: {"description": "Successfully retrieved repository details"},
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error or API error"},
    },
)
async def get_user_repos_async(
    username: str = Path(..., description="GitHub username")
):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        repos_url = (
            f"{GITHUB_API}/users/{username}/repos?per_page=100&type=owner&sort=pushed"
        )
        try:
            repos_resp = await client.get(repos_url, headers=github_headers(token))
            if repos_resp.status_code == 404:
                raise HTTPException(
                    status_code=404, detail=f"User '{username}' not found"
                )
            repos_resp.raise_for_status()
            repos = repos_resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, detail=f"GitHub API request error: {str(e)}"
            )

        if not isinstance(repos, list):
            raise HTTPException(
                status_code=500,
                detail="Unexpected response format from GitHub API for repositories.",
            )

        tasks = [
            fetch_repo_details(client, repo, token)
            for repo in repos
            if isinstance(repo, dict)
        ]
        results = await asyncio.gather(*tasks)

        return [res for res in results if res is not None]


@dashboard_router.get(
    "/{username}/commits",
    response_model=List[CommitDetail],
    tags=["Dashboard Details"],
    summary="Get User's Commit History Across All Repositories",
    description="Retrieves a list of all commits made by the user across all their owned repositories, sorted by timestamp.",
    responses={
        200: {"description": "Successfully retrieved commit history"},
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error or API error"},
    },
)
async def get_user_commit_history_async(
    username: str = Path(..., description="GitHub username")
):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    all_commits: List[CommitDetail] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        repos_url = f"{GITHUB_API}/users/{username}/repos?per_page=100&type=owner"
        try:
            repos_resp = await client.get(repos_url, headers=github_headers(token))
            if repos_resp.status_code == 404:
                raise HTTPException(
                    status_code=404, detail=f"User '{username}' not found"
                )
            repos_resp.raise_for_status()
            repos = repos_resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"GitHub API error: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, detail=f"GitHub API request error: {str(e)}"
            )

        if not isinstance(repos, list):
            raise HTTPException(
                status_code=500,
                detail="Unexpected response format from GitHub API for repositories.",
            )

        tasks = []
        for repo in repos:
            if (
                isinstance(repo, dict)
                and "name" in repo
                and isinstance(repo.get("owner"), dict)
                and "login" in repo["owner"]
            ):
                repo_name = repo["name"]
                owner = repo["owner"]["login"]
                tasks.append(
                    get_all_commits_for_repo_async(
                        client, owner, repo_name, username, token
                    )
                )

        repo_commits_list = await asyncio.gather(*tasks)
        for repo_commits in repo_commits_list:
            all_commits.extend(repo_commits)

    all_commits.sort(key=lambda x: x.timestamp or "", reverse=True)
    return all_commits
