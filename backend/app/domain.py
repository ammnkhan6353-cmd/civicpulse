"""Domain vocabulary shared by every layer: the three enums from the spec."""

from enum import StrEnum


class Category(StrEnum):
    water = "water"
    electricity = "electricity"
    sanitation = "sanitation"
    roads = "roads"
    streetlights = "streetlights"
    other = "other"


class Priority(StrEnum):
    high = "high"
    normal = "normal"
    low = "low"


class Status(StrEnum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


# Values allowed in complaints.triaged_by. "simulated" is our addition so that
# rows written by the CI fake are honestly labelled instead of pretending to be rules.
TRIAGED_BY_VALUES = ("llm:groq", "llm:ollama", "rules", "rules:fallback", "simulated")
