#!/usr/bin/env python
"""Pre-compute per-user language attribution into the Redis cache.

Measuring a whole account's commit diffs takes minutes -- far longer than a
request may run -- so the API only ever measures what fits inside a short
deadline and serves whole-repo language bytes until enough repos are cached.
This script does the slow part out of band, so the attributed answer is ready
before anyone asks for it.

    python scripts/warm_attribution.py tashifkhan
    python scripts/warm_attribution.py tashifkhan someone-else --passes 6

Needs GITHUB_TOKEN and REDIS_URL in the environment; without Redis there is no
cache to warm and the script says so rather than burning API calls for nothing.

Each pass measures whichever repos are still uncached and stops at the deadline,
so several passes walk steadily through a large account. Re-running is cheap:
cached repos cost nothing until they are pushed to again.
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

from core import cache  # noqa: E402
from core.config import attribution_settings  # noqa: E402
from services.attribution import get_user_contributions  # noqa: E402


async def warm(username: str, token: str, passes: int, deadline: float) -> bool:
    """Walk ``username`` until fully cached or ``passes`` is used up."""
    for attempt in range(1, passes + 1):
        started = time.perf_counter()
        stats = await get_user_contributions(
            username,
            token,
            include_repositories=False,
            deadline_seconds=deadline,
        )
        elapsed = time.perf_counter() - started

        print(
            f"  pass {attempt}/{passes}: coverage {stats.coverage:.0%} "
            f"({stats.repos_analyzed} of {stats.repos_considered} repos, "
            f"{stats.total_commits} commits) in {elapsed:.1f}s"
        )

        if not stats.partial:
            print(f"  {username} fully cached")
            for language in stats.languages[:8]:
                print(f"    {language.name:<20} {language.percentage:6.2f}%")
            return True

    print(f"  {username} still partial -- run again to continue")
    return False


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usernames", nargs="+", help="GitHub usernames to warm")
    parser.add_argument(
        "--passes",
        type=int,
        default=10,
        help="Maximum walks per user (default: 10)",
    )
    parser.add_argument(
        "--deadline",
        type=float,
        default=60.0,
        help="Seconds each walk may spend measuring (default: 60)",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1

    if not cache.redis_enabled():
        print(
            "REDIS_URL is not set, so there is no cache to warm. The API would "
            "keep serving whole-repo language bytes; set REDIS_URL and retry.",
            file=sys.stderr,
        )
        return 1

    print(
        f"warming {len(args.usernames)} user(s), "
        f"{args.deadline:.0f}s per pass, max {args.passes} passes"
    )

    complete = 0
    for username in args.usernames:
        print(f"\n{username}:")
        try:
            if await warm(username, token, args.passes, args.deadline):
                complete += 1
        except Exception as exc:  # keep going through the rest of the list
            print(f"  failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    print(f"\n{complete}/{len(args.usernames)} fully cached")
    return 0 if complete == len(args.usernames) else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
