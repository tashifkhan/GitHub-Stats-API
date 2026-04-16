from fastapi import APIRouter, Depends, Path, Query
from typing import Any, Dict, List, Optional

from modules.github import (
    CommitDetail,
    GitHubStatsResponse,
    LanguageData,
    RepoDetail,
    StarsData,
)
from routes.dependencies import (
    DEFAULT_EXCLUDED_LANGUAGES,
    get_analytics_service,
    parse_excluded_languages,
)
from services.analytics_service import AnalyticsService

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
    exclude: Optional[str] = Query(
        None,
        description="Comma-separated list of languages to exclude (preferred)",
    ),
    excluded: Optional[List[str]] = Query(
        None,
        description="Languages to exclude from the statistics (legacy parameter)",
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> List[LanguageData]:
    excluded_languages = parse_excluded_languages(
        exclude=exclude,
        excluded=excluded,
        default=DEFAULT_EXCLUDED_LANGUAGES,
    )
    return await analytics_service.get_user_language_stats(username, excluded_languages)


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
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> Dict:
    return await analytics_service.get_user_contributions(username, starting_year)


@analytics_router.get(
    "/{username}/stars",
    tags=["Dashboard Details"],
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
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> StarsData:
    return await analytics_service.get_user_stars(username)


@analytics_router.get(
    "/{username}/pinned",
    tags=["Dashboard Details"],
    summary="Get User's Pinned Repositories",
    description="""
    Retrieves a user's pinned repositories (up to 6) using the GitHub GraphQL API.

    Includes: name, description, URL, star count, fork count, and primary language.
    """,
    responses={
        200: {
            "description": "Successfully retrieved pinned repositories",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "name": "awesome-project",
                            "description": "An awesome pinned project",
                            "url": "https://github.com/user/awesome-project",
                            "stars": 123,
                            "forks": 10,
                            "primary_language": "Python",
                        }
                    ]
                }
            },
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"},
    },
)
async def get_user_pinned(
    username: str = Path(
        ...,
        description="GitHub username",
    ),
    first: int = Query(
        6,
        ge=1,
        le=6,
        description="Number of pinned repositories to fetch (1-6)",
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    return await analytics_service.get_user_pinned(username, first)


@analytics_router.get(
    "/{username}/repos",
    tags=["Dashboard Details"],
    summary="Get User's Repository Details",
    description="""
    Retrieves detailed information for each of the user's public repositories including:
    
    - Repository name and description
    - Live website URL (if available in description)
    - Programming languages used
    - Number of commits
    - Number of stars
    - README content (decoded Markdown)
    - Latest releases (including release notes and asset download links)
    
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
                            "readme": "# RepoName\n\nProject documentation in Markdown.",
                            "releases": [
                                {
                                    "id": 123456,
                                    "tag_name": "v1.2.0",
                                    "name": "v1.2.0",
                                    "body": "## Changelog\n\n- Added new feature",
                                    "url": "https://github.com/user/repo/releases/tag/v1.2.0",
                                    "draft": False,
                                    "prerelease": False,
                                    "created_at": "2024-01-01T00:00:00Z",
                                    "published_at": "2024-01-01T01:00:00Z",
                                    "assets": [
                                        {
                                            "name": "repo-v1.2.0.zip",
                                            "download_url": "https://github.com/user/repo/releases/download/v1.2.0/repo-v1.2.0.zip",
                                            "size": 102400,
                                            "download_count": 250,
                                            "content_type": "application/zip",
                                            "updated_at": "2024-01-01T01:05:00Z",
                                        }
                                    ],
                                }
                            ],
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
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> List[RepoDetail]:
    return await analytics_service.get_user_repos(username)


@analytics_router.get(
    "/{username}/commits",
    tags=["Dashboard Details"],
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
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> List[CommitDetail]:
    return await analytics_service.get_user_commits(username)


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
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> Dict[str, Any]:
    return await analytics_service.get_profile_views_count(username, increment, base)


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
    excluded: Optional[List[str]] = Query(
        None,
        description="Legacy list-style language exclusions",
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> GitHubStatsResponse:
    excluded_list = parse_excluded_languages(
        exclude=exclude,
        excluded=excluded,
        default=[],
    )

    return await analytics_service.get_user_stats(username, excluded_list)


@analytics_router.get(
    "/{username}/star-lists",
    tags=["Dashboard Details"],
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
        True, description="Whether to also fetch repositories within each list"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
):
    return await analytics_service.get_user_star_lists(username, include_repos)
