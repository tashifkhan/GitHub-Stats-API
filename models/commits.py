from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class CommitDetail(BaseModel):
    repo: str
    message: Optional[str]
    timestamp: Optional[str]
    sha: Optional[str]
    url: Optional[str]
