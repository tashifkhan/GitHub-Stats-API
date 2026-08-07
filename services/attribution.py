"""Attribute repository stats to a single user's own commits.

The plain ``/repos/{owner}/{repo}/languages`` endpoint reports the whole
repository, which is misleading for forks (where the upstream project dwarfs the
user's patches) and for any repo with more than one contributor. Everything here
measures only the lines the requested user authored, by walking their commits and
resolving each changed file to a language.

Cost control, in order of preference:

1. If the user's commit count in a repo fits the budget, every commit diff is
   read and the result is exact.
2. If it does not, the newest commits are sampled for the *language mix* and
   scaled up to the user's real addition total from the contributor stats.
3. If commit diffs are unavailable entirely, the user's additions are spread
   across the repo's language byte breakdown.

Per-repo results are cached in Redis keyed by the repo's ``pushed_at``, so a repo
is only re-measured after it receives new commits.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from core import cache
from core.config import attribution_settings as settings
from models.attribution import (
    ContributionLanguageStats,
    LanguageContribution,
    RepoContribution,
)
from services.client import GITHUB_API, github_headers
from services.language_map import detect_language, filter_languages, is_vendored

CACHE_VERSION = "v1"

_LAST_PAGE_RE = re.compile(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"')


class AttributionBudget:
    """Caps how many commit-detail requests a single user lookup may spend."""

    def __init__(self, max_commit_details: int):
        self._remaining = max(0, max_commit_details)
        self._lock = asyncio.Lock()

    async def take(self, requested: int) -> int:
        """Reserve up to ``requested`` calls, returning how many were granted."""
        async with self._lock:
            granted = min(requested, self._remaining)
            self._remaining -= granted
            return granted

    @property
    def remaining(self) -> int:
        return self._remaining


def _last_page(response: httpx.Response) -> Optional[int]:
    link = response.headers.get("Link")
    if not link:
        return None
    match = _LAST_PAGE_RE.search(link)
    return int(match.group(1)) if match else None


async def _count_user_commits(
    client: httpx.AsyncClient, owner: str, repo: str, username: str, token: str
) -> int:
    """Number of commits authored by ``username``, via the pagination header."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    params = {"author": username, "per_page": "1"}
    try:
        response = await client.get(url, params=params, headers=github_headers(token))
    except Exception:
        return 0

    # 409 is an empty repository, 404 a missing/blocked one.
    if response.status_code != 200:
        return 0

    last = _last_page(response)
    if last is not None:
        return last

    payload = response.json()
    return len(payload) if isinstance(payload, list) else 0


async def _list_commit_shas(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    username: str,
    token: str,
    limit: int,
) -> List[str]:
    """Newest-first SHAs authored by ``username``, capped at ``limit``."""
    shas: List[str] = []
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    page = 1

    while len(shas) < limit:
        per_page = min(100, limit - len(shas))
        params = {"author": username, "per_page": str(per_page), "page": str(page)}
        try:
            response = await client.get(
                url, params=params, headers=github_headers(token)
            )
        except Exception:
            break

        if response.status_code != 200:
            break

        payload = response.json()
        if not isinstance(payload, list) or not payload:
            break

        for item in payload:
            if isinstance(item, dict) and item.get("sha"):
                shas.append(item["sha"])

        if len(payload) < per_page:
            break
        page += 1

    return shas[:limit]


async def _fetch_commit_files(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    sha: str,
    token: str,
    semaphore: asyncio.Semaphore,
) -> Optional[List[Dict[str, Any]]]:
    """Changed files for one commit. ``None`` when it should not be counted."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}"
    async with semaphore:
        try:
            response = await client.get(url, headers=github_headers(token))
        except Exception:
            return None

    if response.status_code != 200:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    # Merge commits restate work already counted in the parents.
    parents = payload.get("parents")
    if isinstance(parents, list) and len(parents) > 1:
        return []

    files = payload.get("files")
    return files if isinstance(files, list) else []


async def _fetch_contributor_totals(
    client: httpx.AsyncClient, owner: str, repo: str, username: str, token: str
) -> Optional[Dict[str, int]]:
    """The user's exact additions/deletions/commits plus the repo-wide totals.

    Returns ``None`` when GitHub cannot produce the stats (it computes them
    asynchronously and answers 202 while the job is queued).
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/stats/contributors"

    payload: Any = None
    for attempt in range(settings.stats_retries):
        try:
            response = await client.get(url, headers=github_headers(token))
        except Exception:
            return None

        if response.status_code == 202:
            await asyncio.sleep(settings.stats_retry_delay_seconds * (attempt + 1))
            continue
        if response.status_code != 200:
            return None

        try:
            payload = response.json()
        except ValueError:
            return None
        break

    if not isinstance(payload, list):
        return None

    target = username.lower()
    user_additions = user_deletions = user_commits = 0
    repo_additions = 0
    found = False

    for entry in payload:
        if not isinstance(entry, dict):
            continue

        author = entry.get("author")
        login = author.get("login", "") if isinstance(author, dict) else ""
        weeks = entry.get("weeks")
        if not isinstance(weeks, list):
            weeks = []

        additions = sum(int(week.get("a") or 0) for week in weeks if isinstance(week, dict))
        deletions = sum(int(week.get("d") or 0) for week in weeks if isinstance(week, dict))
        repo_additions += additions

        if login.lower() == target:
            found = True
            user_additions = additions
            user_deletions = deletions
            user_commits = int(entry.get("total") or 0)

    if not found:
        return {
            "user_additions": 0,
            "user_deletions": 0,
            "user_commits": 0,
            "repo_additions": repo_additions,
        }

    return {
        "user_additions": user_additions,
        "user_deletions": user_deletions,
        "user_commits": user_commits,
        "repo_additions": repo_additions,
    }


async def _fetch_repo_language_bytes(
    client: httpx.AsyncClient, owner: str, repo: str, token: str
) -> Dict[str, int]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/languages"
    try:
        response = await client.get(url, headers=github_headers(token))
    except Exception:
        return {}

    if response.status_code != 200:
        return {}

    try:
        payload = response.json()
    except ValueError:
        return {}

    return payload if isinstance(payload, dict) else {}


def _accumulate_files(
    files: List[Dict[str, Any]],
    additions_by_language: Dict[str, int],
    deletions_by_language: Dict[str, int],
    files_by_language: Dict[str, int],
) -> Tuple[int, int, int]:
    """Fold one commit's file list into the running per-language tallies."""
    additions = deletions = counted = 0

    for entry in files:
        if not isinstance(entry, dict):
            continue

        path = entry.get("filename") or ""
        if not path or is_vendored(path):
            continue

        language = detect_language(path)
        if not language:
            continue

        file_additions = int(entry.get("additions") or 0)
        file_deletions = int(entry.get("deletions") or 0)

        additions_by_language[language] = (
            additions_by_language.get(language, 0) + file_additions
        )
        deletions_by_language[language] = (
            deletions_by_language.get(language, 0) + file_deletions
        )
        files_by_language[language] = files_by_language.get(language, 0) + 1

        additions += file_additions
        deletions += file_deletions
        counted += 1

    return additions, deletions, counted


def _scale(totals: Dict[str, int], target_total: int) -> Dict[str, int]:
    """Rescale a language distribution so it sums to ``target_total``."""
    current = sum(totals.values())
    if current <= 0 or target_total <= 0:
        return dict(totals)

    factor = target_total / current
    return {name: max(1, round(value * factor)) for name, value in totals.items()}


def _build_language_list(
    additions_by_language: Dict[str, int],
    files_by_language: Dict[str, int],
    excluded: Optional[List[str]],
) -> List[LanguageContribution]:
    filtered = filter_languages(additions_by_language, excluded)
    total = sum(filtered.values())
    if total <= 0:
        return []

    languages = [
        LanguageContribution(
            name=name,
            percentage=round((lines / total) * 100, 2),
            lines=lines,
            files=files_by_language.get(name, 0),
        )
        for name, lines in filtered.items()
    ]
    return sorted(languages, key=lambda item: (item.lines, item.name), reverse=True)


def _cache_key(full_name: str, username: str, version_token: str) -> str:
    return f"gh:attr:{CACHE_VERSION}:{full_name}:{username.lower()}:{version_token}"


async def analyze_repo_contribution(
    client: httpx.AsyncClient,
    repo: Dict[str, Any],
    username: str,
    token: str,
    budget: AttributionBudget,
    semaphore: asyncio.Semaphore,
) -> Optional[RepoContribution]:
    """Measure what ``username`` personally contributed to a single repository."""
    name = repo.get("name")
    owner_payload = repo.get("owner")
    owner = owner_payload.get("login") if isinstance(owner_payload, dict) else None
    if not name or not owner:
        return None

    full_name = repo.get("full_name") or f"{owner}/{name}"
    is_fork = bool(repo.get("fork"))
    version_token = str(repo.get("pushed_at") or repo.get("updated_at") or "head")
    cache_key = _cache_key(full_name, username, version_token)

    cached = await cache.get_json(cache_key)
    if cached:
        try:
            return RepoContribution.model_validate(cached)
        except Exception:
            pass

    total_user_commits = await _count_user_commits(client, owner, name, username, token)
    if total_user_commits == 0:
        return None

    sample_size = min(total_user_commits, settings.max_commits_per_repo)
    granted = await budget.take(sample_size)
    truncated = granted < total_user_commits

    additions_by_language: Dict[str, int] = {}
    deletions_by_language: Dict[str, int] = {}
    files_by_language: Dict[str, int] = {}
    measured_additions = measured_deletions = measured_files = 0

    if granted > 0:
        shas = await _list_commit_shas(client, owner, name, username, token, granted)
        file_lists = await asyncio.gather(
            *(
                _fetch_commit_files(client, owner, name, sha, token, semaphore)
                for sha in shas
            )
        )
        for files in file_lists:
            if not files:
                continue
            commit_additions, commit_deletions, commit_files = _accumulate_files(
                files, additions_by_language, deletions_by_language, files_by_language
            )
            measured_additions += commit_additions
            measured_deletions += commit_deletions
            measured_files += commit_files

    stats = await _fetch_contributor_totals(client, owner, name, username, token)

    contribution_percentage: Optional[float] = None
    if stats and stats["repo_additions"] > 0:
        contribution_percentage = round(
            (stats["user_additions"] / stats["repo_additions"]) * 100, 2
        )

    method = "commits"
    additions = measured_additions
    deletions = measured_deletions
    files_changed = measured_files

    if not additions_by_language:
        # No usable diffs: spread the user's known additions over the repo's
        # language byte breakdown, which at least keeps forks proportional.
        if not stats or stats["user_additions"] <= 0:
            return None

        language_bytes = await _fetch_repo_language_bytes(client, owner, name, token)
        if not language_bytes:
            return None

        additions_by_language = _scale(language_bytes, stats["user_additions"])
        files_by_language = {}
        additions = stats["user_additions"]
        deletions = stats["user_deletions"]
        method = "estimated"

    elif truncated and stats and stats["user_additions"] > measured_additions:
        # The sample gives the language mix; the stats give the true volume.
        additions_by_language = _scale(additions_by_language, stats["user_additions"])
        additions = stats["user_additions"]
        deletions = stats["user_deletions"]
        method = "estimated"

    contribution = RepoContribution(
        repo=name,
        owner=owner,
        full_name=full_name,
        is_fork=is_fork,
        url=repo.get("html_url"),
        commits=total_user_commits,
        additions=additions,
        deletions=deletions,
        files_changed=files_changed,
        languages=_build_language_list(additions_by_language, files_by_language, None),
        contribution_percentage=contribution_percentage,
        method=method,
        truncated=truncated,
    )

    await cache.set_json(
        cache_key, contribution.model_dump(), settings.cache_ttl_seconds
    )
    return contribution


async def get_user_contributions(
    username: str,
    token: str,
    excluded_languages: Optional[List[str]] = None,
    include_forks: bool = True,
    include_repositories: bool = True,
) -> ContributionLanguageStats:
    """Aggregate every repository's per-user attribution into one breakdown."""
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        repos_url = f"{GITHUB_API}/users/{username}/repos"
        params = {"per_page": "100", "sort": "pushed", "type": "all"}
        response = await client.get(
            repos_url, params=params, headers=github_headers(token)
        )

        if response.status_code == 404:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="User not found")
        if response.status_code != 200:
            from fastapi import HTTPException

            raise HTTPException(status_code=502, detail="GitHub API error")

        repos = response.json()
        if not isinstance(repos, list) or not repos:
            return ContributionLanguageStats(username=username)

        candidates = [
            repo
            for repo in repos
            if isinstance(repo, dict)
            and not repo.get("archived")
            and (include_forks or not repo.get("fork"))
        ]
        skipped = max(0, len(candidates) - settings.max_repos)
        candidates = candidates[: settings.max_repos]

        budget = AttributionBudget(settings.max_commit_details)
        semaphore = asyncio.Semaphore(settings.concurrency)

        results = await asyncio.gather(
            *(
                analyze_repo_contribution(
                    client, repo, username, token, budget, semaphore
                )
                for repo in candidates
            ),
            return_exceptions=True,
        )

    contributions = [
        result
        for result in results
        if isinstance(result, RepoContribution) and result.additions > 0
    ]

    additions_by_language: Dict[str, int] = {}
    files_by_language: Dict[str, int] = {}
    for contribution in contributions:
        for language in contribution.languages:
            additions_by_language[language.name] = (
                additions_by_language.get(language.name, 0) + language.lines
            )
            files_by_language[language.name] = (
                files_by_language.get(language.name, 0) + language.files
            )

    contributions.sort(key=lambda item: item.additions, reverse=True)

    return ContributionLanguageStats(
        username=username,
        languages=_build_language_list(
            additions_by_language, files_by_language, excluded_languages
        ),
        total_additions=sum(item.additions for item in contributions),
        total_deletions=sum(item.deletions for item in contributions),
        total_commits=sum(item.commits for item in contributions),
        files_changed=sum(item.files_changed for item in contributions),
        repos_analyzed=len(contributions),
        forks_analyzed=sum(1 for item in contributions if item.is_fork),
        repos_skipped=skipped,
        commits_sampled=settings.max_commit_details - budget.remaining,
        truncated=any(item.truncated for item in contributions),
        repositories=contributions if include_repositories else [],
    )
