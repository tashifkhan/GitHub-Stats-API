#!/usr/bin/env python
"""Measure attribution for users the API has queued, until time or quota runs out.

/languages, /stats and the stats SVG queue a username whenever its authored
language mix is not complete yet. This drains that queue. It runs from the
scheduled GitHub Actions workflow (.github/workflows/warm-attribution.yml),
and can be run by hand:

    python scripts/drain_attribution.py --minutes 10
    python scripts/drain_attribution.py --minutes 10 --seed tashifkhan

Needs GITHUB_TOKENS (or the older single GITHUB_TOKEN), a Redis store
(REDIS_URL or UPSTASH_REDIS_REST_*), and REFRESH_WORKER_ENABLED=true. Each
claimed user gets one walk of --pass-seconds. Measured repos are cached, so an
unfinished user is retried on a later claim and continues where it stopped. The
walk's own rate-limit floor stops it before the token runs dry; when the current
token reaches the floor the pool moves to the next account, and only when every
account is spent does this script stop.
"""

import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local")

from fastapi import HTTPException  # noqa: E402

from core import cache, jobs  # noqa: E402
from core.config import attribution_settings  # noqa: E402
from core.token_pool import NoTokenAvailable, get_token_pool  # noqa: E402
from services.attribution import get_user_contributions  # noqa: E402
from services.languages import COMPLETE_MARKER_TTL_SECONDS, _complete_marker  # noqa: E402


class QuotaExhausted(Exception):
    pass


def make_handler(token, pass_seconds, log=print, max_pass_seconds=None, time_left=None):
    """Walk one claimed user. A user whose coverage stalls gets a longer pass.

    Uncached repos are measured in full or not at all, so a repo too big for
    one pass would block its user forever at a fixed length. The pass doubles
    each time coverage fails to improve, up to ``max_pass_seconds`` and the
    time the drain has left.
    """
    max_pass_seconds = max_pass_seconds or pass_seconds

    def next_token():
        if token:
            return token
        return get_token_pool().acquire(
            min_remaining=attribution_settings.rate_limit_floor
        )

    async def handle(job):
        username = job.payload["subject"]
        planned = float(job.data.get("passSeconds", pass_seconds))
        limit = min(planned, max_pass_seconds, time_left() if time_left else planned)
        started = time.monotonic()
        try:
            active = next_token()
        except NoTokenAvailable as exc:
            raise QuotaExhausted(username) from exc

        async def walk(active_token, seconds):
            return await get_user_contributions(
                username,
                active_token,
                include_repositories=False,
                deadline_seconds=seconds,
            )

        try:
            stats = await walk(active, limit)
        except HTTPException as exc:
            if exc.status_code != 503 or token:
                raise
            # GitHub refused the very first call: the pool has now seen the
            # 403, so try the next account below.
            stats = None

        if not token and (stats is None or stats.status == "rate_limited"):
            # The guard stops at the floor, not at zero, so this token may still
            # have calls left. Another account with real headroom is a better
            # use of the remaining pass than ending the whole drain.
            left = max(1.0, limit - (time.monotonic() - started))
            try:
                fallback = get_token_pool().acquire(
                    min_remaining=attribution_settings.rate_limit_floor
                )
            except NoTokenAvailable:
                raise QuotaExhausted(username)
            if fallback == active:
                raise QuotaExhausted(username)
            try:
                stats = await walk(fallback, left)
            except HTTPException as exc:
                if exc.status_code == 503:
                    raise QuotaExhausted(username) from exc
                raise
        log(
            f"{username}: {stats.status}, coverage {stats.coverage:.0%} "
            f"({stats.repos_analyzed}/{stats.repos_considered} repos) "
            f"in {time.monotonic() - started:.0f}s with a {limit:.0f}s pass"
        )
        if stats.status == "rate_limited":
            raise QuotaExhausted(username)
        complete = not (stats.partial or stats.truncated)
        if complete:
            # Requests for this user stop queueing work until the marker expires.
            await cache.set_json(_complete_marker(username), {"complete": True}, COMPLETE_MARKER_TTL_SECONDS)
            job.data.pop("passSeconds", None)
            job.data.pop("lastCoverage", None)
        else:
            if stats.coverage <= float(job.data.get("lastCoverage", -1)):
                job.data["passSeconds"] = min(planned * 2, max_pass_seconds)
            job.data["lastCoverage"] = stats.coverage
        return complete

    return handle


async def queued_jobs():
    # EVAL works on native Redis and the Upstash REST client alike.
    count = await jobs.command("eval", "return redis.call('ZCARD', KEYS[1])", 1, jobs.QUEUE)
    return int(count or 0)


async def drain(handler, minutes, pass_seconds, run_once=None, clock=time.monotonic,
                max_pass_seconds=None, pending=None, sleep=asyncio.sleep):
    """Claim jobs until the queue is empty, time is up, or GitHub quota runs low."""
    run_once = run_once or jobs.run_once
    pending = pending or queued_jobs
    max_pass_seconds = max_pass_seconds or pass_seconds
    stop_at = clock() + minutes * 60
    claimed = 0
    quota = {"exhausted": False}

    async def guarded(job):
        try:
            return await handler(job)
        except QuotaExhausted:
            quota["exhausted"] = True
            raise

    # Start a claim only while a base-length pass still fits. The handler
    # trims longer passes to the time that is left.
    while clock() + pass_seconds < stop_at and not quota["exhausted"]:
        if await run_once(guarded, timeout=max_pass_seconds + 30):
            claimed += 1
            continue
        # Nothing due right now. An unfinished user is re-queued a few seconds
        # (or a backoff) ahead, so only stop once the queue is really empty.
        if not await pending():
            break
        await sleep(3)
    return claimed, quota["exhausted"]


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minutes", type=float, default=10, help="Total time to spend (default 10)")
    parser.add_argument("--pass-seconds", type=float, default=60, help="Walk deadline per claim (default 60)")
    parser.add_argument("--max-pass-seconds", type=float, default=None, help="Longest pass for a stalled user (default: 4x --pass-seconds)")
    parser.add_argument("--seed", nargs="*", default=[], help="Usernames to queue before draining")
    args = parser.parse_args()

    if not get_token_pool().configured:
        print("GITHUB_TOKENS (or GITHUB_TOKEN) is not set", file=sys.stderr)
        return 1
    if not jobs.enabled():
        print("Set REFRESH_WORKER_ENABLED=true and a Redis store (REDIS_URL or UPSTASH_REDIS_REST_*).", file=sys.stderr)
        return 1

    for username in args.seed:
        if not await jobs.enqueue("languages", username):
            print(f"could not queue {username}", file=sys.stderr)

    max_pass = args.max_pass_seconds or args.pass_seconds * 4
    stop_at = time.monotonic() + args.minutes * 60
    handler = make_handler(None, args.pass_seconds, max_pass_seconds=max_pass,
                           time_left=lambda: max(10.0, stop_at - time.monotonic() - 10))
    claimed, exhausted = await drain(handler, args.minutes, args.pass_seconds, max_pass_seconds=max_pass)
    print(f"claimed {claimed} job(s)" + (", stopped at the GitHub quota floor" if exhausted else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
