"""Common job posting schema.

Every source fetcher (MyCareersFuture today; company career pages and
aggregator APIs later) normalizes its raw results into this shape, so the
rest of the pipeline (dedupe, filter, scoring, storage) never has to know
which source a job came from.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Job:
    # Stable identifier for de-duplication. Prefer a source-provided ID;
    # fall back to a hash of (source, url) if the source has none.
    id: str
    source: str  # e.g. "mycareersfuture"
    title: str
    company: str
    url: str

    description: str = ""
    location: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: str = ""  # e.g. "Monthly", "Annual"
    employment_types: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    posted_date: str = ""  # ISO date string when available

    # MyCareersFuture's own seniority classification, e.g. "Fresh/entry level",
    # "Junior Executive", "Senior Executive", "Manager" — authoritative,
    # unlike guessing seniority from title keywords.
    position_levels: list[str] = field(default_factory=list)
    min_years_experience: Optional[int] = None

    # Filled in later by the filter/scoring step, not by fetchers.
    match_score: float = 0.0
    match_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def salary_str(self) -> str:
        if self.salary_min and self.salary_max:
            return f"${self.salary_min:,}-${self.salary_max:,} {self.salary_type}".strip()
        if self.salary_min:
            return f"${self.salary_min:,}+ {self.salary_type}".strip()
        return ""
