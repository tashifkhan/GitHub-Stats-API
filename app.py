# app.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from typing import List, Dict, Optional
from datetime import datetime
import httpx
import os
from dotenv import load_dotenv
from pydantic import BaseModel
import asyncio

# Load environment variables
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
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "url": "https://github.com/yourusername/github-analytics-api",
    },
)

@app.get("/",
    tags=["General"],
    summary="API Documentation",
    description="Redirects to the API documentation page")
async def root():
    return RedirectResponse(url="/docs")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Helper functions
async def execute_graphql_query(query: str, token: str) -> Dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.github.com/graphql',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            json={'query': query}
        )
        return response.json()

def build_contribution_graph_query(user: str, year: int) -> str:
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

async def get_language_stats(username: str, token: str, excluded_languages: List[str]) -> List[LanguageData]:
    async with httpx.AsyncClient() as client:
        # Fetch repositories
        repos_response = await client.get(
            f"https://api.github.com/users/{username}/repos",
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if repos_response.status_code != 200:
            raise HTTPException(status_code=404, detail="User not found or API error")
        
        repos = repos_response.json()
        
        # Fetch language data for each repository
        language_totals: Dict[str, int] = {}
        for repo in repos:
            lang_response = await client.get(
                repo['languages_url'],
                headers={'Authorization': f'Bearer {token}'}
            )
            if lang_response.status_code == 200:
                langs = lang_response.json()
                for lang, bytes in langs.items():
                    if lang not in excluded_languages:
                        language_totals[lang] = language_totals.get(lang, 0) + bytes

        # Calculate percentages
        total_bytes = sum(language_totals.values())
        if total_bytes == 0:
            return []

        language_stats = [
            LanguageData(
                name=name,
                percentage=round((bytes / total_bytes) * 100)
            )
            for name, bytes in language_totals.items()
        ]

        # Sort by percentage and get top 5
        return sorted(language_stats, key=lambda x: x.percentage, reverse=True)[:5]

async def get_contribution_graphs(username: str, token: str, starting_year: Optional[int] = None) -> Dict:
    current_year = datetime.now().year
    
    # Get current year's contributions first
    query = build_contribution_graph_query(username, current_year)
    initial_response = await execute_graphql_query(query, token)
    
    if not initial_response.get('data', {}).get('user'):
        raise HTTPException(status_code=404, detail="User not found or API error")
    
    user_created_date = initial_response['data']['user']['createdAt']
    user_created_year = int(user_created_date.split('-')[0])
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
        weeks = year_data.get('data', {}).get('user', {}).get('contributionsCollection', {}).get('contributionCalendar', {}).get('weeks', [])
        for week in weeks:
            for day in week.get('contributionDays', []):
                total_commits += day.get('contributionCount', 0)
    return total_commits

def calculate_longest_streak(contribution_data: Dict) -> int:
    current_streak = 0
    longest_streak = 0
    all_days = []
    
    for year_data in contribution_data.values():
        weeks = year_data.get('data', {}).get('user', {}).get('contributionsCollection', {}).get('contributionCalendar', {}).get('weeks', [])
        for week in weeks:
            all_days.extend(week.get('contributionDays', []))
    
    all_days.sort(key=lambda x: x['date'])
    
    for day in all_days:
        if day['contributionCount'] > 0:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0
            
    return longest_streak

# Routes
@app.get("/{username}/languages",
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
                        {"name": "C++", "percentage": 3}
                    ]
                }
            }
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"}
    })
async def get_user_language_stats(
    username: str,
    excluded: List[str] = Query(
        default=["Markdown", "JSON", "YAML", "XML"],
        description="Languages to exclude from the statistics"
    )
) -> List[LanguageData]:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")
    return await get_language_stats(username, token, excluded)

@app.get("/{username}/contributions",
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
                        "contributions": {"2023": {"data": {"user": {"contributionsCollection": {"weeks": []}}}}},
                        "totalCommits": 1234,
                        "longestStreak": 30
                    }
                }
            }
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"}
    })
async def get_user_contributions(
    username: str,
    starting_year: Optional[int] = Query(
        None,
        description="Starting year for contribution history (defaults to account creation year)"
    )
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
        "longestStreak": longest_streak
    }

@app.get("/{username}/stats",
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
                        "topLanguages": [
                            {"name": "Python", "percentage": 45}
                        ],
                        "totalCommits": 1234,
                        "longestStreak": 30
                    }
                }
            }
        },
        404: {"description": "User not found"},
        500: {"description": "GitHub token configuration error"}
    })
async def get_user_stats(
    username: str,
    exclude: Optional[str] = Query(
        None,
        description="Comma-separated list of languages to exclude"
    )
):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    # Parse excluded languages from query parameter
    excluded_list = exclude.split(",") if exclude else []

    # Fetch contributions and languages concurrently
    contribution_data, language_stats = await asyncio.gather(
        get_contribution_graphs(username, token),
        get_language_stats(username, token, excluded_list)
    )

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)

    return {
        "topLanguages": language_stats,
        "totalCommits": total_commits,
        "longestStreak": longest_streak
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000)
