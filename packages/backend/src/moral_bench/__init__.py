"""MoralBench - Package to measure the morality of LLMs."""

from .client import OpenRouterClient
from .config import Config
from .grading import GradingProcessor, Grader, GraderRegistry
from .processor import CSVReader, PromptProcessor, ResultWriter

__version__ = "0.1.0"

__all__ = [
    "OpenRouterClient",
    "Config",
    "PromptProcessor",
    "CSVReader",
    "ResultWriter",
    "GradingProcessor",
    "Grader",
    "GraderRegistry",
]
