"""Where uploaded CVs live and which one is active.

CV files are saved in cvs/ at the project root. A small cvs/settings.json
remembers which CV is active and any per-CV search terms, so the choice
survives restarting the dashboard.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.cv_match import SUPPORTED_EXTENSIONS, list_cvs

DEFAULT_CV_DIR = Path(__file__).resolve().parent.parent / "cvs"
SETTINGS_NAME = "settings.json"


def _settings_path(cv_dir: Path) -> Path:
    return Path(cv_dir) / SETTINGS_NAME


def load_settings(cv_dir: Path = DEFAULT_CV_DIR) -> dict:
    path = _settings_path(cv_dir)
    if not path.exists():
        return {"active": None, "search_terms": {}}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"active": None, "search_terms": {}}
    data.setdefault("active", None)
    data.setdefault("search_terms", {})
    return data


def save_settings(settings: dict, cv_dir: Path = DEFAULT_CV_DIR) -> None:
    Path(cv_dir).mkdir(parents=True, exist_ok=True)
    _settings_path(cv_dir).write_text(json.dumps(settings, indent=2))


def safe_filename(name: str) -> str:
    stem, dot, ext = Path(name).name.rpartition(".")
    if not dot:
        stem, ext = ext, "txt"
    stem = re.sub(r"[^A-Za-z0-9 _.\-()]+", "_", stem).strip() or "cv"
    return f"{stem}.{ext.lower()}"


def save_upload(filename: str, data: bytes, cv_dir: Path = DEFAULT_CV_DIR) -> Path:
    name = safe_filename(filename)
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Please upload a PDF, Word (.docx) or .txt file.")
    Path(cv_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(cv_dir) / name
    dest.write_bytes(data)
    return dest


def get_active(cv_dir: Path = DEFAULT_CV_DIR) -> Path | None:
    active = load_settings(cv_dir).get("active")
    if not active:
        return None
    path = Path(cv_dir) / active
    return path if path.exists() else None


def set_active(name: str | None, cv_dir: Path = DEFAULT_CV_DIR) -> None:
    settings = load_settings(cv_dir)
    settings["active"] = name
    save_settings(settings, cv_dir)


def get_search_terms(name: str, cv_dir: Path = DEFAULT_CV_DIR) -> list[str]:
    return list(load_settings(cv_dir)["search_terms"].get(name, []))


def set_search_terms(name: str, terms: list[str], cv_dir: Path = DEFAULT_CV_DIR) -> None:
    settings = load_settings(cv_dir)
    cleaned = [t.strip() for t in terms if t.strip()]
    if cleaned:
        settings["search_terms"][name] = cleaned
    else:
        settings["search_terms"].pop(name, None)
    save_settings(settings, cv_dir)


def delete_cv(name: str, cv_dir: Path = DEFAULT_CV_DIR) -> None:
    path = Path(cv_dir) / name
    if path.exists():
        path.unlink()
    settings = load_settings(cv_dir)
    settings["search_terms"].pop(name, None)
    if settings.get("active") == name:
        settings["active"] = None
    save_settings(settings, cv_dir)


__all__ = [
    "DEFAULT_CV_DIR", "list_cvs", "load_settings", "save_upload", "get_active",
    "set_active", "get_search_terms", "set_search_terms", "delete_cv",
]
