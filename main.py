"""Main entry point for MoralBench."""

from pathlib import Path

import typer
from tqdm import tqdm
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


def estimate_tokens(text_or_length: str | int) -> int:
    """Rough estimate of token count (approximately 4 chars per token)."""
    if isinstance(text_or_length, int):
        return text_or_length // 4
    return len(text_or_length) // 4


def print_dry_run_report(
    client: OpenRouterClient,
    models: list[str],
    prompts: list[dict[str, str]],
) -> tuple[list[str], list[str]]:
    """Print a dry-run report with cost estimates.

    Args:
        client: OpenRouter client for fetching model info.
        models: List of model names to process.
        prompts: List of prompt dictionaries.

    Returns:
        Tuple of (valid_models, invalid_models).
    """
    print("\n" + "="*70)
    print("DRY RUN REPORT")
    print("="*70)

    # Calculate token estimates
    total_chars = sum(len(prompt.get('Question', '')) for prompt in prompts)
    total_input_tokens = estimate_tokens(total_chars) if prompts else 0
    avg_input_tokens = total_input_tokens // len(prompts) if prompts else 0
    # Estimate output tokens (rough approximation: 100-500 tokens per response)
    min_output_tokens = 100
    max_output_tokens = 500

    print(f"\nPrompts to process: {len(prompts)}")
    print(f"Average input tokens per prompt: ~{avg_input_tokens}")
    print(f"Expected output tokens per prompt: ~{min_output_tokens}-{max_output_tokens}")
    print(f"\nTotal input tokens estimate: ~{total_input_tokens:,}")
    print(f"Total output tokens estimate: ~{min_output_tokens * len(prompts):,}-{max_output_tokens * len(prompts):,}")

    print(f"\n{'='*70}")
    print(f"MODELS TO PROCESS: {len(models)}")
    print(f"{'='*70}\n")

    valid_models = []
    invalid_models = []
    total_min_cost = 0.0
    total_max_cost = 0.0

    for idx, model_name in enumerate(models, 1):
        print(f"[{idx}/{len(models)}] {model_name}")

        # Verify model
        if not client.verify_model(model_name, verbose=False):
            print(f"  Status: ✗ NOT FOUND")
            invalid_models.append(model_name)
            print()
            continue

        valid_models.append(model_name)

        # Get model info for pricing
        model_info = client.get_model_info(model_name)
        if model_info and 'pricing' in model_info:
            pricing = model_info['pricing']
            # Pricing is returned as string values per token, not per 1M tokens
            # Convert to float and multiply by 1M to get cost per 1M tokens
            prompt_cost_per_token = float(pricing.get('prompt', '0'))
            completion_cost_per_token = float(pricing.get('completion', '0'))

            # Convert to cost per 1M tokens for display
            prompt_cost = prompt_cost_per_token * 1_000_000
            completion_cost = completion_cost_per_token * 1_000_000

            # Calculate costs using per-token prices
            input_cost = total_input_tokens * prompt_cost_per_token
            min_output_cost = (min_output_tokens * len(prompts)) * completion_cost_per_token
            max_output_cost = (max_output_tokens * len(prompts)) * completion_cost_per_token

            min_total = input_cost + min_output_cost
            max_total = input_cost + max_output_cost

            total_min_cost += min_total
            total_max_cost += max_total

            print(f"  Status: ✓ AVAILABLE")
            print(f"  Pricing: ${prompt_cost:.2f}/M input, ${completion_cost:.2f}/M output")
            print(f"  Estimated cost: ${min_total:.4f} - ${max_total:.4f}")
        else:
            print(f"  Status: ✓ AVAILABLE")
            print(f"  Pricing: Not available")

        print()

    # Print summary
    print(f"{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Valid models: {len(valid_models)}")
    print(f"Invalid models: {len(invalid_models)}")
    print(f"Total requests: {len(prompts) * len(valid_models):,}")

    if total_min_cost > 0 or total_max_cost > 0:
        print(f"\nTotal estimated cost: ${total_min_cost:.4f} - ${total_max_cost:.4f}")

    print(f"{'='*70}\n")

    return valid_models, invalid_models


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

        # If dry-run mode, show report and exit
        if dry_run:
            from src.moral_bench.processor import CSVReader

            try:
                prompts = CSVReader.read_prompts(prompts_file)
            except FileNotFoundError as e:
                print(f"\nError: {e}")
                raise typer.Exit(code=1)

            valid_models, invalid_models = print_dry_run_report(client, models, prompts)

            if invalid_models:
                print(f"\nWarning: {len(invalid_models)} model(s) not found and will be skipped.")
                print("Remove --dry-run to proceed with valid models only.")
                raise typer.Exit(code=1)
            else:
                print("\nAll models verified! Remove --dry-run to proceed with inference.")
                raise typer.Exit(code=0)

        # Process each model
        total_models = len(models)
        successful = 0
        failed = 0

        for current_model in tqdm(models, desc="Processing models", unit="model", leave=True):
            # Verify model exists
            if not client.verify_model(current_model):
                tqdm.write(f"\nModel verification failed for: {current_model}")
                tqdm.write("Skipping this model...\n")
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
                tqdm.write(f"\nError during processing: {e}")
                tqdm.write("Skipping this model...\n")
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
