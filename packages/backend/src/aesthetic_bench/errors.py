"""Centralized error handling and logging for AestheticBench."""

import logging
from datetime import datetime
from pathlib import Path

# Configure logger for parse errors
parse_logger = logging.getLogger("aestheticbench.parse_errors")


def setup_error_logging(log_dir: Path = Path("logs")) -> None:
    """Set up file logging for parse errors.

    Args:
        log_dir: Directory to store log files
    """
    log_dir.mkdir(exist_ok=True)
    handler = logging.FileHandler(
        log_dir / f"parse_errors_{datetime.now():%Y%m%d}.log"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    parse_logger.addHandler(handler)
    parse_logger.setLevel(logging.WARNING)


def log_parse_error(grader_name: str, raw_response: str, question: str) -> None:
    """Log parsing failures for later analysis.

    Args:
        grader_name: Name of the grader that failed to parse
        raw_response: Raw response from the grader model
        question: The original question being graded
    """
    truncated_response = raw_response[:200] if len(raw_response) > 200 else raw_response
    truncated_question = question[:100] if len(question) > 100 else question
    parse_logger.warning(
        f"[{grader_name}] Failed to parse: {truncated_response}... | Question: {truncated_question}"
    )
