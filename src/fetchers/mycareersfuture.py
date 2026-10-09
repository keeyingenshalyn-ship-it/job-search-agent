"""Fetcher for MyCareersFuture (Singapore's government job portal).

MCF doesn't publish an official third-party API, but the search endpoint
its own website calls (api.mycareersfuture.gov.sg/v2/search) is a plain,
public, unauthenticated JSON endpoint with no login or paywall behind it —
this is the same approach used by existing open-source MCF tools (see
https://github.com/gabrielchua/mcf-jobs). Since it's undocumented, the
response shape could change without notice; this fetcher accesses fields
defensively (.get() with defaults) so a shape change degrades gracefully
(missing fields) rather than crashing the whole run.

Be a good citizen: this fetcher paginates with a short delay between
requests rather than hammering the endpoint.
"""
from __future__ import annotations

import time
from collections.abc import Iterator

import requests

from src.fetchers.base import BaseFetcher
from src.schema import Job

SEARCH_URL = "https://api.mycareersfuture.gov.sg/v2/search"
PAGE_SIZE = 20
REQUEST_DELAY_SECONDS = 1.0


class MyCareersFutureFetcher(BaseFetcher):
    source_name = "mycareersfuture"

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def search(self, term: str, max_pages: int = 3) -> Iterator[Job]:
        for page in range(max_pages):
            payload = self._fetch_page(term, page)
            results = payload.get("results", [])
            if not results:
                return  # no more results, stop paginating

            for raw in results:
                yield self._normalize(raw)

            total = payload.get("total", 0)
            if (page + 1) * PAGE_SIZE >= total:
                return

            time.sleep(REQUEST_DELAY_SECONDS)

    def _fetch_page(self, term: str, page: int) -> dict:
        response = self.session.post(
            SEARCH_URL,
            params={"limit": PAGE_SIZE, "page": page},
            json={"search": term},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                # Identify ourselves plainly rather than spoofing a browser.
                "User-Agent": "job-search-agent/0.1 (personal project)",
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _normalize(raw: dict) -> Job:
        metadata = raw.get("metadata", {}) or {}
        company = raw.get("postedCompany", {}) or {}
        salary = raw.get("salary", {}) or {}
        address = raw.get("address", {}) or {}
        districts = address.get("districts") or []
        region = districts[0].get("region", "") if districts else ""

        job_id = metadata.get("jobPostId") or raw.get("uuid") or ""

        return Job(
            id=job_id,
            source="mycareersfuture",
            title=raw.get("title", ""),
            company=company.get("name", ""),
            url=metadata.get("jobDetailsUrl", ""),
            description=raw.get("description", "") or "",
            location=address.get("district") or region or "",
            salary_min=salary.get("minimum"),
            salary_max=salary.get("maximum"),
            salary_type=salary.get("type", {}).get("salaryType", "")
            if isinstance(salary.get("type"), dict)
            else str(salary.get("type", "")),
            employment_types=[
                e.get("employmentType", "") for e in raw.get("employmentTypes", []) or []
            ],
            categories=[c.get("category", "") for c in raw.get("categories", []) or []],
            skills=[s.get("skill", "") for s in raw.get("skills", []) or []],
            posted_date=metadata.get("newPostingDate", "") or metadata.get("updatedAt", ""),
            position_levels=[
                p.get("position", "") for p in raw.get("positionLevels", []) or []
            ],
            min_years_experience=raw.get("minimumYearsExperience"),
        )
