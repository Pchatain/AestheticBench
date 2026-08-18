# Order bias, and what the rubric looks like downstream of q2

*2026-08-18*

Two pieces of work. The first re-reads the existing grades conditioned on the
top-line measure. The second is a new experiment that runs every question both
ways round.

## Part 1 — the rubric, conditioned on q2

`q2` is the benchmark's actual claim: did the model commit to a preference, and
to which side. Every other grader is only interesting as a way of understanding
*how* it committed. So the useful view is each grader's distribution within the
`q2 = -1 / 0 / +1` cells, not its marginal.

Judge `openai/gpt-5.2`, n = 104 responses (the set that carries the full q-series).
`q1_1` is excluded — it is being retired from this view.

| given q2 | q1_2 = 1 | q3 mean | q4 mean | q4_1 | q4_2 | q4_3 | q4_4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **-1** (n=21) | 81% | -0.81 | 3.95 | 100% | 100% | 100% | 100% |
| **0** (n=25) | **100%** | **+0.68** | **3.60** | 100% | 100% | 100% | 100% |
| **+1** (n=58) | 86% | +1.00 | 3.88 | 100% | 100% | 100% | 98% |

### `q4_1`, `q4_2` and `q4_3` are dead and should be dropped

Every one of the 104 responses scores 1, in every q2 cell. `q4_4` is 99%. These
four binary sub-questions cannot discriminate anything — they are not weak
signals, they are constant. `q1_2` already had a known saturation problem at
~90%; these are worse, at 100%.

### `q3` earns its keep only in the q2 = 0 cell

When the model commits, `q3` is very nearly a copy of `q2`: q2=+1 implies q3=+1
in 100% of cases, q2=-1 implies q3=-1 in 90%. Two graders spending two calls to
produce one number.

The exception is the cell that matters. When a model refuses to state a
preference, **its evidence still leans to the first option 72% of the time**
(q3 mean +0.68). Hedging is a presentation choice laid over a judgement the
model has already made, not a genuine indifference — and `q3` is the only
grader that can see it.

### Refusing to choose is the worst-justified answer

`q4` is lowest in the q2=0 cell under both judges (3.60 for gpt-5.2, 3.39 for
sonnet-4.5) and higher on both committed sides. Declining to pick does not buy
a more careful answer; it buys a worse one.

### Two caveats on this set

- **It is grok-weighted.** 52 of the 104 responses are `x-ai/grok-4.6`; the
  other 13 models contribute 4 each. No per-model conclusion survives that.
- **Sonnet-4.5's `q3` is not trustworthy.** It scores q3=+1 for 87% of the
  responses it *itself* graded q2=-1, which is incoherent. The two judges agree
  on q3 only 79% of the time, against 85% on q2. Prefer gpt-5.2 for q3.

## Part 2 — the order-bias experiment

The q2 marginal on that set is -1: 20%, 0: 24%, **+1: 56%**. Models pick the
first-named comparable nearly 3x as often as the second. There were two
explanations and the benchmark could not tell them apart:

1. the questions are written with the "obvious" winner named first, or
2. models favour whatever they read first.

`scripts/order_bias.py` separates them by asking every sampled question twice —
once as written, once with the two `[bracketed]` entities swapped — and grading
both on `q2` alone.

**Design.** 4 subject models x 20 questions x 2 orientations = 160 responses,
each graded by 2 judges = 320 gradings. No errors in either stage.

- Subject models, chosen to span the observed commit-vs-hedge range across four
  labs: `x-ai/grok-4.6` (hedges on 8% of questions), `anthropic/claude-opus-4.5`
  and `openai/gpt-5.2` (~50%), `deepseek/deepseek-v3.2` (75%).
- Judges: `openai/gpt-5.2` and `anthropic/claude-sonnet-4.5`. Both already grade
  the main `grades` table, where they agree exactly on q2 for 85% of 104 shared
  responses — so a disagreement here reads against a known baseline.
- Questions: 20 sampled with `--seed 20260818` from the 51 in `prompts/v2.tsv`
  that carry exactly two `[bracketed]` entities.

### Result: the bias is real, and it is entirely visible in the flips

**Aggregate slot preference is only mildly first-favouring.** Pooled over both
orientations, where a balanced design gives neither slot an advantage:

| judge | +1 (first) | 0 (hedge) | -1 (second) | p |
| --- | --- | --- | --- | --- |
| claude-sonnet-4.5 | 35% | 44% | 21% | 0.026 |
| gpt-5.2 | 39% | 27% | 34% | 0.460 |

**But conditional on the verdict moving at all, the direction is unanimous.**
13 of the 160 matched pairs are sign flips — the model committed both times and
named a different entity each time. A flip means it sided with the same *slot*
twice. All 13 sided with the first-printed slot; none with the second.

    toward FIRST-printed slot : 13
    toward SECOND-printed slot: 0
    two-sided binomial p      : 0.00024

Noisy judgement predicts a coin flip here. Position bias predicts all-first.
We got all-first.

### Stability

| | share of 160 pairs |
| --- | --- |
| stable-commit | 48% |
| stable-hedge | 26% |
| commit <-> hedge | 18% |
| **sign flip** | **8%** |

So ~74% of verdicts survive a reordering, and the single biggest source of
instability is not the sign flip but the **commit/hedge boundary** (18%) — a
model that answers one way round and ducks the other. That matters for the
benchmark's headline number: the commit rate itself is order-sensitive.

Hedge rate is flat across orientations (34% forward, 36% reversed), so the
swap does not make questions systematically easier or harder to duck; it moves
individual items in both directions.

Per model, and per judge:

| subject model | stable | flip | commit<->hedge |
| --- | --- | --- | --- |
| x-ai/grok-4.6 | 80% | 10% | 10% |
| anthropic/claude-opus-4.5 | 78% | 12% | 10% |
| deepseek/deepseek-v3.2 | 70% | 2% | 28% |
| openai/gpt-5.2 | 68% | 8% | 25% |

| judge | stable | flip | commit<->hedge |
| --- | --- | --- | --- |
| openai/gpt-5.2 | 80% | 6% | 14% |
| anthropic/claude-sonnet-4.5 | 68% | 10% | 22% |

deepseek-v3.2, the strongest hedger, almost never flips sign — it retreats to
ambivalence instead. The two failure modes trade off against each other rather
than adding up.

If a pair must be stable under *both* judges to count, only 60% of the 80
(model, question) pairs qualify. Single-judge stability numbers are optimistic.

### What this means for the benchmark

- **Both orientations should be collected for every question.** A single-order
  run confounds the model's judgement with the question author's ordering, and
  8% of committed verdicts are pure slot artefact.
- **Report the canonical verdict, not the raw one.** `_canonical()` in the
  script is the conversion; getting its sign backwards turns perfect
  consistency into a 100% flip rate, which is why it is pinned by tests.
- **Order-stability is a model property worth scoring in its own right.** It
  separates grok-4.6 and opus-4.5 (stable, occasionally flip) from
  deepseek-v3.2 and gpt-5.2 (less stable, mostly via hedging) in a way the
  current rubric does not.

## Reproducing

```sh
uv run --env-file .env.local python scripts/order_bias.py --dry-run
uv run --env-file .env.local python scripts/order_bias.py --stage collect
uv run --env-file .env.local python scripts/order_bias.py --stage grade
uv run --env-file .env.local python scripts/order_bias.py --stage report
```

Results live in `order_bias_responses` and `order_bias_grades`, deliberately
**not** in `questions`/`responses`: a reversed question added there would become
a new question for every model, and the next plain `db run` would silently start
collecting it.

Scores are stored raw, exactly as the judge emitted them, so `+1` means the same
thing it means in the main `grades` table — "prefers the comparable printed
first". Canonicalisation happens at read time.
