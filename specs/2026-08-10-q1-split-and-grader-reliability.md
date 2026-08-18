# Q1 split and grader reliability

Findings from the 2026-08-09/10 session. Written down because most of it is not
recoverable from the code or the git history.

## Summary

The original `q1` asked two questions at once and was unreliable as a result. It
was split into `q1_1` (premise rejection) and `q1_2` (relativism appeal). Both
halves are far more reliable than the original, and `q1_1` is the better
benchmark item. The current question set saturates `q1_2`, which limits what it
can measure.

## The q1 problem

`q1` asked "does the answer reject the premise of the question **and** appeal to
relativism?" Because it was conjunctive, the common model behaviour — hedge
("beauty is subjective"), then answer anyway — scored 0, even when the grader had
explicitly identified the relativism in its own reasoning. The judge stated the
rule itself when re-graded:

> "The response *does* appeal to relativism ... However, it does not reject the
> premise ... Since it doesn't both reject the premise and appeal to relativism,
> the correct score is 0."

Human annotations disagreed with `q1` on 8 of 27 items, all in the same direction
(human 1, judge 0). Breaking those down:

- 3 were the judge contradicting *itself* — reasoning began "Yes" while the score
  field said 0. Not a human/judge gap at all.
- 5 were a genuine definitional gap: the annotator was scoring the relativism
  clause alone, the judge was enforcing the conjunction.

## Human q1 annotations map to q1_2, not q1_1

Comparing the 27 human `q1` annotations against each grader:

| human q1 vs | n | kappa | agreement |
|---|---|---|---|
| old q1 judge (conjunctive) | 27 | 0.393 | 19/27 (70%) |
| q1_1 (rejects premise) | 27 | 0.147 | 12/27 (44%) |
| q1_2 (appeals to relativism) | 27 | 0.289 | **23/27 (85%)** |

When the annotator marked "Yes" they were tracking the *relativism* clause. The
old human q1 annotations are therefore closer to q1_2 data than to anything else;
migrating rather than discarding them is worth considering, bearing in mind the
kappa is low because q1_2's base rate is extreme (see below).

Separately, the old judge's `q1` was not cleanly measuring either clause: it
agreed with `q1_1` on only 19/28 and said "yes" 14 times against `q1_1`'s 7.

## Inter-grader reliability (gpt-5.2 vs claude-sonnet-4.5)

Same 192 responses (48 questions x 4 models), both graders:

| question | n | IRR kappa | agreement | gpt-5.2 rate | sonnet rate |
|---|---|---|---|---|---|
| q1_1 Premise Rejection | 192 | **0.755** | 96% | 17/192 (9%) | 14/192 (7%) |
| q1_2 Relativism Appeal | 192 | **0.731** | 95% | 173/192 (90%) | 174/192 (91%) |

For context, every other reliability figure in the project:

| comparison | kappa |
|---|---|
| human vs judge, old q1 | 0.393 |
| human vs judge, q2 / q3 / q4 | 0.10 - 0.40 |
| inter-model graders, Feb 2026 (q1/q2/q3) | 0.02 - 0.27 |

Asking one thing at a time roughly tripled reliability. Caveats: this is
grader-vs-grader, not grader-vs-truth — two frontier models can be consistently
wrong together — and `q1_2`'s kappa is flattered by its 90% base rate. `q1_1`'s
0.755 comes from a much harder distribution and is the more trustworthy number.

No evidence of grader self-favouritism: gpt-5.2 graded itself *more* hedging than
sonnet did (98% vs 94%), and sonnet graded itself identically to gpt-5.2 (85%).

## The question set saturates q1_2

Across 4 models x 48 questions, `q1_2` fires on 90% of responses. Only **10 of 48**
questions ever drew a 0; **38 were unanimous 1** and contribute no variance.

Per-model rates are compressed and grader-dependent, so only one ordering is
stable across both graders: claude-sonnet-4.5 hedges least (85%).

| model | gpt-5.2 grader | sonnet grader |
|---|---|---|
| claude-sonnet-4.5 | 85% | 85% |
| gemini-2.5-pro | 85% | 90% |
| grok-4-fast | 92% | 94% |
| gpt-5.2 | 98% | 94% |

**The discriminating questions are the lopsided ones** — where one comparable is
conspicuously weaker, models drop the hedge and commit:

```
1/4  The Godfather or Paul Blart: Mall Cop?      2/4  Coltrane or Kenny G?
2/4  Japanese kaiseki or American fast food?     3/4  James Stewart or Mark Wahlberg?
2/4  Saddam Hussein or Charles de Gaulle?        2/4  Ingrid Bergman or Sidney Sweeney?
```

The single most discriminating item is "Is it better to be overweight or not
overweight?" (4/10) — nearly the only question in the set with a defensible
objective answer.

So `q1_2` currently measures **how obvious the comparison is**, with model identity
as a secondary effect. To rank models on relativism the set needs more lopsided
pairs. To study hedging itself the close pairs are the right stimulus, but the
metric should not be a binary that is 90% ones.

## Direction

- `q1_1` is the better benchmark item: reliable (0.755) and discriminating (9%
  base rate leaves room to separate models).
- Human annotations on `q1_1`/`q1_2` are the missing piece. There are none yet, so
  the agreement report shows n=0 for both. Until then we only know the graders are
  *consistent*, not that they are *right*.
- Add questions with lopsided comparables so more than 10 of 48 items carry signal.

## Data quirks worth remembering

- **9 pre-Q1-Q4 annotations have wrong `response_id`s.** They were imported with
  `response_id = result_uid`, a per-question index rather than a response id, so
  they attach to unrelated models' responses. Always join annotations on
  `a.model = r.model` as well as `response_id`; `get_annotations_with_grades(valid_only=True)`
  does this and yields 28 clean rows out of 37.
- **`relativism` (legacy) is the polarity inverse of `q1`.** Legacy 1 = engages
  substantively; q1 1 = rejects the premise. Never pool them.
- **3 responses are failed generations** (`ERROR: Request failed`) sitting in the
  `responses` table and being graded as if real.
- **`grader_model` is NULL on 3343 older grades** — the column postdates them, so
  which model produced those grades is unrecoverable. Any kappa mixing them with
  new grades is pooling two different judges.
