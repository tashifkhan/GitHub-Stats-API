"""Pending attribution queues the user, and the scheduled worker drains the queue."""

import asyncio
import importlib.util
import pathlib

import pytest
from fastapi import HTTPException

import core.jobs as jobs
from core.token_pool import TokenPool
from models.attribution import ContributionLanguageStats, LanguageContribution
from services import languages

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "drain_attribution.py"
spec = importlib.util.spec_from_file_location("drain_attribution", SCRIPT)
drain_attribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drain_attribution)


def test_pending_request_queues_the_user_and_says_so(monkeypatch):
    queued = []

    async def partial(*args, **kwargs):
        return ContributionLanguageStats(username="taf", repos_considered=4, coverage=0.25, partial=True)

    async def enqueue(kind, subject):
        queued.append((kind, subject))
        return True

    monkeypatch.setattr(languages, "get_user_contributions", partial)
    monkeypatch.setattr(languages, "enqueue", enqueue)
    with pytest.raises(HTTPException) as error:
        asyncio.run(languages.get_attributed_language_stats("taf", "unused", []))
    assert error.value.status_code == 503
    assert error.value.detail["refreshQueued"] is True
    assert queued == [("languages", "taf")]


class MemoryCache:
    def __init__(self):
        self.data = {}

    async def get_json(self, key):
        return self.data.get(key)

    async def set_json(self, key, value, ttl):
        self.data[key] = value
        return True


def test_complete_result_sets_marker_and_later_requests_skip_the_queue(monkeypatch):
    store = MemoryCache()
    queued = []

    async def complete(*args, **kwargs):
        return ContributionLanguageStats(username="taf", repos_considered=4, coverage=1.0)

    async def enqueue(kind, subject):
        queued.append(subject)
        return True

    monkeypatch.setattr(languages, "cache", store)
    monkeypatch.setattr(languages, "get_user_contributions", complete)
    monkeypatch.setattr(languages, "enqueue", enqueue)
    asyncio.run(languages.get_attributed_language_stats("taf", "unused", []))
    assert languages._complete_marker("taf") in store.data
    queued.clear()
    asyncio.run(languages.get_attributed_language_stats("TAF", "unused", []))
    assert queued == []


def test_pending_walk_serves_last_complete_ranking_as_stale(monkeypatch):
    # A push changes one repo's cache key. Until the worker re-measures it,
    # the previous complete ranking should stand in rather than a 503.
    store = MemoryCache()
    queued = []
    walks = iter([
        ContributionLanguageStats(
            username="taf", repos_considered=4, coverage=1.0,
            languages=[LanguageContribution(name="Rust", percentage=100.0, lines=10)],
        ),
        ContributionLanguageStats(username="taf", repos_considered=4, coverage=0.75, partial=True),
    ])

    async def walk(*args, **kwargs):
        return next(walks)

    async def enqueue(kind, subject):
        queued.append(subject)
        return True

    monkeypatch.setattr(languages, "cache", store)
    monkeypatch.setattr(languages, "get_user_contributions", walk)
    monkeypatch.setattr(languages, "enqueue", enqueue)
    fresh = asyncio.run(languages.get_attributed_language_stats("taf", "unused", ["Markdown"]))
    assert [item.name for item in fresh] == ["Rust"]

    stale = asyncio.run(languages.get_attributed_language_stats("TAF", "unused", ["markdown"]))
    assert isinstance(stale, languages.StaleLanguages)
    assert [item.name for item in stale] == ["Rust"]
    assert stale.detail["coverage"] == 0.75
    assert stale.detail["refreshQueued"] is True
    assert stale.detail["measuredAt"]
    # The pending read re-queues the user so the worker measures the change.
    assert queued[-1] == "TAF"


def test_stale_ranking_is_keyed_by_exclusions(monkeypatch):
    store = MemoryCache()
    walks = iter([
        ContributionLanguageStats(
            username="taf", repos_considered=4, coverage=1.0,
            languages=[LanguageContribution(name="Rust", percentage=100.0, lines=10)],
        ),
        ContributionLanguageStats(username="taf", repos_considered=4, coverage=0.75, partial=True),
    ])

    async def walk(*args, **kwargs):
        return next(walks)

    async def enqueue(kind, subject):
        return True

    monkeypatch.setattr(languages, "cache", store)
    monkeypatch.setattr(languages, "get_user_contributions", walk)
    monkeypatch.setattr(languages, "enqueue", enqueue)
    asyncio.run(languages.get_attributed_language_stats("taf", "unused", ["Markdown"]))
    with pytest.raises(HTTPException) as error:
        asyncio.run(languages.get_attributed_language_stats("taf", "unused", []))
    assert error.value.status_code == 503


def test_queueing_happens_before_the_walk(monkeypatch):
    order = []

    async def walk(*args, **kwargs):
        order.append("walk")
        raise asyncio.CancelledError  # what the request budget does on timeout

    async def enqueue(kind, subject):
        order.append("queue")
        return True

    monkeypatch.setattr(languages, "cache", MemoryCache())
    monkeypatch.setattr(languages, "get_user_contributions", walk)
    monkeypatch.setattr(languages, "enqueue", enqueue)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(languages.get_attributed_language_stats("taf", "unused", []))
    assert order == ["queue", "walk"]


def test_worker_marks_a_finished_user(monkeypatch):
    store = MemoryCache()

    async def complete(*args, **kwargs):
        return ContributionLanguageStats(username="taf", repos_considered=4, coverage=1.0, status="complete")

    monkeypatch.setattr(drain_attribution, "cache", store)
    monkeypatch.setattr(drain_attribution, "get_user_contributions", complete)
    handler = drain_attribution.make_handler("unused", 60, log=lambda *_: None)
    job = type("Job", (), {"payload": {"subject": "taf"}, "data": {}})()
    assert asyncio.run(handler(job)) is True
    assert languages._complete_marker("taf") in store.data


def test_worker_tries_every_account_in_the_pool(monkeypatch):
    calls = []

    async def walk(username, token, **kwargs):
        calls.append(token)
        if token == "c":
            return ContributionLanguageStats(
                username="taf",
                repos_considered=4,
                coverage=1.0,
                status="complete",
            )
        return ContributionLanguageStats(
            username="taf",
            repos_considered=4,
            coverage=0.25,
            partial=True,
            status="rate_limited",
        )

    pool = TokenPool(["a", "b", "c"])
    monkeypatch.setattr(drain_attribution, "get_user_contributions", walk)
    monkeypatch.setattr(drain_attribution, "get_token_pool", lambda: pool)

    handler = drain_attribution.make_handler(None, 60, log=lambda *_: None)
    job = type("Job", (), {"payload": {"subject": "taf"}, "data": {}})()

    assert asyncio.run(handler(job)) is True
    assert calls == ["a", "b", "c"]


def test_worker_stops_after_the_whole_pool_is_spent(monkeypatch):
    calls = []

    async def walk(username, token, **kwargs):
        calls.append(token)
        return ContributionLanguageStats(
            username="taf",
            repos_considered=4,
            coverage=0.25,
            partial=True,
            status="rate_limited",
        )

    pool = TokenPool(["a", "b", "c"])
    monkeypatch.setattr(drain_attribution, "get_user_contributions", walk)
    monkeypatch.setattr(drain_attribution, "get_token_pool", lambda: pool)

    handler = drain_attribution.make_handler(None, 60, log=lambda *_: None)
    job = type("Job", (), {"payload": {"subject": "taf"}, "data": {}})()

    with pytest.raises(drain_attribution.QuotaExhausted):
        asyncio.run(handler(job))
    assert calls == ["a", "b", "c"]


def test_claim_lease_outlives_the_handler_timeout(monkeypatch):
    calls = []

    async def command(name, *args, **kwargs):
        calls.append(args)
        return None  # nothing due

    monkeypatch.setattr(jobs, "command", command)
    monkeypatch.setattr(jobs, "enabled", lambda: True)
    assert asyncio.run(jobs.run_once(lambda job: None, timeout=120)) is False
    assert calls[0][0] == jobs.CLAIM
    assert calls[0][-1] == 150


async def no_jobs():
    return 0


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_drain_stops_when_the_queue_is_empty():
    clock = FakeClock()
    due = ["a", "b"]

    async def run_once(handler, timeout):
        if not due:
            return False
        due.pop()
        clock.now += 30
        return True

    claimed, exhausted = asyncio.run(
        drain_attribution.drain(None, minutes=10, pass_seconds=60, run_once=run_once, clock=clock, pending=no_jobs)
    )
    assert (claimed, exhausted) == (2, False)


def test_drain_leaves_room_for_a_full_pass():
    clock = FakeClock()

    async def run_once(handler, timeout):
        clock.now += 90
        return True

    claimed, _ = asyncio.run(
        drain_attribution.drain(None, minutes=5, pass_seconds=90, run_once=run_once, clock=clock, pending=no_jobs)
    )
    # 300s total, and a claim starts only while a whole 90s pass still fits.
    assert claimed == 3


def test_drain_stops_at_the_quota_floor():
    clock = FakeClock()
    calls = []

    async def handler(job):
        raise drain_attribution.QuotaExhausted("taf")

    async def run_once(handler_, timeout):
        calls.append(timeout)
        try:
            await handler_(object())
        except drain_attribution.QuotaExhausted:
            pass  # run_once records a retry; the job stays queued
        return True

    claimed, exhausted = asyncio.run(
        drain_attribution.drain(handler, minutes=10, pass_seconds=60, run_once=run_once, clock=clock, pending=no_jobs)
    )
    assert (claimed, exhausted) == (1, True)
    assert calls == [90]


def test_stalled_user_gets_a_longer_pass(monkeypatch):
    limits = []

    async def stuck(username, token, **kwargs):
        limits.append(kwargs["deadline_seconds"])
        return ContributionLanguageStats(username="taf", repos_considered=10, coverage=0.9, partial=True, status="deadline")

    monkeypatch.setattr(drain_attribution, "get_user_contributions", stuck)
    handler = drain_attribution.make_handler("unused", 60, log=lambda *_: None, max_pass_seconds=200)
    job = type("Job", (), {"payload": {"subject": "taf"}, "data": {}})()
    for _ in range(4):
        assert asyncio.run(handler(job)) is False
    # First pass sets the baseline, then each pass without progress doubles.
    assert limits == [60, 60, 120, 200]


def test_pass_never_outlasts_the_drain(monkeypatch):
    limits = []

    async def stuck(username, token, **kwargs):
        limits.append(kwargs["deadline_seconds"])
        return ContributionLanguageStats(username="taf", repos_considered=10, coverage=0.9, partial=True)

    monkeypatch.setattr(drain_attribution, "get_user_contributions", stuck)
    handler = drain_attribution.make_handler("unused", 60, log=lambda *_: None, max_pass_seconds=600, time_left=lambda: 45)
    job = type("Job", (), {"payload": {"subject": "taf"}, "data": {"passSeconds": 480}})()
    asyncio.run(handler(job))
    assert limits == [45]


def test_drain_waits_for_a_user_requeued_just_ahead():
    clock = FakeClock()
    attempts = []
    queue = {"due_at": 0, "left": 2}

    async def run_once(handler, timeout):
        attempts.append(clock.now)
        if queue["left"] and clock.now >= queue["due_at"]:
            queue["left"] -= 1
            clock.now += 60
            queue["due_at"] = clock.now + 2  # unfinished: retried shortly
            return True
        return False

    async def pending():
        return queue["left"]

    async def sleep(seconds):
        clock.now += seconds

    claimed, _ = asyncio.run(drain_attribution.drain(
        None, minutes=10, pass_seconds=60, run_once=run_once, clock=clock, pending=pending, sleep=sleep))
    assert claimed == 2
