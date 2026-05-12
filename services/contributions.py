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


async def build_contribution_graph_query(user: str, year: int) -> str:
    start = f"{year}-01-01T00:00:00Z"
    end = f"{year}-12-31T23:59:59Z"
    return f"""
    query {{
        user(login: "{user}") {{
            createdAt
            contributionsCollection(from: "{start}", to: "{end}") {{
                contributionYears
                contributionCalendar {{
                    weeks {{
                        contributionDays {{
                            contributionCount
                            date
                        }}
                    }}
                }}
            }}
        }}
    }}
    """


async def _execute_graphql_query_with_client(
    client: httpx.AsyncClient, query: str, token: str
) -> httpx.Response:
    return await client.post(
        "https://api.github.com/graphql",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
    )


async def get_contribution_graphs(
    username: str, token: str, starting_year: Optional[int] = None
) -> Dict:
    current_year = datetime.now().year

    async with httpx.AsyncClient() as client:
        query = await build_contribution_graph_query(username, current_year)
        initial_response = (
            await _execute_graphql_query_with_client(client, query, token)
        ).json()

        if not initial_response.get("data", {}).get("user"):
            raise HTTPException(status_code=404, detail="User not found or API error")

        user_created_date = initial_response["data"]["user"]["createdAt"]
        user_created_year = int(user_created_date.split("-")[0])
        minimum_year = max(starting_year or user_created_year, 2005)
        years = list(range(minimum_year, current_year + 1))

        semaphore = asyncio.Semaphore(6)

        async def fetch_year(year: int):
            year_query = await build_contribution_graph_query(username, year)
            async with semaphore:
                year_response = await _execute_graphql_query_with_client(
                    client, year_query, token
                )
            return year, year_response.json()

        year_results = await asyncio.gather(*(fetch_year(year) for year in years))
        return {year: data for year, data in sorted(year_results, key=lambda x: x[0])}


def calculate_total_commits(contribution_data: Dict) -> int:
    total_commits = 0
    for year_data in contribution_data.values():
        weeks = (
            year_data.get("data", {})
            .get("user", {})
            .get("contributionsCollection", {})
            .get("contributionCalendar", {})
            .get("weeks", [])
        )
        for week in weeks:
            for day in week.get("contributionDays", []):
                total_commits += day.get("contributionCount", 0)
    return total_commits


def calculate_longest_streak(contribution_data: Dict) -> int:
    current_streak = 0
    longest_streak = 0
    all_days = []

    for year_data in contribution_data.values():
        weeks = (
            year_data.get("data", {})
            .get("user", {})
            .get("contributionsCollection", {})
            .get("contributionCalendar", {})
            .get("weeks", [])
        )
        for week in weeks:
            all_days.extend(week.get("contributionDays", []))

    all_days.sort(key=lambda x: x["date"])

    for day in all_days:
        if day["contributionCount"] > 0:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0

    return longest_streak


def calculate_current_streak(contribution_data: Dict) -> int:
    """
    Calculates the current contribution streak from a user's GitHub contribution data.
    The current streak is the number of consecutive days where the user made at least
    one contribution, counting backwards from the most recent contribution day.

    Args:
        contribution_data: A dictionary containing the user's contribution data,
                          typically from the GitHub GraphQL API.

    Returns:
        The length of the current contribution streak in days.
    """
    all_days = []

    # Collect all contribution days from all years
    for year_data in contribution_data.values():
        weeks = (
            year_data.get("data", {})
            .get("user", {})
            .get("contributionsCollection", {})
            .get("contributionCalendar", {})
            .get("weeks", [])
        )
        for week in weeks:
            all_days.extend(week.get("contributionDays", []))

    if not all_days:
        return 0

    # Sort days by date in descending order (most recent first)
    all_days.sort(key=lambda x: x["date"], reverse=True)

    # Get today's date and the most recent data date
    today = datetime.now().date()
    most_recent_data_date = datetime.strptime(all_days[0]["date"], "%Y-%m-%d").date()

    # If the most recent data is more than 2 days old, no current streak
    days_diff = (today - most_recent_data_date).days
    if days_diff > 2:
        return 0

    current_streak = 0
    last_contribution_date = None

    # Calculate current streak from most recent day backwards
    for day in all_days:
        day_date = datetime.strptime(day["date"], "%Y-%m-%d").date()

        if day["contributionCount"] > 0:
            # If this is the first contribution or consecutive with the last one
            if last_contribution_date is None:
                current_streak = 1
                last_contribution_date = day_date
            else:
                days_between = (last_contribution_date - day_date).days
                if days_between <= 1:  # Consecutive or same day
                    current_streak += 1
                    last_contribution_date = day_date
                else:
                    # Gap found, current streak ends
                    break
        else:
            # No contribution on this day
            if last_contribution_date is not None:
                # Check if this gap is acceptable (only 1 day gap)
                gap_days = (last_contribution_date - day_date).days
                if gap_days > 1:
                    # Gap is too long, streak ends
                    break

    return current_streak
