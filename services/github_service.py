import requests
from typing import List, Dict, Optional
from datetime import datetime
import os

def execute_graphql_query(query: str, token: str) -> Dict:
    """Execute a GraphQL query against the GitHub API."""
    response = requests.post(
        'https://api.github.com/graphql',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json={'query': query}
    )
    return response.json()

def build_contribution_graph_query(user: str, year: int) -> str:
    """Build GraphQL query for contribution data for a given user and year."""
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

def get_language_stats(username: str, token: str, excluded_languages: List[str]) -> List[Dict[str, float]]:
    """Get language statistics for a GitHub user."""
    # Fetch repositories
    repos_response = requests.get(
        f"https://api.github.com/users/{username}/repos?type=all",
        headers={'Authorization': f'Bearer {token}'}
    )
    
    if repos_response.status_code != 200:
        return []
    
    repos = repos_response.json()
    
    # Fetch language data for each repository
    language_totals: Dict[str, int] = {}
    for repo in repos:
        lang_response = requests.get(
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
        {
            "name": name,
            "percentage": round((bytes / total_bytes) * 100, 2)
        }
        for name, bytes in language_totals.items()
    ]
    return sorted(language_stats, key=lambda x: x["percentage"], reverse=True)

def get_contribution_graphs(username: str, token: str, starting_year: Optional[int] = None) -> Dict:
    """Get contribution graph data for a GitHub user."""
    current_year = datetime.now().year
    
    # Get current year's contributions first
    query = build_contribution_graph_query(username, current_year)
    initial_response = execute_graphql_query(query, token)
    
    if not initial_response.get('data', {}).get('user'):
        return {}
    
    user_created_date = initial_response['data']['user']['createdAt']
    user_created_year = int(user_created_date.split('-')[0])
    minimum_year = max(starting_year or user_created_year, 2005)
    
    responses = {}
    for year in range(minimum_year, current_year + 1):
        query = build_contribution_graph_query(username, year)
        response = execute_graphql_query(query, token)
        responses[year] = response
    
    return responses

def calculate_total_commits(contribution_data: Dict) -> int:
    """Calculate total number of commits from contribution data."""
    total_commits = 0
    for year_data in contribution_data.values():
        weeks = year_data.get('data', {}).get('user', {}).get('contributionsCollection', {}).get('contributionCalendar', {}).get('weeks', [])
        for week in weeks:
            for day in week.get('contributionDays', []):
                total_commits += day.get('contributionCount', 0)
    return total_commits

def calculate_longest_streak(contribution_data: Dict) -> int:
    """Calculate the longest streak of consecutive days with contributions."""
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
