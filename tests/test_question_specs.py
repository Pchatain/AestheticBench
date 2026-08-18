"""Keep question_specs.SPECS in step with the grader classes.

The scale of each grader was previously restated in several modules with nothing
checking they agreed. These tests fail if the canonical table and the grader
classes drift apart.
"""

import pytest

from aestheticbench.benchmark.grading import GraderRegistry
from aestheticbench.benchmark.rubric import SPECS, get_spec


@pytest.mark.parametrize("grader_id", sorted(SPECS))
def test_column_names_match_grader_classes(grader_id):
    """column_name is referenced by the frontend, API and old result files."""
    grader = GraderRegistry.get_grader(grader_id)
    spec = SPECS[grader_id]
    assert grader.column_name == spec.column_name
    assert grader.reasoning_column_name == spec.reasoning_column_name


@pytest.mark.parametrize("grader_id", sorted(SPECS))
def test_validate_agrees_with_spec(grader_id):
    """The grader class and the spec must accept and reject the same scores."""
    grader = GraderRegistry.get_grader(grader_id)
    spec = SPECS[grader_id]
    for candidate in (-2, -1, 0, 1, 2, 3, 4, 5, 6):
        assert grader.validate(candidate) == spec.validate(candidate), (
            f"{grader_id} disagrees on score {candidate}: "
            f"class={grader.validate(candidate)} spec={spec.validate(candidate)}"
        )


@pytest.mark.parametrize("grader_id", sorted(SPECS))
def test_prompt_states_the_scale(grader_id):
    """Without an explicit scale, models guess 1-5 and fail validation."""
    grader = GraderRegistry.get_grader(grader_id)
    prompt = grader.construct_prompt("Is A or B better?", "Some response.")
    assert "The score must be" in prompt
    assert SPECS[grader_id].score_hint in prompt


def test_legacy_relativism_is_the_inverse_of_q1():
    """Guard the polarity trap: legacy 1 = engages, q1 1 = rejects premise."""
    assert "ENGAGES" in get_spec("relativism").notes
    assert "rejects the premise" in get_spec("q1").notes


def test_unknown_grader_has_no_spec():
    assert get_spec("custom") is None
