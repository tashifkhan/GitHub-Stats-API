"""README retrieval should preserve GitHub's REST API quota."""

import asyncio
import base64

from services.repositories import _fetch_releases_batch, fetch_repo_details


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

    async def post(self, url: str, **kwargs):
        return _Response(503)

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


def _graphql_release(tag: str) -> dict:
    return {
        "databaseId": 7,
        "tagName": tag,
        "name": tag,
        "description": "notes",
        "url": f"https://github.com/tashifkhan/Paisa/releases/tag/{tag}",
        "isDraft": False,
        "isPrerelease": False,
        "createdAt": "2026-10-01T00:00:00Z",
        "publishedAt": "2026-10-01T00:00:00Z",
        "releaseAssets": {
            "nodes": [
                {
                    "name": "paisa.apk",
                    "downloadUrl": f"https://github.com/tashifkhan/Paisa/releases/download/{tag}/paisa.apk",
                    "size": 10,
                    "downloadCount": 3,
                    "contentType": "application/vnd.android.package-archive",
                    "updatedAt": "2026-10-01T00:00:00Z",
                }
            ]
        },
    }


class _GraphQLClient:
    def __init__(self, response: _Response):
        self.response = response
        self.queries: list[str] = []

    async def post(self, _url: str, **kwargs):
        self.queries.append(kwargs["json"]["query"])
        return self.response


class TestBatchedReleases:
    def _repos(self, count: int) -> list[dict]:
        return [
            {"name": f"repo{i}", "owner": {"login": "tashifkhan"}} for i in range(count)
        ]

    def test_maps_releases_by_full_name_and_skips_unresolved(self):
        client = _GraphQLClient(
            _Response(
                200,
                body={
                    "data": {
                        "r0": {"releases": {"nodes": [_graphql_release("v1.2.0")]}},
                        "r1": {"releases": {"nodes": []}},
                        "r2": None,
                    }
                },
            )
        )

        found = asyncio.run(_fetch_releases_batch(client, self._repos(3), "token"))

        assert [r.tag_name for r in found["tashifkhan/repo0"]] == ["v1.2.0"]
        assert found["tashifkhan/repo0"][0].assets[0].download_url.endswith("paisa.apk")
        assert found["tashifkhan/repo1"] == []
        assert "tashifkhan/repo2" not in found

    def test_splits_large_repo_lists_into_batches(self):
        client = _GraphQLClient(_Response(200, body={"data": {}}))

        asyncio.run(_fetch_releases_batch(client, self._repos(120), "token"))

        assert len(client.queries) == 3

    def test_failed_batch_returns_unknown_not_empty(self):
        client = _GraphQLClient(_Response(502, body=None))

        found = asyncio.run(_fetch_releases_batch(client, self._repos(2), "token"))

        assert found == {}

    def test_lite_detail_uses_batched_releases_without_rest(self):
        client = _Client(_Response(200, text="# Paisa\n"))
        releases = asyncio.run(
            _fetch_releases_batch(
                _GraphQLClient(
                    _Response(
                        200,
                        body={
                            "data": {
                                "r0": {
                                    "releases": {"nodes": [_graphql_release("v1.0.0")]}
                                }
                            }
                        },
                    )
                ),
                [_repo()],
                "token",
            )
        )["tashifkhan/jportal"]

        detail = asyncio.run(
            fetch_repo_details(client, _repo(), "token", releases=releases)
        )

        assert detail is not None
        assert [r.tag_name for r in detail.releases] == ["v1.0.0"]
        assert not any("/releases?" in url for url in client.urls)
