import os


class CacheRateLimitSettings:
    redis_url = os.getenv("REDIS_URL")
    # Vercel's Upstash integration provisions these instead of a REDIS_URL, so
    # they are accepted as an equivalent transport rather than leaving a
    # seemingly-configured deployment running with no cache.
    upstash_rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    cache_ttl_seconds = int(os.getenv("API_CACHE_TTL_SECONDS", "3600"))
    invalid_user_cache_ttl_seconds = int(os.getenv("INVALID_USER_CACHE_TTL_SECONDS", "300"))
    rate_limit_ip_requests = int(os.getenv("RATE_LIMIT_IP_REQUESTS", "60"))
    rate_limit_handle_requests = int(os.getenv("RATE_LIMIT_HANDLE_REQUESTS", "30"))
    rate_limit_window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    invalid_rate_limit_ip_requests = int(os.getenv("INVALID_RATE_LIMIT_IP_REQUESTS", "10"))
    invalid_rate_limit_handle_requests = int(os.getenv("INVALID_RATE_LIMIT_HANDLE_REQUESTS", "5"))
    invalid_rate_limit_window_seconds = int(os.getenv("INVALID_RATE_LIMIT_WINDOW_SECONDS", "600"))
    rate_limit_backoff_base_seconds = int(os.getenv("RATE_LIMIT_BACKOFF_BASE_SECONDS", "5"))
    rate_limit_backoff_max_seconds = int(os.getenv("RATE_LIMIT_BACKOFF_MAX_SECONDS", "300"))


class AttributionSettings:
    """Caps for per-user language attribution, which walks commit diffs.

    Walking every commit of every repo takes minutes, so it can never run to
    completion inside a request. Instead every walk is bounded by a wall-clock
    deadline and each repo's result is cached in Redis keyed by its
    ``pushed_at``. A request measures whatever fits in its deadline, caches it,
    and falls back to whole-repo language bytes until enough repos are warm;
    successive requests widen the cache until the attributed answer takes over.

    Set ``REDIS_URL`` for that warming to persist -- without it every request
    starts cold and the attributed path never reaches its coverage threshold.
    """

    max_repos = int(os.getenv("ATTRIBUTION_MAX_REPOS", "60"))
    max_commits_per_repo = int(os.getenv("ATTRIBUTION_MAX_COMMITS_PER_REPO", "200"))
    max_commit_details = int(os.getenv("ATTRIBUTION_MAX_COMMIT_DETAILS", "600"))
    concurrency = int(os.getenv("ATTRIBUTION_CONCURRENCY", "10"))
    # How many repos may be measured at once. Bounded so that when the deadline
    # expires only a few repos are half-done, and the rest fall back cleanly.
    repo_concurrency = int(os.getenv("ATTRIBUTION_REPO_CONCURRENCY", "6"))
    # How many repos /repos may fetch details for at once. Higher than the
    # attribution caps because these are plain cheap reads with no deadline to
    # degrade against: that endpoint issues five requests per repo and simply
    # has to finish, so throttling it too hard is what pushed it over the
    # function timeout.
    repo_detail_concurrency = int(os.getenv("REPO_DETAIL_CONCURRENCY", "24"))
    request_timeout_seconds = float(os.getenv("ATTRIBUTION_REQUEST_TIMEOUT", "20"))
    cache_ttl_seconds = int(os.getenv("ATTRIBUTION_CACHE_TTL_SECONDS", "604800"))
    stats_retries = int(os.getenv("ATTRIBUTION_STATS_RETRIES", "3"))
    stats_retry_delay_seconds = float(os.getenv("ATTRIBUTION_STATS_RETRY_DELAY", "0.6"))

    # Wall-clock budget for a walk that runs inside a normal request. A walk
    # overruns this by however long its in-flight requests take to land, and the
    # endpoint still has its own work to do afterwards, so this stays well under
    # the platform's function timeout (10s on Vercel Hobby) rather than near it.
    inline_deadline_seconds = float(os.getenv("ATTRIBUTION_INLINE_DEADLINE", "3.5"))
    # Budget for the dedicated breakdown endpoint. Larger than the inline one
    # since warming is its whole purpose, but still inside the function timeout:
    # it is served over HTTP like everything else, so a walk long enough to
    # finish in one go would just be killed by the gateway. Raise it only if the
    # hosting plan allows a longer maxDuration. Offline warming is not bound by
    # this -- scripts/warm_attribution.py passes its own, much longer deadline.
    breakdown_deadline_seconds = float(os.getenv("ATTRIBUTION_BREAKDOWN_DEADLINE", "8"))
    # Stop measuring when GitHub reports fewer than this many calls left in the
    # hour. A cold walk costs hundreds of requests, and without a floor it will
    # drain the 5000/hour budget and take every other endpoint down with it.
    rate_limit_floor = int(os.getenv("ATTRIBUTION_RATE_LIMIT_FLOOR", "500"))
    # Fraction of candidate repos that must be measured before the attributed
    # language mix is trustworthy enough to serve. Below this a partial sample
    # would misrepresent the user, so the legacy whole-repo split is used.
    min_coverage = float(os.getenv("ATTRIBUTION_MIN_COVERAGE", "0.7"))


cache_rate_limit_settings = CacheRateLimitSettings()
attribution_settings = AttributionSettings()
