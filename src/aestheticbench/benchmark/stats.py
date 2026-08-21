"""Agreement and uncertainty statistics for grades on small ordinal scales.

One home for the statistics that were previously implemented twice — by
``agreement.py`` through sklearn and by the order-bias experiment by hand.
Everything here is pure-Python over plain lists, because the scales involved
are tiny ({0,1}, {-1,0,1}, 1-5) and the data sizes are hundreds of items:
clarity and testability beat vectorisation at this size.

``kappa`` is verified equivalent to ``sklearn.metrics.cohen_kappa_score``
(unweighted and quadratic) by tests/test_stats.py, which is what justified
replacing the sklearn calls in agreement.py.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional, Sequence


def kappa(
    a: Sequence,
    b: Sequence,
    labels: Optional[Sequence] = None,
    weights: Optional[str] = None,
) -> float:
    """Cohen's kappa: agreement between two raters, above chance.

    Chance is what two independent raters with these same marginal
    distributions would agree on by luck; kappa = (p_o - p_e) / (1 - p_e).
    0 means no better than chance, 1 perfect. The discount matters whenever
    the marginals are skewed: two raters who both say "+1" 95% of the time
    reach ~90% raw agreement with no skill at all (the kappa paradox).

    weights="quadratic" makes disagreements cost the square of their distance
    in label positions — a -1 vs +1 miss costs 4x a 0 vs +1 miss — which is
    the standard choice for ordinal scales. Returns nan when undefined (fewer
    than 2 items, or both raters constant and identical).
    """
    if len(a) != len(b):
        raise ValueError(f"length mismatch: {len(a)} vs {len(b)}")
    n = len(a)
    if n < 2:
        return float("nan")
    if labels is None:
        labels = sorted(set(a) | set(b))
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)

    def w(i: int, j: int) -> float:
        if weights is None:
            return 0.0 if i == j else 1.0
        if weights == "quadratic":
            return (i - j) ** 2
        raise ValueError(f"unknown weights: {weights!r}")

    observed = Counter((idx[x], idx[y]) for x, y in zip(a, b))
    ma = Counter(idx[x] for x in a)
    mb = Counter(idx[y] for y in b)
    num = sum(w(i, j) * observed[(i, j)] / n for i in range(k) for j in range(k))
    den = sum(w(i, j) * (ma[i] / n) * (mb[j] / n) for i in range(k) for j in range(k))
    return float("nan") if den == 0 else 1.0 - num / den


def krippendorff_ordinal(pairs: Sequence[tuple]) -> float:
    """Krippendorff's alpha over paired reads, squared-distance metric.

    Like kappa it discounts chance, but it is distance-aware and treats the
    two positions in a pair symmetrically (no "rater 1" vs "rater 2").
    alpha = 1 - D_o / D_e: observed mean squared disagreement over the
    disagreement expected if all values were shuffled together.
    """
    if not pairs:
        return float("nan")
    vals = [v for p in pairs for v in p]
    n = len(vals)
    d_o = sum((x - y) ** 2 for x, y in pairs) / len(pairs)
    d_e = sum((x - y) ** 2 for x in vals for y in vals) / (n * (n - 1))
    return float("nan") if d_e == 0 else 1.0 - d_o / d_e


def binom_p_two_sided(k: int, n: int) -> float:
    """Exact two-sided binomial test against p = 0.5.

    The probability, under a fair coin, of an outcome at least as extreme as
    k successes in n trials — summing every outcome whose probability does
    not exceed the observed one. No scipy dependency; exact for the sizes
    this codebase sees.
    """
    if n == 0:
        return float("nan")

    def pmf(i: int) -> float:
        return math.comb(n, i) * 0.5 ** n

    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs + 1e-12))


def majority(scores: Sequence[int]) -> int:
    """The modal score across repeated reads of one thing, ties -> 0.

    A tie between +1 and -1 is exactly the case where the reads support no
    stable verdict, and calling it ambivalent is both true and conservative —
    picking a side would manufacture a verdict the samples do not support.
    """
    counts = Counter(scores)
    top = max(counts.values())
    winners = {s for s, c in counts.items() if c == top}
    return 0 if len(winners) > 1 else winners.pop()


def disagreement_rate(pairs: Sequence[tuple]) -> tuple[float, float]:
    """(any-disagreement rate, sign-flip rate) over paired reads.

    A sign flip is a pair where both reads committed (non-zero) and to
    opposite sides — the failure mode that matters more than commit<->hedge
    wobble on a {-1, 0, +1} scale.
    """
    if not pairs:
        return float("nan"), float("nan")
    any_d = sum(1 for a, b in pairs if a != b) / len(pairs)
    flip = sum(1 for a, b in pairs if a != 0 and b != 0 and a != b) / len(pairs)
    return any_d, flip
