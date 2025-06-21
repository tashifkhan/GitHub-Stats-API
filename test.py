from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List, Dict, Optional
from datetime import datetime
import httpx
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import asyncio
import re
from routes.docs import docs_html_content

load_dotenv()

app = FastAPI(
    title="GitHub Analytics API",
    description="""
    An API for analyzing GitHub user statistics, including:
    * Language usage statistics
    * Contribution history
    * Commit streaks
    * Overall GitHub activity metrics
    
    Use this API to get detailed insights into GitHub user activity patterns.
    Custom API documentation page available at `/`.
    Interactive Swagger UI available at `/docs`.
    Alternative ReDoc documentation available at `/redoc`.
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "url": "https://github.com/tashifkhan/GitHub-Stats-API",
    },
)

# @app.get("/",
#     tags=["General"],
#     summary="API Documentation",
#     description="Redirects to the API documentation page")
# async def root():
#     return RedirectResponse(url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GITHUB_API = "https://api.github.com"


# Models
class LanguageData(BaseModel):
    name: str
    percentage: float


class ContributionDay(BaseModel):
    contributionCount: int
    date: str


class Week(BaseModel):
    contributionDays: List[ContributionDay]


class ContributionCalendar(BaseModel):
    weeks: List[Week]


class ContributionsCollection(BaseModel):
    contributionYears: List[int]
    contributionCalendar: Optional[ContributionCalendar]


class GithubUser(BaseModel):
    createdAt: str
    contributionsCollection: Optional[ContributionsCollection]


class GraphQLResponse(BaseModel):
    data: Optional[Dict]
    errors: Optional[List[Dict[str, str]]]


class RepoDetail(BaseModel):
    title: str
    description: Optional[str]
    live_website_url: Optional[str]
    languages: List[str]
    num_commits: int
    readme: Optional[str]


class CommitDetail(BaseModel):
    repo: str
    message: Optional[str]
    timestamp: Optional[str]
    sha: Optional[str]
    url: Optional[str]


# Helper functions
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

    query = build_contribution_graph_query(username, current_year)
    initial_response = await execute_graphql_query(query, token)

    if not initial_response.get("data", {}).get("user"):
        raise HTTPException(status_code=404, detail="User not found or API error")

    user_created_date = initial_response["data"]["user"]["createdAt"]
    user_created_year = int(user_created_date.split("-")[0])
    minimum_year = max(starting_year or user_created_year, 2005)

    responses = {}
    for year in range(minimum_year, current_year + 1):
        query = build_contribution_graph_query(username, year)
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


def _github_headers(token: str) -> Dict[str, str]:
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
        response = await client.get(commits_url, headers=_github_headers(token))
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


async def _fetch_repo_details(
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
            readme_resp = await client.get(readme_url, headers=_github_headers(token))
            if readme_resp.status_code == 200:
                readme_content_b64 = readme_resp.json().get("content")
        except Exception:
            pass

    async def get_languages():
        nonlocal languages_list
        languages_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/languages"
        try:
            languages_resp = await client.get(
                languages_url, headers=_github_headers(token)
            )
            if languages_resp.status_code == 200:
                languages_list = list(languages_resp.json().keys())
        except Exception:
            pass

    num_commits = await _get_commit_count(client, owner, repo_name, token)

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
        readme=readme_content_b64,
    )


async def _get_all_commits_for_repo_async(
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
            resp = await client.get(commits_url, headers=_github_headers(token))
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


# API Endpoints
@app.get(
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


@app.get(
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
    current_streak = calculate_current_streak(contribution_data)

    return {
        "contributions": contribution_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak,
        "currentStreak": current_streak,
    }


@app.get(
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


@app.get(
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
            repos_resp = await client.get(repos_url, headers=_github_headers(token))
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
            _fetch_repo_details(client, repo, token)
            for repo in repos
            if isinstance(repo, dict)
        ]
        results = await asyncio.gather(*tasks)

        return [res for res in results if res is not None]


@app.get(
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
            repos_resp = await client.get(repos_url, headers=_github_headers(token))
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
                    _get_all_commits_for_repo_async(
                        client, owner, repo_name, username, token
                    )
                )

        repo_commits_list = await asyncio.gather(*tasks)
        for repo_commits in repo_commits_list:
            all_commits.extend(repo_commits)

    all_commits.sort(key=lambda x: x.timestamp or "", reverse=True)
    return all_commits


@app.get("/", response_class=HTMLResponse, tags=["Documentation"])
async def get_custom_documentation():
    """
    Serves the custom HTML API documentation page.
    """
    return HTMLResponse(content=docs_html_content)


def test_new_endpoints():
    """Test the new endpoints: repos, commits, profile-views, and profile-views-badge"""
    print("\n" + "=" * 50)
    print("TESTING NEW ENDPOINTS")
    print("=" * 50)

    username = "tashifkhan"
    base_url = "http://localhost:8989"

    # Test repository details endpoint
    print(f"\n1. Testing repository details endpoint...")
    try:
        response = requests.get(f"{base_url}/{username}/repos")
        if response.status_code == 200:
            repos = response.json()
            print(
                f"✅ Repository details endpoint working! Found {len(repos)} repositories"
            )
            if repos:
                print(f"   First repo: {repos[0]['title']}")
                print(f"   Languages: {repos[0]['languages']}")
                print(f"   Commits: {repos[0]['num_commits']}")
        else:
            print(f"❌ Repository details endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Repository details endpoint error: {e}")

    # Test commit history endpoint
    print(f"\n2. Testing commit history endpoint...")
    try:
        response = requests.get(f"{base_url}/{username}/commits")
        if response.status_code == 200:
            commits = response.json()
            print(f"✅ Commit history endpoint working! Found {len(commits)} commits")
            if commits:
                print(f"   Latest commit: {commits[0]['message'][:50]}...")
                print(f"   Repository: {commits[0]['repo']}")
        else:
            print(f"❌ Commit history endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Commit history endpoint error: {e}")

    # Test profile views endpoint
    print(f"\n3. Testing profile views endpoint...")
    try:
        response = requests.get(f"{base_url}/{username}/profile-views")
        if response.status_code == 200:
            views_data = response.json()
            print(f"✅ Profile views endpoint working!")
            print(f"   Username: {views_data['username']}")
            print(f"   Views: {views_data['views']}")
            print(f"   Incremented: {views_data['incremented']}")
        else:
            print(f"❌ Profile views endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Profile views endpoint error: {e}")

    # Test profile views badge endpoint
    print(f"\n4. Testing profile views badge endpoint...")
    try:
        response = requests.get(f"{base_url}/{username}/profile-views-badge")
        if response.status_code == 200:
            print(f"✅ Profile views badge endpoint working!")
            print(f"   Content-Type: {response.headers.get('content-type')}")
            print(f"   Content length: {len(response.content)} bytes")
            print(f"   Badge URL: {base_url}/{username}/profile-views-badge")
        else:
            print(f"❌ Profile views badge endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Profile views badge endpoint error: {e}")

    # Test updated stats endpoint with profile visitors
    print(f"\n5. Testing updated stats endpoint with profile visitors...")
    try:
        response = requests.get(f"{base_url}/{username}/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Updated stats endpoint working!")
            print(f"   Profile visitors: {stats.get('profile_visitors', 'N/A')}")
            print(f"   Total commits: {stats.get('totalCommits', 'N/A')}")
            print(f"   Longest streak: {stats.get('longestStreak', 'N/A')}")
            print(f"   Current streak: {stats.get('currentStreak', 'N/A')}")
        else:
            print(f"❌ Updated stats endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Updated stats endpoint error: {e}")


if __name__ == "__main__":
    # Run the original tests
    test_language_stats()
    test_contribution_history()
    test_complete_stats()

    # Run the new endpoint tests
    test_new_endpoints()
