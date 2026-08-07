"""The Upstash REST transport must behave like the Redis client it replaces.

Vercel's Upstash integration provisions REST credentials rather than a
``REDIS_URL``. Before this transport existed that combination left the app
running with no cache at all -- and because per-repo attribution measurements
stopped persisting between requests, the attributed language split could never
reach its coverage threshold and silently stayed on whole-repo bytes.
"""

import asyncio
import json
import time

import httpx
import pytest

from core.cache import UpstashRestRedis


class FakeUpstash:
    """In-memory Redis with just enough behaviour, served over Upstash's API."""

    def __init__(self, fail=False):
        self.store: dict[str, str] = {}
        self.expiry: dict[str, float] = {}
        self.requests: list[list[str]] = []
        self.fail = fail

    def _live(self, key):
        if key in self.expiry and self.expiry[key] <= time.time():
            self.store.pop(key, None)
            self.expiry.pop(key, None)
        return key in self.store

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500, json={"error": "boom"})

        command = json.loads(request.content)
        self.requests.append(command)
        name = command[0].upper()
        key = command[1] if len(command) > 1 else None

        if name == "GET":
            return httpx.Response(
                200, json={"result": self.store.get(key) if self._live(key) else None}
            )
        if name == "SET":
            self.store[key] = command[2]
            if len(command) > 4 and command[3].upper() == "EX":
                self.expiry[key] = time.time() + int(command[4])
            return httpx.Response(200, json={"result": "OK"})
        if name == "TTL":
            if not self._live(key):
                return httpx.Response(200, json={"result": -2})
            if key not in self.expiry:
                return httpx.Response(200, json={"result": -1})
            return httpx.Response(
                200, json={"result": int(self.expiry[key] - time.time())}
            )
        if name == "INCR":
            value = int(self.store.get(key, "0")) + 1 if self._live(key) else 1
            self.store[key] = str(value)
            return httpx.Response(200, json={"result": value})
        if name == "EXPIRE":
            self.expiry[key] = time.time() + int(command[2])
            return httpx.Response(200, json={"result": 1})
        if name == "DEL":
            existed = self._live(key)
            self.store.pop(key, None)
            self.expiry.pop(key, None)
            return httpx.Response(200, json={"result": 1 if existed else 0})

        return httpx.Response(400, json={"error": "unknown"})


def make(fake, url="https://example.upstash.io"):
    client = UpstashRestRedis(url, "token")
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(fake.handler),
        headers={"Authorization": "Bearer token"},
    )
    return client


class TestUrlNormalisation:
    @pytest.mark.parametrize(
        "given",
        ["example.upstash.io", "https://example.upstash.io", "https://example.upstash.io/"],
    )
    def test_always_ends_up_absolute_and_unslashed(self, given):
        # A bare host is what the integration stores, and httpx rejects it.
        assert UpstashRestRedis(given, "t")._url == "https://example.upstash.io"

    def test_plain_http_is_left_alone(self):
        assert UpstashRestRedis("http://localhost:8079", "t")._url == (
            "http://localhost:8079"
        )


class TestRedisSemantics:
    def test_set_then_get_round_trips(self):
        fake = FakeUpstash()
        client = make(fake)

        async def run():
            await client.setex("k", 60, '{"a":1}')
            return await client.get("k")

        assert asyncio.run(run()) == '{"a":1}'
        assert fake.requests[0] == ["SET", "k", '{"a":1}', "EX", "60"]

    def test_missing_key_is_none(self):
        assert asyncio.run(make(FakeUpstash()).get("absent")) is None

    def test_ttl_reports_the_window(self):
        fake = FakeUpstash()
        client = make(fake)

        async def run():
            await client.setex("k", 60, "v")
            return await client.ttl("k")

        assert 55 <= asyncio.run(run()) <= 60

    def test_ttl_of_missing_key_matches_redis(self):
        assert asyncio.run(make(FakeUpstash()).ttl("absent")) == -2

    def test_incr_counts_up_from_absent(self):
        fake = FakeUpstash()
        client = make(fake)

        async def run():
            return [await client.incr("c"), await client.incr("c")]

        assert asyncio.run(run()) == [1, 2]

    def test_delete_then_get_is_none(self):
        fake = FakeUpstash()
        client = make(fake)

        async def run():
            await client.setex("k", 60, "v")
            await client.delete("k")
            return await client.get("k")

        assert asyncio.run(run()) is None

    def test_expire_sets_a_window(self):
        fake = FakeUpstash()
        client = make(fake)

        async def run():
            await client.setex("k", 600, "v")
            await client.expire("k", 30)
            return await client.ttl("k")

        assert asyncio.run(run()) <= 30

    def test_integers_are_stringified_for_the_wire(self):
        fake = FakeUpstash()
        asyncio.run(make(fake).setex("k", 60, "v"))
        assert all(isinstance(part, str) for part in fake.requests[0])


class TestFailureHandling:
    """A broken cache must degrade to no cache, never take the request down."""

    def test_error_status_returns_none(self):
        assert asyncio.run(make(FakeUpstash(fail=True)).get("k")) is None

    def test_ttl_falls_back_to_the_missing_sentinel(self):
        # -2 keeps the rate limiter treating the key as absent rather than
        # reading a bad value as a live backoff and locking callers out.
        assert asyncio.run(make(FakeUpstash(fail=True)).ttl("k")) == -2

    def test_incr_reports_zero(self):
        assert asyncio.run(make(FakeUpstash(fail=True)).incr("k")) == 0
