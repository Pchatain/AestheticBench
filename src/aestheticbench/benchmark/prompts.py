"""Grader prompt text, loaded from prompts/graders/.

The prompts are data, not code. Each grader's text lives in
``prompts/graders/<grader_id>.md`` - the earlier generation under
``prompts/graders/legacy/`` - and this module is the only reader of that
directory. To change what a grader asks, edit the file; to add a grader, add
a file here, a ``QuestionSpec`` in rubric.py, and a class in grading.py.

Every grader prompt is sent with a JSON output instruction asking for
``{"reasoning", "score"}``; see ``Grader.construct_prompt`` in grading.py.
The scale each grader scores on is not here - it is in rubric.py, so the
prompt text and the validation can be read side by side but cannot drift.
"""

from functools import lru_cache

from ..paths import GRADER_PROMPTS_DIR

# Graders that reuse another grader's text rather than carrying a copy.
_ALIASES = {"justification": "q4"}


@lru_cache(maxsize=None)
def load_grader_prompt(grader_id: str) -> str:
    """The prompt text for one grader, exactly as it is sent to the judge."""
    grader_id = _ALIASES.get(grader_id, grader_id)
    for candidate in (
        GRADER_PROMPTS_DIR / f"{grader_id}.md",
        GRADER_PROMPTS_DIR / "legacy" / f"{grader_id}.md",
    ):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").rstrip("\n")
    raise FileNotFoundError(
        f"No prompt file for grader {grader_id!r} under {GRADER_PROMPTS_DIR}"
    )


def available_grader_ids() -> list[str]:
    """Every grader that has a prompt file, current generation first."""
    current = sorted(p.stem for p in GRADER_PROMPTS_DIR.glob("*.md"))
    legacy = sorted(p.stem for p in (GRADER_PROMPTS_DIR / "legacy").glob("*.md"))
    return current + legacy


# ---- earlier generation, named as grading.py has always imported them --------
GRADER_PREFERENCE_PROMPT_1 = load_grader_prompt("preference1")  # -1 / 0 / 1
GRADER_PREFERENCE_PROMPT_2 = load_grader_prompt("preference2")  # continuous [-1, 1]
GRADER_JUSTIFICATION_PROMPT = load_grader_prompt("q4")  # 1-5; expects a preference score as context
GRADER_RELATIVISM_PROMPT = load_grader_prompt("relativism")  # 0 / 1
GRADER_WHIMSICAL_PROMPT = load_grader_prompt("whimsical")  # 1-5
GRADER_FACTUAL_DEPTH_PROMPT = load_grader_prompt("factual_depth")  # 1-5

# ---- the q-series ------------------------------------------------------------
# q1 asked two things at once ("rejects the premise AND appeals to relativism"),
# so a response that hedged but still answered was scored 0 even when the
# grader had found the relativism. q1_1 and q1_2 split those halves apart; q1
# is kept only so its existing grades stay readable.
_QUESTION_META: dict[str, tuple[str, str]] = {
    # grader_id: (display name, output_type)
    "q1": ("Relativism", "binary"),
    "q1_1": ("Premise Rejection", "binary"),
    "q1_2": ("Relativism Appeal", "binary"),
    "q2": ("Preference", "ternary"),
    "q3": ("Evidence", "ternary"),
    "q4_1": ("Factual Depth", "binary"),
    "q4_2": ("Specificity", "binary"),
    "q4_3": ("Synthesis", "binary"),
    "q4_4": ("Consistency", "binary"),
}

DEFAULT_QUESTIONS: dict[str, dict[str, str]] = {
    grader_id: {"name": name, "prompt": load_grader_prompt(grader_id), "output_type": output_type}
    for grader_id, (name, output_type) in _QUESTION_META.items()
}
