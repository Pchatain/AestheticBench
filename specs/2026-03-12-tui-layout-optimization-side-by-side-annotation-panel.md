## Problem

The TUI annotation view (`annotate_tui.py`) stacks everything vertically in the left panel:
1. Response header (nav buttons: Models, Prev, jump-to input, Next)
2. Progress dots
3. Response text (scrollable)
4. Question nav buttons (Q1, Q2, Q3, Q4, Q4.1-Q4.4)
5. Annotation panel (question label, LLM grade, score input, reasoning textarea)

This means the response text area is squeezed vertically between the header and the annotation inputs below it, leaving limited space to read the response.

## Proposed Change

Move the annotation panel and question nav buttons to a **right-side column** alongside the response text, instead of stacking them below it. Merge the shortcuts panel into this right column too.

### New layout:
```
Header
[← Models] [← Prev] [Response X / total] [Next →]
[progress dots]
+---------------------------------------+----------------------------+
| Response panel (scrollable)           | [Q1][Q2][Q3][Q4][Q4.1]... |
| Topic: ...                            | Q1 - Relativism (Yes/No)  |
| Question: ...                         | LLM Score: Yes             |
| Response: ...                         | Your Score: [___]          |
|    (gets full remaining height)       | Reasoning: [________]      |
|                                       |                            |
|                                       | Shortcuts:                 |
|                                       | ^A/^D Prev/Next Q          |
|                                       | ^S Save  ^L LLM  ...      |
+---------------------------------------+----------------------------+
Footer
```

### Changes in `annotate_tui.py`:
1. **Restructure `compose()`**: Move `#question-nav` and `#annotation-panel` out of `#left-panel` and into a new `#right-panel` Vertical that sits alongside `#response-scroll` inside the `Horizontal#main-content`. Merge shortcuts into the right panel.
2. **Update CSS**: Give `#right-panel` a fixed width (~35-40 columns), let `#response-scroll` take `1fr` of remaining width and full height.
3. **Remove the separate `#shortcuts-panel`** since its content moves into the right panel below the annotation inputs.
4. **Keep** response-header and progress-dots above the two-column layout (they stay full-width).

This gives the response text the full height of the terminal minus header/footer/nav row, significantly increasing visible text.