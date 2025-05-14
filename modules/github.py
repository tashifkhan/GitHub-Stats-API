from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class GitHubStatsResponse:
    status: str
    message: str
    topLanguages: List[Dict[str, float]]
    totalCommits: int
    longestStreak: int
    contributions: Optional[Dict] = None
    repos: Optional[List['RepoDetail']] = field(default_factory=list)
    commits: Optional[List['CommitDetail']] = field(default_factory=list)

    @classmethod
    def error(cls, status: str, message: str):
        return cls(
            status=status,
            message=message,
            topLanguages=[],
            totalCommits=0,
            longestStreak=0,
            repos=[],
            commits=[]
        )

@dataclass
class LanguageData:
    name: str
    percentage: float

@dataclass
class ContributionDay:
    contributionCount: int
    date: str

@dataclass
class Week:
    contributionDays: List[ContributionDay]

@dataclass
class ContributionCalendar:
    weeks: List[Week]

@dataclass
class ContributionsCollection:
    contributionYears: List[int]
    contributionCalendar: Optional[ContributionCalendar]

@dataclass
class GithubUser:
    createdAt: str
    contributionsCollection: Optional[ContributionsCollection]

@dataclass
class RepoDetail:
    title: str
    description: Optional[str]
    live_website_url: Optional[str]
    languages: List[str]
    num_commits: int
    readme: Optional[str] # Base64 encoded

@dataclass
class CommitDetail:
    repo: str
    message: Optional[str]
    timestamp: Optional[str]
    sha: Optional[str]
    url: Optional[str]
