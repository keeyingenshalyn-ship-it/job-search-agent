"""Data-loading and filtering logic for the dashboard, kept separate from
the Streamlit UI code in dashboard.py.

Why separate: this module only depends on pandas, so it can be unit
tested without Streamlit installed (useful in environments where
Streamlit can't be installed) and reused later — e.g. if the dashboard
moves to a different UI framework.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.cv_match import score_jobs

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def list_result_files(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    """Most recent run first."""
    return sorted(Path(output_dir).glob("jobs_*.json"), reverse=True)


def load_jobs(path: Path) -> pd.DataFrame:
    data = json.loads(Path(path).read_text())
    df = pd.DataFrame(data)
    if df.empty:
        return df

    def _fmt_salary(row) -> str:
        # NaN (pandas' stand-in for a missing salary_min/max) is truthy in
        # Python, so a plain `if lo` would treat a missing salary as present
        # — pd.notna() is required here, not just a truthiness check.
        lo, hi = row.get("salary_min"), row.get("salary_max")
        has_lo, has_hi = pd.notna(lo), pd.notna(hi)
        if has_lo and has_hi:
            return f"${lo:,.0f}-${hi:,.0f} {row.get('salary_type', '')}".strip()
        if has_lo:
            return f"${lo:,.0f}+ {row.get('salary_type', '')}".strip()
        return ""

    df["salary"] = df.apply(_fmt_salary, axis=1)

    # Older output files (from before position_levels was tracked) won't have
    # this column at all; newer ones may still have missing/NaN entries for
    # individual rows. Normalize both cases to an empty list so downstream
    # code (level filter, display) never has to special-case it.
    if "position_levels" not in df.columns:
        df["position_levels"] = [[] for _ in range(len(df))]
    else:
        df["position_levels"] = df["position_levels"].apply(
            lambda v: v if isinstance(v, list) else []
        )
    df["level"] = df["position_levels"].apply(lambda levels: ", ".join(levels))

    return df


def add_cv_scores(df: pd.DataFrame, cv_text: str) -> pd.DataFrame:
    """Add cv_fit (0-100), matched/missing skill columns for the given CV."""
    df = df.copy()
    if df.empty:
        return df
    if "skills" not in df.columns:
        df["skills"] = [[] for _ in range(len(df))]
    df["skills"] = df["skills"].apply(lambda v: v if isinstance(v, list) else [])
    records = df[["title", "skills"]].to_dict("records")
    if "description" in df.columns:
        for rec, desc in zip(records, df["description"].fillna("")):
            rec["description"] = desc
    scores = score_jobs(records, cv_text)
    df["cv_fit"] = [s["cv_fit"] for s in scores]
    df["matched_skills"] = [", ".join(s["matched_skills"]) for s in scores]
    df["missing_skills"] = [", ".join(s["missing_skills"]) for s in scores]
    df["skills_matched"] = [
        f"{len(s['matched_skills'])}/{len(s['matched_skills']) + len(s['missing_skills'])}"
        for s in scores
    ]
    return df


def run_label(path: Path) -> str:
    """'jobs_20260912_000432__Broker-CV' -> '2026-09-12 00:04 · Broker-CV'."""
    stem = Path(path).stem.replace("jobs_", "", 1)
    stamp, _, label = stem.partition("__")
    try:
        from datetime import datetime

        nice = datetime.strptime(stamp, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M")
    except ValueError:
        nice = stamp
    return f"{nice} · {label}" if label else nice


def all_levels(df: pd.DataFrame) -> list[str]:
    seen: set[str] = set()
    for levels in df.get("position_levels", []):
        seen.update(levels)
    return sorted(seen)


def apply_filters(
    df: pd.DataFrame,
    min_score: float = 0.0,
    search: str = "",
    locations: list[str] | None = None,
    levels: list[str] | None = None,
    min_cv_fit: float = 0.0,
) -> pd.DataFrame:
    if df.empty:
        return df

    filtered = df[df["match_score"] >= min_score]

    has_cv = "cv_fit" in filtered.columns
    if has_cv and min_cv_fit:
        filtered = filtered[filtered["cv_fit"] >= min_cv_fit]

    if search:
        mask = filtered["title"].str.contains(search, case=False, na=False) | filtered[
            "company"
        ].str.contains(search, case=False, na=False)
        filtered = filtered[mask]

    if locations:
        filtered = filtered[filtered["location"].isin(locations)]

    if levels:
        wanted = set(levels)
        filtered = filtered[
            filtered["position_levels"].apply(lambda pl: bool(wanted.intersection(pl)))
        ]

    # With a CV selected, rank by how well each job fits it.
    sort_col = "cv_fit" if has_cv else "match_score"
    return filtered.sort_values(sort_col, ascending=False)
