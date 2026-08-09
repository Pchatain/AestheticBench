"""Inspect human annotations next to the LLM judge's grade, item by item.

Shows, for each annotated response: the question, which model produced the
response, when you annotated it, your score and reasoning, and the judge's score
and reasoning trace.

Usage:
    uv run python scripts/inspect_annotations.py                     # q1_2, all items
    uv run python scripts/inspect_annotations.py -g q2               # a different grader
    uv run python scripts/inspect_annotations.py -g q1_1 --disagree  # only disagreements
    uv run python scripts/inspect_annotations.py --response-id 385   # one response
    uv run python scripts/inspect_annotations.py -g q1 --full        # superseded q1, still readable
"""

import argparse
import sqlite3
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "backend" / "src"))

from moral_bench.question_specs import SPECS, get_spec  # noqa: E402

DB_PATH = Path(__file__).parent.parent / "moralbench.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalise_human(value):
    """Human q1 answers are stored as "Yes"/"No" text; everything else is an int."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("yes", "y"):
        return 1
    if text in ("no", "n"):
        return 0
    try:
        return int(text)
    except ValueError:
        return None


def wrap(text, indent, width, full):
    if not text:
        return f"{' ' * indent}(none)"
    text = " ".join(str(text).split())
    if not full and len(text) > 600:
        text = text[:600] + " ..."
    return textwrap.fill(
        text, width=width, initial_indent=" " * indent, subsequent_indent=" " * indent
    )


def fetch(conn, grader_id):
    """Annotations joined to their response, question and grade.

    Joins on model as well as response_id: the pre-Q1-Q4 annotations were
    imported with response_id set to a per-question index, so without the model
    check they attach to unrelated responses.
    """
    return conn.execute(
        """SELECT a.response_id, a.model, a.annotator, a.created_at, a.updated_at,
                  a.q1_score, a.q1_1_score, a.q1_2_score,
                  a.q2_score, a.q3_score, a.q4_score,
                  a.q4_1_score, a.q4_2_score, a.q4_3_score, a.q4_4_score,
                  a.q1_reasoning, a.q1_1_reasoning, a.q1_2_reasoning,
                  a.q2_reasoning, a.q3_reasoning, a.q4_reasoning,
                  a.notes,
                  q.question_text, q.topic,
                  r.response_text,
                  g.score AS judge_score, g.reasoning AS judge_reasoning,
                  g.grader_model, g.grader_version, g.created_at AS graded_at
           FROM annotations a
           JOIN responses r ON r.id = a.response_id AND r.model = a.model
           JOIN questions q ON q.id = r.question_id
           LEFT JOIN grades g ON g.response_id = a.response_id AND g.grader_id = ?
           ORDER BY a.created_at""",
        (grader_id,),
    ).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Legacy graders stay selectable: q1's grades and annotations are still in
    # the database and are the record of why it was split into q1_1/q1_2.
    parser.add_argument("-g", "--grader", default="q1_2", choices=sorted(SPECS),
                        help="which question to inspect (default: q1_2)")
    parser.add_argument("--disagree", action="store_true", help="only items where human and judge differ")
    parser.add_argument("--response-id", type=int, help="show a single response id")
    parser.add_argument("--full", action="store_true", help="do not truncate long text")
    parser.add_argument("--show-response", action="store_true", help="include the graded model response itself")
    parser.add_argument("--width", type=int, default=100)
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        raise SystemExit(1)

    spec = get_spec(args.grader)
    conn = connect()
    rows = fetch(conn, args.grader)

    human_col = f"{args.grader}_score"
    reasoning_col = f"{args.grader}_reasoning"

    shown = agree = disagree = ungraded = 0
    print(f"\n{'=' * args.width}")
    print(f"  {args.grader} - {spec.name}   ({spec.score_hint})")
    if spec.notes:
        print(f"  {spec.notes}")
    print(f"{'=' * args.width}")

    for row in rows:
        if args.response_id and row["response_id"] != args.response_id:
            continue

        human = normalise_human(row[human_col])
        judge = normalise_human(row["judge_score"])
        if human is None:
            continue
        if judge is None:
            ungraded += 1
        elif human == judge:
            agree += 1
        else:
            disagree += 1

        if args.disagree and (judge is None or human == judge):
            continue

        shown += 1
        verdict = "no grade yet" if judge is None else ("AGREE" if human == judge else "DISAGREE")
        print(f"\n{'-' * args.width}")
        print(f"[{verdict}]  response_id={row['response_id']}  topic={row['topic']}")
        print(f"  question       : {row['question_text']}")
        print(f"  response model : {row['model']}")
        print(f"  annotated by   : {row['annotator'] or '(unknown)'} on {str(row['created_at'])[:19]}")
        if row["updated_at"] and str(row["updated_at"])[:19] != str(row["created_at"])[:19]:
            print(f"  last edited    : {str(row['updated_at'])[:19]}")
        graded_at = str(row["graded_at"])[:19] if row["graded_at"] else "-"
        print(f"  graded by      : {row['grader_model'] or '(not recorded)'} on {graded_at}"
              f"  version={row['grader_version'] or '-'}")

        print(f"\n  HUMAN score : {row[human_col]}   ->  {human}")
        print(wrap(row[reasoning_col], 4, args.width, args.full))
        print(f"\n  JUDGE score : {row['judge_score']}")
        print(wrap(row["judge_reasoning"], 4, args.width, args.full))

        if row["notes"]:
            print(f"\n  notes:")
            print(wrap(row["notes"], 4, args.width, args.full))
        if args.show_response:
            print(f"\n  GRADED RESPONSE:")
            print(wrap(row["response_text"], 4, args.width, args.full))

    print(f"\n{'=' * args.width}")
    total = agree + disagree + ungraded
    print(f"  shown {shown}  |  of {total} annotated: {agree} agree, {disagree} disagree, {ungraded} ungraded")
    print(f"{'=' * args.width}\n")
    conn.close()


if __name__ == "__main__":
    main()
