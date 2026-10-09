"""Browse job search agent results in a web UI instead of the terminal/CSV.

Run with: streamlit run src/dashboard.py

This file only wires up widgets — loading/filtering/scoring logic lives in
dashboard_data.py, cv_match.py and cv_store.py so it can be tested
without Streamlit installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable regardless of how this script is
# launched (`streamlit run src/dashboard.py` puts src/ on sys.path,
# not the project root, so `import src...` fails without this).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from src import cv_store
from src.cv_match import cv_skill_summary, extract_text
from src.dashboard_data import (
    add_cv_scores,
    all_levels,
    apply_filters,
    list_result_files,
    load_jobs,
    run_label,
)
from src.filters.keyword_filter import filter_and_score
from src.main import fetch_all, load_config, write_outputs

CONFIG_PATH = PROJECT_ROOT / "config.yaml"
NO_CV = "— None (keyword score only) —"

st.set_page_config(page_title="Job Search Agent", layout="wide")
st.title("Job Search Agent")


@st.cache_data(show_spinner=False)
def _cv_text(path_str: str, mtime: float) -> str:
    # mtime is part of the cache key so re-uploading a CV refreshes it.
    return extract_text(path_str)


# ------------------------------------------------------------------ CV picker
with st.sidebar:
    st.header("Your CV")

    uploaded = st.file_uploader(
        "Add a CV (PDF, Word or .txt)",
        type=["pdf", "docx", "txt"],
        help="Saved in the cvs/ folder of this project. Upload a file with the same name to replace it.",
    )
    if uploaded is not None and st.session_state.get("_last_upload") != (uploaded.name, uploaded.size):
        try:
            saved = cv_store.save_upload(uploaded.name, uploaded.getvalue())
            cv_store.set_active(saved.name)
            st.session_state["_last_upload"] = (uploaded.name, uploaded.size)
            st.success(f"Saved {saved.name}")
            st.rerun()
        except ValueError as e:
            st.error(str(e))

    cvs = cv_store.list_cvs(cv_store.DEFAULT_CV_DIR)
    names = [NO_CV] + [p.name for p in cvs]
    active = cv_store.get_active()
    default_idx = names.index(active.name) if active and active.name in names else 0
    choice = st.selectbox("Score jobs against", names, index=default_idx)
    active_name = None if choice == NO_CV else choice
    if (active.name if active else None) != active_name:
        cv_store.set_active(active_name)

    cv_text = ""
    cv_terms: list[str] = []
    if active_name:
        cv_path = cv_store.DEFAULT_CV_DIR / active_name
        try:
            cv_text = _cv_text(str(cv_path), cv_path.stat().st_mtime)
        except ImportError as e:
            st.error(f"{e}\n\nRun that in Terminal (with your venv active), then restart the dashboard.")
        except Exception as e:  # noqa: BLE001 - show any read failure instead of crashing
            st.error(f"Couldn't read {active_name}: {e}")
        if active_name and not cv_text.strip() and active_name.lower().endswith(".pdf"):
            st.warning(
                "No text could be read from this PDF (it may be a scanned image). "
                "Try uploading the Word version or a .txt copy instead."
            )

        cv_terms = cv_store.get_search_terms(active_name)
        terms_input = st.text_area(
            "Search terms for this CV (one per line)",
            value="\n".join(cv_terms),
            height=90,
            help=(
                "Used by “Fetch new jobs now” while this CV is selected, instead of "
                "the search terms in config.yaml. Leave empty to use config.yaml."
            ),
            placeholder="e.g.\ntrainee broker\ninsurance executive",
        )
        new_terms = [t.strip() for t in terms_input.splitlines() if t.strip()]
        if new_terms != cv_terms:
            cv_store.set_search_terms(active_name, new_terms)
            cv_terms = new_terms

        with st.expander("Remove this CV"):
            if st.button(f"Delete {active_name}", type="secondary"):
                cv_store.delete_cv(active_name)
                st.rerun()

    st.divider()

    fetch_help = (
        f"Searches for: {', '.join(cv_terms)}" if cv_terms else "Searches for the terms in config.yaml"
    )
    if st.button("🔄 Fetch new jobs now", use_container_width=True, help=fetch_help):
        with st.spinner("Searching MyCareersFuture..."):
            config = load_config(str(CONFIG_PATH))
            label = ""
            if cv_terms:
                # A different CV usually means different roles: search for its
                # own terms, and don't apply config.yaml's analyst-specific
                # include_keywords (the CV fit score does the ranking instead).
                config = {**config, "search_terms": cv_terms, "include_keywords": []}
                label = Path(active_name).stem
            all_jobs = fetch_all(config)
            ranked = filter_and_score(all_jobs, config)
            write_outputs(ranked, str(PROJECT_ROOT / config.get("output_dir", "output")), label=label)
        st.success(f"Fetched {len(ranked)} matching jobs.")
        st.rerun()

# -------------------------------------------------------------------- results
files = list_result_files()
if not files:
    st.warning(
        "No results yet. Click “Fetch new jobs now” in the sidebar, "
        "or run `python -m src.main` from Terminal."
    )
    st.stop()

selected_idx = st.sidebar.selectbox(
    "Run", options=range(len(files)), format_func=lambda i: run_label(files[i])
)
df = load_jobs(files[selected_idx])

if df.empty:
    st.info("This run found no matching jobs. Try different search terms and fetch again.")
    st.stop()

using_cv = bool(cv_text.strip())
if using_cv:
    df = add_cv_scores(df, cv_text)

st.sidebar.header("Filters")
min_cv_fit = 0.0
if using_cv:
    min_cv_fit = st.sidebar.slider("Minimum CV fit", 0, 100, 0, 5)
max_score = float(df["match_score"].max()) if not df.empty else 1.0
min_score = 0.0
if max_score > 0:
    min_score = st.sidebar.slider("Minimum keyword score", 0.0, max_score, 0.0, 0.5)
search = st.sidebar.text_input("Search title/company")
locations = sorted(l for l in df["location"].unique() if l)
selected_locations = st.sidebar.multiselect("Location", options=locations)
levels = all_levels(df)
selected_levels = st.sidebar.multiselect(
    "Seniority level",
    options=levels,
    help="From MyCareersFuture's own posting tags. Empty means the posting wasn't tagged.",
)

filtered = apply_filters(
    df,
    min_score=min_score,
    search=search,
    locations=selected_locations,
    levels=selected_levels,
    min_cv_fit=min_cv_fit,
)

if using_cv:
    st.caption(
        f"Ranked by fit with **{active_name}**. CV fit = 70% how many of the job's "
        "listed skills your CV mentions + 30% overall wording similarity. "
        "It's a sorting aid — check the missing skills before applying."
    )
    have, gaps = cv_skill_summary(df.to_dict("records"), cv_text, top=10)
    c1, c2 = st.columns(2)
    c1.markdown("**Most-requested skills your CV shows**  \n" + (", ".join(have) or "—"))
    c2.markdown("**Most-requested skills your CV doesn't mention**  \n" + (", ".join(gaps) or "—"))
elif active_name:
    st.caption("Couldn't read text from the selected CV, so jobs are ranked by keyword score.")
else:
    st.caption("Tip: add a CV in the sidebar to rank these jobs by how well they fit it.")

st.write(f"{len(filtered)} of {len(df)} jobs shown")

columns = ["title", "company", "location", "level", "salary"]
column_config = {
    "url": st.column_config.LinkColumn("Link", display_text="Open"),
    "match_score": st.column_config.NumberColumn("Keyword score", format="%.1f"),
    "level": st.column_config.TextColumn("Level"),
}
if using_cv:
    columns += ["cv_fit", "skills_matched", "missing_skills"]
    column_config.update(
        {
            "cv_fit": st.column_config.ProgressColumn("CV fit", min_value=0, max_value=100, format="%.0f"),
            "skills_matched": st.column_config.TextColumn("Skills matched"),
            "missing_skills": st.column_config.TextColumn("Skills your CV doesn't mention", width="large"),
        }
    )
else:
    columns += ["match_score"]
columns += ["posted_date", "url"]

st.dataframe(
    filtered[columns],
    column_config=column_config,
    hide_index=True,
    use_container_width=True,
)
