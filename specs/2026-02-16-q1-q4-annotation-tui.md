## Q1-Q4 Annotation TUI

### Overview
A Textual-based TUI for human annotation of Q1-Q4, comparing your grades against the LLM judge.

### Key Bindings
| Key | Action |
|-----|--------|
| `Tab` | Next question (Q1→Q2→Q3→Q4) |
| `Shift+Tab` | Previous question |
| `Enter` | Save current annotation |
| `Esc` | Return to model selector |
| `?` | Show prompt/criteria for current question |
| `l` | Toggle LLM reasoning visibility |
| `s` | Skip current response |
| `f` | Toggle filter (all / unannotated only) |
| `Ctrl+N` | Next response |
| `Ctrl+P` | Previous response |

### Flow
1. **Model selector**: Autocomplete textbox suggesting available models
2. **Annotation view**: Shows question, model response, current Q (1-4)
   - LLM score visible; LLM reasoning hidden by default (press `l` to reveal)
   - Input field for your score + optional reasoning textarea
3. **Summary screen** (after Q4): Side-by-side comparison of your 4 scores vs LLM scores, press Enter to advance
4. **Filter toggle**: Switch between all responses / unannotated only

### Input Validation
- **Q1**: Yes/No (y/n)
- **Q2/Q3**: -1/0/1
- **Q4**: 1-5

### Implementation
1. **New file**: `packages/backend/src/moral_bench/annotate_tui.py`
2. **Add dependency**: `textual>=0.50.0` to backend's `pyproject.toml`
3. Uses existing `MoralBenchDB` for data access and persistence
4. Entry point: `uv run python -m moral_bench.annotate_tui`