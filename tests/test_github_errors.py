"""GitHub failures must map to the right status.

A throttled response used to surface as 404, which the cache middleware treats
as proof the account does not exist -- blacklisting a real user and dropping
them onto the stricter invalid-user rate limit for the rest of the TTL.
"""

import asyncio

import pytest
from fastapi import HTTPException

from services.client import (
    is_rate_limited,
    list_user_repositories,
    raise_for_github_status,
    rate_limit_remaining,
)


class FakeResponse:
    def __init__(self, status_code=200, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload

    def json(self):
        return self._payload


class TestListUserRepositories:
    def test_follows_every_page_instead_of_stopping_at_100(self):
        first_page = [{"name": f"repo-{index}"} for index in range(100)]
        second_page = [{"name": "repo-100"}, {"name": "repo-101"}]

        class FakeClient:
            def __init__(self):
                self.pages = []

            async def get(self, _url, params=None, headers=None):
                page = int(params["page"])
                self.pages.append(page)
                payload = first_page if page == 1 else second_page
                remaining = "4000" if page == 1 else "3999"
                return FakeResponse(
                    headers={"x-ratelimit-remaining": remaining}, payload=payload
                )

        client = FakeClient()
        repositories, remaining = asyncio.run(
            list_user_repositories(client, "many-repos", "token")
        )

        assert len(repositories) == 102
        assert repositories[-1]["name"] == "repo-101"
        assert client.pages == [1, 2]
        assert remaining == 3999


class TestIsRateLimited:
    def test_primary_limit_exhausted(self):
        assert is_rate_limited(
            FakeResponse(403, {"x-ratelimit-remaining": "0"})
        ) is True

    def test_secondary_limit_sends_retry_after(self):
        assert is_rate_limited(FakeResponse(403, {"retry-after": "60"})) is True

    def test_explicit_429(self):
        assert is_rate_limited(FakeResponse(429)) is True

    def test_forbidden_with_budget_left_is_not_throttling(self):
        # A private repo the token cannot see, not a rate limit.
        assert is_rate_limited(
            FakeResponse(403, {"x-ratelimit-remaining": "4321"})
        ) is False

    def test_plain_not_found(self):
        assert is_rate_limited(FakeResponse(404)) is False


class TestRateLimitRemaining:
    def test_parses_header(self):
        assert rate_limit_remaining(FakeResponse(200, {"x-ratelimit-remaining": "17"})) == 17

    def test_absent_header(self):
        assert rate_limit_remaining(FakeResponse(200)) is None

    def test_unparseable_header(self):
        assert rate_limit_remaining(FakeResponse(200, {"x-ratelimit-remaining": "?"})) is None


class TestRaiseForGithubStatus:
    def test_success_passes_through(self):
        assert raise_for_github_status(FakeResponse(200), "someone") is None

    def test_throttling_is_503_not_404(self):
        with pytest.raises(HTTPException) as exc:
            raise_for_github_status(
                FakeResponse(403, {"x-ratelimit-remaining": "0"}), "someone"
            )
        assert exc.value.status_code == 503
        assert "rate limit" in exc.value.detail.lower()

    def test_missing_user_is_404(self):
        with pytest.raises(HTTPException) as exc:
            raise_for_github_status(FakeResponse(404), "ghost")
        assert exc.value.status_code == 404
        assert "ghost" in exc.value.detail

    def test_other_failures_are_502(self):
        with pytest.raises(HTTPException) as exc:
            raise_for_github_status(FakeResponse(500), "someone")
        assert exc.value.status_code == 502
