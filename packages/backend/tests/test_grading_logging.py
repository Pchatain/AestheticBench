"""Unit tests for grading with parse error logging."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aesthetic_bench.grading import (
    GraderRegistry,
    GradingProcessor,
    Preference1Grader,
)


class TestGraderParseError:
    def test_preference1_parse_failure(self):
        """Preference1Grader should return parse error on invalid response."""
        grader = Preference1Grader()
        
        success, score, reasoning, error = grader.grade(
            question="test question",
            response="test response",
            grader_model_response="This is not a valid score format at all",
        )
        
        assert success is False
        assert score is None
        assert "PARSE_ERROR" in error

    def test_preference1_validation_failure(self):
        """Preference1Grader should return validation error for out-of-range score."""
        grader = Preference1Grader()
        
        success, score, reasoning, error = grader.grade(
            question="test question",
            response="test response",
            grader_model_response='{"reasoning": "test", "score": 5}',
        )
        
        assert success is False
        assert "VALIDATION_ERROR" in error or "PARSE_ERROR" in error

    def test_preference1_parse_success(self):
        """Preference1Grader should parse valid JSON response."""
        grader = Preference1Grader()
        
        success, score, reasoning, error = grader.grade(
            question="test question",
            response="test response",
            grader_model_response='{"reasoning": "Good preference", "score": 1}',
        )
        
        assert success is True
        assert score == 1
        assert reasoning == "Good preference"
        assert error == ""


class TestGradingProcessorLogging:
    def test_logs_parse_error_on_failure(self):
        """GradingProcessor should call log_parse_error when grading fails after retries."""
        mock_client = MagicMock()
        mock_client.batch_chat_completions.return_value = [
            (0, "prompt", "invalid grader response without score"),
        ]
        # Mock chat_completion for retries - also return invalid responses
        mock_client.chat_completion.return_value = "still invalid response"
        
        processor = GradingProcessor(mock_client)
        
        responses = [
            {
                "Question": "test question",
                "Model Response": "test model response",
            }
        ]
        
        grader = Preference1Grader()
        
        with patch("aesthetic_bench.grading.log_parse_error") as mock_log:
            processor._run_grader(responses, grader, "test-model")
            
            # Should be called multiple times: once per retry + final failure
            assert mock_log.call_count >= 1
            # Check the final call logs the failure
            final_call = mock_log.call_args_list[-1]
            assert final_call[0][0] == "preference1"
            assert final_call[0][2] == "test question"

    def test_no_log_on_success(self):
        """GradingProcessor should not call log_parse_error on successful grading."""
        mock_client = MagicMock()
        mock_client.batch_chat_completions.return_value = [
            (0, "prompt", '{"reasoning": "Good", "score": 1}'),
        ]
        
        processor = GradingProcessor(mock_client)
        
        responses = [
            {
                "Question": "test question",
                "Model Response": "test model response",
            }
        ]
        
        grader = Preference1Grader()
        
        with patch("aesthetic_bench.grading.log_parse_error") as mock_log:
            processor._run_grader(responses, grader, "test-model")
            
            mock_log.assert_not_called()

    def test_retries_on_parse_error_then_succeeds(self):
        """GradingProcessor should retry on parse error and succeed if retry works."""
        mock_client = MagicMock()
        mock_client.batch_chat_completions.return_value = [
            (0, "prompt", "invalid response"),
        ]
        # First retry fails, second succeeds
        mock_client.chat_completion.side_effect = [
            "still invalid",
            '{"reasoning": "Good answer", "score": 1}',
        ]
        
        processor = GradingProcessor(mock_client)
        
        responses = [
            {
                "Question": "test question",
                "Model Response": "test model response",
            }
        ]
        
        grader = Preference1Grader()
        processor._run_grader(responses, grader, "test-model")
        
        # Should have succeeded after retry
        assert responses[0]["Preference_1_Score"] == "1"
        assert responses[0]["Preference_1_Reasoning"] == "Good answer"
        # chat_completion should have been called twice (2 retries before success)
        assert mock_client.chat_completion.call_count == 2

    def test_no_log_on_api_failure(self):
        """GradingProcessor should not call log_parse_error when API returns None."""
        mock_client = MagicMock()
        mock_client.batch_chat_completions.return_value = [
            (0, "prompt", None),  # API failure
        ]
        
        processor = GradingProcessor(mock_client)
        
        responses = [
            {
                "Question": "test question",
                "Model Response": "test model response",
            }
        ]
        
        grader = Preference1Grader()
        
        with patch("aesthetic_bench.grading.log_parse_error") as mock_log:
            processor._run_grader(responses, grader, "test-model")
            
            # Should not log parse error for API failures (those are different)
            mock_log.assert_not_called()
            assert "ERROR: Grading failed" in responses[0][grader.column_name]
