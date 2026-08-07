import asyncio

import pytest

from services import attribution
from services.language_map import detect_language, filter_languages, is_vendored


class TestDetectLanguage:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("src/main.py", "Python"),
            ("app/components/Button.tsx", "TypeScript"),
            ("index.js", "JavaScript"),
            ("cmd/server/main.go", "Go"),
            ("Dockerfile", "Dockerfile"),
            ("Dockerfile.dev", "Dockerfile"),
            ("Makefile", "Makefile"),
            ("deploy/CMakeLists.txt", "CMake"),
            ("styles/app.scss", "SCSS"),
            ("notebooks/eda.ipynb", "Jupyter Notebook"),
            ("readme.md", "Markdown"),
            ("infra/main.tf", "HCL"),
        ],
    )
    def test_known_paths(self, path, expected):
        assert detect_language(path) == expected

    @pytest.mark.parametrize("path", ["", "LICENSE.bin", "assets/logo.png", "noext"])
    def test_unknown_paths(self, path):
        assert detect_language(path) in (None, "Text")

    def test_case_insensitive_extension(self):
        assert detect_language("src/Main.PY") == "Python"


class TestIsVendored:
    @pytest.mark.parametrize(
        "path",
        [
            "node_modules/react/index.js",
            "frontend/dist/bundle.js",
            "vendor/github.com/pkg/errors/errors.go",
            "package-lock.json",
            "uv.lock",
            "static/js/app.min.js",
            "api/service.pb.go",
            "proto/thing_pb2.py",
            "types/index.d.ts",
            "backend/__pycache__/mod.py",
        ],
    )
    def test_vendored(self, path):
        assert is_vendored(path) is True

    @pytest.mark.parametrize(
        "path",
        ["src/app.py", "lib/build.ts", "services/attribution.py", "README.md"],
    )
    def test_authored(self, path):
        assert is_vendored(path) is False

    def test_only_directory_segments_count(self):
        # A file literally named "dist.py" is source, not build output.
        assert is_vendored("src/dist.py") is False


class TestFilterLanguages:
    def test_excludes_case_insensitively(self):
        totals = {"Python": 100, "Markdown": 50, "JSON": 25}
        assert filter_languages(totals, ["markdown", "json"]) == {"Python": 100}

    def test_no_exclusions_returns_copy(self):
        totals = {"Go": 10}
        result = filter_languages(totals, None)
        assert result == totals and result is not totals


class TestAccumulateFiles:
    def test_sums_per_language_and_skips_vendored(self):
        additions, deletions, files = {}, {}, {}
        counted = attribution._accumulate_files(
            [
                {"filename": "src/a.py", "additions": 10, "deletions": 2},
                {"filename": "src/b.py", "additions": 5, "deletions": 0},
                {"filename": "web/c.ts", "additions": 7, "deletions": 3},
                {"filename": "node_modules/d.js", "additions": 900, "deletions": 100},
                {"filename": "assets/logo.png", "additions": 1, "deletions": 0},
            ],
            additions,
            deletions,
            files,
        )

        assert additions == {"Python": 15, "TypeScript": 7}
        assert deletions == {"Python": 2, "TypeScript": 3}
        assert files == {"Python": 2, "TypeScript": 1}
        assert counted == (22, 5, 3)

    def test_handles_empty_and_malformed(self):
        additions, deletions, files = {}, {}, {}
        assert attribution._accumulate_files(
            [None, {}, {"filename": ""}], additions, deletions, files
        ) == (0, 0, 0)
        assert additions == {}


class TestScale:
    def test_preserves_proportions(self):
        scaled = attribution._scale({"Python": 30, "Go": 10}, 400)
        assert scaled == {"Python": 300, "Go": 100}

    def test_noop_on_empty_or_zero_target(self):
        assert attribution._scale({}, 100) == {}
        assert attribution._scale({"Go": 5}, 0) == {"Go": 5}


class TestBuildLanguageList:
    def test_percentages_renormalize_after_exclusion(self):
        languages = attribution._build_language_list(
            {"Python": 75, "Go": 25, "Markdown": 100},
            {"Python": 3, "Go": 1, "Markdown": 9},
            ["Markdown"],
        )
        assert [(item.name, item.percentage) for item in languages] == [
            ("Python", 75.0),
            ("Go", 25.0),
        ]
        assert languages[0].lines == 75
        assert languages[0].files == 3

    def test_empty_when_everything_excluded(self):
        assert attribution._build_language_list({"Markdown": 10}, {}, ["Markdown"]) == []


class TestAttributionBudget:
    def test_grants_until_exhausted(self):
        async def run():
            budget = attribution.AttributionBudget(10)
            first = await budget.take(6)
            second = await budget.take(6)
            third = await budget.take(1)
            return first, second, third, budget.remaining

        assert asyncio.run(run()) == (6, 4, 0, 0)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeClient:
    """Minimal stand-in for httpx.AsyncClient keyed on URL substrings."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def get(self, url, params=None, headers=None):
        self.calls.append(url)
        for fragment, response in self.routes.items():
            if fragment in url:
                return response
        return FakeResponse(status_code=404)


class TestCountUserCommits:
    def test_reads_last_page_from_link_header(self):
        client = FakeClient(
            {
                "/commits": FakeResponse(
                    payload=[{"sha": "a"}],
                    headers={
                        "Link": (
                            '<https://api.github.com/repositories/1/commits'
                            '?author=me&per_page=1&page=2>; rel="next", '
                            '<https://api.github.com/repositories/1/commits'
                            '?author=me&per_page=1&page=47>; rel="last"'
                        )
                    },
                )
            }
        )
        count = asyncio.run(
            attribution._count_user_commits(client, "o", "r", "me", "t")
        )
        assert count == 47

    def test_falls_back_to_payload_length(self):
        client = FakeClient({"/commits": FakeResponse(payload=[{"sha": "a"}])})
        assert asyncio.run(attribution._count_user_commits(client, "o", "r", "me", "t")) == 1

    def test_empty_repo_returns_zero(self):
        client = FakeClient({"/commits": FakeResponse(status_code=409)})
        assert asyncio.run(attribution._count_user_commits(client, "o", "r", "me", "t")) == 0


class TestFetchCommitFiles:
    def _run(self, payload, status_code=200):
        client = FakeClient(
            {"/commits/": FakeResponse(status_code=status_code, payload=payload)}
        )
        return asyncio.run(
            attribution._fetch_commit_files(
                client,
                "o",
                "r",
                "sha",
                "t",
                asyncio.Semaphore(1),
                attribution.Deadline(None),
            )
        )

    def test_returns_files(self):
        files = [{"filename": "a.py", "additions": 1, "deletions": 0}]
        assert self._run({"parents": [{"sha": "p"}], "files": files}) == files

    def test_skips_merge_commits(self):
        assert self._run(
            {"parents": [{"sha": "p1"}, {"sha": "p2"}], "files": [{"filename": "a.py"}]}
        ) == []

    def test_error_status_returns_none(self):
        assert self._run(None, status_code=500) is None


class TestFetchContributorTotals:
    def test_splits_user_from_repo_totals(self):
        payload = [
            {
                "author": {"login": "Me"},
                "total": 12,
                "weeks": [{"a": 100, "d": 10}, {"a": 50, "d": 5}],
            },
            {
                "author": {"login": "someone-else"},
                "total": 40,
                "weeks": [{"a": 850, "d": 200}],
            },
        ]
        client = FakeClient({"/stats/contributors": FakeResponse(payload=payload)})
        totals = asyncio.run(
            attribution._fetch_contributor_totals(
                client, "o", "r", "me", "t", attribution.Deadline(None)
            )
        )
        assert totals == {
            "user_additions": 150,
            "user_deletions": 15,
            "user_commits": 12,
            "repo_additions": 1000,
        }

    def test_user_absent_reports_zero_share(self):
        payload = [{"author": {"login": "other"}, "total": 3, "weeks": [{"a": 40, "d": 0}]}]
        client = FakeClient({"/stats/contributors": FakeResponse(payload=payload)})
        totals = asyncio.run(
            attribution._fetch_contributor_totals(
                client, "o", "r", "me", "t", attribution.Deadline(None)
            )
        )
        assert totals["user_additions"] == 0
        assert totals["repo_additions"] == 40

    def test_unavailable_stats_return_none(self):
        client = FakeClient({"/stats/contributors": FakeResponse(status_code=403)})
        assert (
            asyncio.run(
                attribution._fetch_contributor_totals(
                client, "o", "r", "me", "t", attribution.Deadline(None)
            )
            )
            is None
        )


class TestAnalyzeRepoContribution:
    """End-to-end over a fork where the user wrote a small slice of the code."""

    def _repo(self, **overrides):
        repo = {
            "name": "upstream-project",
            "full_name": "me/upstream-project",
            "owner": {"login": "me"},
            "fork": True,
            "pushed_at": "2026-01-01T00:00:00Z",
            "html_url": "https://github.com/me/upstream-project",
        }
        repo.update(overrides)
        return repo

    def _run(self, client, budget_size=100):
        return asyncio.run(
            attribution.analyze_repo_contribution(
                client,
                self._repo(),
                "me",
                "t",
                attribution.AttributionBudget(budget_size),
                asyncio.Semaphore(2),
            )
        )

    def test_counts_only_the_users_own_lines(self, monkeypatch):
        # 2 commits by the user; the upstream repo is far larger.
        commit_files = {
            "sha1": [
                {"filename": "src/patch.rs", "additions": 40, "deletions": 5},
                {"filename": "node_modules/x.js", "additions": 5000, "deletions": 0},
            ],
            "sha2": [{"filename": "src/other.rs", "additions": 10, "deletions": 1}],
        }

        async def fake_count(*_args, **_kwargs):
            return 2

        async def fake_shas(*_args, **_kwargs):
            return ["sha1", "sha2"]

        async def fake_files(_client, _o, _r, sha, *_a, **_k):
            return commit_files[sha]

        async def fake_stats(*_args, **_kwargs):
            return {
                "user_additions": 50,
                "user_deletions": 6,
                "user_commits": 2,
                "repo_additions": 100000,
            }

        monkeypatch.setattr(attribution, "_count_user_commits", fake_count)
        monkeypatch.setattr(attribution, "_list_commit_shas", fake_shas)
        monkeypatch.setattr(attribution, "_fetch_commit_files", fake_files)
        monkeypatch.setattr(attribution, "_fetch_contributor_totals", fake_stats)

        result = self._run(FakeClient({}))

        assert result is not None
        assert result.is_fork is True
        assert result.commits == 2
        assert result.additions == 50  # vendored bundle excluded
        assert result.deletions == 6
        assert result.files_changed == 2
        assert result.method == "commits"
        assert result.truncated is False
        assert [(l.name, l.lines) for l in result.languages] == [("Rust", 50)]
        assert result.contribution_percentage == 0.05

    def test_returns_none_when_user_has_no_commits(self, monkeypatch):
        async def fake_count(*_args, **_kwargs):
            return 0

        monkeypatch.setattr(attribution, "_count_user_commits", fake_count)
        assert self._run(FakeClient({})) is None

    def test_scales_sampled_mix_to_true_totals_when_truncated(self, monkeypatch):
        async def fake_count(*_args, **_kwargs):
            return 500

        async def fake_shas(_client, _o, _r, _u, _t, limit, _deadline):
            return [f"sha{i}" for i in range(limit)]

        async def fake_files(*_args, **_kwargs):
            return [{"filename": "src/a.py", "additions": 10, "deletions": 1}]

        async def fake_stats(*_args, **_kwargs):
            return {
                "user_additions": 5000,
                "user_deletions": 500,
                "user_commits": 500,
                "repo_additions": 5000,
            }

        monkeypatch.setattr(attribution, "_count_user_commits", fake_count)
        monkeypatch.setattr(attribution, "_list_commit_shas", fake_shas)
        monkeypatch.setattr(attribution, "_fetch_commit_files", fake_files)
        monkeypatch.setattr(attribution, "_fetch_contributor_totals", fake_stats)

        result = self._run(FakeClient({}), budget_size=10)

        assert result.truncated is True
        assert result.method == "estimated"
        assert result.commits == 500
        assert result.additions == 5000
        assert result.languages[0].lines == 5000

    def test_falls_back_to_language_bytes_without_diffs(self, monkeypatch):
        async def fake_count(*_args, **_kwargs):
            return 3

        async def fake_shas(*_args, **_kwargs):
            return ["a", "b", "c"]

        async def fake_files(*_args, **_kwargs):
            return None  # diffs unavailable

        async def fake_stats(*_args, **_kwargs):
            return {
                "user_additions": 200,
                "user_deletions": 20,
                "user_commits": 3,
                "repo_additions": 800,
            }

        async def fake_bytes(*_args, **_kwargs):
            return {"Go": 3000, "Shell": 1000}

        monkeypatch.setattr(attribution, "_count_user_commits", fake_count)
        monkeypatch.setattr(attribution, "_list_commit_shas", fake_shas)
        monkeypatch.setattr(attribution, "_fetch_commit_files", fake_files)
        monkeypatch.setattr(attribution, "_fetch_contributor_totals", fake_stats)
        monkeypatch.setattr(attribution, "_fetch_repo_language_bytes", fake_bytes)

        result = self._run(FakeClient({}))

        assert result.method == "estimated"
        assert result.additions == 200
        assert [(l.name, l.lines) for l in result.languages] == [
            ("Go", 150),
            ("Shell", 50),
        ]
        assert result.contribution_percentage == 25.0


class TestDeadline:
    def test_no_limit_never_expires(self):
        deadline = attribution.Deadline(None)
        assert deadline.expired is False
        assert deadline.remaining == float("inf")

    def test_expires_after_its_window(self):
        assert attribution.Deadline(0).expired is True

    def test_rate_limit_guard_expires_it_early(self):
        guard = attribution.RateLimitGuard(floor=500)
        deadline = attribution.Deadline(3600, guard)
        assert deadline.expired is False

        guard.observe(FakeResponse(headers={"x-ratelimit-remaining": "12"}))
        assert deadline.expired is True
        assert deadline.remaining == 0.0


class TestRateLimitGuard:
    def test_stays_open_above_the_floor(self):
        guard = attribution.RateLimitGuard(floor=500)
        guard.observe(FakeResponse(headers={"x-ratelimit-remaining": "900"}))
        assert guard.exhausted is False

    def test_ignores_responses_without_the_header(self):
        guard = attribution.RateLimitGuard(floor=500)
        guard.observe(FakeResponse())
        assert guard.exhausted is False

    def test_stays_tripped_once_seen(self):
        guard = attribution.RateLimitGuard(floor=500)
        guard.observe(FakeResponse(headers={"x-ratelimit-remaining": "1"}))
        guard.observe(FakeResponse(headers={"x-ratelimit-remaining": "4999"}))
        assert guard.exhausted is True


class TestAnalyzeRepoContributionLimits:
    """A walk that runs out of budget must defer work, never fake an answer."""

    def _repo(self):
        return {
            "name": "proj",
            "full_name": "me/proj",
            "owner": {"login": "me"},
            "pushed_at": "2026-01-01T00:00:00Z",
        }

    def _run(self, **kwargs):
        progress = attribution.WalkProgress()
        result = asyncio.run(
            attribution.analyze_repo_contribution(
                FakeClient({}),
                self._repo(),
                "me",
                "t",
                attribution.AttributionBudget(100),
                asyncio.Semaphore(2),
                progress=progress,
                **kwargs,
            )
        )
        return result, progress

    def test_cache_only_defers_instead_of_measuring(self):
        result, progress = self._run(cache_only=True)
        assert result is None
        assert (progress.resolved, progress.deferred) == (0, 1)

    def test_expired_deadline_defers_instead_of_measuring(self):
        result, progress = self._run(deadline=attribution.Deadline(0))
        assert result is None
        assert (progress.resolved, progress.deferred) == (0, 1)

    def test_repo_without_user_commits_counts_as_resolved(self, monkeypatch):
        # Nothing to measure is a real answer, not a deferral -- otherwise
        # coverage could never reach the threshold for such a user.
        async def no_shas(*_args, **_kwargs):
            return []

        monkeypatch.setattr(attribution, "_list_commit_shas", no_shas)
        result, progress = self._run()
        assert result is None
        assert (progress.resolved, progress.deferred) == (1, 0)

    def _measurable(self, monkeypatch, stored):
        async def fake_shas(*_args, **_kwargs):
            return ["sha1"]

        async def fake_files(*_args, **_kwargs):
            return [{"filename": "src/a.py", "additions": 10, "deletions": 0}]

        async def fake_stats(*_args, **_kwargs):
            return {
                "user_additions": 10,
                "user_deletions": 0,
                "user_commits": 1,
                "repo_additions": 100,
            }

        async def fake_set(key, value, ttl):
            stored.append(key)

        monkeypatch.setattr(attribution, "_list_commit_shas", fake_shas)
        monkeypatch.setattr(attribution, "_fetch_commit_files", fake_files)
        monkeypatch.setattr(attribution, "_fetch_contributor_totals", fake_stats)
        monkeypatch.setattr(attribution.cache, "set_json", fake_set)

    def test_complete_measurement_is_cached(self, monkeypatch):
        stored = []
        self._measurable(monkeypatch, stored)

        result, progress = self._run(deadline=attribution.Deadline(None))

        assert result is not None and result.additions == 10
        assert stored, "a measurement taken with budget to spare should be cached"
        assert (progress.resolved, progress.deferred) == (1, 0)

    def test_measurement_cut_short_is_returned_but_not_cached(self, monkeypatch):
        """A deadline-truncated figure must not be served for the whole TTL."""
        stored = []
        self._measurable(monkeypatch, stored)

        # Mimics a deadline that runs out mid-walk: the entry gate reads it as
        # live and lets the repo through, the write-back check reads it as
        # expired. Every stub above bypasses the checks in between.
        class ExpiringDeadline(attribution.Deadline):
            def __init__(self):
                super().__init__(None)
                self.checks = 0

            @property
            def expired(self):
                self.checks += 1
                return self.checks > 1

            @property
            def remaining(self):
                return float("inf")

        result, progress = self._run(deadline=ExpiringDeadline())

        assert result is not None, "partial numbers are still worth returning"
        assert not stored, "a truncated measurement must not poison the cache"
        assert (progress.resolved, progress.deferred) == (0, 1)

    def test_empty_listing_under_expired_deadline_defers(self, monkeypatch):
        """An empty page can mean "no commits" or "ran out of time" -- and the
        second must not be recorded as a settled repo."""

        class ExpiredAfterGate(attribution.Deadline):
            def __init__(self):
                super().__init__(None)
                self.checks = 0

            @property
            def expired(self):
                self.checks += 1
                return self.checks > 1

        async def no_shas(*_args, **_kwargs):
            return []

        monkeypatch.setattr(attribution, "_list_commit_shas", no_shas)
        result, progress = self._run(deadline=ExpiredAfterGate())

        assert result is None
        assert (progress.resolved, progress.deferred) == (0, 1)


class TestExplain:
    """An empty breakdown must say why, or prod failures look identical."""

    def _progress(self, resolved, deferred):
        p = attribution.WalkProgress()
        p.resolved, p.deferred = resolved, deferred
        return p

    def _guard(self, tripped):
        g = attribution.RateLimitGuard(floor=500)
        if tripped:
            g.observe(FakeResponse(headers={"x-ratelimit-remaining": "1"}))
        return g

    def test_rate_limit_wins_over_every_other_cause(self):
        # A tripped guard is what caused the thin coverage, so it is the
        # useful thing to report even though the others are also true.
        status, message = attribution._explain(
            self._progress(0, 60), self._guard(True), cache_enabled=False, cache_only=True
        )
        assert status == "rate_limited"
        assert "quota" in message.lower()

    def test_complete_walk(self):
        status, message = attribution._explain(
            self._progress(60, 0), self._guard(False), cache_enabled=True, cache_only=False
        )
        assert status == "complete"

    def test_missing_redis_is_called_out(self):
        status, message = attribution._explain(
            self._progress(5, 55), self._guard(False), cache_enabled=False, cache_only=False
        )
        assert status == "cache_disabled"
        assert "REDIS_URL" in message

    def test_deadline_when_cache_is_working(self):
        status, message = attribution._explain(
            self._progress(5, 55), self._guard(False), cache_enabled=True, cache_only=False
        )
        assert status == "deadline"
        assert "again" in message.lower()

    def test_cache_only_mode_points_at_the_warm_script(self):
        status, message = attribution._explain(
            self._progress(5, 55), self._guard(False), cache_enabled=True, cache_only=True
        )
        assert status == "deadline"
        assert "warm_attribution" in message
