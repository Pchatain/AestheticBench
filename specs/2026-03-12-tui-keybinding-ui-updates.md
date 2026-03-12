
## Changes to `annotate_tui.py`

### 1. Replace function key bindings with letter-based keys

Current → New mapping:

| Action | Old Key | New Key | Rationale |
|---|---|---|---|
| Prev Question | F1 | `ctrl+a` | Left side of keyboard |
| Next Question | F2 | `ctrl+d` | Right side, next to prev |
| Save | F3 | `ctrl+s` | Standard save shortcut |
| Toggle LLM | F4 | `ctrl+l` | L for LLM |
| Skip Response | F5 | `ctrl+k` | K for skip |
| Filter | F6 | `ctrl+f` | F for filter |
| Prev Response | F7 | `ctrl+left` | Arrow-based, left for prev |
| Next Response | F8 | `ctrl+right` | Arrow-based, right for next |
| Help | F9 | `ctrl+h` | H for help |
| Model Select | Escape | Escape | Keep as-is |

Note: Prev/Next pairs are now spatially consistent (prev=left, next=right).

### 2. Add Prev/Next Response buttons in the header

Add two buttons (`< Prev` and `Next >`) in the `#response-header` Horizontal container, flanking the response index input. Wire them to `action_prev_response` and `action_next_response`.

### 3. Make progress dots clickable

Replace the `Static` widget for `#progress-dots` with clickable elements. Each dot will be a small `Button` or we'll use `on_click` with coordinate math on a `Static` to determine which dot was clicked and jump to that response index.

Most practical approach: render each dot as a small `Button` widget inside a `Horizontal` container (or use a custom widget with `on_click` that calculates dot index from click position). Given up to 500 dots, using coordinate math on a single `Static` with `on_click` is more performant.

### 4. Add "Back to Model Select" button

Add a visible `Button("← Models", id="back-to-model-btn")` in the response header area. Wire it to `action_back_to_model`.

### 5. Save/resume application state

- On model load + response navigation, write `{"model": "...", "response_idx": N}` to `.annotator_state.json` in the project root.
- On app mount, if the state file exists, pre-fill the model input and auto-load to the saved response index.
- The state file path: `DB_PATH.parent / ".annotator_state.json"` (same directory as `moralbench.db`).

### 6. Update shortcuts panel text

Update the shortcuts panel Static widget to reflect the new keybindings.
