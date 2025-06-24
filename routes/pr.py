from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Path,
    Depends,
)
from typing import List, Dict, Optional
from dataclasses import asdict
import os

from modules.github import (
    PullRequestDetail,
    OrganizationContribution,
)
from services.github_service import (
    get_language_stats,
    get_contribution_graphs,
    calculate_total_commits,
    calculate_longest_streak,
    calculate_current_streak,
)


async def get_github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GitHub token not configured")

    return token


pr_router = APIRouter()


@pr_router.get("/{username}/stats", tags=["User Analytics"])
async def get_user_stats_route(
    username: str = Path(..., description="GitHub username"),
    exclude: Optional[str] = Query(
        None, description="Comma-separated list of languages to exclude"
    ),
    token: str = Depends(get_github_token),
):
    excluded_list = (
        [lang.strip() for lang in exclude.split(",")]
        if exclude
        else ["Markdown", "JSON", "YAML", "XML"]
    )

    contribution_data = await get_contribution_graphs(username, token)
    if not contribution_data or not contribution_data.get(
        list(contribution_data.keys())[0] if contribution_data else None, {}
    ).get("data", {}).get("user"):
        raise HTTPException(
            status_code=404, detail="User not found or API error fetching contributions"
        )

    language_stats_data = await get_language_stats(username, token, excluded_list)

    total_commits = calculate_total_commits(contribution_data)
    longest_streak = calculate_longest_streak(contribution_data)
    current_streak = calculate_current_streak(contribution_data)

    return {
        "topLanguages": language_stats_data,
        "totalCommits": total_commits,
        "longestStreak": longest_streak,
        "currentStreak": current_streak,
    }


@pr_router.get(
    "/{username}/me/pulls",
    response_model=List[PullRequestDetail],
    tags=["Dashboard Details"],
)
async def get_user_pull_requests_route(
    username: str = Path(..., description="GitHub username"),
    token: str = Depends(get_github_token),
):
    pulls = await get_user_pull_requests(username, token)
    if pulls is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve pull requests")
    return pulls


@pr_router.get(
    "/{username}/org-contributions",
    response_model=List[OrganizationContribution],
    tags=["Dashboard Details"],
)
async def get_organization_contributions_route(
    username: str = Path(..., description="GitHub username"),
    token: str = Depends(get_github_token),
):
    org_contributions = await get_organization_contributions(username, token)
    return org_contributions


@pr_router.get(
    "/{username}/prs",
    response_model=List[PullRequestDetail],
    tags=["Dashboard Details"],
)
async def get_user_external_prs_route(
    username: str = Path(..., description="GitHub username"),
    token: str = Depends(get_github_token),
):
    # Use the GitHub Search API to get all PRs opened by the user
    import httpx

    prs: List[PullRequestDetail] = []
    per_page = 100
    page = 1
    while True:
        search_url = f"https://api.github.com/search/issues?q=type:pr+author:{username}&per_page={per_page}&page={page}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                search_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
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
                repo_parts = repo_url.split("/")
                if len(repo_parts) < 2:
                    continue
                org_or_owner = repo_parts[-2]
                repo_name = repo_parts[-1]
                # Only include PRs not in user's own repos
                if org_or_owner.lower() == username.lower():
                    continue
                prs.append(
                    PullRequestDetail(
                        repo=repo_name,
                        number=pr.get("number", 0),
                        title=pr.get("title", ""),
                        state=pr.get("state", ""),
                        created_at=pr.get("created_at", ""),
                        updated_at=pr.get("updated_at", ""),
                        closed_at=pr.get("closed_at"),
                        merged_at=(
                            pr.get("pull_request", {}).get("merged_at")
                            if pr.get("pull_request")
                            else None
                        ),
                        user=username,
                        url=pr.get("html_url", ""),
                        body=pr.get("body"),
                    )
                )
            if len(items) < per_page:
                break
            page += 1
    return prs
