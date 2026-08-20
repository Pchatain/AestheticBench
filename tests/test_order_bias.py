"""Tests for the order-bias experiment harness.

The load-bearing piece is `_canonical`. If its sign convention is backwards the
report turns perfect consistency into a 100% flip rate and vice versa — a wrong
answer that looks exactly like a real finding, so it is pinned here explicitly
rather than left to the report to reveal.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "backend" / "src"))

import order_bias as ob


class TestCanonical:
    """Raw +1 means 'first slot'; canonical +1 must always mean 'entity_a'."""

    def test_forward_passes_through(self):
        assert ob._canonical(1, "forward") == 1
        assert ob._canonical(-1, "forward") == -1
        assert ob._canonical(0, "forward") == 0

    def test_reversed_inverts_sign(self):
        # In the reversed prompt the first slot holds entity_b, so a raw +1
        # ("prefers the first-printed") is a vote for entity_b, i.e. canonical -1.
        assert ob._canonical(1, "reversed") == -1
        assert ob._canonical(-1, "reversed") == 1

    def test_hedge_is_orientation_free(self):
        assert ob._canonical(0, "reversed") == 0

    def test_a_model_with_pure_position_bias_reads_as_all_flips(self):
        """Always picking the first slot => raw +1 both ways => canonical +1/-1."""
        fwd, rev = ob._canonical(1, "forward"), ob._canonical(1, "reversed")
        assert fwd != rev and fwd != 0 and rev != 0

    def test_a_model_with_a_stable_view_reads_as_no_flip(self):
        """Always picking entity_a => raw +1 forward, raw -1 reversed."""
        assert ob._canonical(1, "forward") == ob._canonical(-1, "reversed") == 1


class TestItem:
    def test_prompt_swaps_and_strips(self):
        item = ob.Item("Beauty", "Who is greater, [Beethoven] or [Lizzo]?", "Beethoven", "Lizzo")
        assert item.prompt("forward") == "Who is greater, Beethoven or Lizzo?"
        assert item.prompt("reversed") == "Who is greater, Lizzo or Beethoven?"

    def test_key_is_orientation_independent(self):
        item = ob.Item("Beauty", "Who is greater, [Beethoven] or [Lizzo]?", "Beethoven", "Lizzo")
        assert item.key == item.prompt("forward")
        assert "[" not in item.key

    def test_no_prompt_reaches_a_grader_with_brackets(self):
        """construct_prompt rejects brackets, so both orientations must be clean."""
        item = ob.Item("Beauty", "Who is greater, [Beethoven] or [Lizzo]?", "Beethoven", "Lizzo")
        for o in ob.ORIENTATIONS:
            assert "[" not in item.prompt(o) and "]" not in item.prompt(o)


class TestSampling:
    def _pool(self, n):
        return [ob.Item("T", f"Is [A{i}] or [B{i}] better?", f"A{i}", f"B{i}") for i in range(n)]

    def test_same_seed_same_sample(self):
        pool = self._pool(50)
        assert ob.sample_items(pool, 20, 7) == ob.sample_items(pool, 20, 7)

    def test_different_seed_different_sample(self):
        pool = self._pool(50)
        assert ob.sample_items(pool, 20, 7) != ob.sample_items(pool, 20, 8)

    def test_sample_is_not_the_whole_pool(self):
        """Guards against a silent 'n >= len(pool)' path making the seed a no-op."""
        pool = self._pool(50)
        assert len(ob.sample_items(pool, 20, 7)) == 20

    def test_asking_for_more_than_exists_returns_all(self):
        pool = self._pool(5)
        assert len(ob.sample_items(pool, 20, 7)) == 5

    def test_input_order_does_not_affect_the_draw(self):
        """The pool is sorted first, so a reordered TSV yields the same sample."""
        pool = self._pool(50)
        assert ob.sample_items(pool, 20, 7) == ob.sample_items(list(reversed(pool)), 20, 7)


class TestLoadItems:
    def test_rejects_questions_without_exactly_two_entities(self, tmp_path):
        tsv = tmp_path / "p.tsv"
        tsv.write_text(
            "Topic\tQuestion\n"
            "Beauty\tWho is greater, [Beethoven] or [Lizzo]?\n"
            "Beauty\tIs [Bach] good?\n"                       # one entity
            "Beauty\tRank [A], [B] and [C].\n"                # three
            "Beauty\tNo entities at all?\n",
            encoding="utf-8",
        )
        items = ob.load_items(tsv)
        assert [i.entity_a for i in items] == ["Beethoven"]

    def test_entities_are_assigned_in_printed_order(self, tmp_path):
        tsv = tmp_path / "p.tsv"
        tsv.write_text("Topic\tQuestion\nB\tX [First] or [Second]?\n", encoding="utf-8")
        item = ob.load_items(tsv)[0]
        assert (item.entity_a, item.entity_b) == ("First", "Second")


class TestBinomP:
    def test_even_split_is_not_significant(self):
        assert ob._binom_p(50, 100) > 0.9

    def test_lopsided_split_is_significant(self):
        assert ob._binom_p(90, 100) < 0.001

    def test_empty_is_nan(self):
        assert ob._binom_p(0, 0) != ob._binom_p(0, 0)  # nan != nan


class TestMajority:
    """Collapsing repeat generations of one condition into a single verdict."""

    def test_unanimous(self):
        assert ob._majority([1, 1, 1]) == 1
        assert ob._majority([-1, -1, -1]) == -1
        assert ob._majority([0, 0, 0]) == 0

    def test_two_one_split_takes_the_two(self):
        assert ob._majority([1, 1, 0]) == 1
        assert ob._majority([-1, -1, 1]) == -1
        assert ob._majority([0, 0, 1]) == 0

    def test_three_way_split_is_ambivalent(self):
        assert ob._majority([1, 0, -1]) == 0

    def test_even_split_between_sides_is_ambivalent(self):
        """A 1-1 split between +1 and -1 is exactly 'no stable view'.

        Picking a side here would manufacture a verdict the samples do not
        support, and would inflate the stable-commit rate.
        """
        assert ob._majority([1, -1]) == 0

    def test_single_sample_passes_through(self):
        assert ob._majority([1]) == 1


class TestDisagreementRate:
    def test_identical_pairs_never_disagree(self):
        assert ob._disagreement_rate([(1, 1), (0, 0), (-1, -1)]) == (0.0, 0.0)

    def test_sign_flip_counts_as_both(self):
        any_d, flip = ob._disagreement_rate([(1, -1)])
        assert any_d == 1.0 and flip == 1.0

    def test_commit_to_hedge_is_disagreement_but_not_a_flip(self):
        any_d, flip = ob._disagreement_rate([(1, 0)])
        assert any_d == 1.0 and flip == 0.0

    def test_empty_is_nan(self):
        a, f = ob._disagreement_rate([])
        assert a != a and f != f


class TestMigration:
    """The pre-run_index table must gain the column without losing grades."""

    def _legacy_db(self, path):
        import sqlite3

        con = sqlite3.connect(path)
        con.executescript("""
            CREATE TABLE order_bias_responses (
                id INTEGER PRIMARY KEY, experiment TEXT NOT NULL,
                question_key TEXT NOT NULL, topic TEXT,
                entity_a TEXT NOT NULL, entity_b TEXT NOT NULL,
                orientation TEXT NOT NULL, prompt_text TEXT NOT NULL,
                model TEXT NOT NULL, response_text TEXT NOT NULL,
                created_at TIMESTAMP,
                UNIQUE(experiment, question_key, model, orientation)
            );
            CREATE TABLE order_bias_grades (
                id INTEGER PRIMARY KEY, response_id INTEGER NOT NULL,
                grader_id TEXT NOT NULL, grader_model TEXT NOT NULL,
                score INTEGER NOT NULL, reasoning TEXT, created_at TIMESTAMP,
                UNIQUE(response_id, grader_id, grader_model)
            );
            INSERT INTO order_bias_responses
                (id, experiment, question_key, entity_a, entity_b, orientation,
                 prompt_text, model, response_text)
            VALUES (7,'order-bias-v1','Q','A','B','forward','Q','m','resp');
            INSERT INTO order_bias_grades
                (response_id, grader_id, grader_model, score)
            VALUES (7,'q2','judge',1);
        """)
        con.commit()
        con.close()

    def test_adds_column_and_backfills_run_1(self, tmp_path):
        db = tmp_path / "legacy.db"
        self._legacy_db(db)
        con = ob.connect(db)
        row = con.execute("SELECT id, run_index FROM order_bias_responses").fetchone()
        assert (row["id"], row["run_index"]) == (7, 1)
        con.close()

    def test_grades_stay_attached(self, tmp_path):
        """Response ids are carried over verbatim, so the join must survive."""
        db = tmp_path / "legacy.db"
        self._legacy_db(db)
        con = ob.connect(db)
        n = con.execute(
            "SELECT count(*) FROM order_bias_grades g "
            "JOIN order_bias_responses r ON r.id = g.response_id"
        ).fetchone()[0]
        assert n == 1
        con.close()

    def test_second_run_is_now_insertable(self, tmp_path):
        """The whole point: the old UNIQUE silently dropped repeat generations."""
        db = tmp_path / "legacy.db"
        self._legacy_db(db)
        con = ob.connect(db)
        con.execute(
            "INSERT OR IGNORE INTO order_bias_responses "
            "(experiment, question_key, entity_a, entity_b, orientation, "
            " prompt_text, model, run_index, response_text) "
            "VALUES ('order-bias-v1','Q','A','B','forward','Q','m',2,'resp2')"
        )
        con.commit()
        assert con.execute("SELECT count(*) FROM order_bias_responses").fetchone()[0] == 2
        con.close()

    def test_migration_is_idempotent(self, tmp_path):
        db = tmp_path / "legacy.db"
        self._legacy_db(db)
        ob.connect(db).close()
        con = ob.connect(db)
        assert con.execute("SELECT count(*) FROM order_bias_responses").fetchone()[0] == 1
        con.close()


class TestKappa:
    def test_perfect_agreement_is_1(self):
        assert ob._kappa([(1, 1), (0, 0), (-1, -1)] * 10) == 1.0

    def test_chance_level_is_0(self):
        """Two raters flipping independent fair coins over {0,1}: p_o = p_e = 0.5."""
        pairs = [(0, 0), (0, 1), (1, 0), (1, 1)] * 25
        assert abs(ob._kappa(pairs)) < 1e-9

    def test_the_kappa_paradox(self):
        """90% raw agreement can be WORSE than chance when marginals are skewed.

        Both raters say +1 on 95% of items, so chance alone produces 90.5%
        agreement — the observed 90% lands just below it and kappa goes
        slightly negative. This is exactly why raw agreement cannot be the
        headline number for a grader that says +1 most of the time.
        """
        pairs = [(1, 1)] * 90 + [(1, 0)] * 5 + [(0, 1)] * 5
        k = ob._kappa(pairs)
        assert -0.1 < k < 0

    def test_empty_is_nan(self):
        assert ob._kappa([]) != ob._kappa([])


class TestKrippendorffOrdinal:
    def test_perfect_agreement_is_1(self):
        assert ob._krippendorff_ordinal([(1, 1), (-1, -1)] * 5) == 1.0

    def test_sign_flip_costs_more_than_hedge(self):
        """The metric must be distance-aware: -1 vs +1 is a worse miss than 0 vs +1."""
        base = [(1, 1), (0, 0), (-1, -1)] * 20
        with_hedge = ob._krippendorff_ordinal(base + [(1, 0)])
        with_flip = ob._krippendorff_ordinal(base + [(1, -1)])
        assert with_flip < with_hedge < 1.0
