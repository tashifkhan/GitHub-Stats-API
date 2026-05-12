from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class PinnedRepo(BaseModel):
    name: str
    description: Optional[str]
    url: str
    stars: int
    forks: int
    primary_language: Optional[str] = None
