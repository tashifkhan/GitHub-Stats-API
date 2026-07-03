import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routes.badges import get_badges  # noqa: E402
from services.achievements import get_user_achievements  # noqa: E402


class FakeAnalyticsService:
    async def get_user_achievements(self, username):
        return [
            {
                "id": "pull-shark",
                "name": "Pull Shark",
                "icon": "https://github.githubassets.com/images/modules/profile/achievements/pull-shark-default.png",
                "level": "x2",
            }
        ]


class BadgeEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_badges_endpoint_returns_canonical_envelope(self):
        payload = await get_badges("octocat", FakeAnalyticsService())

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["platform"], "github")
        self.assertEqual(payload["username"], "octocat")
        self.assertEqual(payload["data"]["count"], 1)
        self.assertEqual(payload["data"]["active"]["name"], "Pull Shark")

    async def test_achievement_fetch_errors_return_empty_list(self):
        class BrokenClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers):
                import httpx

                raise httpx.ConnectError("offline")

        import services.achievements as achievements

        original_client = achievements.httpx.AsyncClient
        achievements.httpx.AsyncClient = lambda **kwargs: BrokenClient()
        try:
            self.assertEqual(await get_user_achievements("octocat"), [])
        finally:
            achievements.httpx.AsyncClient = original_client


if __name__ == "__main__":
    unittest.main()
