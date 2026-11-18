"""Request-scoped clients, source deduplication, and a total request budget."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx
from starlette.responses import JSONResponse

from core.token_pool import GITHUB_RESPONSE_HOOKS

logger = logging.getLogger("stats_api")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=4.0,
        follow_redirects=True,
        event_hooks=GITHUB_RESPONSE_HOOKS,
    )


@dataclass
class RequestState:
    deadline: float
    client: httpx.AsyncClient
    tasks: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


state: ContextVar[RequestState | None] = ContextVar("stats_request", default=None)


def remaining(default=6.0):
    current = state.get()
    return max(0.001, current.deadline - time.monotonic()) if current else default


@asynccontextmanager
async def http_client():
    current = state.get()
    if current:
        yield current.client
    else:
        async with _client() as client:
            yield client


async def once(key, producer):
    current = state.get()
    if current is None:
        return await producer()
    if key not in current.tasks:
        current.tasks[key] = asyncio.create_task(producer())
    return await current.tasks[key]


# Cold profile and repo routes need 10-14s before their first cached response.
# The function limit on this project is above that, so the budget sits under it
# rather than under the 10s that other Stats APIs run with.
DEFAULT_BUDGET_SECONDS = 25.0


def budget_seconds():
    try:
        return float(os.environ.get("REQUEST_BUDGET_SECONDS", DEFAULT_BUDGET_SECONDS))
    except ValueError:
        return DEFAULT_BUDGET_SECONDS


class RequestBudgetMiddleware:
    def __init__(self, app, seconds=None):
        self.app, self.seconds = app, seconds if seconds is not None else budget_seconds()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started, sent, status = time.monotonic(), False, 500
        async with _client() as client:
            current = RequestState(started + self.seconds, client)
            token = state.set(current)

            async def tracked(message):
                nonlocal sent, status
                if message["type"] == "http.response.start":
                    sent, status = True, message["status"]
                    # Service-level enrichment metadata does not change existing data shapes.
                    if current.meta:
                        headers = list(message.get("headers", []))
                        headers = [(k, v) for k, v in headers if k.lower() != b"cache-control"]
                        headers.append((b"cache-control", b"no-store"))
                        import json
                        headers.append((b"x-data-state", json.dumps(current.meta, separators=(",", ":")).encode()))
                        message["headers"] = headers
                await send(message)

            try:
                await asyncio.wait_for(self.app(scope, receive, tracked), self.seconds)
            except asyncio.TimeoutError:
                if sent:
                    raise
                response = JSONResponse(
                    {"status": "error", "message": "Upstream request deadline exceeded"},
                    status_code=504, headers={"Cache-Control": "no-store"},
                )
                await response(scope, receive, tracked)
            finally:
                pending = [task for task in current.tasks.values() if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                state.reset(token)
                logger.info("request route=%s status=%s elapsed_ms=%s", getattr(scope.get("route"), "path", "unmatched"), status, int((time.monotonic() - started) * 1000))
