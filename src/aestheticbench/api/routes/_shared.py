"""Shared utilities for API routes."""

import csv
import os
import re
from pathlib import Path

from fastapi import HTTPException


from aestheticbench.paths import RESULTS_DIR

DATA_DIR = RESULTS_DIR / "v2"
RESPONSES_DIR = DATA_DIR / "responses"
GRADES_DIR = DATA_DIR / "grades"


def get_openrouter_headers() -> dict[str, str]:
    """Get headers for OpenRouter API requests."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENROUTER_API_KEY not configured on server"
        )
    return {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/aestheticbench",
        "X-Title": "AestheticBench",
    }


def parse_model_from_filename(filename: str) -> str:
    """Extract model name from filename like 'openai_gpt-5_2025-11-26_21-26-11_graded_....csv'."""
    match = re.match(r"(.+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_graded_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.csv", filename)
    if match:
        return match.group(1)
    match = re.match(r"(.+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.csv", filename)
    if match:
        return match.group(1)
    return filename.replace(".csv", "")


def parse_graded_timestamp(filename: str) -> str:
    """Extract the graded timestamp from filename for sorting.

    Filename format: model_YYYY-MM-DD_HH-MM-SS_graded_YYYY-MM-DD_HH-MM-SS.csv
    Returns the second timestamp (grading time) for comparison.
    """
    match = re.search(r"_graded_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.csv$", filename)
    if match:
        return match.group(1)
    return ""


def get_latest_graded_files() -> dict[str, Path]:
    """Get the most recent graded file for each model.

    Returns dict mapping model name to the Path of its most recent graded file.
    """
    if not GRADES_DIR.exists():
        return {}

    model_files: dict[str, list[tuple[str, Path]]] = {}

    for f in GRADES_DIR.glob("*.csv"):
        model_name = parse_model_from_filename(f.name)
        timestamp = parse_graded_timestamp(f.name)

        if model_name not in model_files:
            model_files[model_name] = []
        model_files[model_name].append((timestamp, f))

    latest: dict[str, Path] = {}
    for model_name, files in model_files.items():
        files.sort(key=lambda x: x[0], reverse=True)
        latest[model_name] = files[0][1]

    return latest


def load_csv(filepath: Path) -> list[dict]:
    """Load a CSV file and return list of dicts with UID added."""
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            row["uid"] = idx
            rows.append(row)
    return rows
