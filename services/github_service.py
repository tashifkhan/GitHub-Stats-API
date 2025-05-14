import requests
from typing import List, Dict, Optional, Any
from datetime import datetime
import os
import re
import base64

from modules.github import RepoDetail, CommitDetail

GITHUB_API = "https://api.github.com"

def _github_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _extract_url_from_description(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    match = re.search(r'(https?://[^\s]+)', description)
    return match.group(1) if match else None

def _get_commit_count(owner: str, repo_name: str, token: str) -> int:
    commits_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/commits?per_page=1"
    try:
        response = requests.get(commits_url, headers=_github_headers(token))
        
        if response.status_code == 200:
            link_header = response.headers.get('Link')
            if link_header:
                match = re.search(r'<.*?page=(\d+)>; rel="last"', link_header)
                if match:
                    return int(match.group(1))
            # No 'last' link, implies a single page of results or an empty repo if per_page=1 was used.
            # If per_page=1, and the response is 200, then response.json() will be a list with one commit object, or an empty list.
            page_commits = response.json()
            return 1 if isinstance(page_commits, list) and page_commits else 0

        elif response.status_code == 409: # Empty repository
            return 0
        elif response.status_code in [404, 403]: # Not found or forbidden
            return 0
        
        # For other status codes that are not 200, 409, 404, 403, raise an error.
        response.raise_for_status() 
        return 0 # Should ideally not be reached if raise_for_status() is effective.
        
    except requests.exceptions.HTTPError: # Catch errors from raise_for_status()
        # Log error or handle as needed, returning 0 for now.
        return 0
    except requests.exceptions.RequestException: # Network error, timeout, etc.
        return 0
    except (ValueError, TypeError): # JSON parsing error or unexpected structure from response.json()
        return 0

def _fetch_repo_details(repo_data: Dict[str, Any], token: str) -> Optional[RepoDetail]:
    repo_name = repo_data.get("name")
    owner_data = repo_data.get("owner")
    if not repo_name or not owner_data or not isinstance(owner_data, dict):
        return None
    owner = owner_data.get("login")
    if not owner:
        return None

    readme_content_b64 = None
    languages_list = []

    readme_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/readme"
    try:
        readme_resp = requests.get(readme_url, headers=_github_headers(token))
        if readme_resp.status_code == 200:
            readme_content_b64 = readme_resp.json().get("content")
    except requests.exceptions.RequestException:
        pass

    languages_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/languages"
    try:
        languages_resp = requests.get(languages_url, headers=_github_headers(token))
        if languages_resp.status_code == 200:
            languages_list = list(languages_resp.json().keys())
    except requests.exceptions.RequestException:
        pass

    num_commits = _get_commit_count(owner, repo_name, token)

    description = repo_data.get("description")
    homepage_url = repo_data.get("homepage")
    live_url = None

    if homepage_url and isinstance(homepage_url, str) and homepage_url.startswith(('http://', 'https://')):
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

def get_user_repos(username: str, token: str) -> List[RepoDetail]:
    repos_url = f"{GITHUB_API}/users/{username}/repos?per_page=100&type=owner&sort=pushed"
    detailed_repos: List[RepoDetail] = []
    try:
        repos_resp = requests.get(repos_url, headers=_github_headers(token))
        if repos_resp.status_code == 404:
            return []
        repos_resp.raise_for_status()
        repos_data = repos_resp.json()

        if not isinstance(repos_data, list):
            return []

        for repo_item in repos_data:
            if isinstance(repo_item, dict):
                details = _fetch_repo_details(repo_item, token)
                if details:
                    detailed_repos.append(details)
        return detailed_repos
    except requests.exceptions.RequestException:
        return []
    except ValueError:
        return []

def _get_all_commits_for_repo(owner: str, repo_name: str, username: str, token: str) -> List[CommitDetail]:
    commits_data: List[CommitDetail] = []
    page = 1
    per_page = 100
    while True:
        commits_url = (
            f"{GITHUB_API}/repos/{owner}/{repo_name}/commits"
            f"?author={username}&per_page={per_page}&page={page}"
        )
        try:
            resp = requests.get(commits_url, headers=_github_headers(token))
            if resp.status_code != 200:
                break
            page_commits = resp.json()
            if not page_commits or not isinstance(page_commits, list):
                break
            
            for commit_item in page_commits:
                if not isinstance(commit_item, dict): continue
                commit_details_dict = commit_item.get("commit", {})
                if not isinstance(commit_details_dict, dict): continue
                author_details_dict = commit_details_dict.get("author", {})
                if not isinstance(author_details_dict, dict): continue
                
                commits_data.append(CommitDetail(
                    repo=repo_name,
                    message=commit_details_dict.get("message"),
                    timestamp=author_details_dict.get("date"),
                    sha=commit_item.get("sha"),
                    url=commit_item.get("html_url"),
                ))
            
            if len(page_commits) < per_page:
                break
            page += 1
        except requests.exceptions.RequestException:
            break
        except ValueError:
            break
    return commits_data

def get_user_commit_history(username: str, token: str) -> List[CommitDetail]:
    all_commits: List[CommitDetail] = []
    repos_url = f"{GITHUB_API}/users/{username}/repos?per_page=100&type=owner"
    try:
        repos_resp = requests.get(repos_url, headers=_github_headers(token))
        if repos_resp.status_code == 404:
            return []
        repos_resp.raise_for_status()
        repos_data = repos_resp.json()

        if not isinstance(repos_data, list):
            return []

        for repo_item in repos_data:
            if isinstance(repo_item, dict) and "name" in repo_item:
                owner_data = repo_item.get("owner")
                if isinstance(owner_data, dict) and "login" in owner_data:
                    repo_name = repo_item["name"]
                    owner = owner_data["login"]
                    if owner == username:
                         repo_commits = _get_all_commits_for_repo(owner, repo_name, username, token)
                         all_commits.extend(repo_commits)
    
    except requests.exceptions.RequestException:
        return []
    except ValueError:
        return []

    all_commits.sort(key=lambda x: x.timestamp or "", reverse=True)
    return all_commits

def execute_graphql_query(query: str, token: str) -> Dict:
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
    repos_response = requests.get(
        f"https://api.github.com/users/{username}/repos?type=all",
        headers={'Authorization': f'Bearer {token}'}
    )
    
    if repos_response.status_code != 200:
        return []
    
    repos = repos_response.json()
    
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
    current_year = datetime.now().year
    
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
