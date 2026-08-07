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

A full cold walk costs minutes, far more than a serverless request allows, so
every walk carries a :class:`Deadline`. Cached repos are always free; uncached
ones are measured newest-first until the deadline expires, after which the rest
resolve from cache or not at all. The result reports how much it covered, and
callers that need a trustworthy language mix fall back to whole-repo bytes when
coverage is too thin.
"""

import asyncio
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from core import cache
from core.config import attribution_settings as settings
from models.attribution import (
    ContributionLanguageStats,
    LanguageContribution,
    RepoContribution,
)
from services.client import (
    GITHUB_API,
    github_headers,
    raise_for_github_status,
    rate_limit_remaining,
)
from services.language_map import detect_language, filter_languages, is_vendored

CACHE_VERSION = "v1"

_LAST_PAGE_RE = re.compile(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"')


class Deadline:
    """When a walk must stop issuing new requests.

    Two things end a walk: running out of wall-clock time, and running the
    GitHub hourly budget down to its floor. Work already in flight is allowed
    to finish either way -- this only gates *starting* more, which keeps the
    response inside the platform's function timeout instead of being killed
    mid-flight by the gateway.
    """

    def __init__(self, seconds: Optional[float], guard: Optional["RateLimitGuard"] = None):
        self._expires_at = None if seconds is None else time.monotonic() + seconds
        self._guard = guard

    @property
    def expired(self) -> bool:
        if self._guard is not None and self._guard.exhausted:
            return True
        return self._expires_at is not None and time.monotonic() >= self._expires_at

    @property
    def remaining(self) -> float:
        if self._guard is not None and self._guard.exhausted:
            return 0.0
        if self._expires_at is None:
            return float("inf")
        return max(0.0, self._expires_at - time.monotonic())


class RateLimitGuard:
    """Halts a walk once GitHub's hourly budget runs low.

    Attribution is by far the most request-hungry thing this API does, so
    without a floor one cold walk can spend the entire 5000/hour allowance and
    leave every other endpoint answering 403s until the window resets. Any
    response carrying a remaining-count keeps this up to date, so the walk
    notices the budget draining without spending a request to ask.
    """

    def __init__(self, floor: int):
        self._floor = floor
        self._tripped = False

    def observe(self, response: httpx.Response) -> None:
        remaining = rate_limit_remaining(response)
        if remaining is not None and remaining < self._floor:
            self._tripped = True

    @property
    def exhausted(self) -> bool:
        return self._tripped


class WalkProgress:
    """How much of a walk actually got settled.

    A repo is *resolved* once its contribution is known -- including the common
    case of a repo the user never committed to, which is a real answer even
    though it produces no numbers. It is *deferred* only when the deadline or
    cache-only mode stopped it from being measured at all. Keeping the two
    apart is what lets coverage reach 1.0 for a user whose repo list is full of
    projects they never pushed to.
    """

    def __init__(self) -> None:
        self.resolved = 0
        self.deferred = 0


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
    deadline: "Deadline",
) -> List[str]:
    """Newest-first SHAs authored by ``username``, capped at ``limit``."""
    shas: List[str] = []
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    page = 1

    while len(shas) < limit and not deadline.expired:
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
    deadline: "Deadline",
    guard: Optional["RateLimitGuard"] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Changed files for one commit. ``None`` when it should not be counted."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}"
    async with semaphore:
        # Re-checked after acquiring: this commit may have queued behind many
        # others and the budget can have run out while it waited.
        if deadline.expired:
            return None
        try:
            response = await client.get(url, headers=github_headers(token))
        except Exception:
            return None

    # Commit details are the bulk of a walk's spending, so watching their
    # headers is enough to notice the hourly budget draining.
    if guard is not None:
        guard.observe(response)

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
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    username: str,
    token: str,
    deadline: "Deadline",
) -> Optional[Dict[str, int]]:
    """The user's exact additions/deletions/commits plus the repo-wide totals.

    Returns ``None`` when GitHub cannot produce the stats (it computes them
    asynchronously and answers 202 while the job is queued).
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/stats/contributors"

    payload: Any = None
    for attempt in range(settings.stats_retries):
        if deadline.expired:
            return None
        try:
            response = await client.get(url, headers=github_headers(token))
        except Exception:
            return None

        if response.status_code == 202:
            # GitHub is still computing. Only wait if the budget can absorb it.
            delay = settings.stats_retry_delay_seconds * (attempt + 1)
            if delay >= deadline.remaining:
                return None
            await asyncio.sleep(delay)
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


def _explain(
    progress: WalkProgress,
    guard: RateLimitGuard,
    cache_enabled: bool,
    cache_only: bool,
) -> Tuple[str, str]:
    """Say why a walk stopped where it did.

    An empty breakdown is ambiguous on its own -- exhausted GitHub quota, a
    cold cache and a missing Redis all look the same from outside -- and that
    ambiguity is expensive to debug in production. Worst cause wins, since a
    tripped rate limit explains the thin coverage that follows from it.
    """
    if guard.exhausted:
        return (
            "rate_limited",
            "GitHub API quota ran low, so attribution stopped early to leave "
            "budget for other endpoints. Retry after the hourly reset.",
        )

    if progress.deferred == 0:
        return "complete", "Every eligible repository was measured."

    if not cache_enabled:
        return (
            "cache_disabled",
            "REDIS_URL is not set, so measurements cannot persist between "
            "requests and coverage will never build up. Set it to enable "
            "attributed language stats.",
        )

    if cache_only:
        return (
            "deadline",
            "Served from cache only. Warm the rest with "
            "scripts/warm_attribution.py or the breakdown endpoint.",
        )

    return (
        "deadline",
        "The time budget ran out before every repository was measured. "
        "Call again to continue from the cached results.",
    )


def _cache_key(full_name: str, username: str, version_token: str) -> str:
    return f"gh:attr:{CACHE_VERSION}:{full_name}:{username.lower()}:{version_token}"


async def analyze_repo_contribution(
    client: httpx.AsyncClient,
    repo: Dict[str, Any],
    username: str,
    token: str,
    budget: AttributionBudget,
    semaphore: asyncio.Semaphore,
    deadline: Optional[Deadline] = None,
    cache_only: bool = False,
    progress: Optional[WalkProgress] = None,
    guard: Optional[RateLimitGuard] = None,
) -> Optional[RepoContribution]:
    """Measure what ``username`` personally contributed to a single repository.

    Returns the cached measurement when there is one. Otherwise measures the
    repo, unless ``cache_only`` is set or ``deadline`` has expired -- in which
    case it returns ``None`` and the caller treats the repo as unmeasured.
    """
    deadline = deadline or Deadline(None)
    progress = progress or WalkProgress()

    name = repo.get("name")
    owner_payload = repo.get("owner")
    owner = owner_payload.get("login") if isinstance(owner_payload, dict) else None
    if not name or not owner:
        progress.resolved += 1
        return None

    full_name = repo.get("full_name") or f"{owner}/{name}"
    is_fork = bool(repo.get("fork"))
    version_token = str(repo.get("pushed_at") or repo.get("updated_at") or "head")
    cache_key = _cache_key(full_name, username, version_token)

    cached = await cache.get_json(cache_key)
    if cached:
        try:
            restored = RepoContribution.model_validate(cached)
            progress.resolved += 1
            return restored
        except Exception:
            pass

    # Nothing cached, and no budget left to measure it now. A later call will
    # pick this repo up once the earlier ones are cached and cost nothing.
    if cache_only or deadline.expired:
        progress.deferred += 1
        return None

    # List first, then reserve budget for exactly the commits that exist. Sizing
    # the reservation from the listing keeps a repo with five commits from
    # holding 200 slots that another repo needs.
    shas = await _list_commit_shas(
        client, owner, name, username, token, settings.max_commits_per_repo, deadline
    )

    # A listing that stopped short of the cap has already enumerated every
    # commit, so the separate count request is only needed when it filled up.
    if len(shas) < settings.max_commits_per_repo:
        total_user_commits = len(shas)
    else:
        total_user_commits = await _count_user_commits(
            client, owner, name, username, token
        )

    if total_user_commits == 0:
        # A repo the user never committed to is settled, not deferred -- but an
        # empty listing also happens when the deadline cut the paging short, and
        # that repo still needs measuring on a later call.
        if deadline.expired:
            progress.deferred += 1
        else:
            progress.resolved += 1
        return None

    granted = await budget.take(len(shas))
    shas = shas[:granted]
    truncated = granted < total_user_commits

    additions_by_language: Dict[str, int] = {}
    deletions_by_language: Dict[str, int] = {}
    files_by_language: Dict[str, int] = {}
    measured_additions = measured_deletions = measured_files = 0

    if shas:
        file_lists = await asyncio.gather(
            *(
                _fetch_commit_files(
                    client, owner, name, sha, token, semaphore, deadline, guard
                )
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

    stats = await _fetch_contributor_totals(
        client, owner, name, username, token, deadline
    )

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
            # Missing stats can mean the deadline cut them off rather than the
            # user genuinely having nothing here, so only claim this repo as
            # settled when there was budget left to ask properly.
            if deadline.expired:
                progress.deferred += 1
            else:
                progress.resolved += 1
            return None

        language_bytes = await _fetch_repo_language_bytes(client, owner, name, token)
        if not language_bytes:
            progress.resolved += 1
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

    if deadline.expired:
        # The deadline cut this measurement short, so it undercounts. Hand it
        # back for this response but leave the cache empty, otherwise a
        # truncated figure would be served for the whole TTL.
        progress.deferred += 1
        return contribution

    await cache.set_json(
        cache_key, contribution.model_dump(), settings.cache_ttl_seconds
    )
    progress.resolved += 1
    return contribution


async def get_user_contributions(
    username: str,
    token: str,
    excluded_languages: Optional[List[str]] = None,
    include_forks: bool = True,
    include_repositories: bool = True,
    deadline_seconds: Optional[float] = None,
    cache_only: bool = False,
) -> ContributionLanguageStats:
    """Aggregate every repository's per-user attribution into one breakdown.

    ``deadline_seconds`` caps the wall-clock time spent measuring uncached
    repos; ``cache_only`` measures nothing and reports only what is already
    cached. Either way the result says how many repos it covered, so callers
    can decide whether the language mix is representative enough to serve.
    """
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        repos_url = f"{GITHUB_API}/users/{username}/repos"
        params = {"per_page": "100", "sort": "pushed", "type": "all"}
        response = await client.get(
            repos_url, params=params, headers=github_headers(token)
        )

        raise_for_github_status(response, username)

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
        guard = RateLimitGuard(settings.rate_limit_floor)
        guard.observe(response)
        deadline = Deadline(deadline_seconds, guard)
        repo_slots = asyncio.Semaphore(settings.repo_concurrency)
        progress = WalkProgress()

        async def measure(repo: Dict[str, Any]) -> Optional[RepoContribution]:
            async with repo_slots:
                return await analyze_repo_contribution(
                    client,
                    repo,
                    username,
                    token,
                    budget,
                    semaphore,
                    deadline=deadline,
                    cache_only=cache_only,
                    progress=progress,
                    guard=guard,
                )

        # Candidates are newest-pushed first, so when the deadline cuts the walk
        # short the repos that were measured are the ones the user works in now.
        results = await asyncio.gather(
            *(measure(repo) for repo in candidates),
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
    considered = progress.resolved + progress.deferred
    cache_enabled = cache.redis_enabled()
    status, message = _explain(progress, guard, cache_enabled, cache_only)

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
        repos_considered=considered,
        coverage=round(progress.resolved / considered, 4) if considered else 0.0,
        partial=progress.deferred > 0,
        status=status,
        message=message,
        cache_enabled=cache_enabled,
        repositories=contributions if include_repositories else [],
    )
