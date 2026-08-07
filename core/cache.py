import json
from base64 import b64decode, b64encode
from typing import Any

import httpx
from redis import asyncio as redis

from core.config import cache_rate_limit_settings as settings


class UpstashRestRedis:
    """The slice of the Redis API this app uses, spoken over Upstash's REST API.

    Upstash issues two sets of credentials: a ``rediss://`` URL for the wire
    protocol and a REST endpoint plus token. Vercel's integration provisions
    only the REST pair, so a deployment that looks fully configured would
    otherwise find ``REDIS_URL`` empty and silently run with no cache at all --
    which disables response caching, rate limiting, and (because per-repo
    measurements stop persisting) own-commit attribution along with them.

    REST also suits serverless better than a pooled TCP connection, since
    functions rarely live long enough to reuse one.
    """

    def __init__(self, url: str, token: str):
        # Upstash shows the endpoint with a scheme, but integrations and
        # copy-paste both routinely drop it, and httpx rejects a bare host.
        url = url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        self._url = url
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0, headers=self._headers)
        return self._client

    async def _command(self, *parts: Any) -> Any:
        """Run one Redis command; ``None`` if it failed, matching the client."""
        response = await self._http().post(
            self._url, json=[str(part) for part in parts]
        )
        if response.status_code != 200:
            return None
        return response.json().get("result")

    async def get(self, key: str) -> Any:
        return await self._command("GET", key)

    async def setex(self, key: str, ttl_seconds: int, value: str) -> Any:
        return await self._command("SET", key, value, "EX", ttl_seconds)

    async def ttl(self, key: str) -> int:
        result = await self._command("TTL", key)
        return int(result) if result is not None else -2

    async def incr(self, key: str) -> int:
        result = await self._command("INCR", key)
        return int(result) if result is not None else 0

    async def expire(self, key: str, ttl_seconds: int) -> Any:
        return await self._command("EXPIRE", key, ttl_seconds)

    async def delete(self, key: str) -> Any:
        return await self._command("DEL", key)


_client: redis.Redis | UpstashRestRedis | None = None


def redis_enabled() -> bool:
    return bool(settings.redis_url) or bool(
        settings.upstash_rest_url and settings.upstash_rest_token
    )


def get_redis() -> redis.Redis | UpstashRestRedis | None:
    global _client
    if _client is not None:
        return _client

    # A wire-protocol URL wins when both are set: it is the faster transport
    # and the one the rest of the ecosystem assumes.
    if settings.redis_url:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    elif settings.upstash_rest_url and settings.upstash_rest_token:
        _client = UpstashRestRedis(
            settings.upstash_rest_url, settings.upstash_rest_token
        )

    return _client


async def get_json(key: str) -> dict[str, Any] | None:
    client = get_redis()
    if client is None:
        return None
    try:
        value = await client.get(key)
    except Exception:
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


async def set_json(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.setex(key, ttl_seconds, json.dumps(value, separators=(",", ":")))
    except Exception:
        return


def encode_body(body: bytes) -> str:
    return b64encode(body).decode("ascii")


def decode_body(body: str) -> bytes:
    return b64decode(body.encode("ascii"))
