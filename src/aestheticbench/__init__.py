"""AestheticBench - does a language model commit to an aesthetic judgement, or retreat into relativism?

Layout (see README.md alongside this file):

    benchmark/   runs the benchmark: client, run, grading, rubric, prompts, agreement
    labelling/   the human-annotation TUI
    store/       SQLite persistence
    api/         FastAPI app served to web/
    cli/         the `aestheticbench` command
    paths.py     every filesystem anchor
"""

from .benchmark.client import OpenRouterClient
from .benchmark.config import Config
from .benchmark.grading import Grader, GraderRegistry, GradingProcessor
from .benchmark.prompts import DEFAULT_QUESTIONS
from .benchmark.run import CSVReader, PromptProcessor, ResultWriter
from .benchmark.text_utils import strip_entity_brackets
from .store.database import AestheticBenchDB, Grade, Question, Response

__version__ = "0.1.0"

__all__ = [
    "OpenRouterClient",
    "Config",
    "AestheticBenchDB",
    "Question",
    "Response",
    "Grade",
    "PromptProcessor",
    "CSVReader",
    "ResultWriter",
    "GradingProcessor",
    "Grader",
    "GraderRegistry",
    "DEFAULT_QUESTIONS",
    "strip_entity_brackets",
]
