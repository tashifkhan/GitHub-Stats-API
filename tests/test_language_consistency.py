"""One language definition across JSON, cards, filters, and cache states."""

import asyncio
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from models.analytics import GitHubStatsResponse, LanguageData
from models.attribution import ContributionLanguageStats, LanguageContribution
from routes.analytics import analytics_router
from routes.dependencies import get_analytics_service, parse_excluded_languages
from services import attribution, languages
from services.analytics_service import AnalyticsService
from services.canonical_mapper import stats_from
from services.language_distribution import DEFAULT_EXCLUDED_LANGUAGES, language_distribution
from services.stats_svg import render_stats_svg


def test_rounding_totals_exactly_100_and_ties_ignore_input_order():
    first = language_distribution({"Rust": 1, "Python": 1, "Go": 1, "Markdown": 100}, ["MARKDOWN"])
    second = language_distribution({"Go": 1, "Python": 1, "Rust": 1})
    assert first == second
    assert [(name, pct) for name, _, pct in first] == [
        ("Go", 33.34), ("Python", 33.33), ("Rust", 33.33),
    ]
    assert sum(Decimal(str(pct)) for _, _, pct in first) == Decimal("100.00")


def test_explicit_empty_exclusion_allows_every_language():
    assert parse_excluded_languages(exclude="", default=DEFAULT_EXCLUDED_LANGUAGES) == []


@pytest.mark.parametrize("truncated", [False, True])
def test_public_ranking_never_publishes_incomplete_measurements(monkeypatch, truncated):
    calls = []

    async def raw(*args, **kwargs):
        calls.append(kwargs)
        return ContributionLanguageStats(
            username="tashifkhan", repos_considered=10, coverage=1 if truncated else 0.1,
            partial=not truncated, truncated=truncated,
            languages=[LanguageContribution(name="Python", percentage=100, lines=1)],
        )

    monkeypatch.setattr(languages, "get_user_contributions", raw)
    with pytest.raises(HTTPException) as error:
        asyncio.run(languages.get_attributed_language_stats("tashifkhan", "unused", []))
    assert error.value.detail["code"] == "language_attribution_pending"
    assert calls[0]["cache_only"] is True


def test_pending_languages_preserve_core_stats_with_explicit_state(monkeypatch):
    from services import analytics_service

    async def graph(*args, **kwargs):
        return {}

    async def pending(*args, **kwargs):
        raise HTTPException(503, detail={
            "code": "language_attribution_pending", "coverage": 0.2, "partial": True,
        })

    async def views(*args, **kwargs):
        return 0

    monkeypatch.setattr(analytics_service, "get_contribution_graphs", graph)
    monkeypatch.setattr(analytics_service, "get_profile_views", views)
    service = AnalyticsService("unused")
    monkeypatch.setattr(service, "get_user_language_stats", pending)
    stats = asyncio.run(service.get_user_stats("tashifkhan", None))
    assert stats.topLanguages == []
    assert stats.languageStats["status"] == "pending"
    assert stats.languageStats["coverage"] == 0.2
    assert stats.languageStats["excluded"] == DEFAULT_EXCLUDED_LANGUAGES


@pytest.mark.parametrize("pending", [False, True])
def test_language_defaults_and_precision_match_across_live_routes(monkeypatch, pending):
    from core import middleware
    from core.rate_limit import RateLimitResult

    requested = []
    stored = {}
    data = [LanguageData(name="Python", percentage=99.75), LanguageData(name="Rust", percentage=0.25)]

    class Service:
        async def get_user_language_stats(self, username, excluded, **kwargs):
            requested.append(excluded)
            if pending:
                raise HTTPException(503, detail={"code": "language_attribution_pending"}, headers={"Cache-Control": "no-store"})
            return data

        async def get_user_stats(self, username, excluded, **kwargs):
            requested.append(excluded)
            return GitHubStatsResponse(
                status="success", message="retrieved", topLanguages=[] if pending else data,
                totalCommits=12, longestStreak=2, currentStreak=1,
                languageStats={"status": "pending" if pending else "complete", "basis": "authored_additions"},
            )

        async def get_user_stars(self, username):
            return None

    async def get_cache(key):
        return stored.get(key)

    async def set_cache(key, value, ttl):
        stored[key] = value

    async def allowed(*args, **kwargs):
        return RateLimitResult(allowed=True)

    monkeypatch.setattr(middleware, "redis_enabled", lambda: True)
    monkeypatch.setattr(middleware, "get_json", get_cache)
    monkeypatch.setattr(middleware, "set_json", set_cache)
    monkeypatch.setattr(middleware, "check_rate_limit", allowed)
    app = FastAPI()
    app.include_router(analytics_router)
    app.dependency_overrides[get_analytics_service] = Service
    app.add_middleware(middleware.CacheRateLimitMiddleware, platform="github")
    with TestClient(app) as client:
        language_response = client.get("/tashifkhan/languages")
        stats_response = client.get("/tashifkhan/stats")
        svg_response = client.get("/tashifkhan/stats/svg")
    assert requested == [DEFAULT_EXCLUDED_LANGUAGES] * 3
    assert stats_response.status_code == svg_response.status_code == 200
    if pending:
        assert language_response.status_code == 503
        assert stats_response.json()["languageStats"]["status"] == "pending"
        assert "Languages pending" in svg_response.text
        assert stats_response.headers["Cache-Control"] == svg_response.headers["Cache-Control"] == "no-store"
        assert stored == {}
    else:
        assert language_response.json() == stats_response.json()["topLanguages"]
        topics = stats_response.json()["data"]["topicAnalysis"]
        assert topics == [{"topic": "Python", "count": 99.75}, {"topic": "Rust", "count": 0.25}]
        assert "99.75%" in svg_response.text and "0.25%" in svg_response.text
        assert language_response.headers["X-Language-Basis"] == "authored_additions"


def test_repo_task_failures_are_missing_coverage(monkeypatch):
    async def repos(*args, **kwargs):
        return [{"name": "broken"}, {"name": "fine"}], None

    async def measure(client, repo, *args, **kwargs):
        if repo["name"] == "broken":
            raise RuntimeError("failed measurement")
        kwargs["progress"].resolved += 1
        return None

    monkeypatch.setattr(attribution, "list_user_repositories", repos)
    monkeypatch.setattr(attribution, "analyze_repo_contribution", measure)
    result = asyncio.run(attribution.get_user_contributions("tashifkhan", "unused"))
    assert result.partial is True
    assert result.repos_considered == 2
    assert result.coverage == 0.5


def test_commit_files_follow_pagination_before_computing_language_mix():
    def handler(request):
        second = request.url.params.get("page") == "2"
        files = [{"filename": "main.rs" if second else "main.py", "additions": 9 if second else 1}]
        headers = {} if second else {"Link": '<https://api.github.com/repos/o/r/commits/sha?page=2>; rel="next"'}
        return httpx.Response(200, json={"parents": [{}], "files": files}, headers=headers)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await attribution._fetch_commit_files(client, "o", "r", "sha", "unused", asyncio.Semaphore(1), attribution.Deadline(None))

    files = asyncio.run(run())
    assert [file["filename"] for file in files] == ["main.py", "main.rs"]


def test_svg_percentages_survive_canonical_mapping():
    response = GitHubStatsResponse(
        status="success", message="retrieved", totalCommits=1, longestStreak=0, currentStreak=0,
        topLanguages=[LanguageData(name="Python", percentage=99.75), LanguageData(name="Rust", percentage=0.25)],
    )
    svg = render_stats_svg("github", "tashifkhan", stats_from(response))
    assert "99.75%" in svg and "0.25%" in svg


@pytest.mark.parametrize("failure", [None, 404, 503])
def test_repository_bytes_respect_forks_filters_and_failures(monkeypatch, failure):
    original_client = httpx.AsyncClient
    urls = []

    async def repos(*args, **kwargs):
        return [
            {"languages_url": "https://api.github.com/owned/languages"},
            {"languages_url": "https://api.github.com/fork/languages", "fork": True},
        ], None

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(failure or 200, json={"Python": 75, "Rust": 25, "Markdown": 100})

    monkeypatch.setattr(languages, "list_user_repositories", repos)
    monkeypatch.setattr(languages.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    call = languages.get_language_stats("tashifkhan", "unused", ["MARKDOWN"], include_forks=False)
    if failure:
        with pytest.raises(HTTPException) as error:
            asyncio.run(call)
        assert error.value.status_code == 502
    else:
        result = asyncio.run(call)
        assert [(item.name, item.percentage) for item in result] == [("Python", 75), ("Rust", 25)]
    assert urls == ["https://api.github.com/owned/languages"]


def test_commit_listing_keeps_page_size_constant_at_a_non_round_limit():
    page_sizes = []

    def handler(request):
        size, page = int(request.url.params["per_page"]), int(request.url.params["page"])
        page_sizes.append(size)
        start = (page - 1) * size
        return httpx.Response(200, json=[{"sha": str(i)} for i in range(start, start + size)])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await attribution._list_commit_shas(client, "o", "r", "tashifkhan", "unused", 250, attribution.Deadline(None))

    assert asyncio.run(run()) == [str(i) for i in range(250)]
    assert page_sizes == [100, 100, 100]


def test_commit_listing_failure_does_not_become_a_successful_zero():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
            return await attribution._list_commit_shas(client, "o", "r", "tashifkhan", "unused", 200, attribution.Deadline(None))

    with pytest.raises(HTTPException):
        asyncio.run(run())
