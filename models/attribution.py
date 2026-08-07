from typing import List, Optional

from pydantic import BaseModel, Field


class LanguageContribution(BaseModel):
    """A language, weighted by what the user personally wrote in it."""

    name: str
    percentage: float
    lines: int = 0
    files: int = 0


class RepoContribution(BaseModel):
    """What one user actually wrote in one repository."""

    repo: str
    owner: str
    full_name: str
    is_fork: bool = False
    url: Optional[str] = None

    commits: int = 0
    additions: int = 0
    deletions: int = 0
    files_changed: int = 0

    languages: List[LanguageContribution] = Field(default_factory=list)

    # Share of the repository's total line additions that came from this user,
    # 0-100. ``None`` when GitHub could not supply contributor stats.
    contribution_percentage: Optional[float] = None

    # "commits" when measured from real commit diffs, "estimated" when the
    # language mix was sampled or derived from the repo's byte breakdown.
    method: str = "commits"

    # True when a budget cap meant some of the user's commits went unmeasured.
    truncated: bool = False


class ContributionLanguageStats(BaseModel):
    """Language breakdown attributed to a single user's own commits."""

    username: str
    languages: List[LanguageContribution] = Field(default_factory=list)

    total_additions: int = 0
    total_deletions: int = 0
    total_commits: int = 0
    files_changed: int = 0

    repos_analyzed: int = 0
    forks_analyzed: int = 0
    repos_skipped: int = 0
    commits_sampled: int = 0
    truncated: bool = False

    # Repos that were eligible for measurement, whether or not the deadline
    # allowed them to be reached.
    repos_considered: int = 0
    # Share of those eligible repos that got settled, 0-1. Note this counts
    # repos the user never committed to, which are a real answer -- unlike
    # ``repos_analyzed``, which only counts repos they actually wrote code in.
    # Callers use this to decide if the language mix is representative.
    coverage: float = 0.0
    # True when the wall-clock deadline stopped the walk early, so some
    # eligible repos went unmeasured. Call again to widen the cached set.
    partial: bool = False

    repositories: List[RepoContribution] = Field(default_factory=list)
