"""Shared language filtering and percentage arithmetic."""

from typing import Dict, List, Optional

from services.language_map import filter_languages


DEFAULT_EXCLUDED_LANGUAGES = ["Markdown", "JSON", "YAML", "XML"]


def language_distribution(
    totals: Dict[str, int], excluded: Optional[List[str]] = None
) -> list[tuple[str, int, float]]:
    """Round once to hundredths, with deterministic ties and a 100% total."""
    filtered = {
        name: value for name, value in filter_languages(totals, excluded).items()
        if value > 0
    }
    ordered = sorted(filtered, key=lambda name: (-filtered[name], name.casefold(), name))
    total = sum(filtered.values())
    if not total:
        return []
    units = {name: filtered[name] * 10000 // total for name in ordered}
    remainder_order = sorted(
        ordered, key=lambda name: (-(filtered[name] * 10000 % total), name.casefold(), name)
    )
    for name in remainder_order[:10000 - sum(units.values())]:
        units[name] += 1
    return [(name, filtered[name], units[name] / 100) for name in ordered]
