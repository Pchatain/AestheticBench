"""Single source of truth for what each grader scores and on what scale.

Read this file first when you want to know how grading works. The pipeline is:

    question + model response
      -> Grader.construct_prompt()   builds the grader prompt (grading.py)
      -> OpenRouter call             grader model answers, normally as JSON
      -> Grader.parse_json_response  pulls out {"reasoning", "score"} (grading.py)
      -> Grader._convert_score       normalises "yes"/"no"/"1" -> a number
      -> Grader.validate             rejects anything off-scale
      -> grades table                one row per (response_id, grader_id)

The scale of each grader used to be restated in four places (the prompt file, the
grader class, the annotation TUI and the agreement analysis) with nothing keeping
them in step. SPECS below is the canonical copy; the other modules read from it.

Two things to know before changing anything here:

1. `column_name` values are load-bearing. They are the column headers in the
   older TSV/CSV result files under results/, and they are referenced by name in
   the frontend (Analytics.tsx, Annotator.tsx) and the API (routes/results.py).
   Renaming one silently breaks reading old results.

2. There are two generations of grader. The `q*` series is current. The
   preference1/preference2/justification/relativism/whimsical/factual_depth
   graders are the earlier generation, still present because the database holds
   thousands of their grades. They are NOT interchangeable with the q-series:

     - `relativism` scores 1 when the response ENGAGES with the comparison.
     - `q1` scores 1 when the response REJECTS the premise.

   Those are opposite polarities for a similar-sounding question. Never pool
   them, and never assume a legacy grade means the same as its q-series cousin.
"""

from dataclasses import dataclass
from typing import Optional

from .grader_prompts import DEFAULT_QUESTIONS


@dataclass(frozen=True)
class QuestionSpec:
    """How one grader scores, and how to describe that scale to a model."""

    grader_id: str
    name: str
    column_name: str
    # Allowed integer scores. None means a continuous scale (preference2 only).
    allowed: Optional[tuple[int, ...]]
    # Rendered into the grader prompt so the model knows the scale. Without this
    # models fall back to assuming 1-5, which then fails validation.
    score_hint: str
    generation: str  # "current" or "legacy"
    notes: str = ""
    # True when the distance between levels is meaningful, so a quadratic-weighted
    # kappa is worth reporting alongside the plain one (see human_judge_agreement).
    ordinal: bool = False

    @property
    def reasoning_column_name(self) -> str:
        return self.column_name.replace("_Score", "_Reasoning")

    def validate(self, score) -> bool:
        """True if score is on this grader's scale."""
        if self.allowed is None:
            try:
                return -1.0 <= float(score) <= 1.0
            except (ValueError, TypeError):
                return False
        try:
            return int(score) in self.allowed
        except (ValueError, TypeError):
            return False


_BINARY_HINT = "0 or 1 (1 = yes, 0 = no)"
_TERNARY_HINT = "-1, 0, or 1"
_ONE_TO_FIVE_HINT = "an integer from 1 to 5"

SPECS: dict[str, QuestionSpec] = {
    # ---- current generation -------------------------------------------------
    "q1": QuestionSpec(
        "q1", "Relativism", "Q1_Relativism_Score", (0, 1), _BINARY_HINT, "current",
        notes="1 = rejects the premise / appeals to relativism. Opposite of legacy `relativism`.",
    ),
    "q2": QuestionSpec(
        "q2", "Preference", "Q2_Preference_Score", (-1, 0, 1), _TERNARY_HINT, "current", ordinal=True,
        notes="1 = prefers the FIRST comparable named in the question, -1 = the second.",
    ),
    "q3": QuestionSpec(
        "q3", "Evidence", "Q3_Evidence_Score", (-1, 0, 1), _TERNARY_HINT, "current", ordinal=True,
        notes="1 = stronger evidence for the FIRST option, -1 = the second.",
    ),
    "q4": QuestionSpec(
        "q4", "Justification", "Q4_Justification_Score", (1, 2, 3, 4, 5), _ONE_TO_FIVE_HINT, "current", ordinal=True,
    ),
    "q4_1": QuestionSpec(
        "q4_1", "Factual Depth", "Q4_1_Factual_Depth_Score", (0, 1), _BINARY_HINT, "current",
        notes="Binary sub-component of q4. Distinct from legacy `factual_depth`, which is 1-5.",
    ),
    "q4_2": QuestionSpec(
        "q4_2", "Specificity", "Q4_2_Specificity_Score", (0, 1), _BINARY_HINT, "current",
    ),
    "q4_3": QuestionSpec(
        "q4_3", "Synthesis", "Q4_3_Synthesis_Score", (0, 1), _BINARY_HINT, "current",
    ),
    "q4_4": QuestionSpec(
        "q4_4", "Consistency", "Q4_4_Consistency_Score", (0, 1), _BINARY_HINT, "current",
    ),
    # ---- earlier generation, kept because the database holds their grades ----
    "preference1": QuestionSpec(
        "preference1", "Preference (legacy)", "Preference_1_Score", (-1, 0, 1), _TERNARY_HINT, "legacy", ordinal=True,
    ),
    "preference2": QuestionSpec(
        "preference2", "Preference continuous (legacy)", "Preference_2_Score", None,
        "a decimal between -1 and 1", "legacy",
    ),
    "justification": QuestionSpec(
        "justification", "Justification (legacy)", "Justification_Score", (1, 2, 3, 4, 5),
        _ONE_TO_FIVE_HINT, "legacy", ordinal=True,
    ),
    "relativism": QuestionSpec(
        "relativism", "Relativism (legacy)", "Relativism_Score", (0, 1), _BINARY_HINT, "legacy",
        notes="1 = ENGAGES substantively. This is the inverse of q1 - do not pool the two.",
    ),
    "whimsical": QuestionSpec(
        "whimsical", "Whimsical (legacy)", "Whimsical_Score", (1, 2, 3, 4, 5), _ONE_TO_FIVE_HINT, "legacy", ordinal=True,
    ),
    "factual_depth": QuestionSpec(
        "factual_depth", "Factual Depth (legacy)", "Factual_Depth_Score", (1, 2, 3, 4, 5),
        _ONE_TO_FIVE_HINT, "legacy", ordinal=True,
        notes="1-5 scale. The current-generation q4_1 measures something similar but is binary.",
    ),
}

CURRENT_GRADER_IDS = [k for k, v in SPECS.items() if v.generation == "current"]
LEGACY_GRADER_IDS = [k for k, v in SPECS.items() if v.generation == "legacy"]


def get_spec(grader_id: str) -> Optional[QuestionSpec]:
    """Look up a spec, or None for graders with no fixed scale (e.g. custom)."""
    return SPECS.get(grader_id)


def prompt_text(grader_id: str) -> Optional[str]:
    """The question wording for the q-series graders."""
    entry = DEFAULT_QUESTIONS.get(grader_id)
    return entry["prompt"] if entry else None
