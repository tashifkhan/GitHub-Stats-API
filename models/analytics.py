from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class LanguageData(BaseModel):
    name: str
    percentage: float

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
