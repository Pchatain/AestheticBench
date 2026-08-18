# `aestheticbench` — the one Python package

| Directory | Responsibility |
| --- | --- |
| `benchmark/` | Runs the benchmark. `client.py` (OpenRouter, with retries), `config.py`, `run.py` (batch inference over the question set), `grading.py` (builds judge prompts, parses and validates answers), `rubric.py` (**start here** — every grader's scale, column name and generation), `prompts.py` (the only reader of `prompts/graders/`), `agreement.py` (Cohen's kappa, human vs judge and judge vs judge), `text_utils.py`, `errors.py`. |
| `labelling/` | `tui.py`, the Textual annotation TUI. `make tui`. |
| `store/` | `database.py` — SQLite: `questions`, `responses`, `grades`, `annotations`. |
| `api/` | FastAPI app for `web/`: `routes/`, `schemas/`, `services/`. `make backend`. |
| `cli/` | `main.py`, the `aestheticbench` command (`uv run aestheticbench --help`). |
| `paths.py` | Every filesystem anchor, resolved once. Nothing else may compute a path from `__file__`. |

`api/services/` and the top-level `run`/`grade`/`export-*` CLI commands are the
older CSV workflow under `results/v2/`; the `db` subcommands and `routes/annotations.py`
are the current SQLite one. Collapsing to one is the next job
(`specs/2026-08-18-repo-reorganization-plan.md`, phase 1).

## Two generations of grader

The `q*` series (`q1_1`, `q1_2`, `q2`, `q3`, `q4`, `q4_1`–`q4_4`) is current. The
`preference1` / `preference2` / `justification` / `relativism` / `whimsical` /
`factual_depth` series is legacy, retained because the database holds thousands
of their grades.

They are not interchangeable. `relativism` scores 1 when a response **engages**
with the comparison; `q1` scores 1 when it **rejects** the premise — opposite
polarities for a similar-sounding question. Never pool them. See the module
docstring in `benchmark/rubric.py`.
