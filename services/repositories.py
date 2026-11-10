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
from models.repositories import (
    Contributor,
    ReleaseAsset,
    ReleasePage,
    RepoDetail,
    RepoRelease,
    RepoReleases,
)
from services.attribution import (
    AttributionBudget, Deadline, RateLimitGuard, analyze_repo_contribution,
    authorship_cache_key, scan_commit_authors,
)
from services.client import github_headers, list_user_repositories

BASE_GITHUB_URL = "https://github.com"
GITHUB_API = "https://api.github.com"

# Portfolio consumers need README, languages, contributors, and releases.
# Commit counts remain opt-in because that extra REST round-trip per repository
# pushed the whole /repos payload past Vercel's function timeout. Releases come
# from one batched GraphQL query per 50 repos instead of a REST call per repo.
# README.md itself is fetched from GitHub's raw CDN first, preserving the REST
# API quota for metadata that cannot be served there.
#
# v8 includes co-authors in contributors and reports discovery completeness.
# v9 adds releases to the default lite response.
# v10 embeds the first page of releases with releases_page metadata; the rest
# come from /{owner}/repos/{repo}/releases.
REPO_DETAILS_CACHE_PREFIX = "repo_details:v10"
RELEASE_PAGE_CACHE_PREFIX = "repo_releases:v1"

# Releases embedded per repo in /repos, and the default page size of the
# releases endpoint. Clients follow releases_page.next for older ones.
RELEASES_PER_PAGE = 10
# GitHub's largest page, for releases and for assets on each release.
MAX_RELEASES_PER_PAGE = 100
# A GraphQL query may touch at most 500k nodes:
# 50 repos x 10 releases x 100 assets is 50k.
RELEASE_BATCH_SIZE = 50


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


def releases_next_path(owner: str, repo: str, page: int, per_page: int) -> str:
    return f"/{owner}/repos/{repo}/releases?page={page}&per_page={per_page}"


def _release_page_meta(
    owner: str,
    repo: str,
    page: int,
    per_page: int,
    total_count: Optional[int],
    has_more: Optional[bool] = None,
) -> ReleasePage:
    if has_more is None:
        has_more = total_count is not None and page * per_page < total_count
    return ReleasePage(
        total_count=total_count,
        page=page,
        per_page=per_page,
        has_more=has_more,
        next=releases_next_path(owner, repo, page + 1, per_page) if has_more else None,
    )


async def _release_total_count(
    client: httpx.AsyncClient, owner: str, repo_name: str, token: str
) -> Optional[int]:
    """How many releases the repo has. REST cannot say without walking pages."""
    if not token:
        return None
    query = (
        f"query {{ r: repository(owner: {_graphql_string(owner)}, "
        f"name: {_graphql_string(repo_name)}) {{ releases {{ totalCount }} }} }}"
    )
    data = await _graphql_query(client, token, query)
    count = (((data or {}).get("r") or {}).get("releases") or {}).get("totalCount")
    return count if isinstance(count, int) else None


async def fetch_release_page(
    client: httpx.AsyncClient,
    owner: str,
    repo_name: str,
    token: str,
    page: int = 1,
    per_page: int = RELEASES_PER_PAGE,
) -> Optional[RepoReleases]:
    """One page of a repo's releases, newest first. None when the repo is missing.

    The page itself comes from REST, whose page/per_page map straight onto the
    API's. has_more trusts GitHub's Link header; total_count is one small
    GraphQL lookup run alongside.
    """
    releases_url = (
        f"{GITHUB_API}/repos/{owner}/{repo_name}/releases"
        f"?per_page={per_page}&page={page}"
    )
    response, total_count = await asyncio.gather(
        client.get(releases_url, headers=github_headers(token)),
        _release_total_count(client, owner, repo_name, token),
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="GitHub releases request failed")
    data = response.json()
    rows = data if isinstance(data, list) else []
    releases = [
        _release_from_rest(rel, owner, repo_name) for rel in rows if isinstance(rel, dict)
    ]
    link = response.headers.get("Link") or ""
    return RepoReleases(
        owner=owner,
        repo=repo_name,
        releases=releases,
        releases_page=_release_page_meta(
            owner,
            repo_name,
            page,
            per_page,
            total_count,
            has_more='rel="next"' in link,
        ),
    )


async def get_release_page(
    owner: str, repo_name: str, token: str, page: int, per_page: int
) -> RepoReleases:
    """Cached wrapper around fetch_release_page for the releases endpoint."""
    cache_key = f"{RELEASE_PAGE_CACHE_PREFIX}:{owner.lower()}:{repo_name.lower()}:{page}:{per_page}"
    cached = await cache.get_json(cache_key)
    if cached:
        try:
            return RepoReleases.model_validate(cached)
        except Exception:
            pass
    async with httpx.AsyncClient(timeout=12.0) as client:
        result = await fetch_release_page(client, owner, repo_name, token, page, per_page)
    if result is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    await cache.set_json(
        cache_key,
        result.model_dump(mode="json"),
        cache_rate_limit_settings.cache_ttl_seconds,
    )
    return result


def _release_from_rest(rel: Dict, owner: str, repo_name: str) -> RepoRelease:
    assets: List[ReleaseAsset] = []
    for asset in rel.get("assets") or []:
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
    return RepoRelease(
        id=rel.get("id") or 0,
        tag_name=rel.get("tag_name") or "untagged",
        name=rel.get("name"),
        body=rel.get("body"),
        url=rel.get("html_url") or f"{BASE_GITHUB_URL}/{owner}/{repo_name}/releases",
        draft=bool(rel.get("draft")),
        prerelease=bool(rel.get("prerelease")),
        created_at=rel.get("created_at"),
        published_at=rel.get("published_at"),
        assets=assets,
    )


def _release_fields(first: int = RELEASES_PER_PAGE) -> str:
    return f"""
        releases(first: {first}, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
            totalCount
            nodes {{
                databaseId tagName name description url isDraft isPrerelease
                createdAt publishedAt
                releaseAssets(first: {MAX_RELEASES_PER_PAGE}) {{
                    nodes {{ name downloadUrl size downloadCount contentType updatedAt }}
                }}
            }}
        }}
    """


async def _graphql_query(
    client: httpx.AsyncClient, token: str, query: str
) -> Optional[Dict]:
    try:
        response = await client.post(
            f"{GITHUB_API}/graphql",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"query": query},
        )
        if response.status_code != 200:
            return None
        return (response.json() or {}).get("data") or {}
    except Exception:
        return None


def _graphql_string(value: str) -> str:
    """Quote a value for inline use in a GraphQL document."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _release_from_graphql(node: Dict, owner: str, repo_name: str) -> RepoRelease:
    assets: List[ReleaseAsset] = []
    for asset in (node.get("releaseAssets") or {}).get("nodes") or []:
        if not isinstance(asset, dict) or not asset.get("downloadUrl"):
            continue
        assets.append(
            ReleaseAsset(
                name=asset.get("name") or "asset",
                download_url=asset["downloadUrl"],
                size=asset.get("size") or 0,
                download_count=asset.get("downloadCount") or 0,
                content_type=asset.get("contentType"),
                updated_at=asset.get("updatedAt"),
            )
        )
    return RepoRelease(
        id=node.get("databaseId") or 0,
        tag_name=node.get("tagName") or "untagged",
        name=node.get("name"),
        body=node.get("description"),
        url=node.get("url") or f"{BASE_GITHUB_URL}/{owner}/{repo_name}/releases",
        draft=bool(node.get("isDraft")),
        prerelease=bool(node.get("isPrerelease")),
        created_at=node.get("createdAt"),
        published_at=node.get("publishedAt"),
        assets=assets,
    )


async def _fetch_releases_batch(
    client: httpx.AsyncClient, repos: List[Dict], token: str
) -> Dict[str, RepoReleases]:
    """First page of releases for many repos via aliased GraphQL lookups.

    Keyed by ``owner/name``. One request per ``RELEASE_BATCH_SIZE`` repos keeps
    releases in the lite path without the per-repo REST round-trip that blew
    the function timeout. A failed batch leaves its repos out of the map;
    callers treat a missing key as "unknown", not "no releases".
    """
    targets = [
        (repo["owner"]["login"], repo["name"])
        for repo in repos
        if isinstance(repo, dict) and repo.get("name") and repo.get("owner")
    ]
    if not token or not targets:
        return {}

    release_fields = _release_fields()

    async def run_batch(batch: List[tuple]) -> Dict[str, RepoReleases]:
        aliases = "\n".join(
            f"r{i}: repository(owner: {_graphql_string(owner)}, name: {_graphql_string(name)}) {{ {release_fields} }}"
            for i, (owner, name) in enumerate(batch)
        )
        data = await _graphql_query(client, token, f"query {{ {aliases} }}")
        if data is None:
            return {}

        found: Dict[str, RepoReleases] = {}
        for i, (owner, name) in enumerate(batch):
            repo_data = data.get(f"r{i}")
            # null means GitHub could not resolve this repo; leave it unknown.
            if not isinstance(repo_data, dict):
                continue
            connection = repo_data.get("releases") or {}
            releases = [
                _release_from_graphql(node, owner, name)
                for node in connection.get("nodes") or []
                if isinstance(node, dict)
            ]
            total = connection.get("totalCount")
            found[f"{owner}/{name}".lower()] = RepoReleases(
                owner=owner,
                repo=name,
                releases=releases,
                releases_page=_release_page_meta(
                    owner,
                    name,
                    1,
                    RELEASES_PER_PAGE,
                    total if isinstance(total, int) else None,
                ),
            )
        return found

    batches = [
        targets[i : i + RELEASE_BATCH_SIZE]
        for i in range(0, len(targets), RELEASE_BATCH_SIZE)
    ]
    merged: Dict[str, RepoReleases] = {}
    for result in await asyncio.gather(*(run_batch(b) for b in batches)):
        merged.update(result)
    return merged


def _releases_key(repo: Dict) -> str:
    return f"{repo['owner']['login']}/{repo['name']}".lower()


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
    client: httpx.AsyncClient, repo: Dict, token: str, deadline: Deadline,
    guard: Optional[RateLimitGuard] = None,
) -> tuple[List[Contributor], bool]:
    owner, repo_name = repo["owner"]["login"], repo["name"]
    scan = await scan_commit_authors(
        client, owner, repo_name, token, deadline,
        guard=guard, checkpoint_key=authorship_cache_key(repo),
    )
    def ranked(entries: List[Contributor]) -> List[Contributor]:
        return sorted(entries, key=lambda item: (-item.contributions, item.login.lower()))[:10]
    if scan.complete:
        return ranked([Contributor.model_validate(item) for item in scan.contributors.values()]), True

    # Keep the existing REST counts while discovery continues. Only add known
    # co-authored credits, since primary-author commits are already in REST.
    contributors: Dict[str, Contributor] = {}
    contributors_url = (
        f"{GITHUB_API}/repos/{owner}/{repo_name}/contributors?per_page=10"
    )
    try:
        response = await client.get(contributors_url, headers=github_headers(token))
        if response.status_code == 200:
            contributors_data = response.json()
            for item in contributors_data:
                if isinstance(item, dict) and item.get("login"):
                    contributor = Contributor.model_validate(item)
                    contributors[contributor.login.lower()] = contributor
    except Exception:
        pass
    for login, stats in scan.coauthors.items():
        if login in contributors:
            contributors[login].contributions += stats["count"]
        else:
            contributors[login] = Contributor.model_validate(scan.contributors[login])
    return ranked(list(contributors.values())), False


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
            for repo in repos
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
    deadline: Optional[Deadline] = None,
    guard: Optional[RateLimitGuard] = None,
    releases: Optional[RepoReleases] = None,
) -> Optional[RepoDetail]:
    """Detail for one repo.

    ``releases`` comes from the batched GraphQL lookup. When it is ``None`` (the
    batch failed or missed this repo) a ``full`` request falls back to REST.
    """
    deadline = deadline or Deadline(attribution_settings.repo_details_deadline_seconds)
    repo_name = repo["name"]
    owner = repo["owner"]["login"]

    readme_content_markdown = None
    # Prefer the list payload's primary language so a languages call failure
    # still leaves the card usable.
    languages_list = _primary_language_list(repo)
    contributors_list: List[Contributor] = []
    contributors_complete = False
    release_page: Optional[RepoReleases] = releases
    num_commits = 0

    async def get_readme():
        nonlocal readme_content_markdown
        try:
            raw_readme_url = (
                f"https://raw.githubusercontent.com/"
                f"{owner}/{repo_name}/HEAD/README.md"
            )
            raw_readme_resp = await client.get(raw_readme_url)
            if raw_readme_resp.status_code == 200:
                readme_content_markdown = raw_readme_resp.text.strip() or None
                if readme_content_markdown:
                    return

            # The Contents API resolves alternate README names and casing. It
            # is only a fallback so conventional README.md files cost no REST
            # API quota.
            readme_url = f"{GITHUB_API}/repos/{owner}/{repo_name}/readme"
            readme_resp = await client.get(
                readme_url, headers=github_headers(token)
            )
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
        nonlocal contributors_list, contributors_complete
        contributors_list, contributors_complete = await _fetch_contributors(
            client, repo, token, deadline, guard
        )

    async def get_releases():
        nonlocal release_page
        try:
            release_page = await fetch_release_page(client, owner, repo_name, token)
        except Exception:
            release_page = None

    async def get_commit_count():
        nonlocal num_commits
        num_commits = await _get_commit_count(client, owner, repo_name, token)

    # Lite path (default): README + languages + contributors, with releases
    # handed in from the batched GraphQL query. README.md normally comes from
    # the raw CDN. Contributor discovery reuses cached authorship scans and
    # resumes unfinished scans within the deadline.
    tasks = [get_readme(), get_languages(), get_contributors()]
    if full:
        tasks.append(get_commit_count())
        if releases is None:
            tasks.append(get_releases())

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
        contributors_complete=contributors_complete,
        releases=release_page.releases if release_page else [],
        releases_page=release_page.releases_page if release_page else None,
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
        full: When True, also fetch commit counts. Releases and contributors
            are included in the default portfolio path alongside README and
            languages.

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
            repos, remaining = await list_user_repositories(
                client, username, token, sort="updated", repo_type="all"
            )
            if not repos:
                return []
            guard = RateLimitGuard(attribution_settings.rate_limit_floor)
            guard.observe_remaining(remaining)

            # One GraphQL pass for every repo's releases (~4s for 95 repos).
            # It runs alongside the per-repo REST work; lite details pick up
            # their releases after both finish.
            releases_task = asyncio.create_task(
                _fetch_releases_batch(client, repos, token)
            )
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
                    # A full request needs to know up front whether the batch
                    # covered this repo, so it can fall back to REST.
                    releases = (
                        (await releases_task).get(_releases_key(repo))
                        if full
                        else None
                    )
                    return await fetch_repo_details(
                        client,
                        repo,
                        token,
                        contribution,
                        full=full,
                        deadline=Deadline(max(0.0, deadline - time.monotonic()), guard),
                        guard=guard,
                        releases=releases,
                    )

            repo_details = await asyncio.gather(
                *(detail_for(repo) for repo in repos), return_exceptions=True
            )

            valid_repo_details: List[RepoDetail] = [
                cast(RepoDetail, detail)
                for detail in repo_details
                if detail is not None and not isinstance(detail, Exception)
            ]

            releases_by_repo = await releases_task
            owner_by_name = {
                repo["name"]: repo["owner"]["login"]
                for repo in repos
                if isinstance(repo, dict) and repo.get("owner")
            }
            for detail in valid_repo_details:
                if detail.releases_page is not None:
                    continue
                owner = owner_by_name.get(detail.title)
                page = (
                    releases_by_repo.get(f"{owner}/{detail.title}".lower())
                    if owner
                    else None
                )
                if page:
                    detail.releases = page.releases
                    detail.releases_page = page.releases_page

            # Unfinished contributor scans must keep progressing on later calls.
            if any(detail.readme for detail in valid_repo_details) and all(
                detail.contributors_complete for detail in valid_repo_details
            ):
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
