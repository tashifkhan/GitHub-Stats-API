"""Cache middleware must accept collection endpoint responses."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.middleware import _is_invalid_user


def _body(payload) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_successful_json_array_is_not_an_invalid_user():
    assert _is_invalid_user(200, _body([{"name": "jportal"}])) is False


def test_error_envelope_can_still_mark_an_invalid_user():
    payload = {"status": "error", "message": "User not found"}
    assert _is_invalid_user(400, _body(payload)) is True


def test_404_is_always_an_invalid_user():
    assert _is_invalid_user(404, _body([])) is True


@pytest.mark.parametrize("complete", [True, False])
def test_repo_response_caches_only_complete_contributors(monkeypatch, complete):
    from core import middleware
    from core.rate_limit import RateLimitResult
    from models.repositories import RepoDetail
    from routes.analytics import analytics_router
    from routes.dependencies import get_analytics_service

    cached = {}
    calls = []

    async def get_cache(key):
        return cached.get(key)

    async def set_cache(key, value, ttl):
        cached[key] = value

    async def allowed(*args, **kwargs):
        return RateLimitResult(allowed=True)

    class Service:
        async def get_user_repos(self, username, **kwargs):
            calls.append(username)
            return [RepoDetail(
                title="repo", description=None, live_website_url=None,
                languages=[], num_commits=0, readme="# Repo", contributors_complete=complete,
            )]

    monkeypatch.setattr(middleware, "redis_enabled", lambda: True)
    monkeypatch.setattr(middleware, "get_json", get_cache)
    monkeypatch.setattr(middleware, "set_json", set_cache)
    monkeypatch.setattr(middleware, "check_rate_limit", allowed)
    app = FastAPI()
    app.include_router(analytics_router)
    app.dependency_overrides[get_analytics_service] = lambda: Service()
    app.add_middleware(middleware.CacheRateLimitMiddleware, platform="github")
    with TestClient(app) as client:
        first = client.get("/user/repos")
        second = client.get("/user/repos")
    assert first.status_code == second.status_code == 200
    assert second.json()[0]["contributors_complete"] is complete
    assert len(calls) == (1 if complete else 2)
    assert bool(cached) is complete
    if not complete:
        assert second.headers["cache-control"] == "no-store"
