"""Integration tests that hit the real OpenRouter API.

These tests require OPENROUTER_API_KEY to be set.
Total cost should be under 10 cents (using cheap model and minimal queries).
"""

import os
import tempfile
from pathlib import Path

import pytest

from aestheticbench.benchmark.client import OpenRouterClient
from aestheticbench.benchmark.config import Config
from aestheticbench.benchmark.errors import setup_error_logging, log_parse_error
from aestheticbench.benchmark.grading import GradingProcessor, Preference1Grader


# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set"
)


@pytest.fixture
def config():
    """Create config from environment."""
    return Config.from_env()


@pytest.fixture
def client(config):
    """Create a real API client."""
    client = OpenRouterClient(config)
    yield client
    client.close()


# Use a cheap model for integration tests
CHEAP_MODEL = "openai/gpt-4o-mini"


class TestRealAPIConnection:
    def test_health_check(self, client):
        """Verify we can connect to OpenRouter API."""
        assert client.health_check() is True

    def test_single_completion(self, client):
        """Test a single chat completion (~0.001 cents)."""
        response = client.chat_completion(
            "Say 'hello' and nothing else.",
            model=CHEAP_MODEL,
        )
        assert response is not None
        assert len(response) > 0
        assert "hello" in response.lower()

    def test_batch_completion_single_message(self, client):
        """Test batch completion with single message (~0.001 cents)."""
        results = client.batch_chat_completions(
            ["Reply with just the number 42."],
            model=CHEAP_MODEL,
            max_workers=0,  # Sequential
        )
        
        assert len(results) == 1
        idx, msg, response = results[0]
        assert idx == 0
        assert response is not None
        assert "42" in response


class TestRealGrading:
    def test_grade_single_response(self, client):
        """Test grading a single response (~0.002 cents)."""
        grader = Preference1Grader()
        
        # Construct a prompt that should result in a clear preference score
        prompt = grader.construct_prompt(
            question="Which is better: chocolate or vanilla ice cream?",
            response="I strongly prefer chocolate ice cream because of its rich flavor.",
        )
        
        # Get grading response from API
        grader_response = client.chat_completion(prompt, model=CHEAP_MODEL)
        
        # Parse the response
        success, score, reasoning, error = grader.grade(
            question="Which is better: chocolate or vanilla ice cream?",
            response="I strongly prefer chocolate ice cream because of its rich flavor.",
            grader_model_response=grader_response,
        )
        
        assert success is True, f"Grading failed: {error}"
        assert score in {-1, 0, 1}
        print(f"Grading result: score={score}, reasoning={reasoning[:100]}...")


class TestErrorLoggingIntegration:
    def test_parse_error_logged_to_file(self):
        """Test that parse errors are actually written to log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            setup_error_logging(log_dir)
            
            log_parse_error(
                grader_name="integration_test",
                raw_response="This is a test error response",
                question="Test question for integration"
            )
            
            log_files = list(log_dir.glob("parse_errors_*.log"))
            assert len(log_files) >= 1
            
            content = log_files[0].read_text()
            assert "[integration_test]" in content
            assert "test error response" in content
