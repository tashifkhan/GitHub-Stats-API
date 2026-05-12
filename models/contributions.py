from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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
