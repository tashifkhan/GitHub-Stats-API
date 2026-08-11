"""Attributed language stats must never include somebody else's code."""

import asyncio

from fastapi import HTTPException

from models.attribution import ContributionLanguageStats, LanguageContribution
from services import languages as languages_service


def _walk(coverage, langs=(("Rust", 100.0, 500, 5),)):
    return ContributionLanguageStats(
        username="tashifkhan",
        languages=[
            LanguageContribution(name=n, percentage=p, lines=l, files=f)
            for n, p, l, f in langs
        ],
        repos_considered=10,
        repos_analyzed=int(coverage * 10),
        coverage=coverage,
        partial=coverage < 1.0,
    )


def _stub(monkeypatch):
    """Swap the own-commit source and reject whole-repository fallback calls."""
    state = {"walk": _walk(1.0), "legacy_called": False}

    async def fake_walk(*_args, **_kwargs):
        result = state["walk"]
        if isinstance(result, Exception):
            raise result
        return result

    async def fake_legacy(*_args, **_kwargs):
        state["legacy_called"] = True
        raise AssertionError("attributed stats must not read whole-repository languages")

    monkeypatch.setattr(languages_service, "get_user_contributions", fake_walk)
    monkeypatch.setattr(languages_service, "get_language_stats", fake_legacy)
    return state


def _run():
    return asyncio.run(
        languages_service.get_attributed_language_stats("tashifkhan", "t", [])
    )


class TestStrictOwnCommitAttribution:
    def test_full_coverage_serves_attributed(self, monkeypatch):
        stubbed = _stub(monkeypatch)
        assert [l.name for l in _run()] == ["Rust"]
        assert stubbed["legacy_called"] is False

    def test_thin_coverage_still_never_serves_whole_repo_data(self, monkeypatch):
        stubbed = _stub(monkeypatch)
        stubbed["walk"] = _walk(0.2)
        assert [l.name for l in _run()] == ["Rust"]
        assert stubbed["legacy_called"] is False

    def test_no_measured_languages_returns_empty_instead_of_repo_mix(self, monkeypatch):
        stubbed = _stub(monkeypatch)
        stubbed["walk"] = _walk(1.0, langs=())
        assert _run() == []
        assert stubbed["legacy_called"] is False

    def test_attribution_failure_is_not_hidden_by_repo_data(self, monkeypatch):
        stubbed = _stub(monkeypatch)
        stubbed["walk"] = HTTPException(status_code=503, detail="throttled")
        status_code = None
        try:
            _run()
        except HTTPException as exc:
            status_code = exc.status_code
        else:
            raise AssertionError("the attribution error should be surfaced")
        assert status_code == 503
