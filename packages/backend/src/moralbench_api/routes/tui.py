"""TUI remote control routes for external process control."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/tui", tags=["tui"])

# File paths - project root
PROJECT_ROOT = Path(__file__).parents[5]
COMMAND_FILE = PROJECT_ROOT / ".annotator_commands.json"
STATE_FILE = PROJECT_ROOT / ".annotator_state.json"


class TUICommand(BaseModel):
    """Command to send to the TUI."""
    action: Literal[
        "next_question",
        "prev_question",
        "set_score",
        "save",
        "next_response",
        "prev_response",
        "skip_response",
    ] = Field(..., description="Action to execute")
    value: Optional[str] = Field(None, description="Value for set_score action")


class TUICommandResponse(BaseModel):
    """Response after sending a command."""
    success: bool
    command_id: str
    message: str


class TUIState(BaseModel):
    """Current TUI state."""
    model: Optional[str] = None
    response_idx: int = 0
    current_question: str = "q1"
    total_responses: int = 0
    human_scores: dict = {}
    timestamp: Optional[str] = None
    error: Optional[str] = None


@router.post("/command", response_model=TUICommandResponse)
def send_command(command: TUICommand) -> TUICommandResponse:
    """Send a command to the TUI via file-based queue.
    
    The TUI polls this file and executes commands when detected.
    """
    command_id = str(uuid.uuid4())
    
    command_data = {
        "command_id": command_id,
        "action": command.action,
        "value": command.value,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    
    try:
        COMMAND_FILE.write_text(json.dumps(command_data, indent=2))
        return TUICommandResponse(
            success=True,
            command_id=command_id,
            message=f"Command '{command.action}' queued successfully",
        )
    except Exception as e:
        return TUICommandResponse(
            success=False,
            command_id=command_id,
            message=f"Failed to write command: {e}",
        )


@router.get("/state", response_model=TUIState)
def get_state() -> TUIState:
    """Get the current TUI state from the state file."""
    if not STATE_FILE.exists():
        return TUIState(error="No state file found - TUI may not be running")
    
    try:
        state = json.loads(STATE_FILE.read_text())
        return TUIState(
            model=state.get("model"),
            response_idx=state.get("response_idx", 0),
            current_question=state.get("current_question", "q1"),
            total_responses=state.get("total_responses", 0),
            human_scores=state.get("human_scores", {}),
            timestamp=state.get("timestamp"),
        )
    except json.JSONDecodeError as e:
        return TUIState(error=f"Invalid state file: {e}")
    except Exception as e:
        return TUIState(error=f"Failed to read state: {e}")
