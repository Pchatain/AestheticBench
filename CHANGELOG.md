# Changelog

## 2026-08-17

### Changed
- **Renamed the project from MoralBench to AestheticBench.** The benchmark
  measures whether models commit to aesthetic judgements; the old name described
  a different project. Entries below this one predate the rename and keep the old
  identifiers as a record.

  | Old | New |
  | --- | --- |
  | `moral_bench` | `aesthetic_bench` |
  | `moralbench_api` | `aestheticbench_api` |
  | `moralbench` / `moralbench-api` (distributions) | `aestheticbench` / `aestheticbench-api` |
  | `moralbench-ui` (npm) | `aestheticbench-ui` |
  | `MORALBENCH_WORKERS`, `MORALBENCH_RESULTS_DIR` | `AESTHETICBENCH_WORKERS`, `AESTHETICBENCH_RESULTS_DIR` |
  | `moralbench.db` | `aestheticbench.db` |
  | `moralbench-*` localStorage keys | `aestheticbench-*` |

  Grader IDs, database columns and stored results are **unchanged** — they
  describe the measurement, not the product.

### Migration
- Rename your local database: `mv moralbench.db aestheticbench.db`.
- Update `MORALBENCH_*` to `AESTHETICBENCH_*` in `.env.local` and any shell
  profile. `AESTHETICBENCH_RESULTS_DIR` is read at import time, so a stale
  variable surfaces as a `KeyError` at test collection.
- Frontend UI state (selected model, collapsed panels) resets once, because the
  localStorage key prefix changed.

- Rewrote `README.md` around what the benchmark measures, and corrected three
  stale sections: a results path that did not exist, instructions referencing the
  removed `prompts/v1.csv`, and stray `droid --resume` lines.

## 2026-02-08

### Added
- **Human Judge Agreement Module** (`packages/backend/src/moral_bench/human_judge_agreement.py`)
  - Load human annotations from JSON into SQLite database
  - Compute Cohen's kappa between human annotations and automated grades
  - Compute inter-model agreement (model vs model) on Q1-Q4 and preference graders
  - Generate interactive Plotly visualizations (heatmaps, bar charts, confusion matrices)
  - Generate markdown summary reports

- **Annotations table** in database schema (`database.py`)
  - Store human annotations with preference/justification scores and reasoning

- **`db agreement` CLI command** with options:
  - `--json` - Load annotations from JSON file
  - `--inter-model` - Compute agreement between different models
  - `--plots` - Generate Plotly HTML visualizations
  - `--graders` - Specify which graders to analyze (default: q1,q2,q3,q4)
  - `--output` - Output directory for plots and reports

- Added `scikit-learn` dependency for Cohen's kappa computation
- Added `plotly` and `kaleido` dependencies for visualizations

### Usage
```bash
# Load annotations and compute human-model agreement
uv run python main.py db agreement --json path/to/annotations.json

# Compute inter-model agreement with plots
uv run python main.py db agreement --inter-model --plots

# Full analysis with all graders
uv run python main.py db agreement --json annotations.json --inter-model --plots --graders "q1,q2,q3,q4,preference1,preference2"
```

---

- `ScoringService` in `packages/backend/src/moralbench_api/services/scoring.py`
  - Computes aggregate statistics (mean, median, std dev, error rate) per model across Q1-Q4
  - Question-level comparison across models
- `compute-scores` CLI command in `main.py`
  - Default: aggregate stats per model → `model_scores.csv`
  - `--by-question` flag: question-by-question comparison across models
  
### Usage
```bash
# Aggregate stats per model
uv run python main.py compute-scores grades_summary.csv -o model_scores.csv

# Per-question comparison across models
uv run python main.py compute-scores grades_summary.csv --by-question -o question_comparison.csv
```
