import asyncio
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
from modules.github import LanguageData
import os
from services.github_service import *

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
    "/{username}/stats",
    tags=["User Analytics"],
    summary="Get User's Complete Statistics",
    description="""
    Retrieves comprehensive GitHub statistics for a user, combining:
    
    - Top programming languages
    - Total contribution count
    - Longest contribution streak
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
                        "contributions": None,
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
        error_response = GitHubStatsResponse.error(
            status="error", message="GitHub token not configured"
        )
        return JSONResponse(content=error_response.model_dump(), status_code=500)

    excluded_list = exclude.split(",") if exclude else []

    try:
        contribution_data = await get_contribution_graphs(username, token)
    except HTTPException as e:
        if e.status_code == 404:
            error_response = GitHubStatsResponse.error(
                status="error",
                message="User not found or API error fetching contributions",
            )
            return JSONResponse(content=error_response.model_dump(), status_code=404)
        error_response = GitHubStatsResponse.error(
            status="error", message=str(e.detail)
        )
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=getattr(e, "status_code", 500),
        )

    try:
        language_stats = await get_language_stats(username, token, excluded_list)

    except HTTPException as e:
        if e.status_code == 404:
            error_response = GitHubStatsResponse.error(
                status="error",
                message="User not found or API error fetching language stats",
            )
            return JSONResponse(content=error_response.model_dump(), status_code=404)

        error_response = GitHubStatsResponse.error(
            status="error", message=str(e.detail)
        )
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=getattr(e, "status_code", 500),
        )

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)
    current_streak = calculate_current_streak(contribution_data)

    response = GitHubStatsResponse(
        status="success",
        message="retrieved",
        topLanguages=language_stats,
        totalCommits=total_commits,
        longestStreak=longest_streak,
        currentStreak=current_streak,
        contributions=contribution_data,
    )
    return response
