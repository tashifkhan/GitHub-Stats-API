from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List, Dict, Optional
from modules.github import *
from datetime import datetime
import httpx
import asyncio
import re

GITHUB_API = "https://api.github.com"


async def execute_graphql_query(query: str, token: str) -> Dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.github.com/graphql",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query},
        )
        return response.json()


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


async def get_language_stats(
    username: str, token: str, excluded_languages: List[str]
) -> List[LanguageData]:
    async with httpx.AsyncClient() as client:
        repos_response = await client.get(
            f"https://api.github.com/users/{username}/repos",
            headers={"Authorization": f"Bearer {token}"},
        )

        if repos_response.status_code != 200:
            raise HTTPException(status_code=404, detail="User not found or API error")

        repos = repos_response.json()

        language_totals: Dict[str, int] = {}
        for repo in repos:
            lang_response = await client.get(
                repo["languages_url"], headers={"Authorization": f"Bearer {token}"}
            )
            if lang_response.status_code == 200:
                langs = lang_response.json()
                for lang, bytes in langs.items():
                    if lang not in excluded_languages:
                        language_totals[lang] = language_totals.get(lang, 0) + bytes

        total_bytes = sum(language_totals.values())
        if total_bytes == 0:
            return []

        language_stats = [
            LanguageData(name=name, percentage=round((bytes / total_bytes) * 100, 2))
            for name, bytes in language_totals.items()
        ]
        return sorted(language_stats, key=lambda x: x.percentage, reverse=True)


async def get_contribution_graphs(
    username: str, token: str, starting_year: Optional[int] = None
) -> Dict:
    current_year = datetime.now().year

    query = await build_contribution_graph_query(username, current_year)
    initial_response = await execute_graphql_query(query, token)

    if not initial_response.get("data", {}).get("user"):
        raise HTTPException(status_code=404, detail="User not found or API error")

    user_created_date = initial_response["data"]["user"]["createdAt"]
    user_created_year = int(user_created_date.split("-")[0])
    minimum_year = max(starting_year or user_created_year, 2005)

    responses = {}
    for year in range(minimum_year, current_year + 1):
        query = await build_contribution_graph_query(username, year)
        response = await execute_graphql_query(query, token)
        responses[year] = response

    return responses


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


async def fetch_repo_details(
    client: httpx.AsyncClient, repo: Dict, token: str
) -> Optional[RepoDetail]:
    repo_name = repo["name"]
    owner = repo["owner"]["login"]

    readme_content_b64 = None
    languages_list = []

    async def get_readme():
        nonlocal readme_content_b64
        readme_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/readme"
        try:
            readme_resp = await client.get(readme_url, headers=github_headers(token))
            if readme_resp.status_code == 200:
                readme_content_b64 = readme_resp.json().get("content")
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

    num_commits = await _get_commit_count(client, owner, repo_name, token)
    stars_count = repo.get("stargazers_count", 0)

    await asyncio.gather(get_readme(), get_languages())

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
        readme=readme_content_b64,
    )


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
            valid_repo_details = [
                detail
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


async def get_user_pull_requests(username: str, token: str) -> List[PullRequestDetail]:
    """
    Fetch all pull requests created by the user across their public repositories.
    The state field will be 'merged' if merged, 'closed' if closed but not merged, or 'open' if still open.
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

            pull_requests: List[PullRequestDetail] = []
            for repo in repos:
                repo_name = repo["name"]
                owner = repo["owner"]["login"]
                page = 1
                per_page = 100
                while True:
                    pulls_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/pulls?state=all&per_page={per_page}&page={page}"  # all states
                    pulls_resp = await client.get(
                        pulls_url, headers=github_headers(token)
                    )
                    if pulls_resp.status_code != 200:
                        break
                    pulls = pulls_resp.json()
                    if not pulls:
                        break
                    for pr in pulls:
                        # Only include PRs created by the user
                        if pr["user"]["login"].lower() != username.lower():
                            continue
                        merged_at = pr.get("merged_at")
                        closed_at = pr.get("closed_at")
                        if merged_at:
                            pr_state = "merged"
                        elif closed_at:
                            pr_state = "closed"
                        else:
                            pr_state = pr.get("state", "open")
                        pull_requests.append(
                            PullRequestDetail(
                                repo=repo_name,
                                number=pr["number"],
                                title=pr["title"],
                                state=pr_state,
                                created_at=pr["created_at"],
                                updated_at=pr["updated_at"],
                                closed_at=closed_at,
                                merged_at=merged_at,
                                user=pr["user"]["login"],
                                url=pr["html_url"],
                                body=pr.get("body"),
                            )
                        )
                    if len(pulls) < per_page:
                        break
                    page += 1
            return pull_requests
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            raise HTTPException(status_code=500, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching pull requests: {str(e)}"
            )


async def get_organization_contributions(
    username: str, token: str, orgs: Optional[List[str]] = None
) -> List[OrganizationContribution]:
    """
    Find all organizations where the user has contributed (via merged PRs), regardless of membership.
    Uses the GitHub Search API to find all merged PRs by the user, then groups repos by organization.
    """
    async with httpx.AsyncClient() as client:
        per_page = 100
        page = 1
        org_repo_map = {}
        org_meta_map = {}
        while True:
            search_url = f"{GITHUB_API}/search/issues?q=type:pr+author:{username}+is:merged&per_page={per_page}&page={page}"
            resp = await client.get(search_url, headers=github_headers(token))
            if resp.status_code != 200:
                break
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for pr in items:
                repo_url = pr.get("repository_url")
                if not repo_url:
                    continue
                # repo_url: https://api.github.com/repos/{org}/{repo}
                parts = repo_url.split("/")
                if len(parts) < 2:
                    continue
                org_login = parts[-2]
                repo_name = parts[-1]
                if org_login not in org_repo_map:
                    org_repo_map[org_login] = set()
                org_repo_map[org_login].add(repo_name)
                if org_login not in org_meta_map:
                    # Fetch org meta (id, avatar_url)
                    org_api_url = f"{GITHUB_API}/orgs/{org_login}"
                    org_resp = await client.get(
                        org_api_url, headers=github_headers(token)
                    )
                    if org_resp.status_code == 200:
                        org_data = org_resp.json()
                        org_meta_map[org_login] = {
                            "id": org_data.get("id", 0),
                            "avatar_url": org_data.get("avatar_url", ""),
                        }
                    else:
                        org_meta_map[org_login] = {"id": 0, "avatar_url": ""}
            if len(items) < per_page:
                break
            page += 1
        org_contributions = []
        for org_login, repos in org_repo_map.items():
            meta = org_meta_map.get(org_login, {"id": 0, "avatar_url": ""})
            org_contributions.append(
                OrganizationContribution(
                    org=org_login,
                    org_id=meta["id"],
                    org_url=f"https://github.com/{org_login}",
                    org_avatar_url=meta["avatar_url"],
                    repos=sorted(list(repos)),
                )
            )
        return org_contributions
