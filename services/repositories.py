import asyncio
import base64
import re
import time
from typing import Dict, List, Optional, cast

import httpx
from fastapi import HTTPException

from core import cache
from core.config import attribution_settings, cache_rate_limit_settings
from models.attribution import RepoContribution
from models.repositories import Contributor, ReleaseAsset, RepoDetail, RepoRelease
from services.attribution import AttributionBudget, analyze_repo_contribution
from services.client import github_headers, list_user_repositories

BASE_GITHUB_URL = "https://github.com"
GITHUB_API = "https://api.github.com"

# Portfolio consumers need README + languages most. Contributors, releases, and
# commit counts cost three extra GitHub round-trips each and were pushing the
# whole /repos payload past Vercel's function timeout before Redis could warm.
REPO_DETAILS_CACHE_PREFIX = "repo_details:v2"


def _repo_details_cache_key(username: str, full: bool, attributed: bool) -> str:
    mode = "full" if full else "lite"
    attr = "attr" if attributed else "plain"
    return f"{REPO_DETAILS_CACHE_PREFIX}:{username.lower()}:{mode}:{attr}"


def _extract_url_from_description(description: Optional[str]) -> Optional[str]:
    if not description:
        return None
    match = re.search(r"(https?://[^\s]+)", description)
    return match.group(1) if match else None


def _decode_readme_to_markdown(content_b64: Optional[str]) -> Optional[str]:
    if not content_b64:
        return None

    try:
        normalized = content_b64.replace("\n", "")
        decoded = base64.b64decode(normalized, validate=False)
        text = decoded.decode("utf-8", errors="replace").strip()
        return text or None
    except Exception:
        return None


async def _fetch_releases(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str, limit: int = 5
) -> List[RepoRelease]:
    releases_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/releases?per_page={limit}"
    try:
        response = await client.get(releases_url, headers=github_headers(token))
        if response.status_code != 200:
            return []

        releases_data = response.json()
        if not isinstance(releases_data, list):
            return []

        releases: List[RepoRelease] = []
        for rel in releases_data:
            if not isinstance(rel, dict):
                continue

            assets_data = rel.get("assets")
            assets: List[ReleaseAsset] = []
            if isinstance(assets_data, list):
                for asset in assets_data:
                    if not isinstance(asset, dict):
                        continue
                    download_url = asset.get("browser_download_url")
                    if not isinstance(download_url, str) or not download_url:
                        continue

                    assets.append(
                        ReleaseAsset(
                            name=asset.get("name") or "asset",
                            download_url=download_url,
                            size=asset.get("size") or 0,
                            download_count=asset.get("download_count") or 0,
                            content_type=asset.get("content_type"),
                            updated_at=asset.get("updated_at"),
                        )
                    )

            releases.append(
                RepoRelease(
                    id=rel.get("id") or 0,
                    tag_name=rel.get("tag_name") or "untagged",
                    name=rel.get("name"),
                    body=rel.get("body"),
                    url=rel.get("html_url")
                    or f"{BASE_GITHUB_URL}/{owner}/{repo_name}/releases",
                    draft=bool(rel.get("draft")),
                    prerelease=bool(rel.get("prerelease")),
                    created_at=rel.get("created_at"),
                    published_at=rel.get("published_at"),
                    assets=assets,
                )
            )

        return releases
    except Exception:
        return []


async def _get_commit_count(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str
) -> int:
    commits_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/commits?per_page=1"
    try:
        response = await client.get(commits_url, headers=github_headers(token))
        if response.status_code == 200:
            link_header = response.headers.get("Link")
            if link_header:
                match = re.search(r'<.*?page=(\d+)>; rel="last"', link_header)
                if match:
                    return int(match.group(1))
            page_commits = response.json()
            if page_commits:
                return len(page_commits) if isinstance(page_commits, list) else 0
            return 0
        elif response.status_code in [404, 403]:
            return 0
        response.raise_for_status()
        return 0
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 409:
            return 0
        return 0
    except Exception:
        return 0


async def _fetch_contributors(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str
) -> List[Contributor]:
    contributors_url = (
        f"{GITHUB_API}/repos/{owner}/{repo_name}/contributors?per_page=10"
    )
    try:
        response = await client.get(contributors_url, headers=github_headers(token))
        if response.status_code == 200:
            contributors_data = response.json()
            return [
                Contributor(
                    login=c["login"],
                    avatar_url=c["avatar_url"],
                    html_url=c["html_url"],
                    contributions=c["contributions"],
                )
                for c in contributors_data
                if isinstance(c, dict)
            ]
        return []
    except Exception:
        return []


async def _attribute_repos(
    client: httpx.AsyncClient, repos: List[Dict], username: str, token: str
) -> Dict[str, RepoContribution]:
    """Per-user contribution for each repo, keyed by ``owner/name``.

    Cache-only: this endpoint is already the heaviest one in the API, and
    measuring commit diffs here would push it past the function timeout. Repos
    show their ``user_*`` fields once the attribution cache has been warmed by
    ``/{username}/contributions/breakdown`` or the warm script.
    """
    # Nothing is spent in cache-only mode, so the budget and semaphore are just
    # the arguments the signature wants.
    budget = AttributionBudget(0)
    semaphore = asyncio.Semaphore(1)

    results = await asyncio.gather(
        *(
            analyze_repo_contribution(
                client,
                repo,
                username,
                token,
                budget,
                semaphore,
                cache_only=True,
            )
            for repo in repos[: attribution_settings.max_repos]
            if isinstance(repo, dict)
        ),
        return_exceptions=True,
    )

    attributed: Dict[str, RepoContribution] = {}
    for result in results:
        if isinstance(result, RepoContribution):
            attributed[result.full_name] = result
            attributed.setdefault(result.repo, result)
    return attributed


def _live_url_for_repo(repo: Dict) -> Optional[str]:
    homepage_url = repo.get("homepage")
    if (
        homepage_url
        and isinstance(homepage_url, str)
        and homepage_url.startswith(("http://", "https://"))
    ):
        return homepage_url
    return _extract_url_from_description(repo.get("description"))


def _topics_for_repo(repo: Dict) -> List[str]:
    topics_raw = repo.get("topics") or []
    if not isinstance(topics_raw, list):
        return []
    return [str(t) for t in topics_raw if t]


def _primary_language_list(repo: Dict) -> List[str]:
    language = repo.get("language")
    if isinstance(language, str) and language:
        return [language]
    return []


def _skeleton_repo_detail(
    repo: Dict, contribution: Optional[RepoContribution] = None
) -> RepoDetail:
    """List-endpoint fields only — used when the request budget is exhausted."""
    return RepoDetail(
        title=repo["name"],
        description=repo.get("description"),
        live_website_url=_live_url_for_repo(repo),
        languages=_primary_language_list(repo),
        topics=_topics_for_repo(repo),
        num_commits=0,
        stars=repo.get("stargazers_count", 0) or 0,
        readme=None,
        contributors=[],
        releases=[],
        is_fork=bool(repo.get("fork")),
        user_commits=contribution.commits if contribution else 0,
        user_additions=contribution.additions if contribution else 0,
        user_deletions=contribution.deletions if contribution else 0,
        user_files_changed=contribution.files_changed if contribution else 0,
        user_languages=contribution.languages if contribution else [],
        contribution_percentage=(
            contribution.contribution_percentage if contribution else None
        ),
    )


async def fetch_repo_details(
    client: httpx.AsyncClient,
    repo: Dict,
    token: str,
    contribution: Optional[RepoContribution] = None,
    *,
    full: bool = False,
) -> Optional[RepoDetail]:
    repo_name = repo["name"]
    owner = repo["owner"]["login"]

    readme_content_markdown = None
    # Prefer the list payload's primary language so a languages call failure
    # still leaves the card usable.
    languages_list = _primary_language_list(repo)
    contributors_list: List[Contributor] = []
    releases_list: List[RepoRelease] = []
    num_commits = 0

    async def get_readme():
        nonlocal readme_content_markdown
        readme_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/readme"
        try:
            readme_resp = await client.get(readme_url, headers=github_headers(token))
            if readme_resp.status_code == 200:
                readme_content_markdown = _decode_readme_to_markdown(
                    readme_resp.json().get("content")
                )
        except Exception:
            pass

    async def get_languages():
        nonlocal languages_list
        languages_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/languages"
        try:
            languages_resp = await client.get(
                languages_url, headers=github_headers(token)
            )
            if languages_resp.status_code == 200:
                keys = list(languages_resp.json().keys())
                if keys:
                    languages_list = keys
        except Exception:
            pass

    async def get_contributors():
        nonlocal contributors_list
        contributors_list = await _fetch_contributors(client, owner, repo_name, token)

    async def get_releases():
        nonlocal releases_list
        releases_list = await _fetch_releases(client, owner, repo_name, token)

    async def get_commit_count():
        nonlocal num_commits
        num_commits = await _get_commit_count(client, owner, repo_name, token)

    # Lite path (default): README + languages only — enough for portfolio pages
    # and ~2 GitHub calls per repo instead of 5.
    tasks = [get_readme(), get_languages()]
    if full:
        tasks.extend([get_contributors(), get_releases(), get_commit_count()])

    await asyncio.gather(*tasks)

    return RepoDetail(
        title=repo_name,
        description=repo.get("description"),
        live_website_url=_live_url_for_repo(repo),
        languages=languages_list,
        topics=_topics_for_repo(repo),
        num_commits=num_commits,
        stars=repo.get("stargazers_count", 0) or 0,
        readme=readme_content_markdown,
        contributors=contributors_list,
        releases=releases_list,
        is_fork=bool(repo.get("fork")),
        user_commits=contribution.commits if contribution else 0,
        user_additions=contribution.additions if contribution else 0,
        user_deletions=contribution.deletions if contribution else 0,
        user_files_changed=contribution.files_changed if contribution else 0,
        user_languages=contribution.languages if contribution else [],
        contribution_percentage=(
            contribution.contribution_percentage if contribution else None
        ),
    )


async def get_repo_details(
    username: str,
    token: str,
    attributed: bool = True,
    *,
    full: bool = False,
) -> List[RepoDetail]:
    """
    Get detailed information for all public repositories of a user.

    Args:
        username: GitHub username
        token: GitHub API token
        attributed: Fill the ``user_*`` fields from cached own-commit
            attribution. Reads the cache only, never walks commit diffs
        full: When True, also fetch contributors, releases, and commit counts.
            Default is the lite portfolio path (README + languages) so the
            endpoint finishes inside a serverless function budget.

    Returns:
        List of repository details
    """
    cache_key = _repo_details_cache_key(username, full=full, attributed=attributed)
    cached = await cache.get_json(cache_key)
    if cached and isinstance(cached.get("repos"), list):
        try:
            return [RepoDetail.model_validate(item) for item in cached["repos"]]
        except Exception:
            pass

    # Leave headroom under the platform timeout so we can still serialize and
    # write the cache even when the account has many repos.
    deadline = time.monotonic() + attribution_settings.repo_details_deadline_seconds

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            repos, _ = await list_user_repositories(
                client, username, token, sort="updated", repo_type="all"
            )
            if not repos:
                return []

            contributions: Dict[str, RepoContribution] = {}
            if attributed:
                contributions = await _attribute_repos(client, repos, username, token)

            slots = asyncio.Semaphore(attribution_settings.repo_detail_concurrency)

            async def detail_for(repo: Dict) -> Optional[RepoDetail]:
                contribution = contributions.get(
                    repo.get("full_name") or repo.get("name", "")
                )
                if time.monotonic() >= deadline:
                    return _skeleton_repo_detail(repo, contribution)
                async with slots:
                    if time.monotonic() >= deadline:
                        return _skeleton_repo_detail(repo, contribution)
                    return await fetch_repo_details(
                        client,
                        repo,
                        token,
                        contribution,
                        full=full,
                    )

            repo_details = await asyncio.gather(
                *(detail_for(repo) for repo in repos), return_exceptions=True
            )

            valid_repo_details: List[RepoDetail] = [
                cast(RepoDetail, detail)
                for detail in repo_details
                if detail is not None and not isinstance(detail, Exception)
            ]

            # Only cache when at least one README landed — a pure-skeleton
            # timeout would otherwise poison the cache for the whole TTL.
            if any(detail.readme for detail in valid_repo_details):
                await cache.set_json(
                    cache_key,
                    {
                        "repos": [
                            detail.model_dump(mode="json")
                            for detail in valid_repo_details
                        ]
                    },
                    cache_rate_limit_settings.cache_ttl_seconds,
                )

            return valid_repo_details

        except HTTPException:
            # Already carries the right status (404 missing user, 503 throttled);
            # the catch-all below would otherwise rewrite it as a 500.
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found")
            raise HTTPException(status_code=500, detail="GitHub API error")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error fetching repository details: {str(e)}"
            )
