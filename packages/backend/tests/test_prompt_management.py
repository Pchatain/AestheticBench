"""Tests for prompt management: bracket stripping, entity swapping, and clean delivery to LLM."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aesthetic_bench.client import OpenRouterClient
from aesthetic_bench.grading import (
    GradingProcessor,
    Preference1Grader,
    JustificationGrader,
    Q1RelativismGrader,
)
from aesthetic_bench.processor import CSVReader, PromptProcessor
from aesthetic_bench.text_utils import strip_entity_brackets, swap_entities


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """An OpenRouterClient mock that logs every prompt it receives."""
    client = MagicMock(spec=OpenRouterClient)
    client.captured_prompts = []

    def capture_chat(message, model="openai/gpt-4o", timeout=None):
        client.captured_prompts.append(message)
        return '{"reasoning": "mock", "score": 1}'

    def capture_batch(messages, model="openai/gpt-4o", **kwargs):
        client.captured_prompts.extend(messages)
        return [(i, msg, '{"reasoning": "mock", "score": 1}') for i, msg in enumerate(messages)]

    client.chat_completion.side_effect = capture_chat
    client.batch_chat_completions.side_effect = capture_batch
    return client


@pytest.fixture
def bracketed_tsv(tmp_path):
    """Create a small TSV with [entity] brackets."""
    tsv = tmp_path / "test_prompts.tsv"
    tsv.write_text(
        "Topic\tQuestion\n"
        "Beauty\tWho is a greater musical artist, [Beethoven] or [Lizzo]?\n"
        "Language\tWhat language has more depth, [English] or [Spanish]?\n"
    )
    return tsv


@pytest.fixture
def clean_results_csv(tmp_path):
    """Create a results CSV with clean (no brackets) questions, as produced by the pipeline."""
    csv_path = tmp_path / "results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Topic", "Question", "Model Response", "Timestamp"])
        writer.writeheader()
        writer.writerow({
            "Topic": "Beauty",
            "Question": "Who is a greater musical artist, Beethoven or Lizzo?",
            "Model Response": "I think Beethoven is greater because of his lasting impact.",
            "Timestamp": "2026-01-01T00:00:00",
        })
        writer.writerow({
            "Topic": "Language",
            "Question": "What language has more depth, English or Spanish?",
            "Model Response": "English has a larger vocabulary overall.",
            "Timestamp": "2026-01-01T00:00:00",
        })
    return csv_path


# ---------------------------------------------------------------------------
# Unit tests: text_utils
# ---------------------------------------------------------------------------

class TestStripEntityBrackets:
    def test_removes_brackets(self):
        assert strip_entity_brackets("[Beethoven]") == "Beethoven"

    def test_multiple_entities(self):
        text = "Who is greater, [Beethoven] or [Lizzo]?"
        assert strip_entity_brackets(text) == "Who is greater, Beethoven or Lizzo?"

    def test_no_brackets_unchanged(self):
        text = "Who is greater, Beethoven or Lizzo?"
        assert strip_entity_brackets(text) == text

    def test_empty_brackets(self):
        assert strip_entity_brackets("[]") == ""

    def test_nested_not_supported(self):
        # Regex only matches innermost content up to first ]
        result = strip_entity_brackets("[[nested]]")
        assert "[" not in result or result == "[nested]"


class TestSwapEntities:
    def test_basic_swap(self):
        text = "Who is greater, [Beethoven] or [Lizzo]?"
        assert swap_entities(text) == "Who is greater, [Lizzo] or [Beethoven]?"

    def test_preserves_surrounding_text(self):
        text = "Compare [A] and [B] in detail."
        swapped = swap_entities(text)
        assert swapped == "Compare [B] and [A] in detail."

    def test_no_entities_unchanged(self):
        text = "No entities here."
        assert swap_entities(text) == text


# ---------------------------------------------------------------------------
# Integration: PromptProcessor strips brackets before sending to LLM
# ---------------------------------------------------------------------------

class TestPromptProcessorBracketStripping:
    def test_model_receives_clean_prompts(self, mock_client, bracketed_tsv, tmp_path):
        """The mock LLM should receive prompts with NO brackets."""
        processor = PromptProcessor(mock_client)
        processor.process_prompts(bracketed_tsv, tmp_path / "output")

        assert len(mock_client.captured_prompts) == 2
        for prompt in mock_client.captured_prompts:
            assert "[" not in prompt, f"Brackets leaked to LLM: {prompt!r}"
            assert "]" not in prompt, f"Brackets leaked to LLM: {prompt!r}"

    def test_model_receives_correct_text(self, mock_client, bracketed_tsv, tmp_path):
        """Verify the exact cleaned text reaches the model."""
        processor = PromptProcessor(mock_client)
        processor.process_prompts(bracketed_tsv, tmp_path / "output")

        assert mock_client.captured_prompts[0] == "Who is a greater musical artist, Beethoven or Lizzo?"
        assert mock_client.captured_prompts[1] == "What language has more depth, English or Spanish?"


# ---------------------------------------------------------------------------
# Integration: Graders reject bracketed questions
# ---------------------------------------------------------------------------

class TestGraderBracketValidation:
    def test_base_grader_rejects_brackets(self):
        grader = Preference1Grader()
        with pytest.raises(ValueError, match="entity.*brackets"):
            grader.construct_prompt(
                "[Beethoven] or [Lizzo]?",
                "Some response",
            )

    def test_justification_grader_rejects_brackets(self):
        grader = JustificationGrader()
        with pytest.raises(ValueError, match="entity.*brackets"):
            grader.construct_prompt(
                "[Beethoven] or [Lizzo]?",
                "Some response",
                context={"Preference_1_Score": "1"},
            )

    def test_grader_accepts_clean_question(self):
        grader = Preference1Grader()
        prompt = grader.construct_prompt("Beethoven or Lizzo?", "Some response")
        assert "Beethoven or Lizzo?" in prompt


# ---------------------------------------------------------------------------
# Integration: GradingProcessor sends clean prompts to mock LLM
# ---------------------------------------------------------------------------

class TestGradingProcessorPrompts:
    def test_grading_sends_clean_prompts(self, mock_client, clean_results_csv, tmp_path):
        """Grader prompts sent to LLM should contain the clean question, no brackets."""
        processor = GradingProcessor(mock_client)
        processor.grade_responses(
            clean_results_csv,
            tmp_path / "graded",
            grader_ids=["q1"],
            grader_model="openai/gpt-4o-mini",
        )

        assert len(mock_client.captured_prompts) == 2
        for prompt in mock_client.captured_prompts:
            assert "[" not in prompt or '{"' in prompt, (
                f"Unexpected brackets in grading prompt: {prompt!r}"
            )
            # The original question text should appear in the prompt
            assert "Beethoven" in prompt or "English" in prompt

    def test_grading_prompt_includes_question_and_response(self, mock_client, clean_results_csv, tmp_path):
        """Verify the grading prompt contains both the question and model response."""
        processor = GradingProcessor(mock_client)
        processor.grade_responses(
            clean_results_csv,
            tmp_path / "graded",
            grader_ids=["q1"],
            grader_model="openai/gpt-4o-mini",
        )

        first_prompt = mock_client.captured_prompts[0]
        assert "Beethoven" in first_prompt
        assert "lasting impact" in first_prompt


# ---------------------------------------------------------------------------
# Round-trip: bracketed TSV -> process -> grade -> no brackets anywhere
# ---------------------------------------------------------------------------

class TestEndToEndBracketStripping:
    def test_full_pipeline_no_bracket_leakage(self, mock_client, bracketed_tsv, tmp_path):
        """Run process_prompts then grade the output — brackets must never reach the LLM."""
        # Step 1: Process prompts (model inference)
        processor = PromptProcessor(mock_client)
        output_csv = processor.process_prompts(
            bracketed_tsv, tmp_path / "output", model="test-model"
        )

        # Verify output CSV has clean questions
        with open(output_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert "[" not in row["Question"], f"Brackets in output CSV: {row['Question']!r}"

        # Step 2: Grade the output
        mock_client.captured_prompts.clear()
        grading = GradingProcessor(mock_client)
        grading.grade_responses(
            output_csv,
            tmp_path / "graded",
            grader_ids=["q1"],
            grader_model="test-model",
        )

        # Verify grading prompts are also clean
        for prompt in mock_client.captured_prompts:
            # Allow [ only inside JSON format instructions like {"reasoning": ...}
            # Strip out the JSON format instruction before checking
            non_json_parts = prompt.split('{"reasoning"')[0]
            assert "[" not in non_json_parts, f"Brackets leaked to grader: {non_json_parts!r}"
