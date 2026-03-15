## Implementation Plan: External TUI Control via FastAPI Backend

### Overview
Add a file-based command queue system that allows external processes (like cmux) to control the AnnotateTUI through FastAPI API calls.

---

### 1. New Backend Route: `/api/tui/command`

**File:** `packages/backend/src/moralbench_api/routes/tui.py` (new file)

Create a new router with:
- `POST /api/tui/command` - Write command to `.annotator_commands.json`
- `GET /api/tui/state` - Read current state from `.annotator_state.json`

**Command schema:**
```python
class TUICommand(BaseModel):
    action: Literal["next_question", "prev_question", "set_score", "save", 
                    "next_response", "prev_response", "skip_response"]
    value: Optional[str] = None  # For set_score action
```

**Response schema:**
```python
class TUIState(BaseModel):
    model: Optional[str]
    response_idx: int
    current_question: str  # e.g., "q1", "q4_1", etc.
    total_responses: int
    human_scores: dict
```

---

### 2. Command File Structure

**File:** `.annotator_commands.json` (project root)

```json
{
  "command_id": "uuid-here",
  "action": "next_question",
  "value": null,
  "timestamp": "2026-03-13T..."
}
```

The TUI will:
1. Poll this file every ~200ms using a Textual timer
2. Detect new `command_id` (different from last processed)
3. Execute the action
4. Clear the file (or mark as processed)

---

### 3. TUI Modifications

**File:** `packages/backend/src/moral_bench/annotate_tui.py`

Add to `AnnotateTUI` class:
- `COMMAND_PATH` class constant pointing to `.annotator_commands.json`
- `_last_command_id: str` instance variable to track processed commands
- `_setup_command_watcher()` called from `on_mount()` - starts a timer
- `_check_for_commands()` - polls command file, executes if new
- `_execute_command(action, value)` - maps actions to existing methods
- `_update_state_file()` - called after each state change to write current question

**Key changes:**
- Add timer-based polling using Textual's `set_interval()` in `on_mount()`
- Update `_save_app_state()` to include `current_question` and `human_scores`
- Add `_execute_remote_command()` method to dispatch commands

---

### 4. State File Enhancement

**File:** `.annotator_state.json` (already exists, enhance it)

Current:
```json
{"model": "...", "response_idx": 0}
```

Enhanced:
```json
{
  "model": "...",
  "response_idx": 0,
  "current_question": "q1",
  "total_responses": 50,
  "human_scores": {"q1": "Yes", "q2": "1", ...},
  "timestamp": "2026-03-13T..."
}
```

---

### 5. Register Router in Main App

**File:** `packages/backend/src/moralbench_api/main.py`

Add `from .routes import tui` and `app.include_router(tui.router, prefix="/api")`

---

### Files to Create/Modify

| File | Action |
|------|--------|
| `packages/backend/src/moralbench_api/routes/tui.py` | **Create** - New router for TUI commands |
| `packages/backend/src/moral_bench/annotate_tui.py` | **Modify** - Add command polling and state updates |
| `packages/backend/src/moralbench_api/main.py` | **Modify** - Register new router |
| `.annotator_commands.json` | **Auto-created** - Command queue file |

---

### API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tui/command` | POST | Send command to TUI |
| `/api/tui/state` | GET | Get current TUI state |

---

### Testing

After implementation:
1. Start the TUI: `uv run annotate-tui`
2. Test via curl: `curl -X POST http://localhost:8000/api/tui/command -d '{"action":"next_question"}'`
3. Verify TUI responds to command within ~200ms