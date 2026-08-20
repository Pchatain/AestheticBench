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
sys.path.insert(0, str(REPO_ROOT / "src"))

from aestheticbench.benchmark.client import OpenRouterClient  # noqa: E402
from aestheticbench.benchmark.config import Config  # noqa: E402
from aestheticbench.benchmark.grading import GraderRegistry  # noqa: E402
from aestheticbench.benchmark.text_utils import strip_entity_brackets, swap_entities  # noqa: E402

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
    run_index INTEGER NOT NULL DEFAULT 1,
    response_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment, question_key, model, orientation, run_index)
);
CREATE TABLE IF NOT EXISTS order_bias_grades (
    id INTEGER PRIMARY KEY,
    response_id INTEGER NOT NULL REFERENCES order_bias_responses(id),
    grader_id TEXT NOT NULL,
    grader_model TEXT NOT NULL,
    grade_round INTEGER NOT NULL DEFAULT 1,
    score INTEGER NOT NULL,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(response_id, grader_id, grader_model, grade_round)
);
CREATE INDEX IF NOT EXISTS idx_ob_resp_model ON order_bias_responses(model);
CREATE INDEX IF NOT EXISTS idx_ob_grades_resp ON order_bias_grades(response_id);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    _migrate_run_index(con)
    _migrate_grade_round(con)
    con.executescript(SCHEMA)
    return con


def _migrate_grade_round(con: sqlite3.Connection) -> None:
    """Add grade_round to a grades table created before re-grading existed.

    Same failure mode as the responses migration: the old UNIQUE makes a second
    grading of the same response by the same judge collide with the first, and
    INSERT OR IGNORE drops it in silence — so a repeatability study would
    read one grading as two perfectly-agreeing ones.
    """
    have = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='order_bias_grades'"
    ).fetchone()
    if not have:
        return
    cols = {r[1] for r in con.execute("PRAGMA table_info(order_bias_grades)")}
    if "grade_round" in cols:
        return
    n = con.execute("SELECT count(*) FROM order_bias_grades").fetchone()[0]
    print(f"  migrating order_bias_grades: adding grade_round to {n} existing rows (-> round 1)")
    con.executescript("""
        BEGIN;
        CREATE TABLE order_bias_grades_new (
            id INTEGER PRIMARY KEY,
            response_id INTEGER NOT NULL REFERENCES order_bias_responses(id),
            grader_id TEXT NOT NULL,
            grader_model TEXT NOT NULL,
            grade_round INTEGER NOT NULL DEFAULT 1,
            score INTEGER NOT NULL,
            reasoning TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(response_id, grader_id, grader_model, grade_round)
        );
        INSERT INTO order_bias_grades_new
            (id, response_id, grader_id, grader_model, grade_round, score, reasoning, created_at)
        SELECT id, response_id, grader_id, grader_model, 1, score, reasoning, created_at
        FROM order_bias_grades;
        DROP TABLE order_bias_grades;
        ALTER TABLE order_bias_grades_new RENAME TO order_bias_grades;
        COMMIT;
    """)
    kept = con.execute("SELECT count(*) FROM order_bias_grades").fetchone()[0]
    assert kept == n, f"migration lost rows: {n} -> {kept}"
    print(f"  migration ok: {kept} rows, all at grade_round=1")


def _migrate_run_index(con: sqlite3.Connection) -> None:
    """Add run_index to a table created before repeat generations existed.

    The original UNIQUE(experiment, question_key, model, orientation) makes a
    second generation collide with the first, and the insert is INSERT OR
    IGNORE — so without this the extra runs are dropped in silence and the
    variance report reads a single sample as perfectly self-consistent. SQLite
    cannot alter a UNIQUE constraint, so the table is rebuilt.
    """
    have = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='order_bias_responses'"
    ).fetchone()
    if not have:
        return
    cols = {r[1] for r in con.execute("PRAGMA table_info(order_bias_responses)")}
    if "run_index" in cols:
        return

    n = con.execute("SELECT count(*) FROM order_bias_responses").fetchone()[0]
    print(f"  migrating order_bias_responses: adding run_index to {n} existing rows (-> run 1)")
    con.executescript("""
        PRAGMA foreign_keys=off;
        BEGIN;
        CREATE TABLE order_bias_responses_new (
            id INTEGER PRIMARY KEY,
            experiment TEXT NOT NULL,
            question_key TEXT NOT NULL,
            topic TEXT,
            entity_a TEXT NOT NULL,
            entity_b TEXT NOT NULL,
            orientation TEXT NOT NULL CHECK (orientation IN ('forward','reversed')),
            prompt_text TEXT NOT NULL,
            model TEXT NOT NULL,
            run_index INTEGER NOT NULL DEFAULT 1,
            response_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(experiment, question_key, model, orientation, run_index)
        );
        INSERT INTO order_bias_responses_new
            (id, experiment, question_key, topic, entity_a, entity_b,
             orientation, prompt_text, model, run_index, response_text, created_at)
        SELECT id, experiment, question_key, topic, entity_a, entity_b,
               orientation, prompt_text, model, 1, response_text, created_at
        FROM order_bias_responses;
        DROP TABLE order_bias_responses;
        ALTER TABLE order_bias_responses_new RENAME TO order_bias_responses;
        COMMIT;
        PRAGMA foreign_keys=on;
    """)
    # Grades key on response_id, and ids are carried over verbatim above, so the
    # 320 existing grades stay attached to the responses they were made on.
    kept = con.execute("SELECT count(*) FROM order_bias_responses").fetchone()[0]
    assert kept == n, f"migration lost rows: {n} -> {kept}"
    print(f"  migration ok: {kept} rows, all at run_index=1")


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


def stage_collect(con, items, models, runs, workers, dry_run: bool) -> None:
    todo = []
    for model in models:
        for item in items:
            for orientation in ORIENTATIONS:
                for run in runs:
                    if _has_response(con, item.key, model, orientation, run):
                        continue
                    todo.append((model, item, orientation, run))

    planned = len(models) * len(items) * 2 * len(runs)
    print(f"\n[collect] {len(todo)} responses to gather "
          f"({len(models)} models x {len(items)} questions x 2 orientations "
          f"x {len(runs)} runs = {planned}, "
          f"minus {planned - len(todo)} already present)")
    if dry_run:
        for model, item, orientation, run in todo[:6]:
            print(f"  run{run} {model:30s} {orientation:8s} {item.prompt(orientation)[:52]}")
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
            prompts = [item.prompt(orientation) for _, item, orientation, _ in entries]
            print(f"  {model}: {len(prompts)} prompts")
            results = client.batch_chat_completions(prompts, model)
            ok = err = 0
            for idx, _prompt, response in results:
                _, item, orientation, run = entries[idx]
                if not response:
                    err += 1
                    continue
                con.execute(
                    "INSERT OR IGNORE INTO order_bias_responses "
                    "(experiment, question_key, topic, entity_a, entity_b, orientation, "
                    " prompt_text, model, run_index, response_text) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (EXPERIMENT, item.key, item.topic, item.entity_a, item.entity_b,
                     orientation, item.prompt(orientation), model, run, response),
                )
                ok += 1
            con.commit()
            print(f"    ok={ok} errors={err}")


def _has_response(con, key: str, model: str, orientation: str, run: int) -> bool:
    return con.execute(
        "SELECT 1 FROM order_bias_responses WHERE experiment=? AND question_key=? "
        "AND model=? AND orientation=? AND run_index=?",
        (EXPERIMENT, key, model, orientation, run),
    ).fetchone() is not None


# --------------------------------------------------------------------------- #
# stage: grade
# --------------------------------------------------------------------------- #


def stage_grade(con, grader_models, grade_round, workers, dry_run: bool) -> None:
    grader = GraderRegistry.get_grader(GRADER_ID)
    rows = con.execute(
        "SELECT * FROM order_bias_responses WHERE experiment=?", (EXPERIMENT,)
    ).fetchall()

    plan = []
    for gm in grader_models:
        for row in rows:
            done = con.execute(
                "SELECT 1 FROM order_bias_grades WHERE response_id=? AND grader_id=? "
                "AND grader_model=? AND grade_round=?", (row["id"], GRADER_ID, gm, grade_round),
            ).fetchone()
            if not done:
                plan.append((gm, row))

    print(f"\n[grade] {len(plan)} gradings to run "
          f"({len(rows)} responses x {len(grader_models)} judges, "
          f"grader_id={GRADER_ID!r}, grade_round={grade_round})")
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
                    "(response_id, grader_id, grader_model, grade_round, score, reasoning) "
                    "VALUES (?,?,?,?,?,?)",
                    (row["id"], GRADER_ID, gm, grade_round, int(score), reasoning),
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


def _majority(scores: list[int]) -> int:
    """The modal score across repeat generations of the same condition.

    Ties are broken toward 0. A 1-1 split between +1 and -1 is exactly the case
    where the model has no stable view, and calling that ambivalent is both true
    and the conservative choice — picking a side would manufacture a verdict the
    samples do not support.
    """
    counts = collections.Counter(scores)
    top = max(counts.values())
    winners = {s for s, c in counts.items() if c == top}
    return 0 if len(winners) > 1 else winners.pop()


def _disagreement_rate(pairs: list[tuple[int, int]]) -> tuple[float, float]:
    """(any-disagreement rate, sign-flip rate) over a list of score pairs."""
    if not pairs:
        return float("nan"), float("nan")
    any_d = sum(1 for a, b in pairs if a != b) / len(pairs)
    flip = sum(1 for a, b in pairs if a != 0 and b != 0 and a != b) / len(pairs)
    return any_d, flip


def stage_variance(con) -> None:
    """The noise floor, and whether the order effect clears it.

    Without repeat generations the order-bias report cannot distinguish "the
    swap changed the verdict" from "the model is not self-consistent and the
    swap changed nothing". This measures both on the same footing: the
    probability that two independently sampled responses disagree, within one
    orientation (noise) and across orientations (noise + any order effect).
    """
    rows = con.execute(
        "SELECT g.score, g.grader_model, r.orientation, r.model, r.question_key, r.run_index "
        "FROM order_bias_grades g JOIN order_bias_responses r ON r.id = g.response_id "
        "WHERE r.experiment=? AND g.grader_id=? AND g.grade_round=1", (EXPERIMENT, GRADER_ID),
    ).fetchall()
    if not rows:
        print("\n[variance] nothing graded yet")
        return

    samples = collections.defaultdict(dict)  # (model,q,judge,orientation) -> {run: score}
    for r in rows:
        samples[(r["model"], r["question_key"], r["grader_model"], r["orientation"])][r["run_index"]] = r["score"]

    runs = sorted({r["run_index"] for r in rows})
    print(f"\n{'=' * 74}\nVARIANCE REPORT  ({EXPERIMENT}, runs={runs})\n{'=' * 74}")
    n_full = sum(1 for v in samples.values() if len(v) == len(runs))
    print(f"conditions with all {len(runs)} runs: {n_full} of {len(samples)}")
    if len(runs) < 2:
        print("need at least 2 runs to measure variance")
        return

    # ---- within-orientation: the noise floor ------------------------------ #
    within = collections.defaultdict(list)
    for (model, q, judge, orientation), byrun in samples.items():
        rs = sorted(byrun)
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                within[(model, judge)].append((byrun[rs[i]], byrun[rs[j]]))

    # ---- cross-orientation: noise + any order effect ---------------------- #
    cross = collections.defaultdict(list)
    keys = {(m, q, j) for (m, q, j, _o) in samples}
    for (model, q, judge) in keys:
        fwd = samples.get((model, q, judge, "forward"), {})
        rev = samples.get((model, q, judge, "reversed"), {})
        for rf, sf in fwd.items():
            for rr, sr in rev.items():
                cross[(model, judge)].append((_canonical(sf, "forward"), _canonical(sr, "reversed")))

    all_within = [p for v in within.values() for p in v]
    all_cross = [p for v in cross.values() for p in v]
    wd, wf = _disagreement_rate(all_within)
    cd, cf = _disagreement_rate(all_cross)

    print("\n1. IS THE ORDER EFFECT BIGGER THAN THE NOISE?")
    print("   Both rows are the same statistic: the chance that two independently")
    print("   sampled responses disagree. Within-orientation is pure generation")
    print("   noise. Cross-orientation is that noise PLUS any order effect.")
    print(f"\n   {'comparison':<34}{'pairs':>8}{'disagree':>11}{'sign flip':>12}")
    print(f"   {'within orientation (noise floor)':<34}{len(all_within):>8}{wd:>10.0%}{wf:>12.0%}")
    print(f"   {'across orientations':<34}{len(all_cross):>8}{cd:>10.0%}{cf:>12.0%}")
    print(f"   {'excess attributable to order':<34}{'':>8}{cd - wd:>+10.0%}{cf - wf:>+12.0%}")

    print("\n   by subject model:")
    print(f"   {'model':<28}{'noise':>9}{'cross':>9}{'excess':>9}"
          f"{'  |':>3}{'noise flip':>12}{'cross flip':>12}{'excess':>9}")
    for model in sorted({k[0] for k in within}):
        w = [p for k, v in within.items() if k[0] == model for p in v]
        c = [p for k, v in cross.items() if k[0] == model for p in v]
        wd_, wf_ = _disagreement_rate(w)
        cd_, cf_ = _disagreement_rate(c)
        print(f"   {model:<28}{wd_:>8.0%}{cd_:>9.0%}{cd_ - wd_:>+9.0%}"
              f"{'  |':>3}{wf_:>11.0%}{cf_:>12.0%}{cf_ - wf_:>+9.0%}")

    print("\n   by judge:")
    print(f"   {'judge':<28}{'noise':>9}{'cross':>9}{'excess':>9}")
    for judge in sorted({k[1] for k in within}):
        w = [p for k, v in within.items() if k[1] == judge for p in v]
        c = [p for k, v in cross.items() if k[1] == judge for p in v]
        wd_, _ = _disagreement_rate(w)
        cd_, _ = _disagreement_rate(c)
        print(f"   {judge:<28}{wd_:>8.0%}{cd_:>9.0%}{cd_ - wd_:>+9.0%}")

    # ---- flip direction, over every cross-orientation pair ----------------- #
    print("\n   Direction of the cross-orientation sign flips. Noise cannot have a")
    print("   direction; a slot preference must. This is the test that survives")
    print("   even when the excess above the noise floor is small.")
    toward_first = sum(1 for a, b in all_cross if a != 0 and b != 0 and a != b and a == 1)
    toward_second = sum(1 for a, b in all_cross if a != 0 and b != 0 and a != b and a == -1)
    n_dir = toward_first + toward_second
    print(f"   toward FIRST-printed slot : {toward_first}")
    print(f"   toward SECOND-printed slot: {toward_second}")
    if n_dir:
        print(f"   two-sided binomial p      : {_binom_p(toward_first, n_dir):.2e}")

    # ---- self-consistency -------------------------------------------------- #
    print("\n2. SELF-CONSISTENCY — how often do all runs of one condition agree?")
    print(f"   {'model':<28}{'conditions':>12}{'unanimous':>12}{'2-1 split':>12}{'3-way':>8}")
    for model in sorted({k[0] for k in samples}):
        conds = [v for k, v in samples.items() if k[0] == model and len(v) == len(runs)]
        if not conds:
            continue
        una = sum(1 for v in conds if len(set(v.values())) == 1)
        three = sum(1 for v in conds if len(set(v.values())) == 3)
        split = len(conds) - una - three
        n = len(conds)
        print(f"   {model:<28}{n:>12}{una / n:>11.0%}{split / n:>12.0%}{three / n:>8.0%}")

    # ---- how much does majority voting change the headline? ---------------- #
    print("\n3. WHAT THE REPEATS BUY — single run vs majority-of-3 verdicts")
    for label, pick in (("run 1 only", lambda v: v.get(runs[0])),
                        ("majority of 3", lambda v: _majority(list(v.values())))):
        flips = stable = 0
        for (model, q, judge) in keys:
            f = samples.get((model, q, judge, "forward"), {})
            r = samples.get((model, q, judge, "reversed"), {})
            if not f or not r:
                continue
            a, b = pick(f), pick(r)
            if a is None or b is None:
                continue
            ca, cb = _canonical(a, "forward"), _canonical(b, "reversed")
            if ca == cb:
                stable += 1
            elif ca != 0 and cb != 0:
                flips += 1
        tot = len(keys)
        print(f"   {label:<16} stable {stable:>3}/{tot} ({stable / tot:>4.0%})   "
              f"sign flips {flips:>3}/{tot} ({flips / tot:>4.0%})")


def _kappa(pairs: list[tuple[int, int]]) -> float:
    """Cohen's kappa: agreement above what the two marginals produce by chance.

    p_o is raw agreement; p_e is the agreement two independent raters with these
    same marginal distributions would reach by luck. kappa = (p_o - p_e)/(1 - p_e):
    0 means "no better than chance", 1 means perfect. It matters here because a
    judge that says +1 56% of the time agrees with itself often by luck alone.
    """
    if not pairs:
        return float("nan")
    n = len(pairs)
    p_o = sum(1 for a, b in pairs if a == b) / n
    cats = sorted({v for p in pairs for v in p})
    ma = collections.Counter(a for a, _ in pairs)
    mb = collections.Counter(b for _, b in pairs)
    p_e = sum((ma[c] / n) * (mb[c] / n) for c in cats)
    return float("nan") if p_e == 1 else (p_o - p_e) / (1 - p_e)


def _krippendorff_ordinal(pairs: list[tuple[int, int]]) -> float:
    """Krippendorff's alpha with a squared-distance (interval) metric.

    Unlike kappa, distance-aware: a -1 vs +1 disagreement costs 4x a 0 vs +1
    disagreement, which matches how we read the scale (a sign flip is worse
    than a hedge). alpha = 1 - D_o/D_e, observed vs expected squared distance.
    """
    if not pairs:
        return float("nan")
    vals = [v for p in pairs for v in p]
    n = len(vals)
    d_o = sum((a - b) ** 2 for a, b in pairs) * 2 / len(pairs) / 2  # mean over ordered pairs
    d_e = sum((a - b) ** 2 for a in vals for b in vals) / (n * (n - 1))
    return float("nan") if d_e == 0 else 1 - (d_o / d_e)


def stage_grader(con) -> None:
    """Grader repeatability: the same judge, the same response, graded twice.

    This isolates the one variance component the run-repeat experiment
    confounds. Within-orientation disagreement (two fresh generations) is
    generation noise PLUS grader noise; this is grader noise alone, because the
    response text is byte-identical between rounds. Whatever disagreement
    remains here is the judge's own instability.
    """
    rows = con.execute(
        "SELECT g.response_id rid, g.grader_model gm, g.grade_round rnd, g.score sc, "
        "       r.model, r.orientation "
        "FROM order_bias_grades g JOIN order_bias_responses r ON r.id = g.response_id "
        "WHERE r.experiment=? AND g.grader_id=?", (EXPERIMENT, GRADER_ID),
    ).fetchall()
    rounds = sorted({r["rnd"] for r in rows})
    print(f"\n{'=' * 74}\nGRADER REPEATABILITY  ({EXPERIMENT}, rounds={rounds})\n{'=' * 74}")
    if len(rounds) < 2:
        print("need at least 2 grade rounds; run --stage grade --grade-round 2 first")
        return

    by = collections.defaultdict(dict)   # (gm, rid) -> {round: score}
    meta = {}
    for r in rows:
        by[(r["gm"], r["rid"])][r["rnd"]] = r["sc"]
        meta[r["rid"]] = (r["model"], r["orientation"])

    judges = sorted({k[0] for k in by})
    print("\n1. TEST-RETEST — same judge, byte-identical response, graded twice")
    print(f"   {'judge':<30}{'n':>6}{'agree':>8}{'kappa':>8}{'alpha':>8}{'sign flips':>12}")
    judge_pairs = {}
    for gm in judges:
        pairs = [(v[rounds[0]], v[rounds[1]]) for k, v in by.items()
                 if k[0] == gm and rounds[0] in v and rounds[1] in v]
        judge_pairs[gm] = pairs
        if not pairs:
            continue
        agree = sum(1 for a, b in pairs if a == b) / len(pairs)
        flips = sum(1 for a, b in pairs if a != 0 and b != 0 and a != b)
        print(f"   {gm:<30}{len(pairs):>6}{agree:>8.0%}{_kappa(pairs):>8.2f}"
              f"{_krippendorff_ordinal(pairs):>8.2f}{flips:>12}")

    print("\n   where the changes land (round 1 -> round 2):")
    for gm in judges:
        moves = collections.Counter((a, b) for a, b in judge_pairs[gm] if a != b)
        if not moves:
            continue
        desc = ", ".join(f"{a:+d}->{b:+d}: {c}" for (a, b), c in
                         sorted(moves.items(), key=lambda x: -x[1]))
        print(f"   {gm}: {desc}")

    # decomposition: subtract grader noise from the run-repeat noise floor
    print("\n2. VARIANCE DECOMPOSITION (disagreement rates, per judge)")
    print("   within-orientation run pairs = generation + grader;")
    print("   test-retest = grader alone. Independence gives")
    print("   P(disagree) = 1 - (1-p_gen)(1-p_grader), so p_gen backs out.")
    gen_rows = con.execute(
        "SELECT g.score sc, g.grader_model gm, r.model, r.question_key q, r.orientation o, "
        "       r.run_index run "
        "FROM order_bias_grades g JOIN order_bias_responses r ON r.id = g.response_id "
        "WHERE r.experiment=? AND g.grader_id=? AND g.grade_round=1", (EXPERIMENT, GRADER_ID),
    ).fetchall()
    cond = collections.defaultdict(dict)
    for r in gen_rows:
        cond[(r["gm"], r["model"], r["q"], r["o"])][r["run"]] = r["sc"]
    print(f"\n   {'judge':<30}{'run-pairs':>10}{'grader':>9}{'=> generation':>14}")
    for gm in judges:
        wp = []
        for k, byrun in cond.items():
            if k[0] != gm:
                continue
            rs = sorted(byrun)
            for i in range(len(rs)):
                for j in range(i + 1, len(rs)):
                    wp.append((byrun[rs[i]], byrun[rs[j]]))
        if not wp or not judge_pairs[gm]:
            continue
        p_both = sum(1 for a, b in wp if a != b) / len(wp)
        p_grader = sum(1 for a, b in judge_pairs[gm] if a != b) / len(judge_pairs[gm])
        # run-pair disagreement involves grader noise on BOTH sides; retest has it
        # on one (relative to the other read). Keep the simple one-sided model and
        # report it as a bound rather than a point estimate.
        p_gen = 1 - (1 - p_both) / (1 - p_grader) if p_grader < 1 else float("nan")
        print(f"   {gm:<30}{p_both:>10.0%}{p_grader:>9.0%}{max(0.0, p_gen):>13.0%}")
    print("\n   (generation is a lower bound: the independence model charges grader")
    print("    noise once, but a run-pair carries an independent grader draw on")
    print("    each side, so some of what is labelled generation is still grader.)")


def stage_bounds(con, n_boot: int = 4000, seed: int = DEFAULT_SEED) -> None:
    """Cluster-bootstrap confidence intervals on the per-model numbers.

    The unit of resampling is the QUESTION, not the grade. The 20 questions are
    the sample from the population of possible comparisons; every grade inside
    a question shares that question's quirks (its lopsidedness, how easy it is
    to hedge on), so treating the 2,880 grades per model as independent would
    understate the interval severely. Resampling whole questions keeps that
    correlation intact — each bootstrap draw asks "what if the benchmark had
    sampled 20 *other* questions like these?", which is the uncertainty a user
    of the benchmark actually faces.

    Every read is kept (3 runs x 2 orientations x 2 judges x 2 grade rounds),
    so generation noise, order effects and grader noise are all inside the
    interval rather than assumed away.
    """
    import random as _random

    rows = con.execute(
        "SELECT g.score sc, r.model m, r.question_key q, r.orientation o "
        "FROM order_bias_grades g JOIN order_bias_responses r ON r.id = g.response_id "
        "WHERE r.experiment=? AND g.grader_id=?", (EXPERIMENT, GRADER_ID),
    ).fetchall()
    if not rows:
        print("\n[bounds] nothing graded yet")
        return
    grades = collections.defaultdict(list)  # (model, question) -> [(score, orientation)]
    for r in rows:
        grades[(r["m"], r["q"])].append((r["sc"], r["o"]))
    models = sorted({m for m, _ in grades})
    questions = sorted({q for _, q in grades})
    rng = _random.Random(seed)

    def stats_for(model, qs):
        ss = [(sc, o) for q in qs for sc, o in grades[(model, q)]]
        n = len(ss)
        commit = sum(1 for sc, _ in ss if sc != 0) / n
        canon = [sc if o == "forward" else -sc for sc, o in ss]
        return commit, sum(canon) / n

    print(f"\n{'=' * 74}\nERROR BOUNDS  (cluster bootstrap over questions, B={n_boot})\n{'=' * 74}")
    print(f"reads per model: {sum(len(v) for (m, _), v in grades.items() if m == models[0])} "
          f"({len(questions)} questions x 2 orientations x 3 runs x 2 judges x 2 rounds)")
    print(f"\n   {'model':<28}{'commit rate':>18}{'95% CI':>16}{'mean pref':>11}{'95% CI':>18}")
    for m in models:
        pt_c, pt_p = stats_for(m, questions)
        cs, ps = [], []
        for _ in range(n_boot):
            draw = [questions[rng.randrange(len(questions))] for _ in questions]
            c, pr = stats_for(m, draw)
            cs.append(c)
            ps.append(pr)
        cs.sort(); ps.sort()
        lo, hi = cs[int(0.025 * n_boot)], cs[int(0.975 * n_boot)]
        plo, phi = ps[int(0.025 * n_boot)], ps[int(0.975 * n_boot)]
        print(f"   {m:<28}{pt_c:>17.0%} {'':>2}[{lo:>4.0%},{hi:>4.0%}]"
              f"{pt_p:>+11.2f}  [{plo:>+.2f},{phi:>+.2f}]")
    print("\n   commit rate: share of reads with q2 != 0. mean pref: canonical score")
    print("   (+1 = entity named first in the TSV as written), averaged over reads —")
    print("   near 0 means orientation-balanced judgements, not indifference.")
    print("\n   Repeated reads help — going from 1 read to all 24 per question cuts")
    print("   the CI width by roughly a third — but a floor remains that only more")
    print("   QUESTIONS can remove: with n=20 the question draw dominates the interval.")


def stage_report(con) -> None:
    rows = con.execute(
        "SELECT g.score, g.grader_model, r.orientation, r.model, r.question_key, "
        "       r.entity_a, r.entity_b, r.topic, r.run_index "
        "FROM order_bias_grades g JOIN order_bias_responses r ON r.id = g.response_id "
        "WHERE r.experiment=? AND g.grader_id=? AND g.grade_round=1", (EXPERIMENT, GRADER_ID),
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
    samples = collections.defaultdict(list)   # (model,q,judge,orientation) -> [scores]
    meta = {}
    for r in rows:
        samples[(r["model"], r["question_key"], r["grader_model"], r["orientation"])].append(r["score"])
        meta[(r["model"], r["question_key"], r["grader_model"])] = r

    paired = collections.defaultdict(dict)
    for (model, q, judge, orientation), scores in samples.items():
        paired[(model, q, judge)][orientation] = _majority(scores)
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
    ap.add_argument("--stage", choices=["collect", "grade", "report", "variance", "grader", "bounds", "all"],
                    default="all")
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--grader-models", default=",".join(DEFAULT_GRADER_MODELS))
    ap.add_argument("--questions", type=int, default=20)
    ap.add_argument("--grade-round", type=int, default=1,
                    help="Which grading pass this is; >1 re-grades the same responses "
                         "with the same judges, for grader repeatability")
    ap.add_argument("--runs", default="1,2,3",
                    help="Comma-separated run indices to collect (repeat generations)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--db", type=Path, default=REPO_ROOT / "aestheticbench.db")
    ap.add_argument("--prompts", type=Path, default=REPO_ROOT / "prompts" / "v2.tsv")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    runs = [int(r) for r in args.runs.split(",") if r.strip()]
    grader_models = [m.strip() for m in args.grader_models.split(",") if m.strip()]

    print("=" * 74)
    print("  AestheticBench - order-bias experiment")
    print("=" * 74)
    print(f"experiment    : {EXPERIMENT}")
    print(f"subject models: {', '.join(models)}")
    print(f"judges        : {', '.join(grader_models)}")
    print(f"grader         : {GRADER_ID} (preference only)")
    print(f"seed          : {args.seed}")
    print(f"runs          : {runs}")

    all_items = load_items(args.prompts)
    items = sample_items(all_items, args.questions, args.seed)
    print(f"questions     : {len(items)} sampled from {len(all_items)} eligible")
    if args.dry_run:
        for i in items:
            print(f"  [{i.topic}] {i.entity_a}  vs  {i.entity_b}")

    con = connect(args.db)
    try:
        if args.stage in ("collect", "all"):
            stage_collect(con, items, models, runs, args.workers, args.dry_run)
        if args.stage in ("grade", "all"):
            stage_grade(con, grader_models, args.grade_round, args.workers, args.dry_run)
        if args.stage in ("report", "all") and not args.dry_run:
            stage_report(con)
        if args.stage in ("variance", "all") and not args.dry_run:
            stage_variance(con)
        if args.stage == "grader" and not args.dry_run:
            stage_grader(con)
        if args.stage == "bounds" and not args.dry_run:
            stage_bounds(con, seed=args.seed)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
