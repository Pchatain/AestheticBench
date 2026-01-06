"""Results API routes."""

import csv
import os
import re
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class PlaygroundRequest(BaseModel):
    prompt: str
    model: str = "openai/gpt-4o"


class PlaygroundResponse(BaseModel):
    response: str
    model: str


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
        "HTTP-Referer": "https://github.com/moralbench",
        "X-Title": "MoralBench",
    }


@router.post("/playground/run", response_model=PlaygroundResponse)
async def run_prompt(request: PlaygroundRequest):
    """Run a prompt through a model and return the response."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=get_openrouter_headers(),
                json={
                    "model": request.model,
                    "messages": [{"role": "user", "content": request.prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            return PlaygroundResponse(
                response=data["choices"][0]["message"]["content"],
                model=request.model,
            )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"OpenRouter API error: {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Read from results directory set by run.sh
RESULTS_DIR = Path(os.environ["MORALBENCH_RESULTS_DIR"])
DATA_DIR = RESULTS_DIR / "v2"
RESPONSES_DIR = DATA_DIR / "responses"
GRADES_DIR = DATA_DIR / "grades"

# Base columns that always exist, plus dynamic grading columns
BASE_COLUMNS = ["uid", "model", "Topic", "Question", "Model Response", "Timestamp"]


def parse_model_from_filename(filename: str) -> str:
    """Extract model name from filename like 'openai_gpt-5_2025-11-26_21-26-11_graded_....csv'."""
    # Try graded format first: model_timestamp_graded_timestamp.csv
    match = re.match(r"(.+)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_graded_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.csv", filename)
    if match:
        return match.group(1)
    # Fallback to response format: model_timestamp.csv
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
    
    # Select the file with the latest timestamp for each model
    latest: dict[str, Path] = {}
    for model_name, files in model_files.items():
        # Sort by timestamp descending and take the first
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


def get_all_headers() -> list[str]:
    """Get union of all column headers from the latest graded files."""
    latest_files = get_latest_graded_files()
    if not latest_files:
        return BASE_COLUMNS
    
    all_headers = set()
    for f in latest_files.values():
        with open(f, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader, [])
            all_headers.update(headers)
    
    # Return ordered: base columns first, then any extra columns sorted
    result = []
    for col in BASE_COLUMNS:
        if col in all_headers:
            result.append(col)
            all_headers.discard(col)
    result.extend(sorted(all_headers))
    return result


@router.get("/headers")
def list_headers():
    """List all unique column headers across graded files."""
    headers = get_all_headers()
    return {"headers": headers}


@router.get("/models")
def list_models():
    """List available models from the latest graded files."""
    latest_files = get_latest_graded_files()
    if not latest_files:
        return {"models": []}
    
    models = [
        {"name": model_name, "filename": f.name}
        for model_name, f in latest_files.items()
    ]
    
    return {"models": sorted(models, key=lambda x: x["name"])}


@router.get("/topics")
def list_topics(model: Optional[str] = None):
    """List unique topics, optionally filtered by model."""
    topics = set()
    
    latest_files = get_latest_graded_files()
    if not latest_files:
        return {"topics": []}
    
    files = list(latest_files.values())
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
    """Get graded results with optional filtering (uses latest graded files only)."""
    latest_files = get_latest_graded_files()
    if not latest_files:
        return {"results": [], "total": 0, "headers": BASE_COLUMNS}
    
    all_results = []
    all_headers = get_all_headers()
    
    for model_name, f in latest_files.items():
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
            
            # Build result with all headers, using empty string for missing
            result = {"uid": row["uid"], "model": model_name}
            for header in all_headers:
                if header in ("uid", "model"):
                    continue
                result[header] = row.get(header, "")
            
            all_results.append(result)
    
    return {"results": all_results, "total": len(all_results), "headers": all_headers}


@router.get("/grades/summary")
def get_grades_summary(
    models: Optional[str] = Query(None, description="Comma-separated model names"),
    topics: Optional[str] = Query(None, description="Comma-separated topic names"),
):
    """Get aggregated grade summaries per model (uses latest graded files only)."""
    latest_files = get_latest_graded_files()
    if not latest_files:
        return {"summaries": [], "topic_counts": {}}
    
    model_list = [m.strip() for m in models.split(",")] if models else None
    topic_list = [t.strip() for t in topics.split(",")] if topics else None
    
    # Aggregate scores per model
    model_scores: dict[str, dict] = {}
    topic_counts: dict[str, int] = {}
    
    for model_name, f in latest_files.items():
        if model_list and model_name not in model_list:
            continue
        
        model_scores[model_name] = {
            "preference1_sum": 0.0,
            "preference1_count": 0,
            "preference2_sum": 0.0,
            "preference2_count": 0,
            "justification_sum": 0.0,
            "justification_count": 0,
            "total_count": 0,
        }
        
        rows = load_csv(f)
        for row in rows:
            topic = row.get("Topic", "")
            
            if topic_list and topic not in topic_list:
                continue
            
            # Count topics
            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            model_scores[model_name]["total_count"] += 1
            
            # Parse and accumulate scores
            pref1 = row.get("Preference_1_Score", "")
            if pref1 and not pref1.startswith("ERROR"):
                try:
                    model_scores[model_name]["preference1_sum"] += float(pref1)**2
                    model_scores[model_name]["preference1_count"] += 1
                except ValueError:
                    pass
            
            pref2 = row.get("Preference_2_Score", "")
            if pref2 and not pref2.startswith("ERROR"):
                try:
                    model_scores[model_name]["preference2_sum"] += float(pref2)**2
                    model_scores[model_name]["preference2_count"] += 1
                except ValueError:
                    pass
            
            justification = row.get("Justification_Score", "")
            if justification and not justification.startswith("ERROR"):
                try:
                    model_scores[model_name]["justification_sum"] += float(justification)
                    model_scores[model_name]["justification_count"] += 1
                except ValueError:
                    pass
    
    # Calculate averages
    summaries = []
    for model_name, scores in model_scores.items():
        summary = {
            "model": model_name,
            "preference1_avg": (
                scores["preference1_sum"] / scores["preference1_count"]
                if scores["preference1_count"] > 0 else None
            ),
            "preference2_avg": (
                scores["preference2_sum"] / scores["preference2_count"]
                if scores["preference2_count"] > 0 else None
            ),
            "justification_avg": (
                scores["justification_sum"] / scores["justification_count"]
                if scores["justification_count"] > 0 else None
            ),
            "count": scores["total_count"],
        }
        summaries.append(summary)
    
    return {"summaries": summaries, "topic_counts": topic_counts}


@router.get("/grades/{model}")
def get_grades(model: str):
    """Get grades for a specific model (uses latest graded file only)."""
    latest_files = get_latest_graded_files()
    if model not in latest_files:
        return {"grades": [], "available": False}
    
    grades = load_csv(latest_files[model])
    return {"grades": grades, "available": True}
