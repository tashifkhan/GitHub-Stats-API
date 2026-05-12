"""Builds the canonical cross-platform card for GitHub (``development`` category).

Mapping: total commits -> ``stats.totalSolved``; top languages -> topic analysis;
the contribution calendar -> heatmap; scraped profile achievements -> badges.
GitHub has no contests / rating, so those sections stay empty. See ../CANONICAL_SCHEMA.md.
"""

from datetime import date, timedelta
from math import ceil
from typing import Any, Dict, List, Optional

from models.canonical.badges import BadgeItem, Badges
from models.canonical.card import Card
from models.canonical.contests import Contests
from models.canonical.heatmap import HeatDay, Heatmap, YearContribution
from models.canonical.profile import Profile, Social
from models.canonical.rating import Rating
from models.canonical.stats import TopicCount, Stats
from models.canonical.summary import Summary
from services.heatmap_window import window_heatmap


def profile_from(
    user: Dict[str, Any],
    username: str,
    social_accounts: Optional[List[Dict[str, Any]]] = None,
) -> Profile:
    user = user or {}
    blog = (user.get("blog") or "").strip()
    twitter = user.get("twitter_username")
    linkedin = None
    for account in social_accounts or []:
        if (account.get("provider") or "").lower() == "linkedin":
            linkedin = account.get("url")
            break
    return Profile(
        displayName=user.get("name") or user.get("login") or username,
        username=user.get("login") or username,
        avatar=user.get("avatar_url"),
        country=user.get("location"),
        company=user.get("company"),
        bio=user.get("bio"),
        websites=[blog] if blog else [],
        social=Social(
            github=user.get("html_url") or f"https://github.com/{username}",
            twitter=f"https://twitter.com/{twitter}" if twitter else None,
            linkedin=linkedin,
        ),
        verified=False,
    )


def badges_from(achievements: Optional[List[Dict[str, Any]]]) -> Badges:
    items = [
        BadgeItem(
            id=a.get("id"),
            name=a.get("name"),
            icon=a.get("icon"),
            level=a.get("level"),
        )
        for a in (achievements or [])
    ]
    return Badges(count=len(items), active=items[0] if items else None, list=items)


def stats_from(
    stats_response,
    pr_count: int = 0,
    issue_count: int = 0,
    review_count: int = 0,
) -> Stats:
    if stats_response is None:
        return Stats()
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
    return Stats(
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
) -> Heatmap:
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
        return Heatmap(longestStreak=longest_streak, currentStreak=current_streak)

    active_dates = sorted(active)
    max_daily = max(active.values())

    yearly: dict[int, dict] = {}
    for day, count in active.items():
        bucket = yearly.setdefault(day.year, {"totalSubmissions": 0, "activeDays": 0})
        bucket["totalSubmissions"] += count
        bucket["activeDays"] += 1

    return Heatmap(
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


def summary_from(card: Card) -> Summary:
    return Summary(
        totalSolved=card.stats.totalSolved,
        totalActiveDays=card.heatmap.totalActiveDays,
    )


async def build_card(username: str, analytics_service) -> Card:
    import asyncio
    user, social_accounts, stats, pr_count, issue_count, review_count, achievements = await asyncio.gather(
        analytics_service.get_user_profile(username),
        analytics_service.get_user_social_accounts(username),
        analytics_service.get_user_stats(username, []),
        analytics_service.get_user_pr_count(username),
        analytics_service.get_user_issue_count(username),
        analytics_service.get_user_review_count(username),
        analytics_service.get_user_achievements(username),
    )
    contributions = stats.contributions or {}
    available_years = sorted((int(y) for y in contributions.keys()), reverse=True) if isinstance(contributions, dict) else None
    return Card(
        username=username,
        profile=profile_from(user, username, social_accounts),
        stats=stats_from(stats, pr_count, issue_count, review_count),
        contests=Contests(),
        rating=Rating(),
        heatmap=window_heatmap(
            heatmap_from(stats.contributions, stats.longestStreak, stats.currentStreak),
            "all",
            None,
            available_years=available_years or None,
        ),
        badges=badges_from(achievements),
    )
