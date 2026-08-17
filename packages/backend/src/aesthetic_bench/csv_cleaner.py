#!/usr/bin/env python3
"""
CSV Cleaner for AestheticBench results.

Combines multiple model result CSV files into a single table with model names as columns.
"""

import csv
from pathlib import Path
from typing import Dict, List
import argparse


def extract_model_name(filename: str) -> str:
    """
    Extract model name from filename.

    Example: 'openai_gpt-4o_2025-11-14_16-32-02.csv' -> 'openai_gpt-4o'
    """
    # Remove .csv extension
    name = filename.replace(".csv", "")
    # Split by underscore and take all parts except the date/time parts
    parts = name.split("_")
    # The last two parts are date and time, remove them
    if len(parts) >= 3:
        model_name = "_".join(parts[:-2])
    else:
        model_name = name
    return model_name


def parse_csv_file(filepath: Path) -> List[Dict[str, str]]:
    """
    Parse a single CSV file and return list of responses.

    Returns:
        List of dicts with 'topic', 'question', and 'response' keys
    """
    responses = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            responses.append(
                {
                    "topic": row["Topic"],
                    "question": row["Question"],
                    "response": row["Model Response"],
                }
            )
    return responses


def normalize_model_name(model_name: str) -> str:
    """
    Normalize model name for matching with ordering list.

    Converts underscores to spaces and handles common variations.
    """
    # Replace underscores with spaces
    normalized = model_name.replace("_", " ")
    # Handle common variations
    normalized = (
        normalized.replace("anthropic ", "")
        .replace("openai ", "")
        .replace("google ", "")
    )
    normalized = (
        normalized.replace("meta-llama ", "")
        .replace("mistralai ", "")
        .replace("x-ai ", "")
    )
    normalized = (
        normalized.replace("deepseek ", "").replace("qwen ", "").replace("z-ai ", "")
    )
    return normalized.strip()


def match_model_to_ordering(model_name: str, ordering_list: List[str]) -> tuple:
    """
    Find the position of a model in the ordering list.

    Returns:
        Tuple of (position, matched_name) or (len(ordering_list), model_name) if not found
    """
    normalized = normalize_model_name(model_name)

    for idx, ordered_name in enumerate(ordering_list):
        # Check if normalized model name contains the ordered name or vice versa
        if (
            ordered_name.lower() in normalized.lower()
            or normalized.lower() in ordered_name.lower()
        ):
            return (idx, model_name)

    # Not found in ordering, put at end
    return (len(ordering_list), model_name)


def combine_results(results_dir: Path, model_ordering: List[str] = None) -> None:
    """
    Combine all CSV files in the results directory into a single combined CSV.

    Args:
        results_dir: Path to directory containing model result CSV files
        model_ordering: Optional list of model names in desired column order
    """
    if model_ordering is None:
        model_ordering = [
            "gpt-4o",
            "sonnet 3.5",
            "gpt-5",
            "sonnet 4.5",
            "grok-4-fast",
            "deepseek chat 3",
            "gemini 2.5-pro",
            "gpt-oss-20b",
            "z.ai glm-4.6",
            "qwen3-235b",
            "mistral nemo",
            "llama 3.1 405b",
        ]

    # Get all CSV files (excluding any previously generated combined files)
    csv_files = [
        f
        for f in sorted(results_dir.glob("*.csv"))
        if not f.name.startswith("combined_")
    ]

    if not csv_files:
        print(f"No CSV files found in {results_dir}")
        return

    # Parse all files and organize by model
    model_responses: Dict[str, List[Dict[str, str]]] = {}

    for csv_file in csv_files:
        model_name = extract_model_name(csv_file.name)
        print(f"Processing {csv_file.name} -> {model_name}")
        model_responses[model_name] = parse_csv_file(csv_file)

    # Sort models according to ordering
    model_names = list(model_responses.keys())
    model_positions = [
        (match_model_to_ordering(m, model_ordering)[0], m) for m in model_names
    ]
    model_positions.sort()
    sorted_model_names = [m for _, m in model_positions]

    # Verify all models have same questions in same order
    first_model = sorted_model_names[0]
    num_questions = len(model_responses[first_model])

    for model in sorted_model_names[1:]:
        if len(model_responses[model]) != num_questions:
            print(
                f"Warning: {model} has {len(model_responses[model])} responses, "
                f"but {first_model} has {num_questions}"
            )

    # Create combined CSV
    output_file = results_dir / "combined.csv"

    with open(output_file, "w", encoding="utf-8", newline="") as f:
        # Create header
        fieldnames = ["Topic", "Question"] + sorted_model_names
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        # Write each question as a row
        for i in range(num_questions):
            row = {
                "Topic": model_responses[first_model][i]["topic"],
                "Question": model_responses[first_model][i]["question"],
            }

            # Add each model's response
            for model in sorted_model_names:
                if i < len(model_responses[model]):
                    row[model] = model_responses[model][i]["response"]
                else:
                    row[model] = ""

            writer.writerow(row)

    print(f"\nCombined CSV created: {output_file}")
    print(f"Total questions: {num_questions}")
    print(f"Total models: {len(sorted_model_names)}")
    print(f"Model order: {', '.join(sorted_model_names)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Combine AestheticBench model results into a single CSV"
    )
    parser.add_argument(
        "results_dir",
        type=str,
        help="Path to directory containing model result CSV files",
    )
    parser.add_argument(
        "--model-order",
        type=str,
        nargs="+",
        help="Custom model ordering (space-separated list of model names)",
    )

    args = parser.parse_args()
    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        return

    if not results_dir.is_dir():
        print(f"Error: Not a directory: {results_dir}")
        return

    combine_results(results_dir, model_ordering=args.model_order)


if __name__ == "__main__":
    main()
