"""Tests for CV scoring and CV storage — no Streamlit or network needed.

Run with: PYTHONPATH=. python -m tests.test_cv_match -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src import cv_store
from src.cv_match import cv_has_skill, cv_skill_summary, extract_text, score_jobs, _normalize
from src.dashboard_data import add_cv_scores, apply_filters, run_label

ANALYST_CV = """
Hen Kee — MSc Business Analytics, UCL
Data analytics intern: built predictive models in Python (pandas, scikit-learn)
and an interactive Tableau dashboard. Wrote SQL queries. Advanced Excel.
Finance admin: updated AR ledgers, reconciled accounts. Fluent Mandarin.
"""

JOBS = [
    {"title": "Data Analyst", "skills": ["Python", "SQL", "Tableau", "Excel"], "description": ""},
    {"title": "Trainee Insurance Broker", "skills": ["Insurance", "Sales", "Negotiation"], "description": ""},
    {"title": "Business Analyst", "skills": ["Power BI", "Stakeholder Management", "SQL"], "description": ""},
    {"title": "Something untagged", "skills": [], "description": "analytics role using python"},
]


class SkillMatching(unittest.TestCase):
    def test_word_boundaries(self):
        cv = _normalize("Excellent communicator")
        self.assertFalse(cv_has_skill(cv, "Excel"))
        self.assertTrue(cv_has_skill(_normalize("Advanced Excel"), "Excel"))

    def test_aliases(self):
        self.assertTrue(cv_has_skill(_normalize("Built PowerBI reports"), "Power BI"))
        self.assertTrue(cv_has_skill(_normalize("wrote PostgreSQL queries"), "SQL"))

    def test_single_letter_skill_needs_alias(self):
        self.assertFalse(cv_has_skill(_normalize("R&D team, Mr Tan"), "R"))
        self.assertTrue(cv_has_skill(_normalize("Python/R for analysis"), "R"))


class Scoring(unittest.TestCase):
    def test_analyst_cv_ranks_analyst_job_above_broker(self):
        results = score_jobs(JOBS, ANALYST_CV)
        self.assertEqual(len(results), len(JOBS))
        self.assertGreater(results[0]["cv_fit"], results[1]["cv_fit"])
        self.assertEqual(results[0]["matched_skills"], ["Python", "SQL", "Tableau", "Excel"])
        self.assertEqual(results[1]["matched_skills"], [])
        for r in results:
            self.assertGreaterEqual(r["cv_fit"], 0)
            self.assertLessEqual(r["cv_fit"], 100)

    def test_different_cv_changes_ranking(self):
        broker_cv = "Insurance sales executive. Strong negotiation and client sales record."
        results = score_jobs(JOBS, broker_cv)
        self.assertGreater(results[1]["cv_fit"], results[0]["cv_fit"])

    def test_summary(self):
        have, gaps = cv_skill_summary(JOBS, ANALYST_CV)
        self.assertIn("SQL", have)
        self.assertIn("Insurance", gaps)


class DashboardIntegration(unittest.TestCase):
    def test_add_cv_scores_and_sort(self):
        df = pd.DataFrame([{**j, "company": "X", "location": "", "match_score": 1.0} for j in JOBS])
        scored = add_cv_scores(df, ANALYST_CV)
        self.assertIn("cv_fit", scored.columns)
        out = apply_filters(scored)
        self.assertEqual(out.iloc[0]["title"], "Data Analyst")
        self.assertEqual(scored.iloc[0]["skills_matched"], "4/4")
        high = apply_filters(scored, min_cv_fit=90)
        self.assertTrue((high["cv_fit"] >= 90).all())

    def test_run_label(self):
        self.assertEqual(run_label(Path("jobs_20260912_000432.json")), "2026-09-12 00:04")
        self.assertEqual(run_label(Path("jobs_20260912_000432__Broker-CV.json")), "2026-09-12 00:04 · Broker-CV")


class Store(unittest.TestCase):
    def test_upload_active_terms_delete(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p = cv_store.save_upload("My CV (broker).txt", b"insurance sales", d)
            self.assertEqual(cv_store.list_cvs(d), [p])
            self.assertIn("insurance", extract_text(p))
            cv_store.set_active(p.name, d)
            self.assertEqual(cv_store.get_active(d), p)
            cv_store.set_search_terms(p.name, ["trainee broker", " "], d)
            self.assertEqual(cv_store.get_search_terms(p.name, d), ["trainee broker"])
            cv_store.delete_cv(p.name, d)
            self.assertIsNone(cv_store.get_active(d))
            self.assertEqual(cv_store.list_cvs(d), [])

    def test_rejects_other_types(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                cv_store.save_upload("photo.png", b"x", Path(d))


if __name__ == "__main__":
    unittest.main()
