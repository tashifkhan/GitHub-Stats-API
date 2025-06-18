from typing import List, Dict, Optional
from pydantic import BaseModel


class GitHubStatsResponse(BaseModel):
    status: str
    message: str
    topLanguages: List["LanguageData"]
    totalCommits: int
    longestStreak: int
    currentStreak: int
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
    readme: Optional[str]


class CommitDetail(BaseModel):
    repo: str
    message: Optional[str]
    timestamp: Optional[str]
    sha: Optional[str]
    url: Optional[str]
