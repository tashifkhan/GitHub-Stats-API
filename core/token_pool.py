"""Run several GitHub tokens as one quota pool.

GitHub counts REST quota per token, not per application: two PATs give two
independent 5,000/hour allowances. The pool keeps tokens in priority order and
moves to the next one when the current token is exhausted, is cooling down
after a secondary limit, or is rejected outright. The API can therefore list
its own account first while the offline attribution worker starts on a
different account, with the rest of the pool available as overflow.

Tokens are never logged. Each is identified by an eight-character digest so a
log line can still say which one was throttled.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

logger = logging.getLogger("stats_api")

DEFAULT_HOURLY_LIMIT = 5000
# How long to avoid a token when GitHub limits it without a reset/retry hint.
DEFAULT_COOLDOWN_SECONDS = 60


class NoTokenAvailable(RuntimeError):
    """No configured token can serve a request right now."""

    def __init__(self, retry_after: int = DEFAULT_COOLDOWN_SECONDS):
        self.retry_after = max(1, int(retry_after))
        super().__init__("no GitHub token is currently available")


def split_tokens(raw: str) -> list[str]:
    """Parse a comma/whitespace separated token list, preserving order."""
    tokens: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[\s,;]+", raw or ""):
        token = chunk.strip().strip('"').strip("'")
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _as_int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@dataclass
class TokenState:
    token: str = field(repr=False)
    label: str
    remaining: Optional[int] = None
    limit: Optional[int] = None
    reset_at: float = 0.0
    cooldown_until: float = 0.0
    disabled: bool = False


class TokenPool:
    """Priority-ordered GitHub tokens with quota-aware failover."""

    def __init__(self, tokens: Iterable[str], *, clock=time.time):
        self._clock = clock
        self._lock = threading.RLock()
        self._states: list[TokenState] = []
        self._by_token: dict[str, TokenState] = {}
        for token in tokens:
            token = token.strip()
            if not token or token in self._by_token:
                continue
            state = TokenState(
                token=token,
                label=hashlib.sha256(token.encode()).hexdigest()[:8],
            )
            self._states.append(state)
            self._by_token[token] = state

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "TokenPool":
        env = os.environ if environ is None else environ
        raw = env.get("GITHUB_TOKENS") or env.get("GITHUB_TOKEN") or ""
        return cls(split_tokens(raw))

    @property
    def configured(self) -> bool:
        return bool(self._states)

    def __len__(self) -> int:
        return len(self._states)

    def acquire(
        self,
        *,
        min_remaining: int = 0,
        exclude: Optional[Iterable[str]] = None,
    ) -> str:
        """Return the first healthy token, or raise ``NoTokenAvailable``.

        ``min_remaining`` lets a long-running worker skip a token that is
        technically usable but already below its safety floor, falling through
        to the next account instead of stopping the whole run. ``exclude``
        prevents a retry loop from selecting an account that just failed.
        """
        now = self._clock()
        soonest_reset: Optional[float] = None
        skipped = set(exclude or ())

        with self._lock:
            for state in self._states:
                if state.disabled or state.token in skipped:
                    continue

                if state.reset_at and state.reset_at <= now:
                    # The hourly window has rolled over; GitHub has not told us
                    # the new balance yet, so start optimistic again.
                    state.remaining = None
                    state.reset_at = 0.0
                if state.cooldown_until and state.cooldown_until <= now:
                    state.cooldown_until = 0.0

                if state.cooldown_until > now:
                    soonest_reset = min(
                        soonest_reset or state.cooldown_until, state.cooldown_until
                    )
                    continue

                if state.remaining is not None and state.remaining <= 0:
                    if not state.reset_at:
                        state.reset_at = now + DEFAULT_COOLDOWN_SECONDS
                    soonest_reset = min(
                        soonest_reset or state.reset_at, state.reset_at
                    )
                    continue

                if state.remaining is not None and state.remaining <= min_remaining:
                    if state.reset_at:
                        soonest_reset = min(
                            soonest_reset or state.reset_at, state.reset_at
                        )
                    continue

                return state.token

        retry_after = DEFAULT_COOLDOWN_SECONDS
        if soonest_reset is not None:
            retry_after = max(1, int(round(soonest_reset - now)))
        raise NoTokenAvailable(retry_after)

    def acquire_or_none(self, *, min_remaining: int = 0) -> Optional[str]:
        try:
            return self.acquire(min_remaining=min_remaining)
        except NoTokenAvailable:
            return None

    def observe(self, token: str, status_code: int, headers: Mapping[str, str]) -> None:
        """Update a token's REST balance from one GitHub response.

        GraphQL and search have their own hourly buckets, reported under a
        different ``x-ratelimit-resource``. Letting them write the REST balance
        either revives an exhausted core token or parks a healthy one, so only
        core REST responses are recorded here.
        """
        state = self._by_token.get(token)
        if state is None:
            return

        resource = (headers.get("x-ratelimit-resource") or "core").strip().lower()
        if resource != "core":
            return

        remaining = _as_int(headers.get("x-ratelimit-remaining"))
        limit = _as_int(headers.get("x-ratelimit-limit"))
        reset = _as_int(headers.get("x-ratelimit-reset"))
        retry_after = _as_int(headers.get("retry-after"))
        now = self._clock()

        with self._lock:
            previous_remaining = state.remaining
            previous_reset = state.reset_at

            if limit is not None and limit > 0:
                state.limit = limit
                if state.remaining is None:
                    state.remaining = limit
            if reset is not None and reset > 0:
                state.reset_at = float(reset)
            if remaining is not None:
                # Responses can land out of order. A success from the window
                # that just ran out must not make its token look usable again.
                same_window = (
                    reset is None
                    or previous_reset == 0
                    or float(reset) <= previous_reset
                )
                stale_success = (
                    previous_remaining == 0
                    and remaining > 0
                    and same_window
                    and state.reset_at > now
                )
                if not stale_success:
                    state.remaining = remaining

            if status_code == 401:
                state.disabled = True
                logger.warning(
                    "GitHub token %s was rejected (401); removed from the pool",
                    state.label,
                )
            elif status_code == 403 and remaining == 0:
                # Primary limit exhausted. GitHub sends the hourly reset too.
                state.remaining = 0
                if state.reset_at <= now:
                    state.reset_at = now + (retry_after or DEFAULT_COOLDOWN_SECONDS)
            elif status_code == 429 or (status_code == 403 and retry_after is not None):
                # Secondary limit: the hourly balance is intact, but this
                # token must sit out the retry window.
                state.cooldown_until = max(
                    state.cooldown_until,
                    now + (retry_after or DEFAULT_COOLDOWN_SECONDS),
                )
            # Never clear cooldown_until on a successful response. It may have
            # been in flight before GitHub applied the secondary limit, and
            # the cooldown expires on its own.

    def observe_response(self, response) -> None:
        """httpx response hook: learn from whichever token made the call."""
        request = getattr(response, "request", None)
        if request is None:
            return
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return
        self.observe(token.strip(), response.status_code, response.headers)

    def snapshot(self) -> list[dict]:
        """Redacted state, for diagnostics and tests."""
        now = self._clock()
        with self._lock:
            return [
                {
                    "id": state.label,
                    "remaining": state.remaining,
                    "limit": state.limit,
                    "reset_in": max(0, int(round(state.reset_at - now)))
                    if state.reset_at
                    else None,
                    "cooling": state.cooldown_until > now,
                    "disabled": state.disabled,
                }
                for state in self._states
            ]


_pool: Optional[TokenPool] = None
_pool_lock = threading.Lock()


def get_token_pool() -> TokenPool:
    """Lazily build the process-wide pool, after dotenv has been loaded."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = TokenPool.from_env()
    return _pool


def reset_token_pool(pool: Optional[TokenPool] = None) -> None:
    """Replace the process-wide pool (tests and scripts that reload env)."""
    global _pool
    with _pool_lock:
        _pool = pool


async def observe_github_response(response) -> None:
    """httpx response hook compatible with every AsyncClient in the codebase.

    httpx awaits response hooks on AsyncClient, so this must be a coroutine.
    """
    get_token_pool().observe_response(response)


# Attach to every client that speaks to api.github.com. Centralized here so a
# new service cannot quietly spend quota the pool never learns about.
GITHUB_RESPONSE_HOOKS = {"response": [observe_github_response]}
