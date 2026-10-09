"""Tests for dashboard_data.py — only needs pandas, no Streamlit required.

Run with: PYTHONPATH=. python -m tests.test_dashboard_data -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dashboard_data import apply_filters, list_result_files, load_jobs

SAMPLE_JOBS = [
    {
        "id": "MCF-0001",
        "title": "Data Analyst, Marketing",
        "company": "Acme Pte Ltd",
        "location": "Central",
        "salary_min": 3500,
        "salary_max": 4500,
        "salary_type": "Monthly",
        "match_score": 4.0,
        "posted_date": "2026-09-10",
        "url": "https://example.com/1",
    },
    {
        "id": "MCF-0002",
        "title": "Business Analyst",
        "company": "BigCorp",
        "location": "East",
        "salary_min": None,
        "salary_max": None,
        "salary_type": "",
        "match_score": 2.0,
        "posted_date": "2026-09-09",
        "url": "https://example.com/2",
    },
]


class DashboardDataTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "jobs_20260911_000000.json"
        self.path.write_text(json.dumps(SAMPLE_JOBS))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_list_result_files_finds_json(self):
        files = list_result_files(Path(self.tmpdir.name))
        self.assertEqual(files, [self.path])

    def test_load_jobs_formats_salary(self):
        df = load_jobs(self.path)
        self.assertEqual(len(df), 2)
        row = df[df["id"] == "MCF-0001"].iloc[0]
        self.assertEqual(row["salary"], "$3,500-$4,500 Monthly")
        row2 = df[df["id"] == "MCF-0002"].iloc[0]
        self.assertEqual(row2["salary"], "")

    def test_apply_filters_min_score(self):
        df = load_jobs(self.path)
        filtered = apply_filters(df, min_score=3.0)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["id"], "MCF-0001")

    def test_apply_filters_search(self):
        df = load_jobs(self.path)
        filtered = apply_filters(df, search="business")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["id"], "MCF-0002")

    def test_apply_filters_location(self):
        df = load_jobs(self.path)
        filtered = apply_filters(df, locations=["East"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered.iloc[0]["location"], "East")


if __name__ == "__main__":
    unittest.main()
