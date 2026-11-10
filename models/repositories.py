from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from models.attribution import LanguageContribution

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

class ReleasePage(BaseModel):
    """Where a list of releases sits in the repo's full release history."""

    # Every release the repo has. None when GitHub's count lookup failed.
    total_count: Optional[int] = None
    page: int = 1
    per_page: int
    has_more: bool = False
    # Path of the next page on this API, e.g.
    # "/tashifkhan/repos/Paisa/releases?page=2&per_page=10". None on the last page.
    next: Optional[str] = None

class RepoReleases(BaseModel):
    """One page of a repo's releases, newest first."""

    owner: str
    repo: str
    releases: List[RepoRelease] = Field(default_factory=list)
    releases_page: ReleasePage

class RepoDetail(BaseModel):
    title: str
    description: Optional[str]
    live_website_url: Optional[str]
    languages: List[str]
    topics: List[str] = Field(default_factory=list)
    num_commits: int
    stars: int = 0
    readme: Optional[str]
    contributors: List[Contributor] = Field(default_factory=list)
    # False while the history scan is unfinished or the upstream API failed.
    contributors_complete: bool = False
    # First page of releases only. Follow releases_page.next for the rest.
    releases: List[RepoRelease] = Field(default_factory=list)
    # None when release data was unavailable, e.g. a skeleton row.
    releases_page: Optional[ReleasePage] = None

    # Whether this repo is a fork of someone else's project.
    is_fork: bool = False

    # Everything below describes the user's authored and co-authored commits, so a
    # fork reports the patches they wrote rather than the upstream codebase.
    # Populated when the endpoint is called with attribution enabled.
    user_commits: int = 0
    user_additions: int = 0
    user_deletions: int = 0
    user_files_changed: int = 0
    user_languages: List[LanguageContribution] = Field(default_factory=list)
    # The user's share of the repo's total line additions, 0-100.
    contribution_percentage: Optional[float] = None
