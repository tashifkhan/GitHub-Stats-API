from fastapi import APIRouter, HTTPException, Query, Path, Depends
from typing import List, Dict, Optional
from dataclasses import asdict
import os

from modules.github import GitHubStatsResponse, RepoDetail, CommitDetail
from services.github_service import (
    get_language_stats,
    get_contribution_graphs,
    calculate_total_commits,
    calculate_longest_streak,
    calculate_current_streak,
    get_user_repos,
    get_user_commit_history,
)

api_router = APIRouter()


# Dependency to get GitHub Token
async def get_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")
    return token


@api_router.get(
    "/{username}/languages",
    response_model=List[Dict[str, float]],
    tags=["User Analytics"],
)
async def get_user_language_stats_route(
    username: str = Path(..., description="GitHub username"),
    excluded: List[str] = Query(
        default=["Markdown", "JSON", "YAML", "XML"],
        description="Languages to exclude from the statistics",
    ),
    token: str = Depends(get_github_token),
):
    language_stats_data = get_language_stats(username, token, excluded)

    if language_stats_data is None:
        raise HTTPException(
            status_code=404,
            detail="Could not retrieve language statistics or user not found",
        )

    return language_stats_data


@api_router.get("/{username}/contributions", tags=["User Analytics"])
async def get_user_contributions_route(
    username: str = Path(..., description="GitHub username"),
    starting_year: Optional[int] = Query(
        None,
        description="Starting year for contribution history (defaults to account creation year)",
    ),
    token: str = Depends(get_github_token),
):
    if starting_year is not None and not (
        isinstance(starting_year, int) and starting_year > 1900 and starting_year < 2200
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid starting_year format. Must be a valid year.",
        )

    contribution_data = get_contribution_graphs(username, token, starting_year)

    if not contribution_data or not contribution_data.get(
        list(contribution_data.keys())[0] if contribution_data else None, {}
    ).get("data", {}).get("user"):
        raise HTTPException(
            status_code=404, detail="User not found or API error fetching contributions"
        )

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)
    current_streak = calculate_current_streak(contribution_data)

    return {
        "contributions": contribution_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak,
        "currentStreak": current_streak,
    }


@api_router.get("/{username}/stats", tags=["User Analytics"])
async def get_user_stats_route(
    username: str = Path(..., description="GitHub username"),
    exclude: Optional[str] = Query(
        None, description="Comma-separated list of languages to exclude"
    ),
    token: str = Depends(get_github_token),
):
    excluded_list = (
        [lang.strip() for lang in exclude.split(",")]
        if exclude
        else ["Markdown", "JSON", "YAML", "XML"]
    )

    contribution_data = get_contribution_graphs(username, token)
    if not contribution_data or not contribution_data.get(
        list(contribution_data.keys())[0] if contribution_data else None, {}
    ).get("data", {}).get("user"):
        raise HTTPException(
            status_code=404, detail="User not found or API error fetching contributions"
        )

    language_stats_data = get_language_stats(username, token, excluded_list)

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)
    current_streak = calculate_current_streak(contribution_data)

    return {
        "topLanguages": language_stats_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak,
        "currentStreak": current_streak,
    }


@api_router.get(
    "/{username}/repos", response_model=List[RepoDetail], tags=["Dashboard Details"]
)
async def get_user_repo_details_route(
    username: str = Path(..., description="GitHub username"),
    token: str = Depends(get_github_token),
):
    repos = get_user_repos(username, token)

    if repos is None:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve repository details"
        )
    return repos


@api_router.get(
    "/{username}/commits", response_model=List[CommitDetail], tags=["Dashboard Details"]
)
async def get_user_commit_details_route(
    username: str = Path(..., description="GitHub username"),
    token: str = Depends(get_github_token),
):
    commits = get_user_commit_history(username, token)

    if commits is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve commit history")
    return commits
