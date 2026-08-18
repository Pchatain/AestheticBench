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
