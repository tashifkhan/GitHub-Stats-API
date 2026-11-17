"""Source cache with request deduplication, owner-safe leases and stale fallback."""
import asyncio
import hashlib
import json
import time
import uuid
from fastapi import HTTPException
from core.cache import command, get_json, set_json, redis_enabled
from core.runtime import once, state

RELEASE = "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0"

async def source(key, producer, ttl=300, stale_ttl=3600):
    key = 'source:v1:' + hashlib.sha256(key.encode()).hexdigest()
    async def load():
        cached = await get_json(key)
        if cached and time.time() - cached['at'] < ttl:
            return cached['data']
        owner = uuid.uuid4().hex
        locked = await command('set', key+':lease', owner, ex=10, nx=True) if redis_enabled() else None
        if redis_enabled() and not locked:
            if cached:
                current = state.get()
                if current: current.meta['source'] = {'status': 'stale', 'updatedAt': cached['at']}
                return cached['data']
            # Bounded coalescing. A failed cache must not cause an unbounded wait.
            for _ in range(3):
                await asyncio.sleep(.05)
                shared = await get_json(key)
                if shared: return shared['data']
        try:
            data = await producer()
            await set_json(key, {'at': time.time(), 'data': data}, stale_ttl)
            return data
        except (HTTPException, TimeoutError):
            if cached:
                current = state.get()
                if current: current.meta['source'] = {'status': 'stale', 'updatedAt': cached['at']}
                return cached['data']
            raise
        finally:
            if locked: await command('eval', RELEASE, 1, key+':lease', owner)
    return await once(key, load)
