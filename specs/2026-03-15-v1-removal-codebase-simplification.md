
## Findings & Fixes

### 1. V1 References to Clean Up

| File | Line | Issue | Fix |
|------|------|-------|-----|
| `csv_cleaner.py:162` | `combined_v1.csv` hardcoded | Change to `combined.csv` (version-agnostic) |
| `discovery.py:248` | Docstring says `prompts/v1.csv` | Update to `prompts/v2.tsv` |
| `discovery.py:252` | Docstring says `results/v1/responses` | Update to `results/v2/responses` |

### 2. Duplicated Utility Functions (High Impact)

**5 functions** are copy-pasted between `results.py` and `experiments.py`:
- `get_openrouter_headers()`
- `parse_model_from_filename()`
- `parse_graded_timestamp()`
- `get_latest_graded_files()`
- `load_csv()`

Plus the module-level constants `RESULTS_DIR`, `DATA_DIR`, `GRADES_DIR` are duplicated.

**Fix:** Create `packages/backend/src/moralbench_api/routes/_shared.py` containing all shared functions and constants. Both `results.py` and `experiments.py` import from there.

### 3. Repetitive Score Accumulation in `results.py`

`get_grades_summary` has 7 nearly identical try/parse/accumulate blocks for each score type. 

**Fix:** Extract a helper like `_accumulate_score(scores_dict, key, raw_value)` and call it 7 times with the column name and dict key.

### 4. Items Reviewed but NOT Fixing (false positives)

- **Response parsing in `experiments.py`** vs `Grader.parse()` in `grading.py` - These serve different purposes (API-layer quick parse vs structured grading with retries). Keeping separate is fine.
- **Grader subclass duplication** (`WhimsicalGrader`, `FactualDepthGrader`, etc. have similar `parse`/`validate`) - These are already structured well via the `Grader` ABC. Parameterizing further would reduce readability for minimal gain.
- **Sequential API calls in `run_multi_question_experiment`** - Could use `asyncio.gather`, but the current sequential approach is simpler and less likely to hit rate limits. Not worth the complexity.
- **OpenRouter API `/v1/` URLs** - These are the actual API endpoint version, not our prompt version. No change needed.
