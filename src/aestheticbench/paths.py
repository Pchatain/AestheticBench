"""Every filesystem anchor in the repo, resolved once.

Nothing else may compute a path from ``__file__``. Before this module existed,
four modules each counted ``Path(__file__).parents[N]`` up to the repo root
with a different N, and every directory move silently broke a different one.

Two anchors honour an environment variable so tests and deployments can
relocate them: ``AESTHETICBENCH_RESULTS_DIR`` and ``AESTHETICBENCH_DB``.
"""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent  # src/aestheticbench
PROJECT_ROOT = PACKAGE_DIR.parents[1]

# Inputs
PROMPTS_DIR = PROJECT_ROOT / "prompts"
QUESTIONS_FILE = PROMPTS_DIR / "v2.tsv"  # the benchmark items
GRADER_PROMPTS_DIR = PROMPTS_DIR / "graders"  # one file per grader
CONFIGURATIONS_DIR = PROJECT_ROOT / "configurations"

# Outputs and state
RESULTS_DIR = Path(os.environ.get("AESTHETICBENCH_RESULTS_DIR", PROJECT_ROOT / "results"))
DB_PATH = Path(os.environ.get("AESTHETICBENCH_DB", PROJECT_ROOT / "aestheticbench.db"))
LOGS_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / ".cache"  # regenerable: OpenRouter model list, legacy annotations.json

# The annotation TUI and its remote-control route talk through two files.
ANNOTATOR_STATE_FILE = PROJECT_ROOT / ".annotator_state.json"
ANNOTATOR_COMMAND_FILE = PROJECT_ROOT / ".annotator_commands.json"
