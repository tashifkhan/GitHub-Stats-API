import json
from base64 import b64decode, b64encode
from typing import Any

import httpx
from redis import asyncio as redis

from core.config import cache_rate_limit_settings as settings


_client: redis.Redis | None = None


def redis_enabled() -> bool:
    return bool(settings.upstash_redis_rest_url and settings.upstash_redis_rest_token) or bool(settings.redis_url)


def upstash_enabled() -> bool:
    return bool(settings.upstash_redis_rest_url and settings.upstash_redis_rest_token)


async def upstash_command(command: str, *args: Any) -> Any | None:
    if not upstash_enabled():
        return None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                settings.upstash_redis_rest_url.rstrip("/"),
                headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
                json=[command, *args],
            )
            response.raise_for_status()
            return response.json().get("result")
    except Exception:
        return None


def get_redis() -> redis.Redis | None:
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def get_json(key: str) -> dict[str, Any] | None:
    value = await upstash_command("GET", key)
    if value:
        try:
            return json.loads(value) if isinstance(value, str) else value
        except ValueError:
            return None

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
    if upstash_enabled():
        await upstash_command("SETEX", key, ttl_seconds, json.dumps(value, separators=(",", ":")))
        return

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
