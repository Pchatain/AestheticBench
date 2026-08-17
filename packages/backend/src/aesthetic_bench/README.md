# Backend source

Two packages live here, and the split matters.

## `aesthetic_bench/` — core library

Everything that knows how the benchmark works. No web framework, no HTTP layer.
Usable from the CLI (`main.py`), the TUI, and scripts.

| Module | Responsibility |
| --- | --- |
| `question_specs.py` | **Start here.** Single source of truth for every grader's scale, column name, and generation. |
| `grader_prompts.py` | Prompt text for each grader. |
| `grading.py` | Builds grader prompts, parses and validates judge responses. |
| `client.py` | OpenRouter client, with retries. |
| `config.py` | Env-driven config (`Config.from_env()`, `AESTHETICBENCH_WORKERS`). |
| `database.py` | SQLite access — `questions`, `responses`, `grades`, `annotations`. |
| `processor.py` | Batch inference over the question set. |
| `human_judge_agreement.py` | Cohen's kappa between humans and judges, and judge vs judge. |
| `annotate_tui.py` | Textual TUI for human annotation. |
| `csv_cleaner.py`, `text_utils.py`, `errors.py` | Supporting utilities. |

## `aestheticbench_api/` — REST layer

FastAPI app serving the React frontend. Routes under `routes/`, request/response
models under `schemas/`, orchestration under `services/`. It depends on
`aesthetic_bench`; nothing in `aesthetic_bench` may import from here.

Note that `routes/_shared.py` reads `AESTHETICBENCH_RESULTS_DIR` at **import**
time, so the variable must be set before the app — or the test suite — loads.

## Two generations of grader

The `q*` series (`q1_1`, `q1_2`, `q2`, `q3`, `q4`, `q4_1`–`q4_4`) is current. The
`preference1` / `preference2` / `justification` / `relativism` / `whimsical` /
`factual_depth` series is legacy, retained because the database holds thousands
of their grades.

They are not interchangeable. `relativism` scores 1 when a response **engages**
with the comparison; `q1` scores 1 when it **rejects** the premise — opposite
polarities for a similar-sounding question. Never pool them. See the module
docstring in `question_specs.py`.
