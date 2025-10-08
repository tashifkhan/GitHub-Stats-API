from typing import List, Dict, Optional, Any
from pydantic import BaseModel


class GitHubStatsResponse(BaseModel):
    status: str
    message: str
    topLanguages: List["LanguageData"]
    totalCommits: int
    longestStreak: int
    currentStreak: int
    profile_visitors: int = 0
    contributions: Optional[Dict] = None

    @classmethod
    def error(cls, status: str, message: str):
        return cls(
            status=status,
            message=message,
            topLanguages=[],
            totalCommits=0,
            longestStreak=0,
            currentStreak=0,
            profile_visitors=0,
        )


class LanguageData(BaseModel):
    name: str
    percentage: float


class ContributionDay(BaseModel):
    contributionCount: int
    date: str


class Week(BaseModel):
    contributionDays: List[ContributionDay]


class ContributionCalendar(BaseModel):
    weeks: List[Week]


class ContributionsCollection(BaseModel):
    contributionYears: List[int]
    contributionCalendar: Optional[ContributionCalendar]


class GithubUser(BaseModel):
    createdAt: str
    contributionsCollection: Optional[ContributionsCollection]


class GraphQLResponse(BaseModel):
    data: Optional[Dict]
    errors: Optional[List[Dict[str, str]]]


class RepoDetail(BaseModel):
    title: str
    description: Optional[str]
    live_website_url: Optional[str]
    languages: List[str]
    num_commits: int
    stars: int = 0
    readme: Optional[str]


class CommitDetail(BaseModel):
    repo: str
    message: Optional[str]
    timestamp: Optional[str]
    sha: Optional[str]
    url: Optional[str]


class StarsData(BaseModel):
    total_stars: int
    repositories: List[Dict[str, Any]]


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


class StarredList(BaseModel):
    """Represents a user's GitHub starred list (a curated list of starred repos)."""

    name: str
    url: str
    repositories: Optional[List[str]] = None
    description: Optional[str] = None
    num_repos: Optional[int] = None


class PinnedRepo(BaseModel):
    name: str
    description: Optional[str]
    url: str
    stars: int
    forks: int
    primary_language: Optional[str] = None
