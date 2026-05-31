"""Builds the unified cross-platform card for GitHub (``development`` category).

Mapping: total commits -> ``stats.totalSolved``; top languages -> topic analysis;
the contribution calendar -> heatmap. GitHub has no contests / rating / badges,
so those sections stay empty. See ../UNIFIED_SCHEMA.md.
"""

from datetime import date, timedelta
from math import ceil
from typing import Any, Dict, List, Optional

from modules.unified import (
    HeatDay,
    TopicCount,
    UnifiedBadges,
    UnifiedCard,
    UnifiedContests,
    UnifiedHeatmap,
    UnifiedProfile,
    UnifiedRating,
    UnifiedSocial,
    UnifiedStats,
    UnifiedSummary,
    YearContribution,
)


def profile_from(user: Dict[str, Any], username: str) -> UnifiedProfile:
    user = user or {}
    blog = (user.get("blog") or "").strip()
    twitter = user.get("twitter_username")
    return UnifiedProfile(
        displayName=user.get("name") or user.get("login") or username,
        username=user.get("login") or username,
        avatar=user.get("avatar_url"),
        country=user.get("location"),
        company=user.get("company"),
        bio=user.get("bio"),
        websites=[blog] if blog else [],
        social=UnifiedSocial(
            github=user.get("html_url") or f"https://github.com/{username}",
            twitter=f"https://twitter.com/{twitter}" if twitter else None,
        ),
        verified=False,
    )


def stats_from(
    stats_response,
    pr_count: int = 0,
    issue_count: int = 0,
    review_count: int = 0,
) -> UnifiedStats:
    if stats_response is None:
        return UnifiedStats()
    topics = [
        TopicCount(topic=lang.name, count=int(round(lang.percentage)))
        for lang in (stats_response.topLanguages or [])
    ]
    commits = stats_response.totalCommits or 0
    by_difficulty: Dict[str, int] = {"commits": commits}
    if pr_count:
        by_difficulty["prs"] = pr_count
    if issue_count:
        by_difficulty["issues"] = issue_count
    if review_count:
        by_difficulty["reviews"] = review_count
    return UnifiedStats(
        totalSolved=commits,
        byDifficulty=by_difficulty,
        topicAnalysis=topics,
    )


def _iter_days(contribution_data: Optional[Dict[str, Any]]):
    """Yield ``(date_str, count)`` across every year in the contribution data."""
    if not contribution_data:
        return
    for year_payload in contribution_data.values():
        try:
            weeks = (
                year_payload["data"]["user"]["contributionsCollection"]
                ["contributionCalendar"]["weeks"]
            )
        except (KeyError, TypeError):
            continue
        for week in weeks:
            for day in week.get("contributionDays", []):
                yield day.get("date"), int(day.get("contributionCount", 0) or 0)


def _level(count: int, max_daily: int) -> int:
    if count <= 0 or max_daily <= 0:
        return 0
    return min(4, max(1, ceil((count / max_daily) * 4)))


def heatmap_from(
    contribution_data: Optional[Dict[str, Any]],
    longest_streak: int = 0,
    current_streak: int = 0,
) -> UnifiedHeatmap:
    date_counts: dict[date, int] = {}
    for date_str, count in _iter_days(contribution_data):
        if not date_str:
            continue
        try:
            day = date.fromisoformat(date_str)
        except ValueError:
            continue
        date_counts[day] = date_counts.get(day, 0) + count

    active = {d: c for d, c in date_counts.items() if c > 0}
    if not active:
        return UnifiedHeatmap(longestStreak=longest_streak, currentStreak=current_streak)

    active_dates = sorted(active)
    max_daily = max(active.values())

    yearly: dict[int, dict] = {}
    for day, count in active.items():
        bucket = yearly.setdefault(day.year, {"totalSubmissions": 0, "activeDays": 0})
        bucket["totalSubmissions"] += count
        bucket["activeDays"] += 1

    return UnifiedHeatmap(
        totalSubmissions=sum(active.values()),
        totalActiveDays=len(active_dates),
        currentStreak=current_streak,
        longestStreak=longest_streak,
        maxDailySubmissions=max_daily,
        firstActiveDate=active_dates[0].isoformat(),
        lastActiveDate=active_dates[-1].isoformat(),
        dailyContributions=[
            HeatDay(date=d.isoformat(), count=active[d], level=_level(active[d], max_daily))
            for d in active_dates
        ],
        yearlyContributions=[
            YearContribution(year=y, totalSubmissions=v["totalSubmissions"], activeDays=v["activeDays"])
            for y, v in sorted(yearly.items())
        ],
    )


def summary_from(card: UnifiedCard) -> UnifiedSummary:
    return UnifiedSummary(
        totalSolved=card.stats.totalSolved,
        totalActiveDays=card.heatmap.totalActiveDays,
        totalContests=0,
        badgesCount=0,
    )


async def build_card(username: str, analytics_service) -> UnifiedCard:
    import asyncio
    user, stats, pr_count, issue_count, review_count = await asyncio.gather(
        analytics_service.get_user_profile(username),
        analytics_service.get_user_stats(username, []),
        analytics_service.get_user_pr_count(username),
        analytics_service.get_user_issue_count(username),
        analytics_service.get_user_review_count(username),
    )
    return UnifiedCard(
        username=username,
        profile=profile_from(user, username),
        stats=stats_from(stats, pr_count, issue_count, review_count),
        contests=UnifiedContests(),
        rating=UnifiedRating(),
        heatmap=heatmap_from(stats.contributions, stats.longestStreak, stats.currentStreak),
        badges=UnifiedBadges(),
    )
