"""Main entry point for MoralBench."""

import sys
from pathlib import Path

import typer
from typing_extensions import Annotated

from src.moral_bench import Config, OpenRouterClient, PromptProcessor

app = typer.Typer()


@app.command()
def run(
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use for completions (e.g., openai/gpt-4o)"
        )
    ] = "openai/gpt-4o",
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
):
    """Run MoralBench morality testing with the specified model."""
    print("========================================")
    print("  MoralBench - LLM Morality Testing")
    print("========================================\n")

    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    # Create client and verify model
    with OpenRouterClient(config) as client:
        # Verify model exists
        if not client.verify_model(model):
            print(f"\nModel verification failed for: {model}")
            raise typer.Exit(code=1)

        # Run health check
        if not client.health_check():
            print("\nHealth check failed. Please verify your setup.")
            raise typer.Exit(code=1)

        # Process prompts
        try:
            processor = PromptProcessor(client)
            processor.process_prompts(
                prompts_file=prompts_file,
                output_dir=output_dir,
                model=model,
            )
        except KeyboardInterrupt:
            print("\n\nProcess interrupted by user")
            raise typer.Exit(code=1)
        except Exception as e:
            print(f"\nError during processing: {e}")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
