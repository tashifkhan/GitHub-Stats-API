from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class GitHubStatsResponse:
    status: str
    message: str
    topLanguages: List[Dict[str, float]]
    totalCommits: int
    longestStreak: int
    contributions: Optional[Dict] = None

    @classmethod
    def error(cls, status: str, message: str):
        return cls(
            status=status,
            message=message,
            topLanguages=[],
            totalCommits=0,
            longestStreak=0
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
