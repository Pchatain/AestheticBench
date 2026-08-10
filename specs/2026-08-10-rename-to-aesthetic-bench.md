# Rename MoralBench → AestheticBench

**Date:** 2026-08-10
**Status:** Planned

The repo no longer measures morality. Every prompt in `prompts/v2.tsv` is an aesthetic
comparison (`Beauty`, `Language`, …) and every current grader (q1_1 … q4_4) scores whether a
model will *commit to an aesthetic judgement* rather than retreat into relativism. The name,
the package identifiers, and the README all still describe the original moral-reasoning
project. This plan renames the whole surface and rewrites the README to match what the
benchmark actually does.

## 1. Naming convention

One decision drives every mechanical edit. Proposal:

| Surface | Old | New |
| --- | --- | --- |
| GitHub repo / display name | `MoralBench` | `AestheticBench` |
| Local directory | `MoralBench/` | `AestheticBench/` |
| Root distribution (`pyproject.toml`) | `moralbench` | `aestheticbench` |
| Backend distribution | `moralbench-api` | `aestheticbench-api` |
| Core import package | `moral_bench` | `aesthetic_bench` |
| API import package | `moralbench_api` | `aestheticbench_api` |
| Frontend npm package | `moralbench-ui` | `aestheticbench-ui` |
| Env var prefix | `MORALBENCH_` | `AESTHETICBENCH_` |
| SQLite file | `moralbench.db` | `aestheticbench.db` |
| Frontend localStorage prefix | `moralbench-` | `aestheticbench-` |

Alternatives if `AestheticBench` reads wrong: `AestheticsBench` / `aesthetics_bench`, or a
non-"bench" name. **Pick before step 2 starts** — it is the only irreversible-ish choice here
(the GitHub rename), and every later step is a mechanical substitution of the table above.

## 2. Pre-flight

1. **Land or close open branches first.** `git branch -a` shows ~15 local branches. A
   directory rename of `src/moral_bench` → `src/aesthetic_bench` turns every unmerged branch
   into a rename/edit conflict. Merge what's live, delete what's dead, then rename.
2. **Back up the database.** `moralbench.db` is gitignored (`.gitignore:9`) and ~9 MB — it
   exists only on this machine. `cp moralbench.db moralbench.db.bak` before touching it.
   Nothing in the rename alters schema or rows; only the filename changes.
3. **Remove the stale worktree** `.claude/worktrees/english-pidgin-prompt` — it carries a full
   copy of the old `packages/backend/src/moral_bench` tree and will confuse repo-wide greps.
4. Note the current baseline so step 8 has something to compare against:
   `uv run --env-file .env.local python -m pytest packages/backend/tests`.

## 3. GitHub + local checkout

1. Rename the repo on GitHub: `Pchatain/MoralBench` → `Pchatain/AestheticBench`. GitHub keeps a
   redirect from the old URL, so existing clones keep working, but update anyway:
   `git remote set-url origin https://github.com/Pchatain/AestheticBench.git`
2. Rename the local directory `~/Documents/ai_projects/MoralBench` → `.../AestheticBench`.
   Consequences to handle in the same pass:
   - Absolute paths in `scripts/analysis.ipynb` (a stored output cell prints
     `/Users/peterchatain/Documents/ai_projects/MoralBench/moralbench.db`) — regenerate or
     clear notebook outputs.
   - Any Claude Code / droid session directories keyed on the old path are orphaned; expected,
     nothing to migrate.
   - `AGENTS.md` is a symlink to `CLAUDE.md` (relative) — survives the move.
3. Do the directory rename **after** the code changes are committed and pushed, so a
   half-renamed working tree never has to be reasoned about across two paths.

## 4. Python packages

Use `git mv` for the directory renames so history follows the files.

```
git mv packages/backend/src/moral_bench    packages/backend/src/aesthetic_bench
git mv packages/backend/src/moralbench_api packages/backend/src/aestheticbench_api
```

Then update, in order:

- `pyproject.toml` — `name = "moralbench"` → `aestheticbench`; the `description` ("Package to
  measure the morality of LLMs") → aesthetic wording; the `moralbench-api` dependency entry;
  the `[tool.uv.sources]` key `moralbench-api = { workspace = true }`.
- `packages/backend/pyproject.toml` — `name`, `description` ("FastAPI backend for MoralBench
  results viewer"), and `[tool.hatch.build.targets.wheel] packages = [...]` which lists both
  source directories explicitly and will silently ship an empty wheel if missed.
- `packages/backend/run.sh:10` — `uvicorn moralbench_api.main:app` → `aestheticbench_api.main:app`.
- Imports: 47 `moral_bench` references across 25 files and 18 `moralbench_api` references
  across 10 files — `main.py`, all nine files under `packages/backend/tests/`, `scripts/*.py`,
  and cross-imports inside the two packages themselves.
- Regenerate the lockfile: `uv lock` (or `uv sync`). `uv.lock` pins both workspace member names
  and will not resolve until it is rebuilt.
- Delete stale bytecode: `find . -name __pycache__ -type d -prune -exec rm -rf {} +`, plus the
  root `__pycache__/` and `*.egg-info` if present. A leftover `moral_bench` egg-link makes the
  old import name keep working locally and hides missed call sites.

## 5. Environment variables

Two variables, hard cut (single-developer repo — no deprecation shim):

- `MORALBENCH_WORKERS` → `AESTHETICBENCH_WORKERS`:
  `packages/backend/src/moral_bench/config.py:42,46,49` and three README examples.
- `MORALBENCH_RESULTS_DIR` → `AESTHETICBENCH_RESULTS_DIR`:
  `packages/backend/run.sh:5,6`, `packages/backend/src/moralbench_api/routes/_shared.py:11`,
  `packages/backend/src/moralbench_api/routes/workflow.py:42`, and `CLAUDE.md:15`.

`_shared.py:11` reads the variable at **import** time, so a stale value exported in an old
shell surfaces as a `KeyError` during test collection rather than a clean error. After the
rename, open a fresh shell (or `unset MORALBENCH_RESULTS_DIR`) before running the backend.

`.env.example` and `.env.local` only hold `OPENROUTER_API_KEY` — no change.

## 6. Database file

Rename the file and the ten places that name it. All are string literals; no schema migration.

```
mv moralbench.db aestheticbench.db
```

- Defaults in `main.py` at lines 803, 827, 867, 960, 1091, 1124, 1156 (seven Typer options).
- `packages/backend/src/moral_bench/database.py:165` — the `Database.__init__` default.
- `packages/backend/src/moral_bench/annotate_tui.py:28` — `Path(__file__).parents[4] / "moralbench.db"`.
- `packages/backend/src/moralbench_api/routes/annotations.py:20` — `parents[5] / "moralbench.db"`.
- `scripts/query_db.py:10`, `scripts/inspect_annotations.py:25`, `scripts/analysis.ipynb`.
- `.gitignore:9`.

The `parents[4]` / `parents[5]` depths stay correct — directory nesting is unchanged, only the
leaf directory names differ. Keep `.annotator_state.json` as-is; it sits next to the DB and its
name carries no product branding.

Verify after: `sqlite3 aestheticbench.db ".tables"` still lists `annotations`, `grades`,
`questions`, `responses`, and `uv run python main.py db stats` (or equivalent) reports the same
row counts as before the move.

## 7. Frontend

- `packages/frontend/package.json` — `"name": "moralbench-ui"`.
- `packages/frontend/index.html:6` — `<title>MoralBench Results</title>`.
- `packages/frontend/src/components/Sidebar.tsx:21` — the `<h1>MoralBench</h1>`.
- localStorage keys: `store.ts:25` (`moralbench-app-store`), `Q1Q4Annotator.tsx:322`
  (`moralbench-q1q4-selected-model`), `useCollapsibleState.ts:14` and `Analytics.tsx:201,209`
  (`moralbench-collapsible-${id}`).

**Renaming the localStorage keys silently resets persisted UI state** — selected model,
collapsed panels, store contents. That is acceptable here (local dev state only). If it isn't,
leave the key strings on the old prefix and note why; they are invisible to users. Decide
explicitly rather than by accident.

Frontend hot-reloads, so no restart is needed; `npm run build` in step 8 is the real check.

## 8. Verification

Run in this order; each catches a different class of miss:

1. `grep -ri "moralbench\|moral_bench" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=results .`
   → should return only `specs/` history and `CHANGELOG.md` (see §9). Note that `results/*.csv`
   contains the words "moral"/"morality" inside *model response prose* — that is data, never
   rename it, hence the `--exclude-dir=results`.
2. `uv sync` — proves the workspace and lockfile agree.
3. `uv run --env-file .env.local python -m pytest packages/backend/tests` — all nine test
   modules import the renamed packages.
4. `uv run --env-file .env.local python main.py --help`, then `main.py db --help` — proves the
   Typer app and the seven DB-path defaults load.
5. `./packages/backend/run.sh` and hit `http://localhost:8000/docs` — proves the uvicorn target
   and both env vars resolve.
6. `cd packages/frontend && npm run build` — proves TypeScript still compiles after the string
   edits, then load `http://localhost:5173`.
7. One real end-to-end call against the new DB name, e.g.
   `uv run --env-file .env.local python main.py db grade --limit 1`.

## 9. Documentation

- **`README.md`** — full rewrite, see §10.
- **`CLAUDE.md`** (and therefore `AGENTS.md`) — update the `MORALBENCH_RESULTS_DIR` reference
  and the `moralbench_api/routes/_shared.py` path.
- **`packages/backend/src/moral_bench/README.md`** — currently one line, "Source code for the
  MoralBench repository". Replace with a real orientation: what lives in `aesthetic_bench` (core
  library: client, grading, question specs, TUI) versus `aestheticbench_api` (REST layer).
- **`CHANGELOG.md`** — add a `## 2026-08-10 — Renamed to AestheticBench` entry recording the old
  → new identifier table, so anyone bisecting past this commit knows why imports change.
- **`specs/*.md`** — historical records; **do not rewrite them.** Nine specs reference the old
  names as they were at the time. Add one line to the top of this file's directory-mates only
  if confusion arises; otherwise leave history alone.
- **`Makefile`** — `tui` target points at
  `packages/backend/src/moral_bench/annotate_tui.py`; update the path.
- **`setup.sh`** — two user-facing banner strings: line 8 (`MoralBench OpenRouter Setup`) and
  line 123 (`To run MoralBench in the future, use:`).

## 10. README rewrite

The current README opens with one accurate sentence ("measure whether LLMs take an aesthetic
preference") and then reads as a moral-benchmark quickstart. Three things are actually wrong,
not just mis-branded, and get fixed in the rewrite:

- It claims results live in `packages/backend/data/results/...`. They do not — `run.sh:5` sets
  the results dir to `<repo>/results`. Delete the stale claim.
- It documents inference against `prompts/v1.csv`; the live prompt set is `prompts/v2.tsv`, and
  `specs/2026-03-15-v1-removal-codebase-simplification.md` removed v1.
- It contains three stray `droid --resume <uuid>` lines pasted mid-document. Remove.

Proposed structure:

1. **What this measures** (new, replaces "Introduction"). AestheticBench asks whether a model
   will commit to an aesthetic judgement or retreat into relativism. Each item is a forced
   comparison — "Who is a greater musical artist, [Beethoven] or [Lizzo]?" — across topics like
   Beauty and Language. A model that answers, argues, and stays consistent scores well; one that
   declares the question unanswerable or purely subjective scores poorly. State plainly that the
   benchmark takes no position on which side is *correct*; it scores willingness to judge and the
   quality of the justification.
2. **What we've found so far** (new, short). Point at
   `specs/2026-08-10-q1-split-and-grader-reliability.md` for grader-reliability numbers and the
   q1 → q1_1/q1_2 split, and name the known limitation already recorded in the roadmap: q1_2
   saturates near 90%, so 38 of 48 questions currently produce no between-model variance.
3. **Quickstart** — `./setup.sh`, then the two servers. Keep, corrected for new env var names.
4. **The rubric (Q1–Q4)** — keep the existing Q1.1–Q4.4 table nearly verbatim; it is the best
   part of the current README. Keep the struck-through Q1 note (it explains why old grades are
   not comparable) and the pointer to `question_specs.py` as the single source of truth. Move
   the legacy grader list (`preference1`, `preference2`, `relativism`, …) into a collapsed
   "Legacy graders" section with the polarity warning — `relativism` is the *inverse* of q1 —
   kept prominent.
5. **Running the benchmark** — dry run, inference, grading, all with `--env-file .env.local` and
   `prompts/v2.tsv`. Merge in the DB-backed commands (`main.py db grade`, `--limit`,
   `--grader-model`) that the current README omits despite them being the primary workflow now.
6. **Data layout** — one accurate paragraph: `prompts/`, `results/v2/{responses,grades}/`,
   `aestheticbench.db` (gitignored, local), `configurations/`.
7. **Project structure** — keep the tree, updated names.
8. **Roadmap** — keep as-is (it is current and honest), retitled and with the rename ticked off.

## 11. Commit sequencing

Small, individually-green commits — this is a wide diff and a bisect target:

1. `git mv` the two source directories + fix all imports. (Tests green.)
2. Distribution names, hatch config, `uv lock`. (`uv sync` green.)
3. Env var rename. (Backend boots.)
4. DB filename. (CLI green.)
5. Frontend strings. (`npm run build` green.)
6. Docs: README rewrite, CLAUDE.md, package README, CHANGELOG.
7. *Outside git:* GitHub repo rename, `git remote set-url`, local directory rename.

## 12. Out of scope

- Schema, column names, and grader IDs (`q1_1`, `Relativism_Score`, …) stay exactly as they are.
  They describe the measurement, not the product, and renaming them would invalidate every
  stored grade.
- Historical result CSVs under `results/` — filenames and contents untouched.
- The `moral`/`morality` strings inside model responses in `results/` — those are data.
