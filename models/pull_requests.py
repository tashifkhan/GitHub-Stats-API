from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class PullRequestDetail(BaseModel):
    repo: str
    number: int
    title: str
    state: str
    created_at: str
    updated_at: str
    closed_at: Optional[str]
    merged_at: Optional[str]
    user: str
    url: str
    body: Optional[str]

class OrganizationContribution(BaseModel):
    org: str
    org_id: int
    org_url: str
    org_avatar_url: str
    repos: List[str]
