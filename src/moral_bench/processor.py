"""Prompt processing and CSV handling for MoralBench."""

import csv
from datetime import datetime
from pathlib import Path
from tqdm import tqdm

from .client import OpenRouterClient


class CSVReader:
    """Read prompts from CSV files."""

    @staticmethod
    def read_prompts(file_path: Path) -> list[dict[str, str]]:
        """Read prompts from a CSV file.

        Args:
            file_path: Path to the CSV file.

        Returns:
            List of dictionaries containing prompt data.

        Raises:
            FileNotFoundError: If the CSV file doesn't exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)


class ResultWriter:
    """Write results to timestamped CSV files."""

    @staticmethod
    def write_results(
        results: list[dict[str, str]],
        output_dir: Path,
        model_name: str,
    ) -> Path:
        """Write results to a timestamped CSV file.

        Args:
            results: List of result dictionaries.
            output_dir: Directory to write the output file.
            model_name: Name of the model used (for filename).

        Returns:
            Path to the created CSV file.
        """
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        sanitized_model_name = model_name.replace("/", "_")
        output_file = output_dir / f"{sanitized_model_name}_{timestamp}.csv"

        # Write results to CSV
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["Topic", "Question", "Model Response", "Timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        return output_file


class PromptProcessor:
    """Process prompts and generate responses using OpenRouter API."""

    def __init__(self, client: OpenRouterClient):
        """Initialize the prompt processor.

        Args:
            client: OpenRouter client for API calls.
        """
        self.client = client

    def process_prompts(
        self,
        prompts_file: Path,
        output_dir: Path,
        model: str = "openai/gpt-4o",
    ) -> Path:
        """Process prompts from CSV and generate responses in parallel.

        Args:
            prompts_file: Path to the input CSV file.
            output_dir: Directory for output CSV files.
            model: Model to use for completions.

        Returns:
            Path to the output CSV file.
        """
        # Read prompts
        print(f"\nReading prompts from {prompts_file}...")
        prompts = CSVReader.read_prompts(prompts_file)
        print(f"Found {len(prompts)} prompts to process")

        # Prepare messages for batch processing
        messages = [prompt.get("Question", "") for prompt in prompts]

        print(
            f"Output will be saved to: {output_dir / model.replace('/', '_')}_<timestamp>.csv"
        )
        print("\nProcessing prompts in parallel...\n")

        # Process in parallel
        batch_results = self.client.batch_chat_completions(messages, model)

        # Format results
        results = []
        for i, (idx, message, response) in enumerate(batch_results, 1):
            prompt = prompts[idx]
            topic = prompt.get("Topic", "")

            if response:
                tqdm.write(f"[{i}/{len(prompts)}] ✓ {topic} ({len(response)} chars)")
                model_response = response
            else:
                tqdm.write(f"[{i}/{len(prompts)}] ✗ {topic} (error)")
                model_response = "ERROR: Request failed"

            results.append(
                {
                    "Topic": topic,
                    "Question": message,
                    "Model Response": model_response,
                    "Timestamp": datetime.now().isoformat(),
                }
            )

        # Write results
        print("\nWriting results...")
        output_file = ResultWriter.write_results(results, output_dir, model)
        print(f"✓ Complete! Results saved to {output_file}")

        return output_file
