"""
Rate limiting middleware for GitHub API
Implements 15 requests per minute and 700 requests per day limits
Uses in-memory storage for rate limiting
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize limiter with in-memory storage
limiter = Limiter(key_func=get_remote_address)
logger.info("Rate limiter initialized with in-memory backend")


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom rate limit exceeded handler"""
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": f"You have exceeded the rate limit. {exc.detail}",
            "retry_after": exc.retry_after,
            "limits": {"per_minute": 15, "per_day": 700},
        },
        headers={"Retry-After": str(exc.retry_after)},
    )
    return response


# Rate limiting decorators
def rate_limit_per_minute():
    """Rate limit decorator for per-minute limits (15 requests/minute)"""
    return limiter.limit("15/minute")


def rate_limit_per_day():
    """Rate limit decorator for per-day limits (700 requests/day)"""
    return limiter.limit("700/day")


def combined_rate_limit():
    """Combined rate limit decorator for both minute and day limits"""

    def decorator(func):
        # Apply both minute and day limits
        func = rate_limit_per_minute()(func)
        func = rate_limit_per_day()(func)
        return func

    return decorator
