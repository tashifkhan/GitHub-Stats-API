"""README retrieval should preserve GitHub's REST API quota."""

import asyncio
import base64

from services.repositories import fetch_repo_details


def _repo() -> dict:
    return {
        "name": "jportal",
        "owner": {"login": "tashifkhan"},
        "description": "Progressive Web App for JIIT Web Portal",
        "language": "JavaScript",
        "topics": [],
        "stargazers_count": 0,
        "fork": True,
    }


class _Response:
    def __init__(self, status_code: int, *, text: str = "", body=None):
        self.status_code = status_code
        self.text = text
        self._body = body

    def json(self):
        return self._body


class _Client:
    def __init__(self, raw_response: _Response):
        self.raw_response = raw_response
        self.urls: list[str] = []

    async def get(self, url: str, **_kwargs):
        self.urls.append(url)
        if url.startswith("https://raw.githubusercontent.com/"):
            return self.raw_response
        if url.endswith("/languages"):
            return _Response(200, body={"JavaScript": 100})
        if "/contributors?" in url:
            return _Response(
                200,
                body=[
                    {
                        "login": "codeblech",
                        "avatar_url": "https://avatars.githubusercontent.com/u/1",
                        "html_url": "https://github.com/codeblech",
                        "contributions": 188,
                    },
                    {
                        "login": "tashifkhan",
                        "avatar_url": "https://avatars.githubusercontent.com/u/2",
                        "html_url": "https://github.com/tashifkhan",
                        "contributions": 17,
                    },
                ],
            )
        if url.endswith("/readme"):
            markdown = "# Alternate README\n"
            content = base64.b64encode(markdown.encode()).decode()
            return _Response(200, body={"content": content})
        raise AssertionError(f"unexpected request: {url}")


class TestRawReadmeDefault:
    def test_conventional_readme_uses_raw_cdn_without_contents_api(self):
        client = _Client(_Response(200, text="# 🎓 JPortal\n"))

        detail = asyncio.run(fetch_repo_details(client, _repo(), "token"))

        assert detail is not None
        assert detail.readme == "# 🎓 JPortal"
        assert not any(url.endswith("/readme") for url in client.urls)

    def test_contents_api_resolves_nonstandard_readme_after_raw_miss(self):
        client = _Client(_Response(404))

        detail = asyncio.run(fetch_repo_details(client, _repo(), "token"))

        assert detail is not None
        assert detail.readme == "# Alternate README"
        assert any(url.endswith("/readme") for url in client.urls)

    def test_default_response_includes_contributors(self):
        client = _Client(_Response(200, text="# JPortal\n"))

        detail = asyncio.run(fetch_repo_details(client, _repo(), "token"))

        assert detail is not None
        assert [contributor.login for contributor in detail.contributors] == [
            "codeblech",
            "tashifkhan",
        ]
        assert any("/contributors?" in url for url in client.urls)
        assert not any("/releases?" in url for url in client.urls)
        assert not any("/commits?" in url for url in client.urls)
