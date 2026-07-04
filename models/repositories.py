from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class Contributor(BaseModel):
    login: str
    avatar_url: str
    html_url: str
    contributions: int

class ReleaseAsset(BaseModel):
    name: str
    download_url: str
    size: int = 0
    download_count: int = 0
    content_type: Optional[str] = None
    updated_at: Optional[str] = None

class RepoRelease(BaseModel):
    id: int
    tag_name: str
    name: Optional[str] = None
    body: Optional[str] = None
    url: str
    draft: bool = False
    prerelease: bool = False
    created_at: Optional[str] = None
    published_at: Optional[str] = None
    assets: List[ReleaseAsset] = Field(default_factory=list)

class OriginalRepo(BaseModel):
    name: str
    full_name: str
    owner: str
    url: str

class RepoDetail(BaseModel):
    title: str
    description: Optional[str]
    live_website_url: Optional[str]
    languages: List[str]
    num_commits: int
    stars: int = 0
    forks: int = 0
    is_fork: bool = False
    original_repo: Optional[OriginalRepo] = None
    readme: Optional[str]
    contributors: List[Contributor] = Field(default_factory=list)
    releases: List[RepoRelease] = Field(default_factory=list)
