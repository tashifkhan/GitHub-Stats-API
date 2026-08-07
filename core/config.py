import os


class CacheRateLimitSettings:
    redis_url = os.getenv("REDIS_URL")
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

    The defaults keep a cold lookup under roughly 700 GitHub API calls, well
    inside the 5000/hour authenticated budget, and results are cached per repo
    until that repo is pushed to again.
    """

    max_repos = int(os.getenv("ATTRIBUTION_MAX_REPOS", "60"))
    max_commits_per_repo = int(os.getenv("ATTRIBUTION_MAX_COMMITS_PER_REPO", "200"))
    max_commit_details = int(os.getenv("ATTRIBUTION_MAX_COMMIT_DETAILS", "600"))
    concurrency = int(os.getenv("ATTRIBUTION_CONCURRENCY", "10"))
    request_timeout_seconds = float(os.getenv("ATTRIBUTION_REQUEST_TIMEOUT", "20"))
    cache_ttl_seconds = int(os.getenv("ATTRIBUTION_CACHE_TTL_SECONDS", "604800"))
    stats_retries = int(os.getenv("ATTRIBUTION_STATS_RETRIES", "3"))
    stats_retry_delay_seconds = float(os.getenv("ATTRIBUTION_STATS_RETRY_DELAY", "0.6"))


cache_rate_limit_settings = CacheRateLimitSettings()
attribution_settings = AttributionSettings()
