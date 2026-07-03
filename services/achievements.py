import re
from typing import Dict, List

import httpx
from bs4 import BeautifulSoup

BASE_GITHUB_URL = "https://github.com"
ACHIEVEMENT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


async def get_user_achievements(username: str) -> List[Dict]:
    """Scrape the achievement badges (Pull Shark, YOLO, etc.) off a user's profile page.

    GitHub doesn't expose achievements through any REST/GraphQL API, so this reads
    the same public profile HTML the "Achievements" section on github.com renders.
    Returns [] if the page can't be fetched or has no achievements section.
    """
    url = f"{BASE_GITHUB_URL}/{username}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers=ACHIEVEMENT_HEADERS)
    except httpx.HTTPError:
        return []

    if resp.status_code != 200:
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return []

    seen = set()
    achievements: List[Dict] = []
    for img in soup.find_all("img", class_="achievement-badge-sidebar"):
        anchor = img.find_parent("a")
        href = anchor.get("href") if anchor else None
        match = re.search(r"achievement=([\w-]+)", href or "")
        slug = match.group(1) if match else None
        if not slug or slug in seen:
            continue
        seen.add(slug)

        alt = (img.get("alt") or "").strip()
        name = re.sub(r"^Achievement:\s*", "", alt) or slug.replace("-", " ").title()

        level = None
        if anchor:
            tier_label = anchor.find(
                "span", class_=lambda c: bool(c and "achievement-tier-label" in c)
            )
            if tier_label:
                level = tier_label.get_text(strip=True) or None

        achievements.append(
            {
                "id": slug,
                "name": name,
                "icon": img.get("src"),
                "level": level,
            }
        )

    return achievements
