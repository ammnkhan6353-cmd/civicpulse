"""RuleBasedTriage - deterministic keyword fallback. Always available, never raises."""

import re

from app.domain import Category, Priority
from app.providers.triage.base import TriageResult

# Order matters: the first category with the most keyword hits wins; ties go to
# the earlier entry. Keywords include common Urdu/Roman-Urdu words citizens use.
CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.water: (
        "water", "pipe", "pipeline", "leak", "burst", "water main", "tap", "flood", "flooding",
        "paani", "pani", "tanker", "supply", "pressure", "valve",
    ),
    Category.electricity: (
        "electricity", "power", "outage", "load shedding", "loadshedding", "transformer",
        "wire", "wires", "sparking", "spark", "voltage", "bijli", "meter", "shock", "cable",
    ),
    Category.sanitation: (
        "garbage", "trash", "waste", "sewage", "sewer", "gutter", "drain", "nala",
        "kachra", "smell", "stink", "overflow", "overflowing", "dump", "mosquito",
    ),
    Category.roads: (
        "road", "pothole", "potholes", "broken street", "asphalt", "speed breaker",
        "footpath", "sarak", "sadak", "crack", "construction", "bridge", "traffic",
    ),
    Category.streetlights: (
        "streetlight", "street light", "street lights", "streetlights", "lamp", "pole",
        "light not working", "dark", "andhera", "bulb",
    ),
}

HIGH_PRIORITY_WORDS = (
    "flood", "flooding", "sparking", "spark", "fire", "shock", "electrocut", "urgent",
    "emergency", "danger", "dangerous", "accident", "children", "bachay", "bachon",
    "hospital", "injured", "collapsed", "burst", "since fajr", "since two days",
    "entering", "open manhole", "manhole",
)
LOW_PRIORITY_WORDS = ("minor", "small", "cosmetic", "suggestion", "request", "whenever")


def _count(text: str, words: tuple[str, ...]) -> int:
    return sum(1 for word in words if re.search(rf"\b{re.escape(word)}", text))


def _summarise(text: str, category: Category) -> str:
    first_line = " ".join(text.split())
    summary = f"{category.value.capitalize()} issue: {first_line}"
    return summary if len(summary) <= 140 else summary[:137].rstrip() + "..."


class RuleBasedTriage:
    name = "rules"

    def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()
        scores = {category: _count(lowered, words) for category, words in CATEGORY_KEYWORDS.items()}
        best_category, best_score = max(scores.items(), key=lambda item: item[1])
        category = best_category if best_score > 0 else Category.other

        if _count(lowered, HIGH_PRIORITY_WORDS) > 0:
            priority = Priority.high
        elif _count(lowered, LOW_PRIORITY_WORDS) > 0:
            priority = Priority.low
        else:
            priority = Priority.normal

        confidence = 0.3 if category is Category.other else min(0.5 + 0.1 * best_score, 0.8)
        return TriageResult(
            category=category,
            priority=priority,
            summary=_summarise(text, category),
            confidence=round(confidence, 2),
        )
