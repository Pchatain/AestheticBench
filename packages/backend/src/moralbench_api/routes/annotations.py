"""Annotations API routes with file-based storage."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()

DATA_DIR = Path(__file__).parents[3] / "data"
ANNOTATIONS_FILE = DATA_DIR / "annotations.json"


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
