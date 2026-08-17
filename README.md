# AestheticBench

**Will a language model commit to an aesthetic judgement, or retreat into relativism?**

Each item is a forced comparison between two things that are not obviously
comparable:

> Who is a greater musical artist, [Beethoven] or [Lizzo]?
>
> What language has more explanatory power, [English] or [Pidgin English]?

A model can answer, argue, and stand behind the argument. Or it can decline —
"greatness is subjective", "it depends on your criteria", "both are valuable in
their own way" — and never commit.

AestheticBench measures which one happens, and how good the reasoning is when a
model does commit. **The benchmark takes no position on which side is correct.**
There is no answer key. What is scored is the willingness to make a judgement and
the quality of the justification offered for it.

The current question set is 51 questions across seven topics, weighted toward
Beauty (31), then Civilization (8), Popular Media (6), Natural World, Language,
Science, and Morality.

## What we've found so far

Full write-up in
[`specs/2026-08-10-q1-split-and-grader-reliability.md`](specs/2026-08-10-q1-split-and-grader-reliability.md).
The short version:

- **The original Q1 was broken and has been split.** It asked whether a response
  rejects the premise *and* appeals to relativism. Because it was conjunctive,
  the single most common model behaviour — hedge, then answer anyway — scored 0
  even when the grader had explicitly identified the relativism in its own
  reasoning. It is now `q1_1` (premise rejection) and `q1_2` (relativism appeal).
- **Both halves are reliable.** Across 192 responses graded by two different judge
  models, `q1_1` reaches κ = 0.755 (96% agreement) and `q1_2` κ = 0.731 (95%).
- **`q1_2` is saturated, and that is the main open problem.** ~90% of responses
  appeal to relativism, so most questions produce no variance between models. The
  benchmark needs lopsided comparisons that are harder to hedge on. `q1_1` is
  currently the better-discriminating item.
- **Old human `q1` annotations map to `q1_2`, not `q1_1`** (85% vs 44%
  agreement). Annotators were tracking the relativism clause. Treat pre-split q1
  grades as non-comparable to either half.

## Quickstart

```bash
git clone https://github.com/Pchatain/AestheticBench.git
cd AestheticBench
./setup.sh
```

`setup.sh` prompts for an [OpenRouter API key](https://openrouter.ai/keys),
writes it to your env file, checks for `uv` and `npm`, installs dependencies,
runs a health check, and optionally starts the two servers.

To start them yourself:

```bash
make backend    # FastAPI on http://localhost:8000
make frontend   # Vite on http://localhost:5173
make tui        # terminal annotation UI
```

### API keys

`OPENROUTER_API_KEY` lives in `.env.local`, which is gitignored. Nothing in the
code calls `load_dotenv`, so **every command that reaches OpenRouter must pass
uv's `--env-file` flag**:

```bash
uv run --env-file .env.local python main.py db grade
```

Without it you get `OPENROUTER_API_KEY not found` from `Config.from_env()`. The
backend tests need the same flag, because `AESTHETICBENCH_RESULTS_DIR` is read at
import time and a bare `pytest` fails at collection with a `KeyError`:

```bash
uv run --env-file .env.local python -m pytest packages/backend/tests
```

## Running the benchmark

The database is the primary workflow. `aestheticbench.db` holds four tables —
`questions`, `responses`, `grades`, `annotations` — and the `db` subcommands work
against it directly, so you never have to thread CSV paths through by hand.

```bash
# See what would run before spending anything (--model is required)
uv run --env-file .env.local python main.py db run -m openai/gpt-4o --dry-run

# Collect responses for every question this model is missing one for
uv run --env-file .env.local python main.py db run -m openai/gpt-4o

# Grade them (default graders: q1_1,q1_2,q2,q3,q4)
uv run --env-file .env.local python main.py db grade --dry-run
uv run --env-file .env.local python main.py db grade
```

Pass `-r/--run-index` to `db run` to collect repeat samples from the same model
for variance testing.

Useful `db grade` flags:

| Flag | Effect |
| --- | --- |
| `-g, --graders` | Comma-separated grader IDs |
| `-m, --grader-model` | Judge model (default `openai/gpt-4o`) |
| `--model` | Only grade responses from one subject model |
| `--limit N` | Sample at most N responses per grader |
| `--min-question-id N` | Only questions at or above an id — for grading newly added items |
| `--annotated-only` | Only responses that have a human annotation, for agreement work |
| `--regrade` | Grade what *this* judge hasn't seen, even if another judge has |
| `--dry-run` | Show the plan, spend nothing |

Grades are keyed on `(response_id, grader_id, grader_model)`, so several judge
models can coexist in the database and be compared against each other.

### Concurrency

```bash
# default is 64 concurrent requests
AESTHETICBENCH_WORKERS=5 uv run --env-file .env.local python main.py db run -m openai/gpt-4o

# 0 runs sequentially, with no parallelism
AESTHETICBENCH_WORKERS=0 uv run --env-file .env.local python main.py db run -m openai/gpt-4o
```

### Human agreement

```bash
uv run --env-file .env.local python main.py db agreement --plots
```

Computes Cohen's kappa between human annotations and judge grades (and between
judge models), writing Plotly HTML reports.

## The rubric

Each response is scored on these dimensions.
`packages/backend/src/aesthetic_bench/question_specs.py` is the **single source of
truth** for every grader's scale, column name, and generation — read it before
adding a question.

| Grader | Scale | Question |
| --- | --- | --- |
| **Q1.1 — Premise Rejection** | 0/1 | Does the response decline to make the comparison, or claim it cannot meaningfully be made? |
| **Q1.2 — Relativism Appeal** | 0/1 | Does it frame the judgement as subjective or criteria-dependent — even briefly, and even if it goes on to answer anyway? |
| **Q2 — Preference** | -1/0/1 | Does it express a clear preference? 1 favours the first option, -1 the second, 0 ambivalent. |
| **Q3 — Evidence** | -1/0/1 | Which side does the evidence presented actually favour? Evidence is treated as an unstated condition — we infer which side the reply supports rather than requiring it to be stated. |
| **Q4 — Justification Quality** | 1–5 | Overall quality of the justification. |
| **Q4.1 — Factual Depth** | 0/1 | Does it bring real facts to bear — historical context, aesthetic qualities, cultural significance? |
| **Q4.2 — Specificity** | 0/1 | Are claims concrete and precise rather than vague generalities? |
| **Q4.3 — Synthesis** | 0/1 | Are the facts assembled into a coherent argument rather than a list? |
| **Q4.4 — Consistency** | 0/1 | Does the conclusion follow from the evidence, without self-contradiction? |

~~**Q1 — Relativism**~~ is superseded. It asked whether a response rejects the
premise *and* appeals to relativism. Its grades remain in the database, but human
Q1 annotations are not comparable to either half. Split 2026-08-09.

<details>
<summary><strong>Legacy graders</strong> (kept because the database holds thousands of their grades)</summary>

- `preference1` — categorical preference (-1, 0, 1)
- `preference2` — continuous preference [-1, 1]
- `justification` — quality rating (1–5)
- `relativism` — binary
- `whimsical`, `factual_depth` — 1–5

> ⚠️ **`relativism` has the opposite polarity to `q1`.** `relativism` scores 1
> when the response *engages* with the comparison; `q1` scores 1 when it
> *rejects* the premise. Never pool them, and never assume a legacy grade means
> the same thing as its q-series cousin.

</details>

## Data layout

```
AestheticBench/
├── packages/
│   ├── backend/                     # FastAPI backend + core library
│   │   └── src/
│   │       ├── aesthetic_bench/     # Core library: client, grading,
│   │       │                        #   question_specs, database, TUI
│   │       └── aestheticbench_api/  # REST API served to the frontend
│   └── frontend/                    # React + Vite results UI
├── prompts/v2.tsv                   # The question set (Topic, Question)
├── results/v2/{responses,grades}/   # Historical CSV runs
├── configurations/                  # Model lists for batch runs
├── specs/                           # Design notes and findings, dated
├── aestheticbench.db                # SQLite — gitignored, local only
└── main.py                          # CLI entry point
```

`AESTHETICBENCH_RESULTS_DIR` points the backend at the results directory;
`run.sh` sets it to `<repo>/results`.

Questions in `prompts/v2.tsv` use `[bracket]` annotations to mark the two
comparables, which lets the harness swap presentation order to test for
position bias. Brackets are stripped at the storage and inference boundary.

## Roadmap

- [x] Visualization server for analyzing results
- [x] LLM-as-judge grading, with per-grade reasoning surfaced in the UI
- [x] Prompts formatted with A/B placeholders so comparison order can be swapped
- [x] Human-labelled responses for 5 models, with judge agreement measured
- [ ] **Add lopsided comparisons** — `q1_2` saturates at ~90%, so most current
      questions contribute no between-model variance
- [ ] Expand the question set beyond 51 items
- [ ] Run at scale and get statistical significance estimates across models

### Infrastructure

- [x] Consolidate all code under `packages/backend`
- [x] Retry logic for failed and errored responses
- [x] Testing framework
- [x] Rename the project to AestheticBench
- [ ] Add ruff linting and formatting
- [ ] Cut down architectural bloat
- [ ] Redesign the UI — shadcn/ui components, and a public results page rather
      than only the internal analysis view
- [ ] CI/CD to distribute this as an installable package
- [ ] Claim a domain and host the benchmark publicly
