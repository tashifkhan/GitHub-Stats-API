from typing import Any, Dict, List, Optional, Tuple

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


async def list_user_repositories(
    client: httpx.AsyncClient,
    username: str,
    token: str,
    *,
    sort: str = "updated",
    repo_type: str = "all",
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """List every repository GitHub exposes for a user, following all pages.

    GitHub caps one repository-list response at 100 items. Centralizing the
    pagination prevents analytics endpoints from silently dropping repository
    101 onward. The second result is the lowest API budget observed while
    paging, allowing expensive callers to honor their rate-limit floor.
    """
    url = f"{GITHUB_API}/users/{username}/repos"
    repositories: List[Dict[str, Any]] = []
    lowest_remaining: Optional[int] = None
    page = 1

    while True:
        response = await client.get(
            url,
            params={
                "per_page": "100",
                "page": str(page),
                "sort": sort,
                "type": repo_type,
            },
            headers=github_headers(token),
        )
        raise_for_github_status(response, username)

        remaining = rate_limit_remaining(response)
        if remaining is not None:
            lowest_remaining = (
                remaining
                if lowest_remaining is None
                else min(lowest_remaining, remaining)
            )

        payload = response.json()
        if not isinstance(payload, list):
            break

        repositories.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < 100:
            break
        page += 1

    return repositories, lowest_remaining


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
