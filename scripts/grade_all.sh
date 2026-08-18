#!/usr/bin/env bash
#
# grade_all.sh — Run LLM grading on all response files for all questions.
#
# This script grades every model's responses using the full question battery:
#
#   Q1      Relativism          (0/1)     Does the answer reject the premise?
#   Q2      Preference          (-1/0/1)  Which option does the response prefer?
#   Q3      Evidence            (-1/0/1)  Which option has stronger evidence?
#   Q4      Justification       (1-5)     Overall justification quality (aggregate)
#   Q4.1    Factual Depth       (0/1)     Does it include substantive facts?
#   Q4.2    Specificity         (0/1)     Are observations concrete & specific?
#   Q4.3    Synthesis           (0/1)     Does it synthesize considerations coherently?
#   Q4.4    Consistency         (0/1)     Is the conclusion consistent with evidence?
#
# The graded CSVs land in results/v2/grades/ and are automatically picked up
# by the web UI (Grade Explorer heatmaps, Analytics histograms, etc.).
#
# Usage:
#   ./scripts/grade_all.sh                         # grade all models, default grader
#   ./scripts/grade_all.sh --grader-model openai/gpt-5  # use a specific grader model
#   ./scripts/grade_all.sh --dry-run               # preview without grading
#
# Prerequisites:
#   - OPENROUTER_API_KEY must be set (in .env or environment)
#   - Response CSV files must exist in results/v2/responses/
#
# Note: Each run appends a timestamped graded CSV. The web UI always reads the
# latest graded file per model, so re-running is safe and non-destructive.
#
set -euo pipefail
cd "$(dirname "$0")/.."

GRADER_MODEL="${GRADER_MODEL:-openai/gpt-4o}"
DRY_RUN=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --grader-model)
      GRADER_MODEL="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="--dry-run"
      shift
      ;;
    -h|--help)
      head -30 "$0" | grep '^#' | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# All questions to grade
GRADERS="q1,q2,q3,q4,q4_1,q4_2,q4_3,q4_4"

echo "========================================"
echo "  AestheticBench — Grade All Questions"
echo "========================================"
echo ""
echo "Grader model:  $GRADER_MODEL"
echo "Questions:     $GRADERS"
echo "Response dir:  results/v2/responses/"
echo ""

# Find all response CSVs
RESPONSE_FILES=$(find results/v2/responses -name '*.csv' 2>/dev/null | sort)

if [[ -z "$RESPONSE_FILES" ]]; then
  echo "Error: No response files found in results/v2/responses/"
  exit 1
fi

FILE_COUNT=$(echo "$RESPONSE_FILES" | wc -l | tr -d ' ')
echo "Found $FILE_COUNT response file(s) to grade."
echo ""

# Grade each file
for FILE in $RESPONSE_FILES; do
  echo "────────────────────────────────────────"
  echo "Grading: $FILE"
  echo "────────────────────────────────────────"
  uv run aestheticbench grade "$FILE" \
    --graders "$GRADERS" \
    --grader-model "$GRADER_MODEL" \
    $DRY_RUN
  echo ""
done

echo "========================================"
echo "  Done!"
echo "========================================"
