"""Annotations API routes with file-based storage and database storage for Q1-Q4."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from moral_bench.database import MoralBenchDB

router = APIRouter()

DATA_DIR = Path(__file__).parents[3] / "data"
ANNOTATIONS_FILE = DATA_DIR / "annotations.json"

# Database path - use the main moralbench.db
DB_PATH = Path(__file__).parents[5] / "moralbench.db"


class AnnotationCreate(BaseModel):
    result_uid: int = Field(..., description="UID of the result being annotated")
    model: str = Field(..., description="Model name")
    notes: str = Field(default="", description="Free-form annotation notes")
    preference_reasoning: str = Field(default="", description="Reasoning for preference score")
    preference_score: Optional[float] = Field(None, ge=-1, le=1, description="Preference score from -1 to 1")
    justification_reasoning: str = Field(default="", description="Reasoning for justification score")
    justification_score: Optional[int] = Field(None, ge=1, le=5, description="Justification score from 1 to 5")


class AnnotationUpdate(BaseModel):
    notes: Optional[str] = Field(None, description="Free-form annotation notes")
    preference_reasoning: Optional[str] = Field(None, description="Reasoning for preference score")
    preference_score: Optional[float] = Field(None, ge=-1, le=1, description="Preference score from -1 to 1")
    justification_reasoning: Optional[str] = Field(None, description="Reasoning for justification score")
    justification_score: Optional[int] = Field(None, ge=1, le=5, description="Justification score from 1 to 5")


class Annotation(BaseModel):
    id: str = Field(..., description="Unique annotation ID")
    result_uid: int = Field(..., description="UID of the result being annotated")
    model: str = Field(..., description="Model name")
    notes: str = Field(default="", description="Free-form annotation notes")
    preference_reasoning: str = Field(default="", description="Reasoning for preference score")
    preference_score: Optional[float] = Field(None, description="Preference score from -1 to 1")
    justification_reasoning: str = Field(default="", description="Reasoning for justification score")
    justification_score: Optional[int] = Field(None, description="Justification score from 1 to 5")
    created_at: str = Field(..., description="ISO timestamp of creation")
    updated_at: str = Field(..., description="ISO timestamp of last update")


def _ensure_data_dir():
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_annotations() -> dict[str, dict]:
    """Load annotations from JSON file."""
    _ensure_data_dir()
    if not ANNOTATIONS_FILE.exists():
        return {}
    with open(ANNOTATIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_annotations(annotations: dict[str, dict]):
    """Save annotations to JSON file."""
    _ensure_data_dir()
    with open(ANNOTATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)


def _make_composite_key(result_uid: int, model: str) -> str:
    """Create a composite key for result_uid + model lookup."""
    return f"{result_uid}:{model}"


@router.get("/annotations")
def list_annotations(
    result_uid: Optional[int] = Query(None, description="Filter by result UID"),
    model: Optional[str] = Query(None, description="Filter by model name"),
):
    """List all annotations with optional filtering."""
    annotations = _load_annotations()
    results = list(annotations.values())
    
    if result_uid is not None:
        results = [a for a in results if a["result_uid"] == result_uid]
    if model:
        results = [a for a in results if a["model"] == model]
    
    return {"annotations": results, "total": len(results)}


@router.get("/annotations/by-result/{result_uid}")
def get_annotations_by_result(result_uid: int):
    """Get all annotations for a specific result UID (across all models)."""
    annotations = _load_annotations()
    results = [a for a in annotations.values() if a["result_uid"] == result_uid]
    return {"annotations": results}


@router.get("/annotations/lookup")
def lookup_annotation(
    result_uid: int = Query(..., description="Result UID"),
    model: str = Query(..., description="Model name"),
):
    """Look up annotation by result_uid and model (composite key)."""
    annotations = _load_annotations()
    for ann in annotations.values():
        if ann["result_uid"] == result_uid and ann["model"] == model:
            return {"annotation": ann, "found": True}
    return {"annotation": None, "found": False}


# ============ Q1-Q4 Database-based Annotations ============
# NOTE: These routes MUST be defined BEFORE the /annotations/{annotation_id} route
# because FastAPI matches routes in order and {annotation_id} would match "q1q4"

class Q1Q4AnnotationCreate(BaseModel):
    """Create/update Q1-Q4 annotation request."""
    response_id: int = Field(..., description="Database response ID")
    model: str = Field(..., description="Model name")
    q1_score: Optional[str] = Field(None, description="Q1 score: Yes or No")
    q1_reasoning: Optional[str] = Field(None, description="Q1 reasoning")
    q2_score: Optional[int] = Field(None, ge=-1, le=1, description="Q2 score: -1, 0, or 1")
    q2_reasoning: Optional[str] = Field(None, description="Q2 reasoning")
    q3_score: Optional[int] = Field(None, ge=-1, le=1, description="Q3 score: -1, 0, or 1")
    q3_reasoning: Optional[str] = Field(None, description="Q3 reasoning")
    q4_score: Optional[int] = Field(None, ge=1, le=5, description="Q4 score: 1-5")
    q4_reasoning: Optional[str] = Field(None, description="Q4 reasoning")


class Q1Q4AnnotationResponse(BaseModel):
    """Q1-Q4 annotation response model."""
    id: Optional[str] = None
    response_id: int
    model: str
    q1_score: Optional[str] = None
    q1_reasoning: Optional[str] = None
    q2_score: Optional[int] = None
    q2_reasoning: Optional[str] = None
    q3_score: Optional[int] = None
    q3_reasoning: Optional[str] = None
    q4_score: Optional[int] = None
    q4_reasoning: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ResponseWithQ1Q4(BaseModel):
    """Response with Q1-Q4 LLM grades and human annotations."""
    response_id: int
    model: str
    response_text: str
    question_id: int
    topic: str
    question_text: str
    # LLM grades
    llm_q1_score: Optional[str] = None
    llm_q1_reasoning: Optional[str] = None
    llm_q2_score: Optional[str] = None
    llm_q2_reasoning: Optional[str] = None
    llm_q3_score: Optional[str] = None
    llm_q3_reasoning: Optional[str] = None
    llm_q4_score: Optional[str] = None
    llm_q4_reasoning: Optional[str] = None
    # Human annotations
    annotation_id: Optional[str] = None
    human_q1_score: Optional[str] = None
    human_q1_reasoning: Optional[str] = None
    human_q2_score: Optional[int] = None
    human_q2_reasoning: Optional[str] = None
    human_q3_score: Optional[int] = None
    human_q3_reasoning: Optional[str] = None
    human_q4_score: Optional[int] = None
    human_q4_reasoning: Optional[str] = None


def _get_db() -> MoralBenchDB:
    """Get database connection."""
    return MoralBenchDB(DB_PATH)


@router.get("/annotations/q1q4")
def list_q1q4_responses(
    model: Optional[str] = Query(None, description="Filter by model name"),
    limit: int = Query(100, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List responses with their Q1-Q4 LLM grades and human annotations."""
    db = _get_db()
    responses = db.get_responses_for_q1q4_annotation(model=model, limit=limit, offset=offset)
    return {"responses": responses, "total": len(responses)}


@router.get("/annotations/q1q4/lookup")
def lookup_q1q4_annotation(
    response_id: int = Query(..., description="Response ID"),
    model: str = Query(..., description="Model name"),
):
    """Look up Q1-Q4 annotation by response_id and model."""
    db = _get_db()
    annotation = db.get_annotation_by_response_id(response_id, model)
    if annotation:
        return {
            "annotation": {
                "id": annotation.id,
                "response_id": annotation.response_id,
                "model": annotation.model,
                "q1_score": annotation.q1_score,
                "q1_reasoning": annotation.q1_reasoning,
                "q2_score": annotation.q2_score,
                "q2_reasoning": annotation.q2_reasoning,
                "q3_score": annotation.q3_score,
                "q3_reasoning": annotation.q3_reasoning,
                "q4_score": annotation.q4_score,
                "q4_reasoning": annotation.q4_reasoning,
                "created_at": str(annotation.created_at) if annotation.created_at else None,
                "updated_at": str(annotation.updated_at) if annotation.updated_at else None,
            },
            "found": True,
        }
    return {"annotation": None, "found": False}


@router.post("/annotations/q1q4")
def save_q1q4_annotation(data: Q1Q4AnnotationCreate):
    """Create or update a Q1-Q4 annotation in the database."""
    db = _get_db()
    
    # Check if annotation already exists
    existing = db.get_annotation_by_response_id(data.response_id, data.model)
    now = datetime.utcnow()
    
    if existing:
        # Update existing annotation - preserve other fields
        annotation_id = existing.id
        created_at = existing.created_at
    else:
        annotation_id = str(uuid.uuid4())
        created_at = now
    
    # Save the annotation
    db.add_annotation(
        annotation_id=annotation_id,
        response_id=data.response_id,
        model=data.model,
        notes=existing.notes if existing else None,
        preference_reasoning=existing.preference_reasoning if existing else None,
        preference_score=existing.preference_score if existing else None,
        justification_reasoning=existing.justification_reasoning if existing else None,
        justification_score=existing.justification_score if existing else None,
        q1_score=data.q1_score,
        q1_reasoning=data.q1_reasoning,
        q2_score=data.q2_score,
        q2_reasoning=data.q2_reasoning,
        q3_score=data.q3_score,
        q3_reasoning=data.q3_reasoning,
        q4_score=data.q4_score,
        q4_reasoning=data.q4_reasoning,
        created_at=created_at,
        updated_at=now,
    )
    
    return {
        "annotation": {
            "id": annotation_id,
            "response_id": data.response_id,
            "model": data.model,
            "q1_score": data.q1_score,
            "q1_reasoning": data.q1_reasoning,
            "q2_score": data.q2_score,
            "q2_reasoning": data.q2_reasoning,
            "q3_score": data.q3_score,
            "q3_reasoning": data.q3_reasoning,
            "q4_score": data.q4_score,
            "q4_reasoning": data.q4_reasoning,
            "created_at": str(created_at),
            "updated_at": str(now),
        },
        "created": existing is None,
    }


@router.get("/annotations/q1q4/models")
def get_models_for_q1q4():
    """Get list of models that have responses in the database."""
    db = _get_db()
    models = db.get_models()
    return {"models": models}


@router.get("/annotations/{annotation_id}")
def get_annotation(annotation_id: str):
    """Get a single annotation by ID."""
    annotations = _load_annotations()
    if annotation_id not in annotations:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return {"annotation": annotations[annotation_id]}


@router.post("/annotations", response_model=dict)
def create_or_update_annotation(data: AnnotationCreate):
    """Create or update an annotation (upsert by result_uid + model)."""
    annotations = _load_annotations()
    now = datetime.utcnow().isoformat() + "Z"
    
    # Check if annotation exists for this result_uid + model
    existing_id = None
    for ann_id, ann in annotations.items():
        if ann["result_uid"] == data.result_uid and ann["model"] == data.model:
            existing_id = ann_id
            break
    
    if existing_id:
        # Update existing
        annotations[existing_id]["notes"] = data.notes
        annotations[existing_id]["preference_reasoning"] = data.preference_reasoning
        annotations[existing_id]["preference_score"] = data.preference_score
        annotations[existing_id]["justification_reasoning"] = data.justification_reasoning
        annotations[existing_id]["justification_score"] = data.justification_score
        annotations[existing_id]["updated_at"] = now
        _save_annotations(annotations)
        return {"annotation": annotations[existing_id], "created": False}
    else:
        # Create new
        new_id = str(uuid.uuid4())
        annotation = {
            "id": new_id,
            "result_uid": data.result_uid,
            "model": data.model,
            "notes": data.notes,
            "preference_reasoning": data.preference_reasoning,
            "preference_score": data.preference_score,
            "justification_reasoning": data.justification_reasoning,
            "justification_score": data.justification_score,
            "created_at": now,
            "updated_at": now,
        }
        annotations[new_id] = annotation
        _save_annotations(annotations)
        return {"annotation": annotation, "created": True}


@router.put("/annotations/{annotation_id}")
def update_annotation(annotation_id: str, data: AnnotationUpdate):
    """Update an existing annotation by ID."""
    annotations = _load_annotations()
    if annotation_id not in annotations:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    now = datetime.utcnow().isoformat() + "Z"
    if data.notes is not None:
        annotations[annotation_id]["notes"] = data.notes
    if data.preference_reasoning is not None:
        annotations[annotation_id]["preference_reasoning"] = data.preference_reasoning
    if data.preference_score is not None:
        annotations[annotation_id]["preference_score"] = data.preference_score
    if data.justification_reasoning is not None:
        annotations[annotation_id]["justification_reasoning"] = data.justification_reasoning
    if data.justification_score is not None:
        annotations[annotation_id]["justification_score"] = data.justification_score
    annotations[annotation_id]["updated_at"] = now
    
    _save_annotations(annotations)
    return {"annotation": annotations[annotation_id]}


@router.delete("/annotations/{annotation_id}")
def delete_annotation(annotation_id: str):
    """Delete an annotation by ID."""
    annotations = _load_annotations()
    if annotation_id not in annotations:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    deleted = annotations.pop(annotation_id)
    _save_annotations(annotations)
    return {"deleted": deleted}
