from typing import List

import httpx

from modules.github import OrganizationContribution, PullRequestDetail
from services.github_service import (
    get_organization_contributions as fetch_organization_contributions,
    get_user_pull_requests as fetch_user_pull_requests,
)


class PRService:
    def __init__(self, token: str):
        self.token = token

    async def get_user_pull_requests(self, username: str) -> List[PullRequestDetail]:
        return await fetch_user_pull_requests(username, self.token)

    async def get_organization_contributions(
        self, username: str
    ) -> List[OrganizationContribution]:
        return await fetch_organization_contributions(username, self.token)

    async def get_user_external_prs(self, username: str) -> List[PullRequestDetail]:
        prs: List[PullRequestDetail] = []
        per_page = 100
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                search_url = (
                    "https://api.github.com/search/issues"
                    f"?q=type:pr+author:{username}&per_page={per_page}&page={page}"
                )
                resp = await client.get(
                    search_url,
                    headers={
                        "Authorization": f"Bearer {self.token}",
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
