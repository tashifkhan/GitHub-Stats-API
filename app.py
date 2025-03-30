from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from typing import List, Dict, Optional
from datetime import datetime
import httpx
import os
from dotenv import load_dotenv
from dataclasses import dataclass, asdict
import requests

load_dotenv()

@dataclass
class GitHubStatsResponse:
    status: str
    message: str
    topLanguages: List[Dict[str, float]]
    totalCommits: int
    longestStreak: int
    contributions: Optional[Dict] = None

    @classmethod
    def error(cls, status: str, message: str):
        return cls(
            status=status,
            message=message,
            topLanguages=[],
            totalCommits=0,
            longestStreak=0
        )





@dataclass
class LanguageData:
    name: str
    percentage: float

@dataclass
class ContributionDay:
    contributionCount: int
    date: str

@dataclass
class Week:
    contributionDays: List[ContributionDay]

@dataclass
class ContributionCalendar:
    weeks: List[Week]

@dataclass
class ContributionsCollection:
    contributionYears: List[int]
    contributionCalendar: Optional[ContributionCalendar]

@dataclass
class GithubUser:
    createdAt: str
    contributionsCollection: Optional[ContributionsCollection]

# Helper functions
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

app = Flask(__name__)
CORS(app)
# Routes
@app.route('/')
def docs():
    html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>GitHub Stats API Documentation</title>
            <style>
                :root {
                    --primary-color: #e4e4e4;
                    --secondary-color: #64ffda;
                    --background-color: #0a192f;
                    --code-background: #112240;
                    --text-color: #8892b0;
                    --heading-color: #ccd6f6;
                    --card-background: #112240;
                    --hover-color: #233554;
                }
                body {
                    font-family: 'SF Mono', 'Fira Code', 'Monaco', monospace;
                    line-height: 1.6;
                    color: var(--text-color);
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 4rem 2rem;
                    background: var(--background-color);
                    transition: all 0.25s ease-in-out;
                }
                h1, h2, h3 {
                    color: var(--heading-color);
                    padding-bottom: 0.75rem;
                    margin-top: 2rem;
                    font-weight: 600;
                    letter-spacing: -0.5px;
                }
                h1 {
                    font-size: clamp(1.8rem, 4vw, 2.5rem);
                    margin-bottom: 2rem;
                    border-bottom: 2px solid var(--secondary-color);
                }
                .endpoint {
                    background: var(--card-background);
                    border-radius: 12px;
                    padding: 0;
                    margin: 1.5rem 0;
                    box-shadow: 0 10px 30px -15px rgba(2,12,27,0.7);
                    border: 1px solid var(--hover-color);
                    transition: all 0.2s ease-in-out;
                    overflow: hidden;
                }
                .endpoint-header {
                    padding: 1.5rem;
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    transition: background-color 0.2s ease;
                }
                .endpoint-header:hover {
                    background-color: var(--hover-color);
                }
                .endpoint-header h2 {
                    margin: 0;
                    padding: 0;
                    border: none;
                }
                .endpoint-content {
                    max-height: 0;
                    overflow: hidden;
                    transition: max-height 0.3s ease;
                    padding: 0 1.5rem;
                }
                .endpoint.active .endpoint-content {
                    max-height: 5000px; /* Large enough to show all content */
                    padding: 0 1.5rem 1.5rem;
                }
                .endpoint-toggle {
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: var(--secondary-color);
                    transition: transform 0.3s ease;
                }
                .endpoint.active .endpoint-toggle {
                    transform: rotate(45deg);
                }
                code {
                    background: var(--code-background);
                    color: var(--secondary-color);
                    padding: 0.3rem 0.6rem;
                    border-radius: 6px;
                    font-family: 'SF Mono', 'Fira Code', monospace;
                    font-size: 0.85em;
                    word-break: break-word;
                    white-space: pre-wrap;
                }
                pre {
                    background: var(--code-background);
                    padding: 1.5rem;
                    border-radius: 12px;
                    overflow-x: auto;
                    margin: 1.5rem 0;
                    border: 1px solid var(--hover-color);
                    position: relative;
                }
                pre code {
                    padding: 0;
                    background: none;
                    color: var(--primary-color);
                    font-size: 0.9em;
                }
                .parameter {
                    margin: 1.5rem 0;
                    padding: 1.25rem;
                    background: var(--hover-color);
                    border-radius: 8px;
                    box-shadow: 0 4px 12px -6px rgba(2,12,27,0.4);
                    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
                }
                .parameter:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 16px -6px rgba(2,12,27,0.5);
                }
                .parameter code {
                    font-size: 0.95em;
                    font-weight: 500;
                    margin-right: 0.5rem;
                }
                .error-response {
                    padding: 1.25rem;
                    margin: 1.25rem 0;
                    background: var(--hover-color);
                    border-radius: 8px;
                    overflow-x: auto;
                }
                .note {
                    background: var(--hover-color);
                    padding: 1.25rem;
                    margin: 1.25rem 0;
                    border-radius: 8px;
                }
                @media (max-width: 768px) {
                    body {
                        padding: 1rem 0.75rem;
                    }
                    .endpoint-header {
                        padding: 1.25rem;
                    }
                    pre {
                        padding: 1rem;
                        font-size: 0.9em;
                    }
                    code {
                        font-size: 0.8em;
                    }
                }
                @media (max-width: 480px) {
                    body {
                        padding: 1rem 0.5rem;
                    }
                    .endpoint-header {
                        padding: 1rem;
                    }
                    h1 {
                        font-size: 1.8rem;
                    }
                    pre {
                        padding: 0.75rem;
                        font-size: 0.85em;
                    }
                    .parameter, .error-response, .note {
                        padding: 1rem;
                        margin: 1rem 0;
                    }
                }
                .method {
                    color: #ff79c6;
                    font-weight: bold;
                }
                .path {
                    color: var(--secondary-color);
                }
                .endpoint-method {
                    display: inline-block;
                    padding: 0.3rem 0.5rem;
                    background: #ff79c6;
                    color: var(--background-color);
                    border-radius: 4px;
                    font-weight: bold;
                    margin-right: 0.5rem;
                }
                ::selection {
                    background: var(--secondary-color);
                    color: var(--background-color);
                }
                .error-section {
                    margin: 2rem 0;
                }
                .error-section h2 {
                    border-bottom: 2px solid var(--secondary-color);
                    padding-bottom: 0.75rem;
                }
                .error-item {
                    margin-bottom: 1rem;
                }
                .error-toggle {
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem;
                    background: var(--card-background);
                    border-radius: 8px;
                    margin-bottom: 1rem;
                    border: 1px solid var(--hover-color);
                }
                .error-toggle:hover {
                    background: var(--hover-color);
                }
                .error-toggle h3 {
                    margin: 0;
                    padding: 0;
                    border: none;
                }
                .error-content {
                    max-height: 0;
                    overflow: hidden;
                    transition: max-height 0.3s ease;
                }
                .error-item.active .error-content {
                    max-height: 1000px;
                }
                .error-toggle-icon {
                    font-size: 1.5rem;
                    font-weight: bold;
                    color: var(--secondary-color);
                    transition: transform 0.3s ease;
                }
                .error-item.active .error-toggle-icon {
                    transform: rotate(45deg);
                }
            </style>
        </head>
        <body>
            <h1>GitHub Stats API Documentation</h1>
            
            <p>This API provides access to GitHub user statistics and contribution data. Click on each endpoint to see details.</p>

            <div class="endpoint">
                <div class="endpoint-header">
                    <h2><span class="endpoint-method">GET</span> Complete Statistics</h2>
                    <span class="endpoint-toggle">+</span>
                </div>
                <div class="endpoint-content">
                    <p>Get comprehensive GitHub statistics for a user, combining top programming languages, total contribution count, and longest contribution streak.</p>
                    <p><code class="path">/{username}/stats</code></p>
                    
                    <div class="parameter">
                        <code>exclude</code> Optional comma-separated list of languages to exclude
                    </div>

                    <div class="note">
                        <h3>Example Request</h3>
                        <pre><code>GET /tashifkhan/stats?exclude=HTML,CSS,Markdown</code></pre>
                    </div>

                    <div class="response">
                        <h3>Response</h3>
                        <pre><code>{
    "topLanguages": [
        {"name": "Python", "percentage": 45}
    ],
    "totalCommits": 1234,
    "longestStreak": 30,
    "status": "success",
    "message": "retrieved",
    "contributions": {
        "2023": {
            "data": {
                "user": {
                    "contributionsCollection": {
                        "weeks": []
                    }
                }
            }
        }
    }
}</code></pre>
                    </div>

                    <div class="error-response">
                        <h3>Error Responses</h3>
                        <p><code>404</code> - User not found or API error</p>
                        <p><code>500</code> - GitHub token configuration error</p>
                    </div>
                </div>
            </div>

            <div class="endpoint">
                <div class="endpoint-header">
                    <h2><span class="endpoint-method">GET</span> Language Statistics</h2>
                    <span class="endpoint-toggle">+</span>
                </div>
                <div class="endpoint-content">
                    <p>Get the programming languages used in a GitHub user's repositories.</p>
                    <p><code class="path">/{username}/languages</code></p>
                    
                    <h3>Parameters</h3>
                    <div class="parameter">
                        <code>exclude</code> Optional comma-separated list of languages to exclude (default: Markdown, JSON, YAML, XML)
                    </div>

                    <div class="note">
                        <h3>Example Request</h3>
                        <pre><code>GET /tashifkhan/languages?exclude=HTML,CSS</code></pre>
                    </div>

                    <div class="response">
                        <h3>Response</h3>
                        <pre><code>{
    "topLanguages": [
        {"name": "Python", "percentage": 45}
    ],
    "status": "success",
    "message": "retrieved"
}</code></pre>
                    </div>

                    <div class="error-response">
                        <h3>Error Responses</h3>
                        <p><code>404</code> - User not found or API error</p>
                        <p><code>500</code> - GitHub token configuration error</p>
                    </div>
                </div>
            </div>

            <div class="endpoint">
                <div class="endpoint-header">
                    <h2><span class="endpoint-method">GET</span> Contribution History</h2>
                    <span class="endpoint-toggle">+</span>
                </div>
                <div class="endpoint-content">
                    <p>Retrieve a user's GitHub contribution history and statistics, including contribution calendar data, total commits, and longest streak.</p>
                    <p><code class="path">/{username}/contributions</code></p>
                    
                    <div class="parameter">
                        <code>starting_year</code> Optional starting year for contribution history (defaults to account creation year)
                    </div>

                    <div class="note">
                        <h3>Example Request</h3>
                        <pre><code>GET /tashifkhan/contributions?starting_year=2022</code></pre>
                    </div>

                    <div class="response">
                        <h3>Response</h3>
                        <pre><code>{
    "contributions": {
        "2023": {
            "data": {
                "user": {
                    "contributionsCollection": {
                        "weeks": []
                    }
                }
            }
        }
    },
    "totalCommits": 1234,
    "longestStreak": 30,
    "status": "success",
    "message": "retrieved"
}</code></pre>
                    </div>

                    <div class="error-response">
                        <h3>Error Responses</h3>
                        <p><code>404</code> - User not found or API error</p>
                        <p><code>500</code> - GitHub token configuration error</p>
                    </div>
                </div>
            </div>

            <div class="error-section">
                <h2>Error Responses</h2>
                
                <div class="error-item">
                    <div class="error-toggle">
                        <h3>User not found</h3>
                        <span class="error-toggle-icon">+</span>
                    </div>
                    <div class="error-content">
                        <pre><code>{
    "status": "error",
    "message": "User not found or API error",
    "topLanguages": [],
    "totalCommits": 0,
    "longestStreak": 0
}</code></pre>
                    </div>
                </div>

                <div class="error-item">
                    <div class="error-toggle">
                        <h3>Server error</h3>
                        <span class="error-toggle-icon">+</span>
                    </div>
                    <div class="error-content">
                        <pre><code>{
    "status": "error",
    "message": "GitHub token not configured",
    "topLanguages": [],
    "totalCommits": 0,
    "longestStreak": 0
}</code></pre>
                    </div>
                </div>
            </div>

            <footer>
                <p>GitHub Analytics API live at <a href="https://github-stats.tashif.codes" style="color: var(--secondary-color); text-decoration: none;">github-stats.tashif.codes</a></p>
                <p>This API is open source and available on <a href="https://github.com/tashifkhan/GitHub-Stats-API.git" style="color: var(--secondary-color); text-decoration: none;">GitHub</a></p>
            </footer>

            <script>
                document.addEventListener('DOMContentLoaded', function() {
                    // Handle endpoint toggles
                    const endpoints = document.querySelectorAll('.endpoint');
                    endpoints.forEach(endpoint => {
                        const header = endpoint.querySelector('.endpoint-header');
                        header.addEventListener('click', () => {
                            endpoint.classList.toggle('active');
                        });
                    });
                    
                    // Handle error toggles
                    const errorItems = document.querySelectorAll('.error-item');
                    errorItems.forEach(item => {
                        const toggle = item.querySelector('.error-toggle');
                        toggle.addEventListener('click', () => {
                            item.classList.toggle('active');
                        });
                    });
                    
                    // Make the first endpoint active by default for better UX
                    if (endpoints.length > 0) {
                        endpoints[0].classList.add('active');
                    }
                });
            </script>
        </body>
        </html>
    """
    return render_template_string(html)

@app.route('/<username>/languages')
def get_user_language_stats(username: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    excluded = request.args.getlist('excluded') or ["Markdown", "JSON", "YAML", "XML"]
    language_stats = get_language_stats(username, token, excluded)
    
    response = GitHubStatsResponse(
        status="success",
        message="retrieved",
        topLanguages=language_stats,
        totalCommits=0,
        longestStreak=0
    )
    return jsonify(asdict(response))

@app.route('/<username>/contributions')
def get_user_contributions(username: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    starting_year = request.args.get('starting_year', type=int)
    contribution_data = get_contribution_graphs(username, token, starting_year)
    
    if not contribution_data:
        error_response = GitHubStatsResponse.error("error", "User not found or API error")
        return jsonify(asdict(error_response)), 404
    
    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)

    response = GitHubStatsResponse(
        status="success",
        message="retrieved",
        topLanguages=[],
        totalCommits=total_commits,
        longestStreak=longest_streak,
        contributions=contribution_data
    )
    return jsonify(asdict(response))

@app.route('/<username>/stats')
def get_user_stats(username: str):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    exclude = request.args.get('exclude')
    excluded_list = exclude.split(",") if exclude else []

    contribution_data = get_contribution_graphs(username, token)
    if not contribution_data:
        error_response = GitHubStatsResponse.error("error", "User not found or API error")
        return jsonify(asdict(error_response)), 404

    language_stats = get_language_stats(username, token, excluded_list)
    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)

    response = GitHubStatsResponse(
        status="success",
        message="retrieved",
        topLanguages=language_stats,
        totalCommits=total_commits,
        longestStreak=longest_streak,
        contributions=contribution_data
    )
    return jsonify(asdict(response))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8989, debug=True)