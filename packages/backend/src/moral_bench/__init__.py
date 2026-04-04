"""MoralBench - Package to measure the morality of LLMs."""

from .client import OpenRouterClient
from .config import Config
from .database import MoralBenchDB, Question, Response, Grade
from .grading import GradingProcessor, Grader, GraderRegistry
from .grader_prompts import DEFAULT_QUESTIONS
from .processor import CSVReader, PromptProcessor, ResultWriter

__version__ = "0.1.0"

__all__ = [
    "OpenRouterClient",
    "Config",
    "MoralBenchDB",
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
]
