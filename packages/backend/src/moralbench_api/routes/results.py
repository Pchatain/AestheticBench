"""Results API routes."""

import csv
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()

# Read from local data folder (copied by run.sh)
DATA_DIR = Path(__file__).parents[3] / "data" / "results" / "v2"
RESPONSES_DIR = DATA_DIR / "responses"
GRADES_DIR = DATA_DIR / "grades"


def parse_model_from_filename(filename: str) -> str:
    """Extract model name from filename like 'openai_gpt-5_2025-11-26_21-26-11.csv'."""
    match = re.match(r"(.+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.csv", filename)
    if match:
        return match.group(1)
    return filename.replace(".csv", "")


def load_csv(filepath: Path) -> list[dict]:
    """Load a CSV file and return list of dicts with UID added."""
    rows = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            row["uid"] = idx
            rows.append(row)
    return rows


@router.get("/models")
def list_models():
    """List available models from response files."""
    if not RESPONSES_DIR.exists():
        return {"models": []}
    
    models = []
    for f in RESPONSES_DIR.glob("*.csv"):
        model_name = parse_model_from_filename(f.name)
        models.append({"name": model_name, "filename": f.name})
    
    return {"models": sorted(models, key=lambda x: x["name"])}


@router.get("/topics")
def list_topics(model: Optional[str] = None):
    """List unique topics, optionally filtered by model."""
    topics = set()
    
    if not RESPONSES_DIR.exists():
        return {"topics": []}
    
    files = list(RESPONSES_DIR.glob("*.csv"))
    if model:
        files = [f for f in files if parse_model_from_filename(f.name) == model]
    
    for f in files:
        rows = load_csv(f)
        for row in rows:
            if "Topic" in row:
                topics.add(row["Topic"])
    
    return {"topics": sorted(topics)}


@router.get("/results")
def get_results(
    model: Optional[str] = Query(None, description="Filter by model name"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    search: Optional[str] = Query(None, description="Search in questions"),
):
    """Get results with optional filtering."""
    if not RESPONSES_DIR.exists():
        return {"results": [], "total": 0}
    
    all_results = []
    
    for f in RESPONSES_DIR.glob("*.csv"):
        model_name = parse_model_from_filename(f.name)
        
        if model and model_name != model:
            continue
        
        rows = load_csv(f)
        for row in rows:
            if topic and row.get("Topic") != topic:
                continue
            
            if search:
                question = row.get("Question", "").lower()
                if search.lower() not in question:
                    continue
            
            all_results.append({
                "uid": row["uid"],
                "model": model_name,
                "topic": row.get("Topic", ""),
                "question": row.get("Question", ""),
                "response": row.get("Model Response", ""),
                "timestamp": row.get("Timestamp", ""),
            })
    
    return {"results": all_results, "total": len(all_results)}


@router.get("/grades/{model}")
def get_grades(model: str):
    """Get grades for a specific model."""
    if not GRADES_DIR.exists():
        return {"grades": [], "available": False}
    
    grade_files = list(GRADES_DIR.glob(f"{model}*.csv"))
    if not grade_files:
        return {"grades": [], "available": False}
    
    grades = []
    for f in grade_files:
        rows = load_csv(f)
        grades.extend(rows)
    
    return {"grades": grades, "available": True}
