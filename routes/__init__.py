from .analytics import analytics_router
from .dashboard import dashboard_router
from .docs import docs_router
from .pr import pr_router

# from .api import api_router

__all__ = [
    "analytics_router",
    # "api_router",
    "dashboard_router",
    "docs_router",
    "pr_router",
]
