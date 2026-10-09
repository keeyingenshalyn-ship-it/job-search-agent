# Job Search Agent — v0 (MyCareersFuture discovery slice)

This is the first working slice of the job discovery agent: it searches
MyCareersFuture for the roles you're after, filters out noise with cheap
keyword rules, ranks what's left, and saves a shortlist. No tracker UI,
no other sources, no LLM scoring yet — on purpose, so you have something
real running before adding the next layer.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Edit `config.yaml` — no code changes needed for day-to-day tuning:
- `search_terms`: what to query MyCareersFuture for
- `include_keywords` / `exclude_keywords`: the cheap filter (title + description)
- `locations`: optional district filter
- `max_pages_per_term`: how deep to paginate per term (20 results/page)

## Run

```bash
python -m src.main
```

This prints a ranked shortlist to the console and writes both a `.json`
and a `.csv` into `output/`, timestamped, so nothing overwrites a
previous run.

## Browse results in a web UI instead of the terminal

```bash
streamlit run src/dashboard.py
```

Opens a local page (usually http://localhost:8501) with a sortable table,
a minimum-match-score slider, a text search, and a location filter. It
reads whatever's in `output/`, so run `python -m src.main` at least once
first. Pick which run to view from the dropdown in the sidebar if you
have more than one.

## Match jobs against your CV (or several CVs)

In the dashboard sidebar, under **Your CV**:

1. **Add a CV** — PDF, Word (.docx) or .txt. It's saved in `cvs/`. Add as
   many as you like (e.g. an analyst CV and a broker CV).
2. **Score jobs against** — pick which CV is active. Jobs are then ranked by
   **CV fit** (0–100): 70% how many of the job's listed MyCareersFuture skills
   your CV mentions, 30% overall wording similarity. The table shows the
   skills matched and the ones your CV doesn't mention, and the top of the page
   lists the most-requested skills you have / don't mention across the run.
   Scoring happens on the fly, so it works on old runs too.
3. **Search terms for this CV** (optional) — e.g. `trainee broker`. While that
   CV is active, “Fetch new jobs now” searches for these instead of
   `config.yaml`'s terms (and skips the analyst-specific `include_keywords`;
   seniority and exclude rules still apply). Those runs are labelled with the
   CV's name in the Run dropdown.

New dependencies for reading PDF/Word files — run once:

```bash
pip install -r requirements.txt
```

If a PDF shows "no text could be read", it's probably a scanned image;
upload the Word version instead.

## Run the tests (no network needed)

```bash
PYTHONPATH=. python -m tests.test_pipeline -v          # fetch -> normalize -> filter
PYTHONPATH=. python -m tests.test_dashboard_data -v     # dashboard's data/filter logic
PYTHONPATH=. python -m tests.test_cv_match -v          # CV reading, scoring and storage
```

Both use fixtures, not the live API or a running Streamlit server, so
they work offline. They passed in the environment this was built in; the
live MyCareersFuture call and the actual Streamlit UI could **not** be
tested there (outbound network was restricted to package registries, and
the package installer there blocks Streamlit specifically), so please run
`python -m src.main` and `streamlit run src/dashboard.py` for real once on
your own machine and sanity-check both before relying on them.

## How it's built (so the next pieces slot in cleanly)

```
src/fetchers/base.py              -> BaseFetcher: the contract every source implements
src/fetchers/mycareersfuture.py   -> today's only source
src/schema.py                     -> Job: the common shape every source normalizes into
src/filters/keyword_filter.py     -> cheap include/exclude/location filter + scoring
src/main.py                       -> orchestrates: fetch all terms -> dedupe -> filter -> save
src/dashboard_data.py             -> loading/filtering for the UI, kept pandas-only and testable
src/cv_match.py                   -> reads CVs (PDF/Word/txt) and scores jobs against them
src/cv_store.py                   -> saved CVs in cvs/, active CV, per-CV search terms
src/dashboard.py                  -> the Streamlit UI itself, thin — just wires up widgets
```

## A note on the MyCareersFuture endpoint

MyCareersFuture doesn't publish an official third-party API. This fetcher
calls the same public, unauthenticated JSON endpoint
(`api.mycareersfuture.gov.sg/v2/search`) that mycareersfuture.gov.sg's own
website calls — the same approach used by existing open-source MCF tools
(e.g. github.com/gabrielchua/mcf-jobs). It's not gated behind a login or a
ToS that prohibits this the way LinkedIn/Indeed are, but being
undocumented, the response shape could change without notice — the
fetcher reads fields defensively so that degrades gracefully rather than
crashing.

## Next steps, in order

1. **Run it for real** on your machine, tune `config.yaml` against what
   you're actually seeing, and use the shortlist (via the dashboard or
   the CSV) for a week or two.
2. **Company career pages** — add a second fetcher under `src/fetchers/`
   implementing `BaseFetcher` for 2-3 companies you specifically care
   about; nothing else in the pipeline changes.
3. **Aggregator API** (Adzuna/JSearch) for broader coverage, same pattern.
4. **LLM scoring layer** — once the shortlist from keyword filtering is
   small, send each job + your CV/profile to a model for a fit score and
   one-line reasoning; this is what makes it feel smart. Keep the keyword
   filter in front of it so you're not paying for every posting.
5. **Scheduling** — run `python -m src.main` automatically (cron, or a
   scheduled task) instead of by hand, so the dashboard always has a
   fresh run to show.
6. **The tracker** — a place for jobs you've decided to act on, with
   status (Applied/Interviewing/Offer/Rejected) and follow-up reminders.
   This agent's output (the ranked shortlist) becomes its input; the
   dashboard is a natural place to add an "add to tracker" action per row.
