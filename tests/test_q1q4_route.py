"""Integration tests for Q1-Q4 annotation routes.

These tests verify that the /api/annotations/q1q4 route correctly returns
both LLM grades and human annotations.
"""

import tempfile
import uuid
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from aestheticbench.store.database import AestheticBenchDB
from aestheticbench.api.main import app
from aestheticbench.api.routes import annotations


@pytest.fixture
def temp_db():
    """Create a temporary database with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = AestheticBenchDB(db_path)
        
        # Add test question
        question_id = db.add_question("Ethics", "Is lying ever justified?")
        
        # Add test response
        response_id = db.add_response(
            question_id=question_id,
            model="test-model",
            response_text="Lying can be justified in certain circumstances to prevent harm.",
        )
        
        # Add LLM grades (q1-q4)
        db.add_grade(response_id, "q1", "No", "The response engages with the premise directly.")
        db.add_grade(response_id, "q2", "0.5", "Moderate preference expressed.")
        db.add_grade(response_id, "q3", "1", "Evidence is provided to support the claim.")
        db.add_grade(response_id, "q4", "4", "Good justification overall.")
        
        # Add human annotation
        db.add_annotation(
            annotation_id=str(uuid.uuid4()),
            response_id=response_id,
            model="test-model",
            q1_score="No",
            q1_reasoning="Human agrees: engages premise directly",
            q2_score=0,
            q2_reasoning="Human sees neutral preference",
            q3_score=1,
            q3_reasoning="Human agrees evidence is present",
            q4_score=3,
            q4_reasoning="Human rates justification as moderate",
        )
        
        yield db, db_path


@pytest.fixture
def client(temp_db):
    """Create test client with patched database path."""
    db, db_path = temp_db
    
    # Patch the DB_PATH in the annotations module
    original_db_path = annotations.DB_PATH
    annotations.DB_PATH = db_path
    
    try:
        yield TestClient(app)
    finally:
        annotations.DB_PATH = original_db_path


class TestQ1Q4Route:
    def test_get_q1q4_responses_returns_llm_grades(self, client, temp_db):
        """Verify that LLM grades are returned in the response."""
        response = client.get("/api/annotations/q1q4")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "responses" in data
        assert len(data["responses"]) >= 1
        
        # Find the test response
        resp = data["responses"][0]
        
        # Check LLM grades are present
        assert resp["llm_q1_score"] == "No"
        assert resp["llm_q1_reasoning"] == "The response engages with the premise directly."
        assert resp["llm_q2_score"] == "0.5"
        assert resp["llm_q3_score"] == "1"
        assert resp["llm_q4_score"] == "4"

    def test_get_q1q4_responses_returns_human_annotations(self, client, temp_db):
        """Verify that human annotations are returned in the response."""
        response = client.get("/api/annotations/q1q4")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["responses"]) >= 1
        resp = data["responses"][0]
        
        # Check human annotations are present
        assert resp["human_q1_score"] == "No"
        assert resp["human_q1_reasoning"] == "Human agrees: engages premise directly"
        assert resp["human_q2_score"] == 0
        assert resp["human_q3_score"] == 1
        assert resp["human_q4_score"] == 3
        assert resp["human_q4_reasoning"] == "Human rates justification as moderate"

    def test_get_q1q4_responses_returns_response_metadata(self, client, temp_db):
        """Verify that response and question metadata are returned."""
        response = client.get("/api/annotations/q1q4")
        
        assert response.status_code == 200
        data = response.json()
        
        resp = data["responses"][0]
        
        # Check metadata
        assert resp["model"] == "test-model"
        assert resp["topic"] == "Ethics"
        assert resp["question_text"] == "Is lying ever justified?"
        assert "Lying can be justified" in resp["response_text"]
        assert resp["response_id"] is not None
        assert resp["question_id"] is not None

    def test_get_q1q4_responses_filter_by_model(self, client, temp_db):
        """Verify model filtering works."""
        # Query with matching model
        response = client.get("/api/annotations/q1q4", params={"model": "test-model"})
        assert response.status_code == 200
        assert len(response.json()["responses"]) >= 1
        
        # Query with non-matching model
        response = client.get("/api/annotations/q1q4", params={"model": "nonexistent-model"})
        assert response.status_code == 200
        assert len(response.json()["responses"]) == 0

    def test_get_q1q4_responses_without_human_annotation(self, temp_db):
        """Verify response works when no human annotation exists."""
        db, db_path = temp_db
        
        # Add another response without human annotation
        question_id = db.add_question("Politics", "Should voting be mandatory?")
        response_id = db.add_response(
            question_id=question_id,
            model="test-model-2",
            response_text="Voting should remain optional to preserve freedom.",
        )
        db.add_grade(response_id, "q1", "Yes", "Appeals to principle of freedom.")
        
        # Patch and test
        original_db_path = annotations.DB_PATH
        annotations.DB_PATH = db_path
        
        try:
            client = TestClient(app)
            response = client.get("/api/annotations/q1q4", params={"model": "test-model-2"})
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["responses"]) >= 1
            
            resp = data["responses"][0]
            # LLM grade should be present
            assert resp["llm_q1_score"] == "Yes"
            # Human annotations should be None
            assert resp["human_q1_score"] is None
            assert resp["annotation_id"] is None
        finally:
            annotations.DB_PATH = original_db_path
