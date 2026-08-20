"""Estimation service for dry-run cost calculations."""

import csv
from dataclasses import dataclass, field
from pathlib import Path

from aestheticbench import OpenRouterClient
from aestheticbench.benchmark.run import CSVReader
from aestheticbench.benchmark.text_utils import strip_entity_brackets


@dataclass
class ModelEstimate:
    """Cost estimate for a single model."""

    model: str
    available: bool
    input_cost_per_m: float | None = None
    output_cost_per_m: float | None = None
    estimated_min_cost: float | None = None
    estimated_max_cost: float | None = None
    error: str | None = None


@dataclass
class DryRunEstimate:
    """Complete dry-run estimate for inference."""

    prompts_count: int
    total_input_tokens: int
    min_output_tokens_per_prompt: int = 100
    max_output_tokens_per_prompt: int = 500
    models: list[ModelEstimate] = field(default_factory=list)
    valid_models: list[str] = field(default_factory=list)
    invalid_models: list[str] = field(default_factory=list)
    total_min_cost: float = 0.0
    total_max_cost: float = 0.0


@dataclass
class FileEstimate:
    """Estimate for a single file."""

    path: str
    filename: str
    response_count: int


@dataclass
class GradingEstimate:
    """Complete dry-run estimate for grading."""

    files: list[FileEstimate] = field(default_factory=list)
    total_responses: int = 0
    graders: list[str] = field(default_factory=list)
    custom_prompt_included: bool = False
    total_grading_calls: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    grader_model: str = "openai/gpt-4o"


class EstimationService:
    """Service for estimating costs before execution."""

    def __init__(self, client: OpenRouterClient):
        self.client = client

    @staticmethod
    def estimate_tokens(text_or_length: str | int) -> int:
        """Rough estimate of token count (approximately 4 chars per token)."""
        if isinstance(text_or_length, int):
            return text_or_length // 4
        return len(text_or_length) // 4

    def estimate_run(
        self,
        models: list[str],
        prompts_file: Path,
    ) -> DryRunEstimate:
        """Estimate costs for an inference run.

        Args:
            models: List of model names to estimate
            prompts_file: Path to prompts CSV/TSV file

        Returns:
            DryRunEstimate with cost breakdown
        """
        # Read prompts
        prompts = CSVReader.read_prompts(prompts_file)
        prompts_count = len(prompts)

        # Calculate token estimates
        total_chars = sum(len(strip_entity_brackets(prompt.get("Question", ""))) for prompt in prompts)
        total_input_tokens = self.estimate_tokens(total_chars)

        estimate = DryRunEstimate(
            prompts_count=prompts_count,
            total_input_tokens=total_input_tokens,
        )

        # Estimate for each model
        for model_name in models:
            model_estimate = self._estimate_model(
                model_name,
                total_input_tokens,
                prompts_count,
                estimate.min_output_tokens_per_prompt,
                estimate.max_output_tokens_per_prompt,
            )
            estimate.models.append(model_estimate)

            if model_estimate.available:
                estimate.valid_models.append(model_name)
                if model_estimate.estimated_min_cost:
                    estimate.total_min_cost += model_estimate.estimated_min_cost
                if model_estimate.estimated_max_cost:
                    estimate.total_max_cost += model_estimate.estimated_max_cost
            else:
                estimate.invalid_models.append(model_name)

        return estimate

    def _estimate_model(
        self,
        model_name: str,
        total_input_tokens: int,
        prompts_count: int,
        min_output_tokens: int,
        max_output_tokens: int,
    ) -> ModelEstimate:
        """Estimate costs for a single model."""
        # Verify model exists
        if not self.client.verify_model(model_name, verbose=False):
            return ModelEstimate(
                model=model_name,
                available=False,
                error="Model not found on OpenRouter",
            )

        # Get pricing info
        model_info = self.client.get_model_info(model_name)
        if not model_info or "pricing" not in model_info:
            return ModelEstimate(
                model=model_name,
                available=True,
                error="Pricing information not available",
            )

        pricing = model_info["pricing"]
        prompt_cost_per_token = float(pricing.get("prompt", "0"))
        completion_cost_per_token = float(pricing.get("completion", "0"))

        # Convert to per-million for display
        input_cost_per_m = prompt_cost_per_token * 1_000_000
        output_cost_per_m = completion_cost_per_token * 1_000_000

        # Calculate costs
        input_cost = total_input_tokens * prompt_cost_per_token
        min_output_cost = (min_output_tokens * prompts_count) * completion_cost_per_token
        max_output_cost = (max_output_tokens * prompts_count) * completion_cost_per_token

        return ModelEstimate(
            model=model_name,
            available=True,
            input_cost_per_m=input_cost_per_m,
            output_cost_per_m=output_cost_per_m,
            estimated_min_cost=input_cost + min_output_cost,
            estimated_max_cost=input_cost + max_output_cost,
        )

    def estimate_grading(
        self,
        files: list[Path],
        grader_ids: list[str],
        grader_model: str = "openai/gpt-4o",
        custom_prompt: str | None = None,
    ) -> GradingEstimate:
        """Estimate costs for a grading run.

        Args:
            files: List of result CSV files
            grader_ids: List of grader identifiers
            grader_model: Model to use for grading
            custom_prompt: Optional custom grader prompt

        Returns:
            GradingEstimate with cost breakdown
        """
        estimate = GradingEstimate(
            graders=grader_ids,
            grader_model=grader_model,
            custom_prompt_included=custom_prompt is not None,
        )

        # Count responses in each file
        for file_path in files:
            path = Path(file_path) if isinstance(file_path, str) else file_path
            response_count = self._count_csv_rows(path)
            estimate.files.append(
                FileEstimate(
                    path=str(path),
                    filename=path.name,
                    response_count=response_count,
                )
            )
            estimate.total_responses += response_count

        # Calculate grading calls
        num_graders = len(grader_ids) + (1 if custom_prompt else 0)
        estimate.total_grading_calls = estimate.total_responses * num_graders

        # Token estimates (rough)
        avg_input_tokens_per_call = 500  # prompt + question + response
        avg_output_tokens_per_call = 100  # reasoning + score

        estimate.estimated_input_tokens = (
            estimate.total_grading_calls * avg_input_tokens_per_call
        )
        estimate.estimated_output_tokens = (
            estimate.total_grading_calls * avg_output_tokens_per_call
        )

        return estimate

    def _count_csv_rows(self, file_path: Path) -> int:
        """Count data rows in a CSV file (excluding header)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                return sum(1 for _ in reader)
        except Exception:
            return 0
