from typing import Dict, Optional

import httpx

BASE_GITHUB_URL = "https://github.com"
GITHUB_API = "https://api.github.com"
STAR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def github_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def is_rate_limited(response: httpx.Response) -> bool:
    """True when GitHub refused the call for rate limiting rather than access.

    GitHub answers both "you may not see this" and "you have asked too often"
    with 403, separated only by headers: the primary limit zeroes
    ``x-ratelimit-remaining``, while secondary limits send ``retry-after``.
    """
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    if response.headers.get("retry-after"):
        return True
    return response.headers.get("x-ratelimit-remaining") == "0"


def rate_limit_remaining(response: httpx.Response) -> Optional[int]:
    """Calls left in the current window, when GitHub reports it."""
    raw = response.headers.get("x-ratelimit-remaining")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def raise_for_github_status(response: httpx.Response, username: str) -> None:
    """Translate a failed GitHub response into the right HTTP error.

    Reporting an exhausted rate limit as a 404 was actively harmful: the cache
    middleware treats 404 as proof the user does not exist, so one throttled
    minute would blacklist a real account and put it on the stricter
    invalid-user rate limit for the rest of the TTL.
    """
    from fastapi import HTTPException

    if response.status_code == 200:
        return

    if is_rate_limited(response):
        raise HTTPException(
            status_code=503,
            detail="GitHub API rate limit exceeded, please retry shortly",
        )

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"User {username} not found")

    raise HTTPException(status_code=502, detail="GitHub API error")
