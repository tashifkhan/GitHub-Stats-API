from .analytics import analytics_router
from .badges import router as badges_router
from .docs import docs_router
from .heatmap import router as heatmap_router
from .profile import router as profile_router
from .pr import pr_router
from .summary import router as summary_router

# from .api import api_router

__all__ = [
    "analytics_router",
    "badges_router",
    # "api_router",
    "docs_router",
    "heatmap_router",
    "profile_router",
    "pr_router",
    "summary_router",
]
