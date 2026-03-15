"""Tests for TUI remote control routes."""

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from moralbench_api.main import app
from moralbench_api.routes import tui


@pytest.fixture
def temp_dir():
    """Create a temporary directory for command/state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def client(temp_dir):
    """Create test client with patched file paths."""
    original_cmd = tui.COMMAND_FILE
    original_state = tui.STATE_FILE
    original_root = tui.PROJECT_ROOT

    tui.COMMAND_FILE = temp_dir / ".annotator_commands.json"
    tui.STATE_FILE = temp_dir / ".annotator_state.json"
    tui.PROJECT_ROOT = temp_dir

    try:
        yield TestClient(app)
    finally:
        tui.COMMAND_FILE = original_cmd
        tui.STATE_FILE = original_state
        tui.PROJECT_ROOT = original_root


class TestTUIRoutes:
    def test_send_command_creates_file(self, client, temp_dir):
        """Verify POST /api/tui/command creates command file."""
        response = client.post(
            "/api/tui/command",
            json={"action": "next_question"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["command_id"]
        assert "next_question" in data["message"]

        # Verify file was created
        assert tui.COMMAND_FILE.exists()
        cmd_data = json.loads(tui.COMMAND_FILE.read_text())
        assert cmd_data["action"] == "next_question"
        assert cmd_data["command_id"] == data["command_id"]

    def test_send_command_with_value(self, client, temp_dir):
        """Verify set_score command includes value."""
        response = client.post(
            "/api/tui/command",
            json={"action": "set_score", "value": "Yes"}
        )

        assert response.status_code == 200
        cmd_data = json.loads(tui.COMMAND_FILE.read_text())
        assert cmd_data["action"] == "set_score"
        assert cmd_data["value"] == "Yes"

    def test_get_state_returns_state(self, client, temp_dir):
        """Verify GET /api/tui/state returns current state."""
        # Create state file
        tui.STATE_FILE.write_text(json.dumps({
            "model": "test-model",
            "response_idx": 5,
            "current_question": "q3",
            "total_responses": 50,
            "human_scores": {"q1": "Yes"},
            "timestamp": "2026-03-14T12:00:00Z"
        }))

        response = client.get("/api/tui/state")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "test-model"
        assert data["response_idx"] == 5
        assert data["current_question"] == "q3"
        assert data["total_responses"] == 50
        assert data["human_scores"] == {"q1": "Yes"}

    def test_get_state_no_file(self, client, temp_dir):
        """Verify GET /api/tui/state handles missing file."""
        response = client.get("/api/tui/state")

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is not None
        assert "No state file" in data["error"]

    def test_all_actions_are_valid(self, client, temp_dir):
        """Verify all action types are accepted."""
        actions = [
            "next_question",
            "prev_question",
            "set_score",
            "save",
            "next_response",
            "prev_response",
            "skip_response",
        ]

        for action in actions:
            response = client.post(
                "/api/tui/command",
                json={"action": action, "value": "test" if action == "set_score" else None}
            )
            assert response.status_code == 200, f"Failed for action: {action}"
            assert response.json()["success"] is True
