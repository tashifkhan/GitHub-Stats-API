"""README retrieval should preserve GitHub's REST API quota."""

import asyncio
import base64

from services.repositories import (
    _fetch_releases_batch,
    fetch_release_page,
    fetch_repo_details,
)


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

        assert [r.tag_name for r in found["tashifkhan/repo0"].releases] == ["v1.2.0"]
        assert found["tashifkhan/repo0"].releases[0].assets[0].download_url.endswith(
            "paisa.apk"
        )
        assert found["tashifkhan/repo1"].releases == []
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
        assert detail.releases_page is not None
        assert detail.releases_page.has_more is False
        assert not any("/releases?" in url for url in client.urls)



class _ReleasesClient:
    """REST page plus the GraphQL totalCount lookup that runs beside it."""

    def __init__(self, rows, *, link="", total=12, status=200):
        self.rows = rows
        self.link = link
        self.total = total
        self.status = status
        self.urls: list[str] = []

    async def get(self, url, **_kwargs):
        self.urls.append(url)
        response = _Response(self.status, body=self.rows)
        response.headers = {"Link": self.link}
        return response

    async def post(self, _url, **_kwargs):
        return _Response(
            200, body={"data": {"r": {"releases": {"totalCount": self.total}}}}
        )


def _rest_release(i: int) -> dict:
    return {"id": i, "tag_name": f"v{i}", "html_url": "u", "assets": []}


class TestReleasePages:
    def test_batch_reports_total_and_next_page(self):
        client = _GraphQLClient(
            _Response(
                200,
                body={
                    "data": {
                        "r0": {
                            "releases": {
                                "totalCount": 12,
                                "nodes": [_graphql_release(f"v{i}") for i in range(10)],
                            }
                        },
                        "r1": {
                            "releases": {
                                "totalCount": 2,
                                "nodes": [_graphql_release("v2"), _graphql_release("v1")],
                            }
                        },
                    }
                },
            )
        )
        repos = [
            {"name": "Patchwork", "owner": {"login": "tashifkhan"}},
            {"name": "small", "owner": {"login": "tashifkhan"}},
        ]

        found = asyncio.run(_fetch_releases_batch(client, repos, "token"))

        big = found["tashifkhan/patchwork"].releases_page
        assert (big.total_count, big.page, big.per_page, big.has_more) == (12, 1, 10, True)
        assert big.next == "/tashifkhan/repos/Patchwork/releases?page=2&per_page=10"
        small = found["tashifkhan/small"].releases_page
        assert small.has_more is False and small.next is None

    def test_page_follows_link_header_for_has_more(self):
        client = _ReleasesClient(
            [_rest_release(i) for i in range(10)],
            link='<https://api.github.com/x?page=2>; rel="next"',
        )

        page = asyncio.run(fetch_release_page(client, "tashifkhan", "Patchwork", "t"))

        assert page is not None
        assert len(page.releases) == 10
        assert page.releases_page.total_count == 12
        assert page.releases_page.next == (
            "/tashifkhan/repos/Patchwork/releases?page=2&per_page=10"
        )
        assert "per_page=10&page=1" in client.urls[0]

    def test_last_page_has_no_next(self):
        client = _ReleasesClient([_rest_release(i) for i in range(2)])

        page = asyncio.run(
            fetch_release_page(client, "tashifkhan", "Patchwork", "t", page=2)
        )

        assert page is not None
        assert page.releases_page.page == 2
        assert page.releases_page.has_more is False
        assert page.releases_page.next is None

    def test_missing_repo_returns_none(self):
        client = _ReleasesClient(None, status=404)

        assert asyncio.run(fetch_release_page(client, "tashifkhan", "nope", "t")) is None
