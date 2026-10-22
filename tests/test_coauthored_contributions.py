import asyncio
import json

import httpx
import pytest

from services import attribution


def commit(sha, authors, additions=20, deletions=4, parents=1):
    return {
        "oid": sha,
        "additions": additions,
        "deletions": deletions,
        "parents": {"totalCount": parents},
        "authors": {
            "nodes": [{"user": {"login": login} if login else None} for login in authors],
            "pageInfo": {"hasNextPage": False},
        },
    }


def page(commits, cursor=None):
    return {"data": {"repository": {"defaultBranchRef": {"target": {"history": {
        "nodes": commits,
        "pageInfo": {"hasNextPage": bool(cursor), "endCursor": cursor},
    }}}}}}


def test_discovery_pages_resolved_authors_and_counts_each_sha_once(monkeypatch):
    monkeypatch.setattr(attribution.settings, "max_commits_per_repo", 2)
    cursors = []

    def handler(request):
        cursor = json.loads(request.content)["variables"]["after"]
        cursors.append(cursor)
        if cursor is None:
            body = page([
                commit("primary-and-coauthor", ["Me", "Me"]),
                commit("coauthored", [None, "mE", "Me"]),
                commit("coauthored", [None, "Me"]),
                commit("unrelated", ["other"]),
                commit("merge", ["other", "Me"], additions=900, parents=2),
            ], "next")
        else:
            body = page([commit("older", ["other", "Me"])])
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await attribution._list_coauthored_commits(
                client, "owner", "repo", "me", "token", attribution.Deadline(None)
            )

    result = asyncio.run(run())
    assert cursors == [None, "next"]
    assert result.shas == ["coauthored", "merge"]
    assert result.count == 3
    assert (result.additions, result.deletions) == (40, 8)
    assert result.complete is True


@pytest.mark.parametrize("failure", [401, 429, {"errors": [{"message": "unavailable"}]}])
def test_failed_discovery_is_incomplete(failure):
    def handler(request):
        if isinstance(failure, int):
            return httpx.Response(failure)
        return httpx.Response(200, json=failure)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await attribution._list_coauthored_commits(
                client, "owner", "repo", "me", "token", attribution.Deadline(None)
            )

    result = asyncio.run(run())
    assert result.count == 0
    assert result.complete is False


def test_discovery_resumes_cached_cursor_after_deadline(monkeypatch):
    checkpoints = {}
    cursors = []

    async def get_cache(key):
        return checkpoints.get(key)

    async def set_cache(key, value, ttl):
        checkpoints[key] = value

    monkeypatch.setattr(attribution.cache, "get_json", get_cache)
    monkeypatch.setattr(attribution.cache, "set_json", set_cache)

    class OnePageDeadline:
        checks = 0

        @property
        def expired(self):
            self.checks += 1
            return self.checks > 1

    def handler(request):
        cursor = json.loads(request.content)["variables"]["after"]
        cursors.append(cursor)
        return httpx.Response(200, json=(
            page([commit("new", ["other", "me"])], "next") if cursor is None
            else page([commit("old", ["other", "me"])])
        ))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            first = await attribution._list_coauthored_commits(
                client, "o", "r", "me", "t", OnePageDeadline(), checkpoint_key="checkpoint"
            )
            second = await attribution._list_coauthored_commits(
                client, "o", "r", "me", "t", attribution.Deadline(None), checkpoint_key="checkpoint"
            )
            cached = await attribution._list_coauthored_commits(
                client, "o", "r", "me", "t", attribution.Deadline(None), checkpoint_key="checkpoint"
            )
            return first, second, cached

    first, second, cached = asyncio.run(run())
    assert cursors == [None, "next"]
    assert first.count == 1 and first.complete is False
    assert second.count == cached.count == 2
    assert second.shas == cached.shas == ["new", "old"]
    assert second.additions == cached.additions == 40
    assert second.complete is cached.complete is True


@pytest.mark.parametrize("primary,budget,partial", [
    (True, 2, False), (False, 2, False), (False, 0, False), (False, 2, True),
])
def test_repo_totals_include_coauthors(monkeypatch, primary, budget, partial):
    stored = []
    details = []

    async def get_cache(*args):
        return None

    async def set_cache(key, value, ttl):
        if not key.endswith(":coauthors"):
            stored.append(value)

    monkeypatch.setattr(attribution.cache, "get_json", get_cache)
    monkeypatch.setattr(attribution.cache, "set_json", set_cache)

    def handler(request):
        path = request.url.path
        if path == "/graphql":
            if json.loads(request.content)["variables"]["after"]:
                return httpx.Response(503)
            nodes = [commit("coauthored", ["someone", "Me", "Me"])]
            if primary:
                nodes.append(commit("mine", ["me", "Me"], additions=10, deletions=1))
            return httpx.Response(200, json=page(nodes, "next" if partial else None))
        if path.endswith("/stats/contributors"):
            return httpx.Response(200, json=[
                {"author": {"login": "me"}, "total": int(primary),
                 "weeks": [{"a": 10 if primary else 0, "d": int(primary)}]},
                {"author": {"login": "someone"}, "total": 5, "weeks": [{"a": 90, "d": 9}]},
            ])
        if path.endswith("/commits"):
            assert request.url.params["author"] == "me"
            return httpx.Response(200, json=[{"sha": "mine"}] if primary else [])
        sha = path.rsplit("/", 1)[-1]
        details.append(sha)
        return httpx.Response(200, json={"parents": [{}], "files": [{
            "filename": "src/shared.ts" if sha == "coauthored" else "src/mine.py",
            "additions": 20 if sha == "coauthored" else 10,
            "deletions": 4 if sha == "coauthored" else 1,
        }]})

    progress = attribution.WalkProgress()

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await attribution.analyze_repo_contribution(
                client, {"name": "repo", "owner": {"login": "owner"}}, "me", "token",
                attribution.AttributionBudget(budget), asyncio.Semaphore(2), progress=progress,
            )

    result = asyncio.run(run())
    assert result.commits == 1 + int(primary)
    assert result.additions == 20 + 10 * int(primary)
    assert result.deletions == 4 + int(primary)
    assert result.contribution_percentage == (30.0 if primary else 22.22)
    assert result.truncated is (budget == 0 or partial)
    assert len(details) == len(set(details)) == min(budget, 1 + int(primary))
    if budget:
        assert {language.name: language.lines for language in result.languages} == (
            {"TypeScript": 20, "Python": 10} if primary else {"TypeScript": 20}
        )
    else:
        assert result.method == "contributor_stats"
        assert result.languages == []
    assert bool(stored) is not partial
    assert (progress.resolved, progress.deferred) == ((0, 1) if partial else (1, 0))
