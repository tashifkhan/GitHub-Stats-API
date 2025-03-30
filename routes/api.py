from flask import Blueprint, jsonify, request, current_app
from dataclasses import asdict
import os

from modules.github import GitHubStatsResponse
from services.github_service import (
    get_language_stats,
    get_contribution_graphs,
    calculate_total_commits,
    calculate_longest_streak,
)

api_bp = Blueprint('api', __name__)

@api_bp.route('/<username>/languages')
def get_user_language_stats(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
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

@api_bp.route('/<username>/contributions')
def get_user_contributions(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
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

@api_bp.route('/<username>/stats')
def get_user_stats(username: str):
    token = current_app.config.get('GITHUB_TOKEN') or os.getenv("GITHUB_TOKEN")
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
