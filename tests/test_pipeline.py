"""Smoke test for the fetch -> normalize -> filter -> write pipeline,
using a mocked MyCareersFuture API response (no real network call).

Run with: python -m tests.test_pipeline
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fetchers.mycareersfuture import MyCareersFutureFetcher
from src.filters.keyword_filter import filter_and_score

FAKE_PAGE = {
    "total": 2,
    "results": [
        {
            "uuid": "job-1",
            "title": "Data Analyst, Marketing",
            "description": "Own dashboards and reporting for the marketing team.",
            "postedCompany": {"name": "Acme Pte Ltd"},
            "metadata": {
                "jobPostId": "MCF-0001",
                "jobDetailsUrl": "https://www.mycareersfuture.gov.sg/job/MCF-0001",
                "newPostingDate": "2026-09-10",
            },
            "salary": {"minimum": 3500, "maximum": 4500, "type": {"salaryType": "Monthly"}},
            "address": {"district": "Central", "districts": [{"region": "Central"}]},
            "employmentTypes": [{"employmentType": "Full Time"}],
            "categories": [{"category": "Information Technology"}],
            "skills": [{"skill": "SQL"}, {"skill": "Tableau"}],
        },
        {
            "uuid": "job-2",
            "title": "Senior Data Analytics Manager",
            "description": "Lead a team of analysts.",
            "postedCompany": {"name": "BigCorp"},
            "metadata": {
                "jobPostId": "MCF-0002",
                "jobDetailsUrl": "https://www.mycareersfuture.gov.sg/job/MCF-0002",
                "newPostingDate": "2026-09-09",
            },
            "salary": {"minimum": 8000, "maximum": 10000, "type": {"salaryType": "Monthly"}},
            "address": {"district": "East", "districts": [{"region": "East"}]},
            "employmentTypes": [{"employmentType": "Full Time"}],
            "categories": [{"category": "Information Technology"}],
            "skills": [{"skill": "Leadership"}],
        },
    ],
}

CONFIG = {
    "include_keywords": ["data analyst", "analytics"],
    "exclude_keywords": ["senior", "manager"],
    "locations": [],
}


class PipelineSmokeTest(unittest.TestCase):
    def test_fetch_normalize_filter(self):
        fake_response = MagicMock()
        fake_response.json.return_value = FAKE_PAGE
        fake_response.raise_for_status.return_value = None

        session = MagicMock()
        session.post.return_value = fake_response

        fetcher = MyCareersFutureFetcher(session=session)
        jobs = list(fetcher.search("data analyst", max_pages=3))

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].title, "Data Analyst, Marketing")
        self.assertEqual(jobs[0].company, "Acme Pte Ltd")
        self.assertEqual(jobs[0].salary_min, 3500)
        self.assertEqual(jobs[0].skills, ["SQL", "Tableau"])
        # only one page's worth of results and total==len(results), so it should stop after page 0
        self.assertEqual(session.post.call_count, 1)

        ranked = filter_and_score(jobs, CONFIG)
        # the "Senior ... Manager" posting should be excluded
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].id, "MCF-0001")
        self.assertGreater(ranked[0].match_score, 0)


if __name__ == "__main__":
    unittest.main()
