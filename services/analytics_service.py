from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from models.analytics import GitHubStatsResponse, LanguageData
from models.commits import CommitDetail
from models.repositories import RepoDetail
from models.stars import StarsData
from services.achievements import get_user_achievements
from services.commits import get_all_commits
from services.contributions import (
    calculate_current_streak,
    calculate_longest_streak,
    calculate_total_commits,
    get_contribution_graphs,
)
from services.languages import get_language_stats
from services.profile import (
    get_user_pinned_repos,
    get_user_profile,
    get_user_social_accounts,
)
from services.pull_requests import (
    get_user_pr_count,
    get_user_issue_count,
    get_user_review_count,
)
from services.repositories import get_repo_details
from services.stars import (
    get_user_starred_lists,
    get_user_stars_data,
)
from services.profile_views_service import get_profile_views, increment_profile_views


class AnalyticsService:
    def __init__(self, token: str):
        self.token = token

    async def get_user_language_stats(
        self, username: str, excluded_languages: List[str]
    ) -> List[LanguageData]:
        return await get_language_stats(username, self.token, excluded_languages)

    async def get_user_profile(self, username: str) -> Dict[str, Any]:
        return await get_user_profile(username, self.token)

    async def get_user_social_accounts(self, username: str) -> List[Dict[str, Any]]:
        return await get_user_social_accounts(username, self.token)

    async def get_user_achievements(self, username: str) -> List[Dict[str, Any]]:
        return await get_user_achievements(username)

    async def get_user_contributions(
        self, username: str, starting_year: Optional[int]
    ) -> Dict[str, Any]:
        contribution_data = await get_contribution_graphs(
            username, self.token, starting_year
        )
        return {
            "contributions": contribution_data,
            "totalCommits": calculate_total_commits(contribution_data),
            "longestStreak": calculate_longest_streak(contribution_data),
            "currentStreak": calculate_current_streak(contribution_data),
        }

    async def get_user_stars(self, username: str) -> StarsData:
        try:
            return await get_user_stars_data(username, self.token)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="User not found or API error"
                )
            raise exc

    async def get_user_pinned(self, username: str, first: int):
        try:
            return await get_user_pinned_repos(username, self.token, first)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="User not found or API error"
                )
            raise exc

    async def get_user_repos(self, username: str) -> List[RepoDetail]:
        try:
            return await get_repo_details(username, self.token)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="User not found or API error"
                )
            raise exc

    async def get_user_commits(self, username: str) -> List[CommitDetail]:
        try:
            return await get_all_commits(username, self.token)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="User not found or API error"
                )
            raise exc

    async def get_profile_views_count(
        self, username: str, increment: bool, base: Optional[int]
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

        views = await get_profile_views(username)
        return {"username": username, "views": views, "incremented": False}

    async def get_user_stats(
        self, username: str, excluded_languages: List[str]
    ) -> GitHubStatsResponse:
        try:
            contribution_data = await get_contribution_graphs(username, self.token)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="User not found or API error fetching contributions",
                )
            raise exc

        try:
            language_stats = await get_language_stats(
                username, self.token, excluded_languages
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="User not found or API error fetching language stats",
                )
            raise exc

        return GitHubStatsResponse(
            status="success",
            message="retrieved",
            topLanguages=language_stats,
            totalCommits=calculate_total_commits(contribution_data),
            longestStreak=calculate_longest_streak(contribution_data),
            currentStreak=calculate_current_streak(contribution_data),
            profile_visitors=await get_profile_views(username),
            contributions=contribution_data,
        )

    async def get_user_star_lists(self, username: str, include_repos: bool):
        try:
            lists = await get_user_starred_lists(username, include_repos)
            if not lists:
                return []
            return [item.model_dump() for item in lists]
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(
                    status_code=404, detail="User not found or API error"
                )
            raise exc

    async def get_user_pr_count(self, username: str) -> int:
        return await get_user_pr_count(username, self.token)

    async def get_user_issue_count(self, username: str) -> int:
        return await get_user_issue_count(username, self.token)

    async def get_user_review_count(self, username: str) -> int:
        return await get_user_review_count(username, self.token)
