from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class StarsData(BaseModel):
    total_stars: int
    repositories: List[Dict[str, Any]]

class StarredList(BaseModel):
    """Represents a user's GitHub starred list (a curated list of starred repos)."""

    name: str
    url: str
    repositories: Optional[List[str]] = None
    description: Optional[str] = None
    num_repos: Optional[int] = None
