import json
from base64 import b64decode, b64encode
from typing import Any

from redis import asyncio as redis

from core.config import cache_rate_limit_settings as settings


_client: redis.Redis | None = None


def redis_enabled() -> bool:
    return bool(settings.redis_url)


def get_redis() -> redis.Redis | None:
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
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
