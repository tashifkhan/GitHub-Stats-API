"""Bounded native Redis and Upstash REST storage, with bulk reads and scripts."""

import asyncio
import json
import weakref
from base64 import b64decode, b64encode
from typing import Any

import httpx
from redis import asyncio as redis

from core.config import cache_rate_limit_settings as settings
from core.runtime import http_client, remaining

OPERATION_TIMEOUT = 0.5


class UpstashRestRedis:
    def __init__(self, url, token):
        self._url = url.strip().rstrip("/")
        if not self._url.startswith(("https://", "http://")):
            self._url = "https://" + self._url
        self._headers = {"Authorization": "Bearer " + token}
        self._client = None  # Optional explicit client, also useful for offline tests.

    async def _command(self, *parts):
        async def execute(client):
            response = await client.post(self._url, headers=self._headers, json=[str(p) for p in parts])
            if response.status_code != 200:
                return None
            body = response.json()
            return None if body.get("error") else body.get("result")
        try:
            async with http_client() as client:
                return await asyncio.wait_for(execute(self._client or client), min(OPERATION_TIMEOUT, remaining()))
        except (httpx.HTTPError, ValueError, asyncio.TimeoutError):
            return None

    async def get(self, key): return await self._command("GET", key)
    async def mget(self, keys): return await self._command("MGET", *keys) if keys else []
    async def setex(self, key, ttl, value): return await self._command("SET", key, value, "EX", ttl)
    async def set(self, key, value, ex=None, nx=False):
        args = ["SET", key, value]
        if ex is not None: args += ["EX", ex]
        if nx: args += ["NX"]
        return await self._command(*args)
    async def ttl(self, key):
        value = await self._command("TTL", key)
        return int(value) if value is not None else -2
    async def incr(self, key): return int(await self._command("INCR", key) or 0)
    async def expire(self, key, ttl): return await self._command("EXPIRE", key, ttl)
    async def delete(self, key): return await self._command("DEL", key)
    async def eval(self, script, numkeys, *args): return await self._command("EVAL", script, numkeys, *args)
    async def hset(self, key, field, value): return await self._command("HSET", key, field, value)
    async def hdel(self, key, *fields): return await self._command("HDEL", key, *fields) if fields else 0
    async def hgetall(self, key):
        value = await self._command("HGETALL", key)
        if isinstance(value, dict): return value
        return dict(zip(value[::2], value[1::2])) if isinstance(value, list) else None


_client = None
_native_clients = weakref.WeakKeyDictionary()


def _rest_settings():
    return (
        getattr(settings, "upstash_rest_url", None) or getattr(settings, "upstash_redis_rest_url", None),
        getattr(settings, "upstash_rest_token", None) or getattr(settings, "upstash_redis_rest_token", None),
    )


def redis_enabled():
    url, token = _rest_settings()
    return bool(getattr(settings, "redis_url", None) or (url and token))


def get_redis():
    global _client
    if _client is not None:
        return _client
    if settings.redis_url:
        loop = asyncio.get_running_loop()
        if loop not in _native_clients:
            _native_clients[loop] = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=OPERATION_TIMEOUT, socket_connect_timeout=OPERATION_TIMEOUT)
        return _native_clients[loop]
    url, token = _rest_settings()
    if url and token:
        _client = UpstashRestRedis(url, token)
    return _client


async def command(name, *args, **kwargs):
    client = get_redis()
    if client is None:
        return None
    try:
        return await asyncio.wait_for(getattr(client, name)(*args, **kwargs), min(OPERATION_TIMEOUT, remaining()))
    except Exception:
        return None


async def get_json(key):
    value = await command("get", key)
    try:
        return json.loads(value) if isinstance(value, (str, bytes)) else value
    except (ValueError, TypeError):
        return None


async def get_many(keys):
    result = []
    for start in range(0, len(keys), 100):
        chunk = keys[start:start + 100]
        values = await command("mget", chunk)
        for value in values if isinstance(values, list) and len(values) == len(chunk) else [None] * len(chunk):
            try: result.append(json.loads(value) if value is not None else None)
            except (ValueError, TypeError): result.append(None)
    return result


async def set_json(key, value, ttl_seconds):
    return await command("setex", key, ttl_seconds, json.dumps(value, separators=(",", ":")))


async def delete_key(key): return await command("delete", key)
def encode_body(body): return b64encode(body).decode("ascii")
def decode_body(body): return b64decode(body.encode("ascii"))


async def upstash_command(name, *args):
    client = get_redis()
    return await client._command(name, *args) if isinstance(client, UpstashRestRedis) else None


def upstash_enabled():
    url, token = _rest_settings()
    return bool(url and token and not settings.redis_url)
