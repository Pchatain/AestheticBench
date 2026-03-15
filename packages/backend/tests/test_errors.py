"""Unit tests for error handling module."""

import logging
import tempfile
from pathlib import Path

import pytest

from moral_bench.errors import log_parse_error, parse_logger, setup_error_logging


class TestSetupErrorLogging:
    def test_creates_log_directory(self):
        """setup_error_logging should create the log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "new_logs"
            assert not log_dir.exists()
            
            setup_error_logging(log_dir)
            
            assert log_dir.exists()

    def test_adds_file_handler(self):
        """setup_error_logging should add a FileHandler to the logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            initial_handlers = len(parse_logger.handlers)
            
            setup_error_logging(log_dir)
            
            assert len(parse_logger.handlers) > initial_handlers
            # Clean up handler
            parse_logger.handlers = parse_logger.handlers[:initial_handlers]

    def test_sets_warning_level(self):
        """setup_error_logging should set logger level to WARNING."""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_error_logging(Path(tmpdir))
            
            assert parse_logger.level == logging.WARNING


class TestLogParseError:
    def test_logs_parse_error(self):
        """log_parse_error should log a warning message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            setup_error_logging(log_dir)
            
            log_parse_error(
                grader_name="test_grader",
                raw_response="invalid response",
                question="test question"
            )
            
            # Find the log file
            log_files = list(log_dir.glob("parse_errors_*.log"))
            assert len(log_files) >= 1
            
            content = log_files[0].read_text()
            assert "[test_grader]" in content
            assert "invalid response" in content
            assert "test question" in content

    def test_truncates_long_response(self):
        """log_parse_error should truncate responses longer than 200 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            setup_error_logging(log_dir)
            
            long_response = "x" * 300
            log_parse_error(
                grader_name="test_grader",
                raw_response=long_response,
                question="test question"
            )
            
            log_files = list(log_dir.glob("parse_errors_*.log"))
            content = log_files[0].read_text()
            # Should contain truncated version (200 chars) not full 300
            assert "x" * 200 in content
            assert "x" * 300 not in content

    def test_truncates_long_question(self):
        """log_parse_error should truncate questions longer than 100 chars."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            setup_error_logging(log_dir)
            
            long_question = "q" * 150
            log_parse_error(
                grader_name="test_grader",
                raw_response="response",
                question=long_question
            )
            
            log_files = list(log_dir.glob("parse_errors_*.log"))
            content = log_files[0].read_text()
            assert "q" * 100 in content
            assert "q" * 150 not in content
