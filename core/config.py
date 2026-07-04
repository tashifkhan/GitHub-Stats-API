import os


class CacheRateLimitSettings:
    redis_url = os.getenv("REDIS_URL")
    upstash_redis_rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
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


cache_rate_limit_settings = CacheRateLimitSettings()
