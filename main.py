"""Main entry point for MoralBench."""

import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from src.moral_bench import Config, OpenRouterClient, PromptProcessor

app = typer.Typer()


def read_models_from_file(file_path: Path) -> list[str]:
    """Read model names from a text file (one per line).

    Args:
        file_path: Path to text file containing model names.

    Returns:
        List of model names (empty lines and comments starting with # are ignored).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Models file not found: {file_path}")

    models = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                models.append(line)

    return models


@app.command()
def run(
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use for completions (e.g., openai/gpt-4o). Mutually exclusive with --models-file."
        )
    ] = None,
    models_file: Annotated[
        Path,
        typer.Option(
            "--models-file",
            "-f",
            help="Path to text file with list of models (one per line). Mutually exclusive with --model."
        )
    ] = None,
    prompts_file: Annotated[
        Path,
        typer.Option(
            "--prompts",
            "-p",
            help="Path to input CSV file with prompts"
        )
    ] = Path("prompts/v1.csv"),
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory for output CSV files"
        )
    ] = Path("results/v1"),
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Verify models and show cost estimates without running inference"
        )
    ] = False,
):
    """Run MoralBench morality testing with the specified model(s)."""
    print("========================================")
    print("  MoralBench - LLM Morality Testing")
    print("========================================\n")

    # Validate mutually exclusive options
    if model and models_file:
        print("Error: Cannot specify both --model and --models-file")
        raise typer.Exit(code=1)

    # Determine which models to use
    if models_file:
        try:
            models = read_models_from_file(models_file)
            print(f"Loaded {len(models)} models from {models_file}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            raise typer.Exit(code=1)
    elif model:
        models = [model]
    else:
        # Default to single model
        models = ["openai/gpt-4o"]
        print("No model specified, using default: openai/gpt-4o")

    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    # Create client and process each model
    with OpenRouterClient(config) as client:
        # Run health check once
        if not client.health_check():
            print("\nHealth check failed. Please verify your setup.")
            raise typer.Exit(code=1)

        # Process each model
        total_models = len(models)
        successful = 0
        failed = 0

        for idx, current_model in enumerate(models, 1):
            print(f"\n{'='*60}")
            print(f"Processing model {idx}/{total_models}: {current_model}")
            print(f"{'='*60}\n")

            # Verify model exists
            if not client.verify_model(current_model):
                print(f"\nModel verification failed for: {current_model}")
                print("Skipping this model...\n")
                failed += 1
                continue

            # Process prompts
            try:
                processor = PromptProcessor(client)
                processor.process_prompts(
                    prompts_file=prompts_file,
                    output_dir=output_dir,
                    model=current_model,
                )
                successful += 1
            except KeyboardInterrupt:
                print("\n\nProcess interrupted by user")
                raise typer.Exit(code=1)
            except Exception as e:
                print(f"\nError during processing: {e}")
                print("Skipping this model...\n")
                failed += 1
                continue

        # Print summary if multiple models
        if total_models > 1:
            print(f"\n{'='*60}")
            print("Summary:")
            print(f"  Total models: {total_models}")
            print(f"  Successful: {successful}")
            print(f"  Failed: {failed}")
            print(f"{'='*60}")

        if failed > 0 and successful == 0:
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
