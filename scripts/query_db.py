"""Sample queries against the AestheticBench SQLite database.

Usage:
    uv run python scripts/query_db.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "aestheticbench.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# 1. How many unique prompts do we have?
# ---------------------------------------------------------------------------
def unique_prompts():
    print_section("Unique prompts")
    conn = connect()
    row = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()
    print(f"Total unique prompts: {row['n']}")

    # Breakdown by topic
    rows = conn.execute(
        "SELECT topic, COUNT(*) AS n FROM questions GROUP BY topic ORDER BY n DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['topic']}: {r['n']}")
    conn.close()


# ---------------------------------------------------------------------------
# 2. For a given prompt, all model responses + metadata
# ---------------------------------------------------------------------------
def responses_for_prompt(question_text: str | None = None):
    print_section("Model responses for a prompt")
    conn = connect()

    if question_text is None:
        # Pick the first question as a demo
        question_text = conn.execute(
            "SELECT question_text FROM questions LIMIT 1"
        ).fetchone()["question_text"]

    print(f"Prompt: {question_text!r}\n")

    rows = conn.execute(
        """SELECT r.model, r.run_index, r.response_text, r.created_at
           FROM responses r
           JOIN questions q ON r.question_id = q.id
           WHERE q.question_text = ?
           ORDER BY r.model, r.run_index""",
        (question_text,),
    ).fetchall()

    for r in rows:
        snippet = r["response_text"][:120].replace("\n", " ")
        print(f"  [{r['model']}] run={r['run_index']}  {r['created_at']}")
        print(f"    {snippet}...")
    print(f"\n  Total responses: {len(rows)}")
    conn.close()


# ---------------------------------------------------------------------------
# 3. For a given prompt, all grades across grader models / grader IDs
# ---------------------------------------------------------------------------
def grades_for_prompt(question_text: str | None = None):
    print_section("Grades for a prompt (all graders × all models)")
    conn = connect()

    if question_text is None:
        question_text = conn.execute(
            "SELECT question_text FROM questions LIMIT 1"
        ).fetchone()["question_text"]

    print(f"Prompt: {question_text!r}\n")

    rows = conn.execute(
        """SELECT r.model AS respondent_model,
                  g.grader_id, g.grader_model, g.score, g.reasoning,
                  g.grader_version, g.created_at
           FROM grades g
           JOIN responses r ON g.response_id = r.id
           JOIN questions q ON r.question_id = q.id
           WHERE q.question_text = ?
           ORDER BY r.model, g.grader_id""",
        (question_text,),
    ).fetchall()

    for r in rows:
        grader_model = r["grader_model"] or "unknown"
        reasoning_snippet = (r["reasoning"] or "")[:80].replace("\n", " ")
        print(f"  [{r['respondent_model']}] grader={r['grader_id']} grader_model={grader_model} score={r['score']}")
        if reasoning_snippet:
            print(f"    reasoning: {reasoning_snippet}...")
    print(f"\n  Total grades: {len(rows)}")
    conn.close()


# ---------------------------------------------------------------------------
# 4. Which grader prompts were used for a given grader_id?
# ---------------------------------------------------------------------------
def grader_prompts_used(grader_id: str = "q1"):
    print_section(f"Distinct grader prompts for grader_id='{grader_id}'")
    conn = connect()

    rows = conn.execute(
        """SELECT grader_prompt, grader_model, COUNT(*) AS n
           FROM grades
           WHERE grader_id = ?
           GROUP BY grader_prompt, grader_model
           ORDER BY n DESC""",
        (grader_id,),
    ).fetchall()

    for r in rows:
        prompt_preview = (r["grader_prompt"] or "NULL")[:100].replace("\n", " ")
        grader_model = r["grader_model"] or "unknown"
        print(f"  model={grader_model}  count={r['n']}")
        print(f"    prompt: {prompt_preview}...")
    print(f"\n  Distinct (prompt, model) combos: {len(rows)}")
    conn.close()


# ---------------------------------------------------------------------------
# 5. All models we have responses for
# ---------------------------------------------------------------------------
def list_models():
    print_section("Models with responses")
    conn = connect()
    rows = conn.execute(
        """SELECT model, COUNT(*) AS n_responses
           FROM responses
           GROUP BY model
           ORDER BY n_responses DESC"""
    ).fetchall()
    for r in rows:
        print(f"  {r['model']}: {r['n_responses']} responses")
    conn.close()


# ---------------------------------------------------------------------------
# 6. Grade distribution for a grader across all models
# ---------------------------------------------------------------------------
def grade_distribution(grader_id: str = "q2"):
    print_section(f"Grade distribution for grader_id='{grader_id}' by model")
    conn = connect()

    rows = conn.execute(
        """SELECT r.model, g.score, COUNT(*) AS n
           FROM grades g
           JOIN responses r ON g.response_id = r.id
           WHERE g.grader_id = ?
           GROUP BY r.model, g.score
           ORDER BY r.model, g.score""",
        (grader_id,),
    ).fetchall()

    current_model = None
    for r in rows:
        if r["model"] != current_model:
            current_model = r["model"]
            print(f"\n  {current_model}:")
        print(f"    score={r['score']}: {r['n']}")
    conn.close()


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run 'uv run python main.py db migrate' first to populate it.")
        raise SystemExit(1)

    unique_prompts()
    list_models()
    responses_for_prompt()
    grades_for_prompt()
    grader_prompts_used()
    grade_distribution()
