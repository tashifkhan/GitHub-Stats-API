"""Attributed language stats must degrade, not fail or mislead.

Walking commit diffs cannot finish inside one request, so a thin walk has to
fall back to whole-repo bytes rather than serve a language mix drawn from a
handful of repos.
"""

import asyncio

import pytest
from fastapi import HTTPException

from core.config import attribution_settings
from models.analytics import LanguageData
from models.attribution import ContributionLanguageStats, LanguageContribution
from services import languages as languages_service


def _walk(coverage, langs=(("Rust", 100.0, 500, 5),)):
    return ContributionLanguageStats(
        username="me",
        languages=[
            LanguageContribution(name=n, percentage=p, lines=l, files=f)
            for n, p, l, f in langs
        ],
        repos_considered=10,
        repos_analyzed=int(coverage * 10),
        coverage=coverage,
        partial=coverage < 1.0,
    )


LEGACY = [LanguageData(name="Python", percentage=100.0)]


@pytest.fixture
def stubbed(monkeypatch):
    """Swap both data sources; each test sets what they return."""
    state = {"walk": _walk(1.0), "legacy": list(LEGACY)}

    async def fake_walk(*_args, **_kwargs):
        result = state["walk"]
        if isinstance(result, Exception):
            raise result
        return result

    async def fake_legacy(*_args, **_kwargs):
        result = state["legacy"]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(languages_service, "get_user_contributions", fake_walk)
    monkeypatch.setattr(languages_service, "get_language_stats", fake_legacy)
    return state


def _run():
    return asyncio.run(
        languages_service.get_attributed_language_stats("me", "t", [])
    )


class TestCoverageGate:
    def test_full_coverage_serves_attributed(self, stubbed):
        assert [l.name for l in _run()] == ["Rust"]

    def test_thin_coverage_serves_legacy(self, stubbed):
        stubbed["walk"] = _walk(0.2)
        assert [l.name for l in _run()] == ["Python"]

    def test_coverage_exactly_at_threshold_is_accepted(self, stubbed):
        stubbed["walk"] = _walk(attribution_settings.min_coverage)
        assert [l.name for l in _run()] == ["Rust"]

    def test_no_languages_serves_legacy(self, stubbed):
        stubbed["walk"] = _walk(1.0, langs=())
        assert [l.name for l in _run()] == ["Python"]


class TestPartialFailures:
    def test_walk_failure_falls_back_to_legacy(self, stubbed):
        stubbed["walk"] = HTTPException(status_code=502, detail="boom")
        assert [l.name for l in _run()] == ["Python"]

    def test_legacy_failure_is_survivable_when_walk_is_good(self, stubbed):
        stubbed["legacy"] = HTTPException(status_code=503, detail="throttled")
        assert [l.name for l in _run()] == ["Rust"]

    def test_both_failing_surfaces_the_walk_error(self, stubbed):
        stubbed["walk"] = HTTPException(status_code=503, detail="throttled")
        stubbed["legacy"] = HTTPException(status_code=502, detail="boom")
        with pytest.raises(HTTPException) as exc:
            _run()
        assert exc.value.status_code == 503

    def test_thin_walk_with_failing_legacy_still_raises(self, stubbed):
        stubbed["walk"] = _walk(0.1)
        stubbed["legacy"] = HTTPException(status_code=503, detail="throttled")
        with pytest.raises(HTTPException) as exc:
            _run()
        assert exc.value.status_code == 503
