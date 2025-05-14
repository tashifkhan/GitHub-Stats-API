from flask import Blueprint, jsonify, request, current_app
from dataclasses import asdict
import os

from modules.github import GitHubStatsResponse, RepoDetail, CommitDetail
from services.github_service import (
    get_language_stats,
    get_contribution_graphs,
    calculate_total_commits,
    calculate_longest_streak,
    get_user_repos,
    get_user_commit_history,
)

api_bp = Blueprint('api', __name__)

@api_bp.route('/<username>/languages')
def get_user_language_stats(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    excluded = request.args.getlist('excluded') or ["Markdown", "JSON", "YAML", "XML"]
    
    language_stats_data = get_language_stats(username, token, excluded)
    
    if language_stats_data is None:
        pass

    return jsonify(language_stats_data)

@api_bp.route('/<username>/contributions')
def get_user_contributions(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    starting_year_str = request.args.get('starting_year')
    starting_year = None
    if starting_year_str:
        try:
            starting_year = int(starting_year_str)
        except ValueError:
            error_response = GitHubStatsResponse.error("error", "Invalid starting_year format. Must be an integer.")
            return jsonify(asdict(error_response)), 400
            
    contribution_data = get_contribution_graphs(username, token, starting_year)
    
    if not contribution_data:
        error_response = GitHubStatsResponse.error("error", "User not found or API error")
        return jsonify(asdict(error_response)), 404
    
    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)

    response_payload = {
        "contributions": contribution_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak
    }
    return jsonify(response_payload)

@api_bp.route('/<username>/stats')
def get_user_stats(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    exclude_param = request.args.get('exclude')
    excluded_list = [lang.strip() for lang in exclude_param.split(',')] if exclude_param else []

    contribution_data = get_contribution_graphs(username, token)
    if not contribution_data:
        error_response = GitHubStatsResponse.error("error", "User not found or API error fetching contributions")
        return jsonify(asdict(error_response)), 404

    language_stats_data = get_language_stats(username, token, excluded_list)

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)

    response_payload = {
        "topLanguages": language_stats_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak
    }
    return jsonify(response_payload)

@api_bp.route('/<username>/repos')
def get_user_repo_details(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    repos = get_user_repos(username, token)
    
    if repos is None:
        error_response = GitHubStatsResponse.error("error", "Failed to retrieve repository details")
        return jsonify(asdict(error_response)), 500

    response_data = [asdict(repo) for repo in repos]
    return jsonify(response_data)

@api_bp.route('/<username>/commits')
def get_user_commit_details(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
    if not token:
        error_response = GitHubStatsResponse.error("error", "GitHub token not configured")
        return jsonify(asdict(error_response)), 500

    commits = get_user_commit_history(username, token)

    if commits is None:
        error_response = GitHubStatsResponse.error("error", "Failed to retrieve commit history")
        return jsonify(asdict(error_response)), 500

    response_data = [asdict(commit) for commit in commits]
    return jsonify(response_data)
