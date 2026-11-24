import unittest
from unittest import mock

from fastapi.middleware.cors import CORSMiddleware

import core.cache as cache
import core.source as source_module
from core.rate_limit import RATE_SCRIPT


class RedisPySignature:
    """Mirrors redis-py's set(name, value, ex=None, px=None, nx=False)."""

    def __init__(self):
        self.calls = []

    async def set(self, name, value, ex=None, px=None, nx=False):
        self.calls.append({"ex": ex, "px": px, "nx": nx})
        return True

    async def get(self, name):
        return None

    async def eval(self, *args):
        return 1


class StoreRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_lease_uses_seconds_and_nx_keywords(self):
        client = RedisPySignature()
        with mock.patch.object(cache, "get_redis", return_value=client), \
             mock.patch.object(source_module, "redis_enabled", return_value=True), \
             mock.patch.object(source_module, "set_json", mock.AsyncMock()):
            async def produce():
                return {"ok": True}
            self.assertEqual(await source_module.source("lease-test", produce), {"ok": True})
        self.assertEqual(client.calls[0], {"ex": 10, "px": None, "nx": True})

    def test_allowed_request_resets_violations_only_at_window_start(self):
        allowed_branch = RATE_SCRIPT.split("if count <= tonumber(ARGV[1]) then", 1)[1].split("local violations", 1)[0]
        self.assertIn("if count == 1 then redis.call('DEL', KEYS[3]) end", allowed_branch)
        self.assertNotIn("\n redis.call('DEL', KEYS[3])", allowed_branch)

    def test_cors_is_outermost_middleware(self):
        from main import app
        self.assertIs(app.user_middleware[0].cls, CORSMiddleware)


if __name__ == "__main__":
    unittest.main()


def test_request_budget_reads_env(monkeypatch):
    from core import runtime

    monkeypatch.delenv("REQUEST_BUDGET_SECONDS", raising=False)
    assert runtime.RequestBudgetMiddleware(None).seconds == runtime.DEFAULT_BUDGET_SECONDS
    monkeypatch.setenv("REQUEST_BUDGET_SECONDS", "12")
    assert runtime.RequestBudgetMiddleware(None).seconds == 12.0
    monkeypatch.setenv("REQUEST_BUDGET_SECONDS", "junk")
    assert runtime.RequestBudgetMiddleware(None).seconds == runtime.DEFAULT_BUDGET_SECONDS
    assert runtime.RequestBudgetMiddleware(None, seconds=3).seconds == 3
