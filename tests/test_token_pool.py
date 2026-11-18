"""The token pool must fail over on quota, not on the first bad minute."""

import asyncio

import httpx
import pytest
from fastapi import HTTPException

from core.token_pool import (
    GITHUB_RESPONSE_HOOKS,
    NoTokenAvailable,
    TokenPool,
    reset_token_pool,
    split_tokens,
)
from routes.dependencies import get_github_token


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def pool(*tokens, clock=None):
    return TokenPool(tokens, clock=clock or Clock())


def test_split_tokens_accepts_commas_newlines_and_duplicates():
    assert split_tokens(" one, two\nthree;one ,, four ") == [
        "one",
        "two",
        "three",
        "four",
    ]


def test_from_env_prefers_the_pool_and_falls_back_to_the_legacy_name():
    assert len(TokenPool.from_env({"GITHUB_TOKENS": "a,b"})) == 2
    assert len(TokenPool.from_env({"GITHUB_TOKEN": "only"})) == 1
    assert len(TokenPool.from_env({})) == 0


def test_first_healthy_token_wins():
    assert pool("a", "b").acquire() == "a"


def test_exhausted_token_is_skipped_until_its_reset():
    clock = Clock()
    tokens = pool("a", "b", clock=clock)
    tokens.observe("a", 200, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(clock.now) + 120)})

    assert tokens.acquire() == "b"

    clock.advance(121)
    # The window rolled over, so the first token is optimistic again.
    assert tokens.acquire() == "a"
    assert tokens.snapshot()[0]["remaining"] is None


def test_primary_limit_403_also_parks_the_token():
    clock = Clock()
    tokens = pool("a", "b", clock=clock)
    tokens.observe("a", 403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(clock.now) + 60)})

    assert tokens.acquire() == "b"


def test_secondary_limit_cools_down_without_draining_the_hour():
    clock = Clock()
    tokens = pool("a", "b", clock=clock)
    tokens.observe("a", 403, {"x-ratelimit-remaining": "4321", "retry-after": "30"})

    assert tokens.acquire() == "b"

    clock.advance(31)
    assert tokens.acquire() == "a"


def test_rejected_token_is_removed_permanently():
    tokens = pool("a", "b")
    tokens.observe("a", 401, {})

    assert tokens.acquire() == "b"
    assert tokens.snapshot()[0]["disabled"] is True


def test_permission_denied_does_not_disable_a_good_token():
    tokens = pool("a", "b")
    tokens.observe("a", 403, {"x-ratelimit-remaining": "4100"})

    assert tokens.acquire() == "a"


def test_all_tokens_spent_reports_when_to_retry():
    clock = Clock()
    tokens = pool("a", "b", clock=clock)
    reset = str(int(clock.now) + 90)
    tokens.observe("a", 200, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset})
    tokens.observe("b", 200, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": reset})

    with pytest.raises(NoTokenAvailable) as exc:
        tokens.acquire()
    assert 1 <= exc.value.retry_after <= 90


def test_min_remaining_lets_a_worker_skip_a_nearly_empty_account():
    tokens = pool("a", "b")
    tokens.observe("a", 200, {"x-ratelimit-remaining": "800"})

    assert tokens.acquire(min_remaining=2_500) == "b"


def test_observe_response_reads_the_bearer_header():
    tokens = pool("a", "b")
    request = httpx.Request(
        "GET",
        "https://api.github.com/users/octocat",
        headers={"Authorization": "Bearer a"},
    )
    response = httpx.Response(
        200,
        headers={"x-ratelimit-remaining": "1234", "x-ratelimit-limit": "5000"},
        request=request,
    )

    tokens.observe_response(response)

    assert tokens.snapshot()[0]["remaining"] == 1234
    assert tokens.snapshot()[0]["limit"] == 5000


def test_observe_response_ignores_other_bearer_tokens():
    tokens = pool("a")
    request = httpx.Request(
        "GET",
        "https://example.test/",
        headers={"Authorization": "Bearer redis-token"},
    )
    response = httpx.Response(
        200, headers={"x-ratelimit-remaining": "1"}, request=request
    )

    tokens.observe_response(response)

    assert tokens.snapshot()[0]["remaining"] is None


def test_snapshot_never_leaks_a_token():
    tokens = pool("super-secret-a", "super-secret-b")

    rendered = repr(tokens.snapshot()) + repr(tokens)

    assert "super-secret" not in rendered


def test_shared_hook_reports_to_the_process_pool():
    tokens = pool("a")
    reset_token_pool(tokens)

    def handler(request):
        return httpx.Response(
            200, headers={"x-ratelimit-remaining": "77"}, request=request
        )

    async def call():
        async with httpx.AsyncClient(
            event_hooks=GITHUB_RESPONSE_HOOKS,
            transport=httpx.MockTransport(handler),
        ) as client:
            await client.get(
                "https://api.github.com/users/octocat",
                headers={"Authorization": "Bearer a"},
            )

    try:
        asyncio.run(call())
        assert tokens.snapshot()[0]["remaining"] == 77
    finally:
        reset_token_pool(None)


def test_dependency_turns_an_empty_pool_into_503_with_retry_after():
    clock = Clock()
    tokens = TokenPool(["a"], clock=clock)
    tokens.observe(
        "a",
        200,
        {
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(int(clock.now) + 45),
        },
    )
    reset_token_pool(tokens)

    try:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_github_token())
        assert exc.value.status_code == 503
        assert exc.value.headers["Retry-After"] == "45"
    finally:
        reset_token_pool(None)
