import asyncio
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse, Response
from typing import Dict, List, Optional, Any
from modules.github import LanguageData, RepoDetail, StarsData
import os
from services.github_service import *
from services.profile_views_service import increment_profile_views, get_profile_views

analytics_router = APIRouter()


@analytics_router.get(
    "/{username}/languages",
    tags=["User Analytics"],
    summary="Get User's Programming Languages",
    description="""
    Retrieves the top programming languages used by a GitHub user based on their repositories.
    
    - Excludes specified languages (default: Markdown, JSON, YAML, XML)
    - Returns top 5 languages by usage percentage
    - Percentages are rounded to nearest integer
    """,
    response_description="List of top programming languages with usage percentages",
    responses={
        200: {
            "description": "Successfully retrieved language statistics",
            "content": {
                "application/json": {
                    "example": [
                        {"name": "Python", "percentage": 45},
                        {"name": "JavaScript", "percentage": 30},
                        {"name": "TypeScript", "percentage": 15},
                        {"name": "Java", "percentage": 7},
                        {"name": "C++", "percentage": 3},
                    ]
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_language_stats(
    username: str,
    excluded: List[str] = Query(
        default=["Markdown", "JSON", "YAML", "XML"],
        description="Languages to exclude from the statistics",
    ),
) -> List[LanguageData]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")
    return await get_language_stats(username, token, excluded)


@analytics_router.get(
    "/{username}/contributions",
    tags=["User Analytics"],
    summary="Get User's Contribution History",
    description="""
    Retrieves a user's GitHub contribution history including:
    
    - Contribution calendar data
    - Total number of commits
    - Longest contribution streak
    
    Optionally specify a starting year to limit the historical data.
    """,
    responses={
        200: {
            "description": "Successfully retrieved contribution data",
            "content": {
                "application/json": {
                    "example": {
                        "contributions": {
                            "2023": {
                                "data": {
                                    "user": {"contributionsCollection": {"weeks": []}}
                                }
                            }
                        },
                        "totalCommits": 1234,
                        "longestStreak": 30,
                    }
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_contributions(
    username: str,
    starting_year: Optional[int] = Query(
        None,
        description="Starting year for contribution history (defaults to account creation year)",
    ),
) -> Dict:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    contribution_data = await get_contribution_graphs(username, token, starting_year)
    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)

    return {
        "contributions": contribution_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak,
    }


@analytics_router.get(
    "/{username}/stars",
    tags=["User Analytics"],
    summary="Get User's Stars Information",
    description="""
    Retrieves stars information for a user's repositories including:
    
    - Total stars across all repositories
    - List of repositories with stars (sorted by star count)
    - Repository details including description, language, and URLs
    
    This endpoint provides comprehensive stars analytics for portfolio displays.
    """,
    response_description="Stars information with total count and repository details",
    responses={
        200: {
            "description": "Successfully retrieved stars information",
            "content": {
                "application/json": {
                    "example": {
                        "total_stars": 150,
                        "repositories": [
                            {
                                "name": "RepoName",
                                "description": "A popular project",
                                "stars": 100,
                                "url": "https://github.com/user/repo",
                                "language": "Python",
                                "created_at": "2023-01-01T00:00:00Z",
                                "updated_at": "2023-12-01T00:00:00Z",
                            }
                        ],
                    }
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_stars(
    username: str = Path(..., description="GitHub username"),
) -> StarsData:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    try:
        return await get_user_stars_data(username, token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found or API error")
        raise e


@analytics_router.get(
    "/{username}/repos",
    tags=["User Analytics"],
    summary="Get User's Repository Details",
    description="""
    Retrieves detailed information for each of the user's public repositories including:
    
    - Repository name and description
    - Live website URL (if available in description)
    - Programming languages used
    - Number of commits
    - Number of stars
    - README content (Base64 encoded)
    
    This endpoint provides comprehensive repository information for portfolio displays.
    """,
    response_description="List of repository details with comprehensive information",
    responses={
        200: {
            "description": "Successfully retrieved repository details",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "title": "RepoName",
                            "description": "A cool project.",
                            "live_website_url": "https://example.com",
                            "languages": ["Python", "JavaScript"],
                            "num_commits": 42,
                            "stars": 25,
                            "readme": "BASE64_ENCODED_README_CONTENT",
                        }
                    ]
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_repos(
    username: str = Path(..., description="GitHub username"),
) -> List[RepoDetail]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    try:
        return await get_repo_details(username, token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found or API error")
        raise e


@analytics_router.get(
    "/{username}/commits",
    tags=["User Analytics"],
    summary="Get User's Commit History",
    description="""
    Retrieves a list of all commits made by the user across their owned repositories.
    
    - Sorted by timestamp (most recent first)
    - Includes commit message, SHA, and URL
    - Provides comprehensive commit history for analysis
    """,
    response_description="List of commit details across all repositories",
    responses={
        200: {
            "description": "Successfully retrieved commit history",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "repo": "RepoName",
                            "message": "Fix: A critical bug",
                            "timestamp": "2023-01-01T12:00:00Z",
                            "sha": "commit_sha_hash",
                            "url": "https://github.com/user/repo/commit/sha",
                        }
                    ]
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_commits(
    username: str = Path(..., description="GitHub username"),
) -> List[CommitDetail]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    try:
        return await get_all_commits(username, token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found or API error")
        raise e


@analytics_router.get(
    "/{username}/profile-views",
    tags=["User Analytics"],
    summary="Get and Increment Profile Views",
    description="""
    Gets the current profile views count for a user and optionally increments it.
    Similar to the GitHub Profile Views Counter service.
    
    - Returns current profile views count
    - Optionally increments the count (when increment=true)
    - Supports base count for migration from other services
    """,
    response_description="Profile views count",
    responses={
        200: {
            "description": "Successfully retrieved profile views count",
            "content": {
                "application/json": {
                    "example": {
                        "username": "tashifkhan",
                        "views": 1234,
                        "incremented": True,
                    }
                }
            },
        },
    },
)
async def get_profile_views_count(
    username: str = Path(..., description="GitHub username"),
    increment: bool = Query(True, description="Whether to increment the view count"),
    base: Optional[int] = Query(None, description="Base count to set (for migration)"),
) -> Dict[str, Any]:
    if base is not None:
        views = await get_profile_views(username, base)
        return {
            "username": username,
            "views": views,
            "incremented": False,
            "base_set": True,
        }

    if increment:
        views = await increment_profile_views(username)
        return {"username": username, "views": views, "incremented": True}
    else:
        views = await get_profile_views(username)
        return {"username": username, "views": views, "incremented": False}


@analytics_router.get(
    "/{username}/stats",
    tags=["User Analytics"],
    summary="Get User's Complete Statistics",
    description="""
    Retrieves comprehensive GitHub statistics for a user, combining:
    
    - Top programming languages
    - Total contribution count
    - Longest contribution streak
    - Current contribution streak
    - Profile visitors count
    - Contribution history data
    
    This endpoint provides a complete overview of a user's GitHub activity.
    """,
    response_model=GitHubStatsResponse,
    responses={
        200: {
            "description": "Successfully retrieved user statistics",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "retrieved",
                        "topLanguages": [{"name": "Python", "percentage": 45.0}],
                        "totalCommits": 1234,
                        "longestStreak": 30,
                        "currentStreak": 15,
                        "profile_visitors": 567,
                        "contributions": {
                            "2023": {
                                "data": {
                                    "user": {
                                        "contributionsCollection": {
                                            "contributionCalendar": {"weeks": []}
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
        404: {
            "description": "User not found or API error",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "User not found or API error",
                        "topLanguages": [],
                        "totalCommits": 0,
                        "longestStreak": 0,
                        "currentStreak": 0,
                        "profile_visitors": 0,
                        "contributions": None,
                    }
                }
            },
        },
        500: {
            "description": "GitHub token configuration error or other server error",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "GitHub token not configured",
                        "topLanguages": [],
                        "totalCommits": 0,
                        "longestStreak": 0,
                        "currentStreak": 0,
                        "profile_visitors": 0,
                        "contributions": None,
                    }
                }
            },
        },
    },
)
async def get_user_stats(
    username: str = Path(..., description="GitHub username"),
    exclude: Optional[str] = Query(
        None,
        description="Comma-separated list of languages to exclude from language stats",
    ),
) -> GitHubStatsResponse:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    excluded_list = exclude.split(",") if exclude else []

    try:
        contribution_data = await get_contribution_graphs(username, token)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="User not found or API error fetching contributions",
            )
        raise e

    try:
        language_stats = await get_language_stats(username, token, excluded_list)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="User not found or API error fetching language stats",
            )
        raise e

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)
    current_streak = calculate_current_streak(contribution_data)

    # Get profile visitors count
    profile_visitors = await get_profile_views(username)

    response = GitHubStatsResponse(
        status="success",
        message="retrieved",
        topLanguages=language_stats,
        totalCommits=total_commits,
        longestStreak=longest_streak,
        currentStreak=current_streak,
        profile_visitors=profile_visitors,
        contributions=contribution_data,
    )
    return response


@analytics_router.get(
    "/{username}/star-lists",
    tags=["User Analytics"],
    summary="Get User's Starred Lists",
    description="""
    Retrieves the public 'Starred Lists' a user has created on GitHub (curated groups of starred repositories).

    Optional query parameter `include_repos=true` will also scrape and include the repository slugs (owner/repo) contained in each list.
    """,
    responses={
        200: {
            "description": "Successfully retrieved starred lists",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "name": "Machine Learning",
                            "url": "https://github.com/stars/username/lists/machine-learning",
                            "repositories": [
                                "pytorch/pytorch",
                                "scikit-learn/scikit-learn",
                            ],
                        }
                    ]
                }
            },
        },
        404: {"description": "User or lists not found"},
    },
)
async def get_user_star_lists(
    username: str = Path(..., description="GitHub username"),
    include_repos: bool = Query(
        False, description="Whether to also fetch repositories within each list"
    ),
):
    try:
        lists = await get_user_starred_lists(username, include_repos)
        if not lists:
            return []
        return [l.model_dump() for l in lists]
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found or API error")
        raise e
