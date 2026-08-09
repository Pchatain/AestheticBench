"""Grades are keyed on (response_id, grader_id, grader_model).

Before that, a second grader model's opinion silently REPLACEd the first, and
there was no test that would have caught it.
"""

import pytest

from moral_bench.database import MoralBenchDB


@pytest.fixture
def db(tmp_path):
    database = MoralBenchDB(tmp_path / "test.db")
    question_id = database.add_question("Test", "Is A or B better?")
    response_id = database.add_response(question_id, "some/model", "A is better.", 0)
    return database, response_id


def test_two_grader_models_coexist(db):
    database, response_id = db
    database.add_grade(response_id, "q1_2", "1", "hedges", grader_model="model/one")
    database.add_grade(response_id, "q1_2", "0", "does not hedge", grader_model="model/two")

    grades = database.get_grades(response_id=response_id)
    assert len(grades) == 2
    assert {g.grader_model for g in grades} == {"model/one", "model/two"}
    assert {g.score for g in grades} == {"0", "1"}


def test_same_grader_model_still_replaces(db):
    """Re-grading with the same model should update, not accumulate duplicates."""
    database, response_id = db
    database.add_grade(response_id, "q1_2", "1", "first", grader_model="model/one")
    database.add_grade(response_id, "q1_2", "0", "second", grader_model="model/one")

    grades = database.get_grades(response_id=response_id)
    assert len(grades) == 1
    assert grades[0].score == "0"


def test_ungraded_is_grader_model_aware(db):
    database, response_id = db
    database.add_grade(response_id, "q1_2", "1", "", grader_model="model/one")

    # Already graded by someone, so the default view considers it done.
    assert database.get_ungraded_responses("q1_2") == []
    # But not yet graded by model/two.
    pending = database.get_ungraded_responses("q1_2", grader_model="model/two")
    assert [r.id for r, _q in pending] == [response_id]
    assert database.get_ungraded_responses("q1_2", grader_model="model/one") == []


def test_agreement_join_does_not_multiply_rows(db):
    """Several grader models on one response must not duplicate the annotation."""
    database, response_id = db
    database.add_annotation(
        annotation_id="ann-1",
        response_id=response_id,
        model="some/model",
        q1_2_score=1,
    )
    for grader_model in ("model/one", "model/two", "model/three"):
        database.add_grade(response_id, "q1_2", "1", "", grader_model=grader_model)

    rows = database.get_annotations_with_grades(valid_only=True)
    assert len(rows) == 1, "annotation duplicated once per grader model"
    assert rows[0]["q1_2_score"] == "1"

    filtered = database.get_annotations_with_grades(
        valid_only=True, grader_model="model/two"
    )
    assert len(filtered) == 1
