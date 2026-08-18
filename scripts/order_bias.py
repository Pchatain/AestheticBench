"""Order-bias experiment: does swapping the two comparables change the verdict?

The top-line AestheticBench measure is q2 — did the model commit to a preference,
and to which side. On the existing 104-response set the judge scores +1 (prefers
the FIRST-named comparable) 56% of the time and -1 only 20%. That gap has two
possible causes and the benchmark currently cannot tell them apart:

  1. the questions are written with the "obvious" winner named first, or
  2. models have a position bias and simply favour whatever they read first.

This script separates them. Every sampled question is asked twice — once as
written ("forward") and once with the two [bracketed] entities swapped
("reversed") — and both responses are graded on q2 alone. Under hypothesis (1)
the *canonical* verdict (which named entity won) is stable across orientations.
Under hypothesis (2) the *raw* verdict (first vs second slot) is stable instead.

Scores are stored RAW, exactly as the grader emitted them: +1 always means "the
comparable printed first in the prompt that was actually sent". Canonicalisation
is a read-time operation (`_canonical`) so the stored grades stay comparable with
the q2 grades in the main `grades` table, which mean the same thing.

Everything lives in its own two tables. It deliberately does NOT write to
`questions`/`responses`: a reversed question added there would become a new
question for every model, and the next plain `db run` would silently start
collecting it.

    uv run --env-file .env.local python scripts/order_bias.py --dry-run
    uv run --env-file .env.local python scripts/order_bias.py --stage collect
    uv run --env-file .env.local python scripts/order_bias.py --stage grade
    uv run --env-file .env.local python scripts/order_bias.py --stage report
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import random
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "backend" / "src"))

from aesthetic_bench.client import OpenRouterClient  # noqa: E402
from aesthetic_bench.config import Config  # noqa: E402
from aesthetic_bench.grading import GraderRegistry  # noqa: E402
from aesthetic_bench.text_utils import strip_entity_brackets, swap_entities  # noqa: E402

# The four subject models, chosen to span the observed commit-vs-hedge range on
# the existing q2 grades (grok-4.6 hedges on 8% of questions, deepseek-v3.2 on
# 75%) while covering four different labs. Override with --models.
DEFAULT_MODELS = [
    "x-ai/grok-4.6",
    "anthropic/claude-opus-4.5",
    "openai/gpt-5.2",
    "deepseek/deepseek-v3.2",
]

# Two judges, both already used on the main `grades` table, where they agree
# exactly on q2 for 85% of 104 shared responses. Reusing them keeps this
# experiment's numbers comparable with the rest of the benchmark, and a
# disagreement here can be read against a known baseline rather than a fresh one.
DEFAULT_GRADER_MODELS = [
    "openai/gpt-5.2",
    "anthropic/claude-sonnet-4.5",
]

GRADER_ID = "q2"  # the preference question, and deliberately the only one
EXPERIMENT = "order-bias-v1"
DEFAULT_SEED = 20260818
ORIENTATIONS = ("forward", "reversed")


@dataclass(frozen=True)
class Item:
    """One question, sampled from prompts/v2.tsv and split into its two entities."""

    topic: str
    raw: str  # still carries the [brackets]
    entity_a: str  # named first in the forward orientation
    entity_b: str

    @property
    def key(self) -> str:
        """Stable identity for the question, independent of orientation."""
        return strip_entity_brackets(self.raw)

    def prompt(self, orientation: str) -> str:
        text = self.raw if orientation == "forward" else swap_entities(self.raw)
        return strip_entity_brackets(text)


# --------------------------------------------------------------------------- #
# schema
# --------------------------------------------------------------------------- #

SCHEMA = """
CREATE TABLE IF NOT EXISTS order_bias_responses (
    id INTEGER PRIMARY KEY,
    experiment TEXT NOT NULL,
    question_key TEXT NOT NULL,
    topic TEXT,
    entity_a TEXT NOT NULL,
    entity_b TEXT NOT NULL,
    orientation TEXT NOT NULL CHECK (orientation IN ('forward','reversed')),
    prompt_text TEXT NOT NULL,
    model TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment, question_key, model, orientation)
);
CREATE TABLE IF NOT EXISTS order_bias_grades (
    id INTEGER PRIMARY KEY,
    response_id INTEGER NOT NULL REFERENCES order_bias_responses(id),
    grader_id TEXT NOT NULL,
    grader_model TEXT NOT NULL,
    score INTEGER NOT NULL,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(response_id, grader_id, grader_model)
);
CREATE INDEX IF NOT EXISTS idx_ob_resp_model ON order_bias_responses(model);
CREATE INDEX IF NOT EXISTS idx_ob_grades_resp ON order_bias_grades(response_id);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


# --------------------------------------------------------------------------- #
# sampling
# --------------------------------------------------------------------------- #


def load_items(prompts_path: Path) -> list[Item]:
    """Every question in the TSV that has exactly two [bracketed] entities.

    A question without exactly two cannot be reversed — `swap_entities` returns
    it unchanged — so including one would silently contribute a matched pair of
    identical prompts and dilute the flip rate toward zero.
    """
    items: list[Item] = []
    skipped: list[str] = []
    with prompts_path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            raw = (row.get("Question") or "").strip()
            if not raw:
                continue
            entities = [m for m in _entities(raw)]
            if len(entities) != 2:
                skipped.append(raw)
                continue
            items.append(Item(row.get("Topic", "").strip(), raw, entities[0], entities[1]))
    if skipped:
        print(f"  note: skipped {len(skipped)} question(s) without exactly 2 [entities]")
        for q in skipped[:5]:
            print(f"    - {q[:70]}")
    return items


def _entities(text: str) -> list[str]:
    import re

    return re.findall(r"\[([^\]]*)\]", text)


def sample_items(items: list[Item], n: int, seed: int) -> list[Item]:
    """Deterministic sample. Sorted first so the seed fully determines the draw."""
    pool = sorted(items, key=lambda i: i.key)
    if n >= len(pool):
        return pool
    return sorted(random.Random(seed).sample(pool, n), key=lambda i: i.key)


# --------------------------------------------------------------------------- #
# stage: collect
# --------------------------------------------------------------------------- #


def stage_collect(con, items, models, workers, dry_run: bool) -> None:
    todo = []
    for model in models:
        for item in items:
            for orientation in ORIENTATIONS:
                if _has_response(con, item.key, model, orientation):
                    continue
                todo.append((model, item, orientation))

    print(f"\n[collect] {len(todo)} responses to gather "
          f"({len(models)} models x {len(items)} questions x 2 orientations, "
          f"minus {len(models) * len(items) * 2 - len(todo)} already present)")
    if dry_run:
        for model, item, orientation in todo[:6]:
            print(f"  {model:32s} {orientation:8s} {item.prompt(orientation)[:60]}")
        if len(todo) > 6:
            print(f"  ... and {len(todo) - 6} more")
        return
    if not todo:
        return

    config = Config.from_env()
    if workers is not None:
        config = config.with_workers(workers)

    with OpenRouterClient(config) as client:
        by_model = collections.defaultdict(list)
        for entry in todo:
            by_model[entry[0]].append(entry)
        for model, entries in by_model.items():
            if not client.verify_model(model, verbose=True):
                print(f"  x skipping unavailable model: {model}")
                continue
            prompts = [item.prompt(orientation) for _, item, orientation in entries]
            print(f"  {model}: {len(prompts)} prompts")
            results = client.batch_chat_completions(prompts, model)
            ok = err = 0
            for idx, _prompt, response in results:
                _, item, orientation = entries[idx]
                if not response:
                    err += 1
                    continue
                con.execute(
                    "INSERT OR IGNORE INTO order_bias_responses "
                    "(experiment, question_key, topic, entity_a, entity_b, orientation, "
                    " prompt_text, model, response_text) VALUES (?,?,?,?,?,?,?,?,?)",
                    (EXPERIMENT, item.key, item.topic, item.entity_a, item.entity_b,
                     orientation, item.prompt(orientation), model, response),
                )
                ok += 1
            con.commit()
            print(f"    ok={ok} errors={err}")


def _has_response(con, key: str, model: str, orientation: str) -> bool:
    return con.execute(
        "SELECT 1 FROM order_bias_responses WHERE experiment=? AND question_key=? "
        "AND model=? AND orientation=?",
        (EXPERIMENT, key, model, orientation),
    ).fetchone() is not None


# --------------------------------------------------------------------------- #
# stage: grade
# --------------------------------------------------------------------------- #


def stage_grade(con, grader_models, workers, dry_run: bool) -> None:
    grader = GraderRegistry.get_grader(GRADER_ID)
    rows = con.execute(
        "SELECT * FROM order_bias_responses WHERE experiment=?", (EXPERIMENT,)
    ).fetchall()

    plan = []
    for gm in grader_models:
        for row in rows:
            done = con.execute(
                "SELECT 1 FROM order_bias_grades WHERE response_id=? AND grader_id=? "
                "AND grader_model=?", (row["id"], GRADER_ID, gm),
            ).fetchone()
            if not done:
                plan.append((gm, row))

    print(f"\n[grade] {len(plan)} gradings to run "
          f"({len(rows)} responses x {len(grader_models)} judges, "
          f"grader_id={GRADER_ID!r} only)")
    if dry_run or not plan:
        return

    config = Config.from_env()
    if workers is not None:
        config = config.with_workers(workers)

    with OpenRouterClient(config) as client:
        by_judge = collections.defaultdict(list)
        for gm, row in plan:
            by_judge[gm].append(row)
        for gm, batch in by_judge.items():
            prompts = [
                grader.construct_prompt(r["prompt_text"], r["response_text"]) for r in batch
            ]
            print(f"  judge {gm}: {len(prompts)} gradings")
            results = client.batch_chat_completions(prompts, gm)
            ok = err = 0
            for idx, _p, raw in results:
                row = batch[idx]
                if not raw:
                    err += 1
                    continue
                success, score, reasoning, error = grader.grade(
                    row["prompt_text"], row["response_text"], raw
                )
                if not success:
                    err += 1
                    print(f"    ! {row['model']} {row['orientation']}: {error[:110]}")
                    continue
                con.execute(
                    "INSERT OR IGNORE INTO order_bias_grades "
                    "(response_id, grader_id, grader_model, score, reasoning) VALUES (?,?,?,?,?)",
                    (row["id"], GRADER_ID, gm, int(score), reasoning),
                )
                ok += 1
            con.commit()
            print(f"    ok={ok} errors={err}")


# --------------------------------------------------------------------------- #
# stage: report
# --------------------------------------------------------------------------- #


def _canonical(score: int, orientation: str) -> int:
    """Re-express a raw grade as a verdict about entity_a.

    Raw +1 means "the comparable printed first". In the reversed orientation the
    entity printed first is entity_b, so the sign has to be turned over before
    the two orientations can be compared at all. Getting this backwards would
    turn perfect consistency into a 100% flip rate, so it lives in one function.
    """
    return score if orientation == "forward" else -score


def _binom_p(k: int, n: int) -> float:
    """Two-sided exact binomial test against p=0.5. No scipy dependency."""
    if n == 0:
        return float("nan")
    def pmf(i):
        return math.comb(n, i) * 0.5 ** n
    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs + 1e-12))


def stage_report(con) -> None:
    rows = con.execute(
        "SELECT g.score, g.grader_model, r.orientation, r.model, r.question_key, "
        "       r.entity_a, r.entity_b, r.topic "
        "FROM order_bias_grades g JOIN order_bias_responses r ON r.id = g.response_id "
        "WHERE r.experiment=? AND g.grader_id=?", (EXPERIMENT, GRADER_ID),
    ).fetchall()
    if not rows:
        print("\n[report] nothing graded yet")
        return

    print(f"\n{'=' * 74}\nORDER-BIAS REPORT  ({EXPERIMENT}, grader_id={GRADER_ID})\n{'=' * 74}")
    print(f"graded responses: {len(rows)}")

    # ---- 1. raw first-slot preference ------------------------------------- #
    print("\n1. RAW slot preference — does the first-printed comparable win?")
    print("   (a balanced forward/reversed design has no reason to favour either")
    print("    slot; +1 and -1 rates that differ ARE the position bias)")
    print(f"\n   {'judge':<32}{'+1 (first)':>12}{'0 (hedge)':>12}{'-1 (second)':>13}{'p':>9}")
    for gm in sorted({r["grader_model"] for r in rows}):
        sub = [r["score"] for r in rows if r["grader_model"] == gm]
        c = collections.Counter(sub)
        committed = c[1] + c[-1]
        p = _binom_p(c[1], committed)
        print(f"   {gm:<32}{c[1]/len(sub):>11.0%}{c[0]/len(sub):>12.0%}"
              f"{c[-1]/len(sub):>13.0%}{p:>9.3f}")

    # ---- 2. canonical flip rate ------------------------------------------- #
    print("\n2. CANONICAL agreement — does the same entity win in both orientations?")
    print("   Each row is one (model, question, judge) triple graded both ways.")
    paired = collections.defaultdict(dict)
    meta = {}
    for r in rows:
        k = (r["model"], r["question_key"], r["grader_model"])
        paired[k][r["orientation"]] = r["score"]
        meta[k] = r
    complete = {k: v for k, v in paired.items() if len(v) == 2}
    print(f"   complete pairs: {len(complete)} of {len(paired)}")

    def classify(fwd, rev):
        cf, cr = _canonical(fwd, "forward"), _canonical(rev, "reversed")
        if cf == cr:
            return "stable-hedge" if cf == 0 else "stable-commit"
        if cf != 0 and cr != 0:
            return "SIGN FLIP"
        return "commit<->hedge"

    overall = collections.Counter(classify(v["forward"], v["reversed"]) for v in complete.values())
    tot = sum(overall.values())
    print()
    for label in ("stable-commit", "stable-hedge", "commit<->hedge", "SIGN FLIP"):
        print(f"   {label:<18}{overall[label]:>5}  {overall[label]/tot:>6.0%}")

    print("\n   by subject model:")
    print(f"   {'model':<32}{'n':>5}{'stable':>9}{'flip':>8}{'c<->h':>8}")
    for model in sorted({k[0] for k in complete}):
        sub = [classify(v["forward"], v["reversed"]) for k, v in complete.items() if k[0] == model]
        c = collections.Counter(sub)
        n = len(sub)
        stable = c["stable-commit"] + c["stable-hedge"]
        print(f"   {model:<32}{n:>5}{stable/n:>8.0%}{c['SIGN FLIP']/n:>8.0%}"
              f"{c['commit<->hedge']/n:>8.0%}")

    print("\n   by judge:")
    print(f"   {'judge':<32}{'n':>5}{'stable':>9}{'flip':>8}{'c<->h':>8}")
    for gm in sorted({k[2] for k in complete}):
        sub = [classify(v["forward"], v["reversed"]) for k, v in complete.items() if k[2] == gm]
        c = collections.Counter(sub)
        n = len(sub)
        stable = c["stable-commit"] + c["stable-hedge"]
        print(f"   {gm:<32}{n:>5}{stable/n:>8.0%}{c['SIGN FLIP']/n:>8.0%}"
              f"{c['commit<->hedge']/n:>8.0%}")

    # ---- 3. hedge rate by orientation -------------------------------------- #
    print("\n3. HEDGE rate by orientation — is one order easier to duck?")
    print(f"   {'orientation':<14}{'n':>6}{'hedge (q2=0)':>15}")
    for o in ORIENTATIONS:
        sub = [r["score"] for r in rows if r["orientation"] == o]
        if sub:
            print(f"   {o:<14}{len(sub):>6}{sum(1 for s in sub if s == 0)/len(sub):>14.0%}")

    # ---- 4. which way do the flips go? ------------------------------------- #
    flips = [(k, v) for k, v in complete.items() if classify(v["forward"], v["reversed"]) == "SIGN FLIP"]
    print("\n4. FLIP DIRECTION — when the verdict does move, which slot wins?")
    print("   This is the sharpest test in the experiment. A flip means the model")
    print("   committed both times and named different entities, so it must have")
    print("   sided with the same SLOT twice — first-printed or second-printed.")
    print("   Position bias predicts all-first; noisy judgement predicts a coin flip.")
    toward_first = sum(1 for _, v in flips if v["forward"] == 1 and v["reversed"] == 1)
    toward_second = sum(1 for _, v in flips if v["forward"] == -1 and v["reversed"] == -1)
    n_dir = toward_first + toward_second
    print(f"\n   toward FIRST-printed slot : {toward_first}")
    print(f"   toward SECOND-printed slot: {toward_second}")
    if n_dir:
        print(f"   two-sided binomial p      : {_binom_p(toward_first, n_dir):.5f}")

    # ---- 5. the flips themselves ------------------------------------------- #
    if flips:
        print(f"\n5. SIGN FLIPS in full ({len(flips)}) — model picked a different entity "
              f"purely on order")
        for (model, key, gm), v in sorted(flips)[:40]:
            r = meta[(model, key, gm)]
            won_fwd = r["entity_a"] if v["forward"] == 1 else r["entity_b"]
            won_rev = r["entity_b"] if v["reversed"] == 1 else r["entity_a"]
            print(f"   {model:<28} judge={gm.split('/')[-1]:<18} {key[:52]}")
            print(f"      forward -> {won_fwd}   |   reversed -> {won_rev}")
    else:
        print("\n5. No sign flips.")


# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["collect", "grade", "report", "all"], default="all")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--grader-models", default=",".join(DEFAULT_GRADER_MODELS))
    ap.add_argument("--questions", type=int, default=20)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--db", type=Path, default=REPO_ROOT / "aestheticbench.db")
    ap.add_argument("--prompts", type=Path, default=REPO_ROOT / "prompts" / "v2.tsv")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    grader_models = [m.strip() for m in args.grader_models.split(",") if m.strip()]

    print("=" * 74)
    print("  AestheticBench - order-bias experiment")
    print("=" * 74)
    print(f"experiment    : {EXPERIMENT}")
    print(f"subject models: {', '.join(models)}")
    print(f"judges        : {', '.join(grader_models)}")
    print(f"grader         : {GRADER_ID} (preference only)")
    print(f"seed          : {args.seed}")

    all_items = load_items(args.prompts)
    items = sample_items(all_items, args.questions, args.seed)
    print(f"questions     : {len(items)} sampled from {len(all_items)} eligible")
    if args.dry_run:
        for i in items:
            print(f"  [{i.topic}] {i.entity_a}  vs  {i.entity_b}")

    con = connect(args.db)
    try:
        if args.stage in ("collect", "all"):
            stage_collect(con, items, models, args.workers, args.dry_run)
        if args.stage in ("grade", "all"):
            stage_grade(con, grader_models, args.workers, args.dry_run)
        if args.stage in ("report", "all") and not args.dry_run:
            stage_report(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
