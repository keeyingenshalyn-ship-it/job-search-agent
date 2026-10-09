"""Cheap keyword filter/scorer — runs before anything smarter (e.g. an LLM
score) touches a job, since it's free and instant and kills most noise.

A job is kept if it matches at least one include keyword and none of the
exclude keywords. match_score is just the count of include keywords that
hit (title hits count double) — good enough to sort a shortlist; replace
or augment with an LLM-based score later without changing this contract.
"""
from __future__ import annotations

from collections.abc import Iterable

from src.schema import Job


def matches(job: Job, config: dict) -> bool:
    include = [k.lower() for k in config.get("include_keywords", [])]
    exclude = [k.lower() for k in config.get("exclude_keywords", [])]
    locations = [l.lower() for l in config.get("locations", [])]
    seniority_levels = [s.lower() for s in config.get("seniority_levels", [])]

    haystack = f"{job.title} {job.description}".lower()

    # Title-keyword exclude always applies — it's the only signal available
    # when MyCareersFuture doesn't return a position_levels tag for a job.
    if exclude and any(term in job.title.lower() for term in exclude):
        return False

    if include and not any(term in haystack for term in include):
        return False

    if locations and not any(loc in job.location.lower() for loc in locations):
        return False

    # Prefer MyCareersFuture's own seniority tag when the job has one — it's
    # authoritative, unlike guessing from title keywords. If a job has no
    # position_levels at all (the field can come back empty), don't drop it
    # on that basis alone; the exclude_keywords check above is the backstop.
    if seniority_levels and job.position_levels:
        job_levels = [p.lower() for p in job.position_levels]
        if not any(level in job_levels for level in seniority_levels):
            return False

    return True


def score(job: Job, config: dict) -> tuple[float, list[str]]:
    include = [k.lower() for k in config.get("include_keywords", [])]
    title = job.title.lower()
    desc = job.description.lower()

    total = 0.0
    reasons = []
    for term in include:
        in_title = term in title
        in_desc = term in desc
        if in_title:
            total += 2
            reasons.append(f'"{term}" in title')
        elif in_desc:
            total += 1
            reasons.append(f'"{term}" in description')

    return total, reasons


def filter_and_score(jobs: Iterable[Job], config: dict) -> list[Job]:
    kept = []
    for job in jobs:
        if not matches(job, config):
            continue
        job.match_score, job.match_reasons = score(job, config)
        kept.append(job)

    kept.sort(key=lambda j: j.match_score, reverse=True)
    return kept
