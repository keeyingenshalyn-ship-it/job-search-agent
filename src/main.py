"""Entry point: run every configured search term through MyCareersFuture,
merge + de-duplicate the results, filter/score them, and write out a
ranked shortlist (CSV + JSON) plus a console summary.

Usage:
    python -m src.main
    python -m src.main --config config.yaml
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

from src.fetchers.mycareersfuture import MyCareersFutureFetcher
from src.filters.keyword_filter import filter_and_score
from src.schema import Job


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def fetch_all(config: dict) -> list[Job]:
    fetcher = MyCareersFutureFetcher()
    seen: dict[str, Job] = {}

    for term in config.get("search_terms", []):
        print(f"Searching MyCareersFuture for: {term!r}", file=sys.stderr)
        try:
            for job in fetcher.search(term, max_pages=config.get("max_pages_per_term", 3)):
                key = job.id or job.url
                if key and key not in seen:
                    seen[key] = job
        except Exception as e:  # noqa: BLE001 - one bad term shouldn't kill the run
            print(f"  ! search failed for {term!r}: {e}", file=sys.stderr)

    return list(seen.values())


def write_outputs(jobs: list[Job], output_dir: str, label: str = "") -> tuple[Path, Path]:
    """label (optional) is appended to the file name, e.g. which CV's search
    terms were used, so runs are easy to tell apart in the dashboard."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if label:
        safe = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-")[:40]
        if safe:
            stamp = f"{stamp}__{safe}"

    json_path = out / f"jobs_{stamp}.json"
    csv_path = out / f"jobs_{stamp}.csv"

    json_path.write_text(json.dumps([j.to_dict() for j in jobs], indent=2))

    if jobs:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(jobs[0].to_dict().keys()))
            writer.writeheader()
            for j in jobs:
                writer.writerow(j.to_dict())

    return json_path, csv_path


def print_summary(jobs: list[Job], limit: int = 20) -> None:
    if not jobs:
        print("No matching jobs found. Try loosening include_keywords/exclude_keywords in config.yaml.")
        return

    print(f"\n{len(jobs)} matching jobs, ranked by match score:\n")
    for j in jobs[:limit]:
        salary = f" | {j.salary_str()}" if j.salary_str() else ""
        print(f"[{j.match_score:>4.1f}] {j.title} — {j.company} ({j.location}){salary}")
        print(f"        {j.url}")
    if len(jobs) > limit:
        print(f"\n...and {len(jobs) - limit} more in the output file.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and rank job postings from MyCareersFuture.")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    all_jobs = fetch_all(config)
    print(f"\nFetched {len(all_jobs)} unique postings before filtering.", file=sys.stderr)

    ranked = filter_and_score(all_jobs, config)
    json_path, csv_path = write_outputs(ranked, config.get("output_dir", "output"))

    print_summary(ranked)
    print(f"\nSaved: {json_path}")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
