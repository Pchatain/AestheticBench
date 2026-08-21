"""Tests for benchmark.stats — the one home of the agreement statistics.

The load-bearing test is sklearn equivalence: agreement.py used
sklearn.metrics.cohen_kappa_score before stats.kappa replaced it, so the
replacement is only legal while the two agree to float precision on the
kinds of data this codebase produces.
"""

import math
import random

import pytest
from sklearn.metrics import cohen_kappa_score

from aestheticbench.benchmark.stats import (
    binom_p_two_sided,
    disagreement_rate,
    kappa,
    krippendorff_ordinal,
    majority,
)


class TestKappaMatchesSklearn:
    """stats.kappa must be a drop-in for cohen_kappa_score."""

    @pytest.mark.parametrize("weights", [None, "quadratic"])
    @pytest.mark.parametrize("label_pool", [(-1, 0, 1), (0, 1), (1, 2, 3, 4, 5)])
    def test_random_data_agrees_with_sklearn(self, weights, label_pool):
        rng = random.Random(hash((weights, label_pool)) & 0xFFFF)
        for trial in range(25):
            n = rng.randrange(2, 60)
            a = [rng.choice(label_pool) for _ in range(n)]
            b = [rng.choice(label_pool) for _ in range(n)]
            ours = kappa(a, b, labels=list(label_pool), weights=weights)
            theirs = cohen_kappa_score(a, b, labels=list(label_pool), weights=weights)
            if math.isnan(theirs):
                assert math.isnan(ours), (a, b)
            else:
                assert ours == pytest.approx(theirs, abs=1e-12), (a, b)

    def test_labels_inferred_when_omitted(self):
        a, b = [-1, 0, 1, 1, 0], [-1, 1, 1, 0, 0]
        assert kappa(a, b) == pytest.approx(cohen_kappa_score(a, b))

    def test_constant_identical_raters_is_nan_not_crash(self):
        """agreement.py leaves kappa out rather than emitting nan; keep that possible."""
        assert math.isnan(kappa([1, 1, 1], [1, 1, 1]))

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            kappa([1, 0], [1])


class TestKappaBehaviour:
    def test_perfect_agreement_is_1(self):
        assert kappa([1, 0, -1] * 10, [1, 0, -1] * 10) == 1.0

    def test_the_kappa_paradox(self):
        """90% raw agreement can be worse than chance under skewed marginals."""
        a = [1] * 95 + [0] * 5
        b = [1] * 90 + [0] * 5 + [1] * 5
        pairs_a = [1] * 90 + [1] * 5 + [0] * 5
        pairs_b = [1] * 90 + [0] * 5 + [1] * 5
        assert -0.1 < kappa(pairs_a, pairs_b) < 0

    def test_quadratic_forgives_near_misses(self):
        """On an ordinal scale, off-by-one should hurt less under quadratic."""
        a = [1, 2, 3, 4, 5] * 8
        b = [2, 3, 4, 5, 4] * 8  # all off by one
        assert kappa(a, b, weights="quadratic") > kappa(a, b)


class TestKrippendorffOrdinal:
    def test_perfect_agreement_is_1(self):
        assert krippendorff_ordinal([(1, 1), (-1, -1)] * 5) == 1.0

    def test_sign_flip_costs_more_than_hedge(self):
        base = [(1, 1), (0, 0), (-1, -1)] * 20
        with_hedge = krippendorff_ordinal(base + [(1, 0)])
        with_flip = krippendorff_ordinal(base + [(1, -1)])
        assert with_flip < with_hedge < 1.0

    def test_empty_is_nan(self):
        assert math.isnan(krippendorff_ordinal([]))


class TestBinomP:
    def test_even_split_is_not_significant(self):
        assert binom_p_two_sided(50, 100) > 0.9

    def test_lopsided_split_is_significant(self):
        assert binom_p_two_sided(90, 100) < 1e-3

    def test_symmetric(self):
        assert binom_p_two_sided(3, 20) == pytest.approx(binom_p_two_sided(17, 20))

    def test_empty_is_nan(self):
        assert math.isnan(binom_p_two_sided(0, 0))


class TestMajority:
    def test_unanimous(self):
        assert majority([1, 1, 1]) == 1
        assert majority([-1, -1, -1]) == -1

    def test_two_one_split_takes_the_two(self):
        assert majority([1, 1, 0]) == 1
        assert majority([-1, -1, 1]) == -1

    def test_ties_are_ambivalent(self):
        assert majority([1, -1]) == 0
        assert majority([1, 0, -1]) == 0

    def test_single_sample_passes_through(self):
        assert majority([1]) == 1


class TestDisagreementRate:
    def test_identical_pairs_never_disagree(self):
        assert disagreement_rate([(1, 1), (0, 0), (-1, -1)]) == (0.0, 0.0)

    def test_sign_flip_counts_as_both(self):
        assert disagreement_rate([(1, -1)]) == (1.0, 1.0)

    def test_commit_to_hedge_is_disagreement_but_not_a_flip(self):
        assert disagreement_rate([(1, 0)]) == (1.0, 0.0)

    def test_empty_is_nan(self):
        a, f = disagreement_rate([])
        assert math.isnan(a) and math.isnan(f)
