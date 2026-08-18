# Repo reorganization — findings and plan

Status: **phases 0, 2, 3, 4 landed on branch `reorg` (2026-08-18); phase 1 is
not started and needs a decision first.** Written 2026-08-18 against
`order-bias-experiment` @ 65ebef5.

What landed, and where it deviates from section 4 below:

- `prompts/v2.tsv` **stayed where it was** rather than moving to
  `prompts/questions/` — the concurrent order-bias work reads that path, and the
  move bought nothing but a merge conflict.
- `human_judge_agreement.py` became `benchmark/agreement.py`, not
  `benchmark/analysis/`; one file does not need a directory.
- `api/services/` stayed inside `api/` untouched. Four of its five modules are
  the CSV half that phase 1 deletes, so moving them first was wasted motion.
- `cli/main.py` was moved, not split by command group — same reason.
- **Added, not in the plan:** `src/aestheticbench/paths.py`. Four modules each
  computed the repo root with a different `Path(__file__).parents[N]`, and the
  move would have broken every one of them differently. `RESULTS_DIR` now
  defaults to `<root>/results`, which is what removed the `--env-file`
  requirement from `pytest` (section 2's `_shared.py` note).
- Untracked artefacts (`results/v0.1`, `results/v1`, `results/agreement`,
  the `.db.bak`, root CSVs) were **not** deleted — they exist only in the main
  checkout, and deleting untracked files is the owner's call.


The ask: `packages/` is noise, "backend" holding both `aesthetic_bench` and
`aestheticbench_api` is confusing, there should be one obvious place to look for
prompts, one for data-labelling code, and one for the benchmark itself.

---

## 1. What is actually confusing

### 1.1 `packages/` holds exactly two things and will never hold three

`packages/{backend,frontend}` is a monorepo shape with no monorepo in it. The
`[tool.uv.workspace]` members list is one entry long. The layer buys nothing and
costs a directory level in every path in the docs.

### 1.2 "backend" is three things, and the two package names differ by one underscore

`packages/backend/src/` contains:

- `aesthetic_bench/` — the core library: OpenRouter client, grading, rubric,
  SQLite access, **and the Textual annotation TUI**
- `aestheticbench_api/` — FastAPI routes, schemas, **and `services/`**

`aesthetic_bench` vs `aestheticbench_api` is a genuine reading hazard: the only
difference is an underscore, and neither name tells you which is which.

**And the stated layering is already violated.**
`packages/backend/src/aesthetic_bench/README.md` says "nothing in
`aesthetic_bench` may import from here" — but `main.py`, the CLI, imports four
service modules *out of the web package*:

```
main.py:23  from aestheticbench_api.services.config_service import ConfigService
main.py:24  from aestheticbench_api.services.discovery   import DiscoveryService
main.py:25  from aestheticbench_api.services.estimation  import EstimationService
main.py:26  from aestheticbench_api.services.scoring     import ScoringService
```

So the split is not library-vs-API. It is *older code vs newer code*. That is
why "why both?" feels wrong — because the boundary doesn't mean anything.

### 1.3 The real problem is bigger than directories: there are two data stores

This is the largest source of confusion in the repo, and moving directories will
not touch it.

| | SQLite `aestheticbench.db` | CSV `results/v2/{responses,grades}` |
| --- | --- | --- |
| CLI | `main.py db run/grade/agreement/...` | `main.py run/grade/export-grades/export-stats/compute-scores` |
| API | `routes/annotations.py` | `routes/results.py`, `routes/experiments.py` |
| services | — | `discovery.py`, `scoring.py`, `estimation.py`, `config_service.py` |
| UI | `Q1Q4Annotator.tsx` | `Annotator.tsx`, `ResultsTable`, `Analytics`, `GradeExplorer` |
| scripts | — | `scripts/grade_all.sh` |

Two annotators in the UI, two `run`/`grade` command families in one CLI, two
storage layers behind one frontend. README already calls the database "the
primary workflow" — the CSV half is a second, undeclared system.

### 1.4 "Prompts" means two different things, in three places

- benchmark **questions** → `prompts/v2.tsv` — correct, top-level, findable
- grader **prompt text** → `aesthetic_bench/grader_prompts.py`, as Python string
  constants
- grader **scales / column names / generation** → `question_specs.py`
- and the rubric is restated in prose in `README.md`, in the `grade_all.sh`
  header, and across `specs/`

Someone asked to "go look at the prompts" finds one third of them.

### 1.5 Leftovers from the MoralBench rename

The rename landed 2026-08-10 (`specs/2026-08-10-rename-to-aesthetic-bench.md`),
but two references survived and they are the reason this repo still reads as
"moral_bench" to a human:

- `pyproject.toml:5` — `description = "Package to measure the morality of LLMs"`
- `aesthetic_bench/__init__.py:1` — same sentence in the docstring
- `CHANGELOG.md:39,73` — paths still say `moral_bench` / `moralbench_api`

---

## 2. Dead code and stale artefacts

Verified by grep across `*.py`, `*.ts`, `*.tsx`, `*.sh`, `*.md`, excluding
`node_modules`.

| Item | Size | Evidence |
| --- | --- | --- |
| `aesthetic_bench/csv_cleaner.py` | 224 lines | **zero** references outside a README table row and one 2026-03 spec |
| `results/v0.1/` | 992 KB | referenced by no code, no script, no doc — **and untracked**, so deletion is permanent |
| `results/v1/` | 2.1 MB | same, also untracked — `specs/2026-03-15-v1-removal…` already planned this |
| `routes/prompts.py` + `GraderPrompts.tsx` | 64 + 53 lines | serves **only** the six legacy graders. The UI's "Prompts" page shows a rubric the benchmark no longer runs |
| `scripts/grade_all.sh` | 90 lines | grades `q1` — superseded, split into `q1_1`/`q1_2` on 2026-08-09 — via the CSV path |
| `packages/backend/data/experiments/` | empty | — |
| `aestheticbench.db.bak-pre-runidx` | 16 MB | untracked backup in the repo root |
| root `*.csv` (`grades_stats`, `grades_summary`, `model_scores`, `question_comparison`), `top.png` | ~130 KB | command outputs living in the repo root |
| `results/agreement/` | **51 MB** | generated Plotly HTML, untracked, regenerable by `db agreement --plots` |

Also worth noting, not strictly dead:

- `Makefile:10` runs the TUI **by file path**
  (`uv run python packages/backend/src/aesthetic_bench/annotate_tui.py`) while
  everything else uses installed-module imports. It works only because the venv
  has the package installed.
- `routes/_shared.py:11` reads `AESTHETICBENCH_RESULTS_DIR` **at import time**,
  which is the sole reason `pytest` needs `--env-file` and fails at *collection*.
  A lazy accessor removes a documented footgun in ~5 lines.
- 63 of the repo's 173 tracked files are `results/v2/` CSVs (42 grades, 21
  responses). `v0.1/`, `v1/` and `agreement/` are **untracked** — archive them
  off-repo before deleting, because git does not have a copy.

---

## 3. Prior art

Common shape across the benchmarks worth copying from:

- **lm-evaluation-harness** — `lm_eval/{api,models,tasks}`; tasks are YAML data,
  not code
- **Inspect AI** — `src/inspect_ai/{dataset,model,solver,scorer,log}`; the
  grader is called a *scorer* and is its own top-level concept
- **HELM** — `src/helm/benchmark/{scenarios,run_specs,metrics}`
- **BIG-bench** — `bigbench/benchmark_tasks/<task>/task.json`; prompts are data
  files, one directory per task

The three things they all share: **one** installable package under `src/`,
**prompts/tasks as data outside the code**, and **one** CLI entry point.

---

## 4. Proposed layout

```
AestheticBench/
├── prompts/                      # ALL prompt text. Data, not code.
│   ├── questions/v2.tsv          #   the benchmark items (moved from prompts/v2.tsv)
│   └── graders/                  #   one file per grader: q1_1.md, q1_2.md, q2.md …
│       └── legacy/               #   preference1, relativism, whimsical …
├── src/aestheticbench/
│   ├── benchmark/                # runs the benchmark
│   │   ├── run.py                #   ← processor.py + services/execution.py
│   │   ├── grading.py            #   judge calls, JSON parsing, validation
│   │   ├── rubric.py             #   ← question_specs.py (scales, columns, generation)
│   │   ├── prompts.py            #   loader for prompts/ — the only reader of that dir
│   │   ├── client.py  config.py  errors.py  text_utils.py
│   │   └── analysis/             #   ← scoring.py, human_judge_agreement.py, estimation.py
│   ├── labelling/                # everything about human labels
│   │   ├── tui.py                #   ← annotate_tui.py
│   │   └── store.py              #   annotation reads/writes
│   ├── store/database.py         # SQLite — the one data layer
│   ├── api/                      # FastAPI. Thin. routes/ + schemas/ only
│   └── cli/                      # ← main.py, split by command group
├── web/                          # ← packages/frontend (React + Vite)
├── results/  configurations/  specs/  scripts/  tests/
└── pyproject.toml                # single project, no workspace
```

What this fixes, point by point:

- `packages/` is gone; top level reads as *what the thing is*, not *how it ships*
- one Python package, `aestheticbench`. No more `aesthetic_bench` /
  `aestheticbench_api` twins
- `benchmark/` is the answer to "where does the benchmark run and grade?"
- `labelling/` + `web/` is the answer to "where's the data-labelling app?"
- `prompts/` is the answer to "where are the prompts?" — **all** of them
- `api/` sits *inside* the package, so `cli/` importing shared logic is no longer
  a layering violation. It stops being wrong by construction rather than by rule.

**Alternative if you want the web app fully separate:** keep `src/aestheticbench/`
for the library+CLI and lift the FastAPI app to a top-level `app/{api,web}/`. I'd
recommend against it — the API is 2.4k lines that exist only to expose the
library, and splitting it back out recreates today's import problem.

---

## 5. Sequencing

Each phase is independently verifiable and separately revertable. **Phases 1 and
2 should not be one PR.** Phase 1 is the one that actually removes confusion;
phase 2 is cosmetic by comparison. Note another session is live on
`order-bias-experiment` (`scripts/order_bias.py`, `tests/test_order_bias.py`) —
phase 2 will conflict with anything in flight, so land it when the tree is quiet.

**Phase 0 — delete the dead. No behaviour change.**
`csv_cleaner.py`, `results/v0.1/`, `results/v1/`, empty `data/experiments/`, the
`.bak` db, root output CSVs. Drop `csv_cleaner` from the module README table. Fix
the two "morality" strings and the `moral_bench` paths in CHANGELOG.
*Verify:* `pytest packages/backend/tests` still green; frontend still builds.
*Size:* ~1 hour, near-zero risk.

**Phase 1 — pick one data store.** SQLite is already declared primary, so port
`routes/results.py`, `routes/experiments.py` and the three CSV services onto the
DB, then delete the CSV CLI commands (`run`, `grade`, `export-grades`,
`export-stats`, `compute-scores`), `grade_all.sh`, `Annotator.tsx`, and
`routes/prompts.py` + `GraderPrompts.tsx`. `results/v2/` becomes archive.
*Confirm first:* that you aren't still running the CSV commands by hand.
*Size:* the real work — its own spec, its own PR. This deletes more code than
everything else here combined (main.py alone is 1,267 lines, most of it the CSV
half).

**Phase 2 — the move.** Mechanical: `git mv` + import rewrite, one commit.
`specs/2026-08-10-rename-to-aesthetic-bench.md` is a working template for it.
Paths to update outside the source: `setup.sh` (11 refs), `Makefile` (3),
`pyproject.toml` (workspace members), `README.md` (4), `CLAUDE.md` (4),
`packages/backend/run.sh`.
*Verify:* tests + `make backend` + `make frontend` + `make tui`.

**Phase 3 — prompts as data.** Extract the grader strings from
`grader_prompts.py` into `prompts/graders/*.md`, load them in
`benchmark/prompts.py`, keep `rubric.py` as the scale/column authority. Adding a
grader becomes: write a file, add a spec row.

**Phase 4 — docs.** README data-layout block, module README, `CLAUDE.md` paths,
Makefile, `run.sh`, `setup.sh`. Fold in the `_shared.py` import-time env fix so
the `--env-file`-at-collection paragraph can be deleted rather than reworded.

---

## 6. If you only do one thing

Phase 1. The directory names are annoying; the two parallel data stores are the
thing that makes this repo hard to reason about, and they are why "backend" ended
up holding two packages in the first place.
