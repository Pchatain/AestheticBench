# Changelog

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
