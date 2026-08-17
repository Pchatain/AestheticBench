"""Results API routes."""

import csv
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ._shared import (
    GRADES_DIR,
    get_latest_graded_files,
    get_openrouter_headers,
    load_csv,
    parse_model_from_filename,
)

router = APIRouter()


class PlaygroundRequest(BaseModel):
    prompt: str
    model: str = "openai/gpt-4o"


class PlaygroundResponse(BaseModel):
    response: str
    model: str


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

# Base columns that always exist, plus dynamic grading columns
BASE_COLUMNS = ["uid", "model", "Topic", "Question", "Model Response", "Timestamp"]


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
    
    # Score column -> accumulator key mapping
    # Entries with square=True accumulate the square of the value (for preference scores)
    SCORE_COLUMNS = [
        ("Preference_1_Score", "preference1", True),
        ("Preference_2_Score", "preference2", True),
        ("Justification_Score", "justification", False),
        ("Q1_Relativism_Score", "q1_relativism", False),
        ("Q2_Preference_Score", "q2_preference", False),
        ("Q3_Evidence_Score", "q3_evidence", False),
        ("Q4_Justification_Score", "q4_justification", False),
    ]

    def _accumulate_score(scores: dict, key: str, raw: str, square: bool) -> None:
        """Parse and accumulate a score value, skipping errors."""
        if not raw or raw.startswith("ERROR") or raw.startswith("PARSE_ERROR"):
            return
        try:
            val = float(raw)
            scores[f"{key}_sum"] += val ** 2 if square else val
            scores[f"{key}_count"] += 1
        except ValueError:
            pass

    # Aggregate scores per model
    model_scores: dict[str, dict] = {}
    topic_counts: dict[str, int] = {}

    for model_name, f in latest_files.items():
        if model_list and model_name not in model_list:
            continue

        scores = {f"{key}_{suffix}": 0.0 if suffix == "sum" else 0
                  for _, key, _ in SCORE_COLUMNS for suffix in ("sum", "count")}
        scores["total_count"] = 0
        model_scores[model_name] = scores

        rows = load_csv(f)
        for row in rows:
            topic = row.get("Topic", "")

            if topic_list and topic not in topic_list:
                continue

            if topic:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

            scores["total_count"] += 1

            for col, key, square in SCORE_COLUMNS:
                _accumulate_score(scores, key, row.get(col, ""), square)

    # Calculate averages
    summaries = []
    for model_name, scores in model_scores.items():
        summary: dict = {"model": model_name}
        for _, key, _ in SCORE_COLUMNS:
            s, c = scores[f"{key}_sum"], scores[f"{key}_count"]
            summary[f"{key}_avg"] = s / c if c > 0 else None
        summary["count"] = scores["total_count"]
        summaries.append(summary)

    return {"summaries": summaries, "topic_counts": topic_counts}


SCORE_COLUMN_MAP = {
    "q1": "Q1_Relativism_Score",
    "q2": "Q2_Preference_Score",
    "q3": "Q3_Evidence_Score",
    "q4": "Q4_Justification_Score",
    "q4_1": "Q4_1_Factual_Depth_Score",
    "q4_2": "Q4_2_Specificity_Score",
    "q4_3": "Q4_3_Synthesis_Score",
    "q4_4": "Q4_4_Consistency_Score",
}


@router.get("/grades/heatmap")
def get_grades_heatmap():
    """Get all LLM grades for heatmap visualization.

    Reads Q1-Q4 (and Q4.1-Q4.4 when available) from graded CSV files.
    Returns one row per (model, uid) pair.
    """
    latest_files = get_latest_graded_files()
    if not latest_files:
        return {"data": []}

    data: list[dict] = []
    for model_name, f in latest_files.items():
        rows = load_csv(f)
        for row in rows:
            entry: dict = {
                "uid": row["uid"],
                "model": model_name,
                "topic": row.get("Topic", ""),
                "question": row.get("Question", ""),
                "response": row.get("Model Response", ""),
            }
            for key, col in SCORE_COLUMN_MAP.items():
                entry[key] = _safe_score(row.get(col))
            data.append(entry)

    return {"data": data}


def _safe_score(val: Optional[str]) -> Optional[float]:
    """Parse a score string to float, returning None on error."""
    if not val or str(val).startswith("ERROR"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


@router.get("/grades/{model}")
def get_grades(model: str):
    """Get grades for a specific model (uses latest graded file only)."""
    latest_files = get_latest_graded_files()
    if model not in latest_files:
        return {"grades": [], "available": False}
    
    grades = load_csv(latest_files[model])
    return {"grades": grades, "available": True}
