from fastapi import APIRouter, Depends, HTTPException, Path
from typing import List

from modules.github import (
    OrganizationContribution,
    PullRequestDetail,
)
from routes.dependencies import get_pr_service
from services.pr_service import PRService


pr_router = APIRouter()


@pr_router.get(
    "/{username}/me/pulls",
    response_model=List[PullRequestDetail],
    tags=["Dashboard Details"],
)
async def get_user_pull_requests_route(
    username: str = Path(..., description="GitHub username"),
    pr_service: PRService = Depends(get_pr_service),
):
    pulls = await pr_service.get_user_pull_requests(username)
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
    pr_service: PRService = Depends(get_pr_service),
):
    org_contributions = await pr_service.get_organization_contributions(username)
    return org_contributions


@pr_router.get(
    "/{username}/prs",
    response_model=List[PullRequestDetail],
    tags=["Dashboard Details"],
)
async def get_user_external_prs_route(
    username: str = Path(..., description="GitHub username"),
    pr_service: PRService = Depends(get_pr_service),
):
    return await pr_service.get_user_external_prs(username)
