"""Main entry point for MoralBench."""

from pathlib import Path

import typer
from tqdm import tqdm
from typing_extensions import Annotated

from src.moral_bench import Config, OpenRouterClient, PromptProcessor
from src.moral_bench.grading import GradingProcessor

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
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                models.append(line)

    return models


def estimate_tokens(text_or_length: str | int) -> int:
    """Rough estimate of token count (approximately 4 chars per token)."""
    if isinstance(text_or_length, int):
        return text_or_length // 4
    return len(text_or_length) // 4


def derive_output_dir(prompts_file: Path, subdir: str = "responses") -> Path:
    """Derive output directory from prompt file name.

    Extracts the version identifier from the prompt file name
    and maps it to results/{version}/{subdir}.

    Args:
        prompts_file: Path to the prompt file (e.g., prompts/v1.csv or prompts/v2.tsv)
        subdir: Subdirectory within results/{version}/ (e.g., 'responses' or 'grades')

    Returns:
        Path to output directory (e.g., results/v1/responses or results/v2/grades)
    """
    # Extract filename without extension (e.g., "v1" from "v1.csv")
    version = prompts_file.stem
    return Path("results") / version / subdir


def derive_grades_output_dir(results_file: Path) -> Path:
    """Derive grades output directory from results file path.

    Tries to intelligently map:
      results/v2/responses/model_timestamp.csv -> results/v2/grades/

    Args:
        results_file: Path to input results CSV

    Returns:
        Path to grades output directory
    """
    parts = results_file.parts

    # Try to find 'results' in the path
    if "results" in parts:
        results_idx = parts.index("results")

        # Check if there's a version directory after 'results'
        if len(parts) > results_idx + 1:
            version = parts[results_idx + 1]
            return Path("results") / version / "grades"

    # Fallback: use results/grades/
    return Path("results") / "grades"


def parse_graders_from_string(graders_str: str) -> list[str]:
    """Parse comma-separated grader string.

    Args:
        graders_str: Comma-separated grader names (e.g., "preference1,justification")

    Returns:
        List of validated grader identifiers

    Raises:
        ValueError: If any grader name is invalid
    """
    valid_graders = {"preference1", "preference2", "justification"}

    graders = [g.strip().lower() for g in graders_str.split(",")]

    invalid = [g for g in graders if g not in valid_graders]
    if invalid:
        raise ValueError(
            f"Invalid grader(s): {', '.join(invalid)}. "
            f"Valid options: {', '.join(valid_graders)}"
        )

    return graders


def select_graders_interactive() -> tuple[list[str], str | None]:
    """Prompt user to select which graders to run or write a custom prompt.

    Returns:
        Tuple of (grader_ids, custom_prompt):
        - grader_ids: List of selected grader identifiers (e.g., ['preference1'])
        - custom_prompt: Custom grader prompt string, or None if using built-in graders
    """
    print("\n" + "=" * 70)
    print("SELECT GRADERS")
    print("=" * 70)
    print("\nAvailable graders:")
    print("  1. preference1   - Categorical (-1, 0, 1) preference scoring")
    print("  2. preference2   - Continuous [-1, 1] preference scoring")
    print("  3. justification - Quality of justification (1-5 scale)")
    print("  4. custom        - Write your own grader prompt")
    print("\nYou can select multiple graders (comma-separated).")
    print("Examples: '1,3' or 'preference1,justification' or 'all'\n")

    grader_map = {
        "1": "preference1",
        "2": "preference2",
        "3": "justification",
        "4": "custom",
        "preference1": "preference1",
        "preference2": "preference2",
        "justification": "justification",
        "custom": "custom",
        "all": ["preference1", "preference2", "justification"],
    }

    selection = typer.prompt("Select graders")

    # Handle 'all' case
    if selection.strip().lower() == "all":
        return grader_map["all"], None

    # Parse comma-separated input
    selected = []
    has_custom = False
    for item in selection.split(","):
        item = item.strip().lower()
        if item in grader_map:
            value = grader_map[item]
            if value == "custom":
                has_custom = True
            elif isinstance(value, list):
                selected.extend(value)
            else:
                selected.append(value)
        else:
            print(f"Warning: Unknown grader '{item}', skipping...")

    # Remove duplicates while preserving order
    selected = list(dict.fromkeys(selected))

    custom_prompt = None
    if has_custom:
        print("\n" + "-" * 70)
        print("CUSTOM GRADER PROMPT")
        print("-" * 70)
        print("Enter your custom grading prompt. This will be used to evaluate responses.")
        print("The prompt should describe how to score the response.")
        print("(Press Enter twice to finish)\n")
        
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                lines.pop()  # Remove trailing empty line
                break
            lines.append(line)
        
        custom_prompt = "\n".join(lines)
        if custom_prompt.strip():
            print(f"\nCustom prompt set ({len(custom_prompt)} chars)")
        else:
            print("Warning: Empty custom prompt, will be ignored")
            custom_prompt = None

    if not selected and not custom_prompt:
        print("Error: No valid graders selected")
        raise typer.Exit(code=1)

    if selected:
        print(f"\nSelected graders: {', '.join(selected)}")
    return selected, custom_prompt


def discover_versions() -> list[str]:
    """Discover available result versions in the results directory.

    Returns:
        List of version names sorted newest first (e.g., ['v2', 'v1', 'v0.1'])
    """
    results_dir = Path("results")
    if not results_dir.exists():
        return []

    versions = []
    for item in results_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            # Check if it has a responses subdirectory
            if (item / "responses").exists():
                versions.append(item.name)

    # Sort versions: extract numeric parts for proper ordering
    def version_key(v: str) -> tuple:
        # Handle versions like 'v2', 'v1', 'v0.1'
        parts = v.lstrip("v").split(".")
        return tuple(int(p) if p.isdigit() else 0 for p in parts)

    return sorted(versions, key=version_key, reverse=True)


def select_version_interactive() -> str:
    """Prompt user to select a version from available results.

    Returns:
        Selected version name (e.g., 'v2')
    """
    versions = discover_versions()

    if not versions:
        print("Error: No result versions found in results/ directory")
        raise typer.Exit(code=1)

    print("\n" + "=" * 70)
    print("SELECT VERSION")
    print("=" * 70)
    print("\nAvailable versions (newest first):")

    for idx, version in enumerate(versions, 1):
        responses_dir = Path("results") / version / "responses"
        file_count = len(list(responses_dir.glob("*.csv"))) if responses_dir.exists() else 0
        print(f"  {idx}. {version} ({file_count} response files)")

    print()
    selection = typer.prompt("Select version (number or name)")

    # Try as number first
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(versions):
            selected = versions[idx]
            print(f"\nSelected: {selected}")
            return selected
    except ValueError:
        pass

    # Try as name
    if selection in versions:
        print(f"\nSelected: {selection}")
        return selection

    print(f"Error: Invalid selection '{selection}'")
    raise typer.Exit(code=1)


def get_file_info(file_path: Path) -> dict:
    """Extract info from a response file.

    Args:
        file_path: Path to response CSV file

    Returns:
        Dictionary with model name, date, and file path
    """
    import os
    from datetime import datetime

    name = file_path.stem
    # Parse filename: {provider}_{model}_{date}_{time}.csv
    parts = name.rsplit("_", 2)

    if len(parts) >= 3:
        model_name = parts[0]
        date_str = parts[1]
        time_str = parts[2]
        try:
            timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y-%m-%d_%H-%M-%S")
            date_display = timestamp.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            date_display = "Unknown date"
    else:
        model_name = name
        date_display = "Unknown date"

    # Get file size
    size_bytes = file_path.stat().st_size
    if size_bytes > 1024 * 1024:
        size_display = f"{size_bytes / (1024 * 1024):.1f}MB"
    elif size_bytes > 1024:
        size_display = f"{size_bytes / 1024:.1f}KB"
    else:
        size_display = f"{size_bytes}B"

    return {
        "path": file_path,
        "model": model_name,
        "date": date_display,
        "size": size_display,
    }


def select_files_interactive(version: str) -> list[Path]:
    """Prompt user to select response files from a version.

    Args:
        version: Version name (e.g., 'v2')

    Returns:
        List of selected file paths
    """
    responses_dir = Path("results") / version / "responses"

    if not responses_dir.exists():
        print(f"Error: Responses directory not found: {responses_dir}")
        raise typer.Exit(code=1)

    files = sorted(responses_dir.glob("*.csv"))
    if not files:
        print(f"Error: No CSV files found in {responses_dir}")
        raise typer.Exit(code=1)

    # Get file info
    file_infos = [get_file_info(f) for f in files]

    print("\n" + "=" * 70)
    print(f"SELECT RESPONSE FILES ({version})")
    print("=" * 70)
    print("\nAvailable response files:")

    # Calculate column widths
    max_model = max(len(info["model"]) for info in file_infos)
    max_model = min(max_model, 45)  # Cap width

    for idx, info in enumerate(file_infos, 1):
        model = info["model"][:45]
        print(f"  {idx:2}. {model:<{max_model}}  {info['date']}  ({info['size']})")

    print("\nEnter file numbers (comma-separated) or 'all'")
    print("Examples: '1,3,5' or '1-3' or 'all'\n")

    selection = typer.prompt("Select files")

    # Parse selection
    selected_indices = set()

    if selection.strip().lower() == "all":
        selected_indices = set(range(len(files)))
    else:
        for part in selection.split(","):
            part = part.strip()
            if "-" in part:
                # Range selection
                try:
                    start, end = part.split("-")
                    for i in range(int(start) - 1, int(end)):
                        if 0 <= i < len(files):
                            selected_indices.add(i)
                except ValueError:
                    print(f"Warning: Invalid range '{part}', skipping...")
            else:
                # Single number
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(files):
                        selected_indices.add(idx)
                    else:
                        print(f"Warning: Index {part} out of range, skipping...")
                except ValueError:
                    print(f"Warning: Invalid selection '{part}', skipping...")

    if not selected_indices:
        print("Error: No valid files selected")
        raise typer.Exit(code=1)

    selected_files = [files[i] for i in sorted(selected_indices)]
    print(f"\nSelected {len(selected_files)} file(s):")
    for f in selected_files:
        print(f"  - {f.name}")

    return selected_files


def validate_results_csv(file_path: Path) -> tuple[bool, str]:
    """Validate that results CSV has expected structure.

    Args:
        file_path: Path to results CSV

    Returns:
        Tuple of (is_valid, error_message)
    """
    import csv

    required_columns = {"Topic", "Question", "Model Response", "Timestamp"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = set(reader.fieldnames or [])

            missing = required_columns - fieldnames
            if missing:
                return False, f"Missing required columns: {', '.join(missing)}"

            return True, ""
    except Exception as e:
        return False, f"Error reading CSV: {e}"


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
    print("\n" + "=" * 70)
    print("DRY RUN REPORT")
    print("=" * 70)

    # Calculate token estimates
    total_chars = sum(len(prompt.get("Question", "")) for prompt in prompts)
    total_input_tokens = estimate_tokens(total_chars) if prompts else 0
    avg_input_tokens = total_input_tokens // len(prompts) if prompts else 0
    # Estimate output tokens (rough approximation: 100-500 tokens per response)
    min_output_tokens = 100
    max_output_tokens = 500

    print(f"\nPrompts to process: {len(prompts)}")
    print(f"Average input tokens per prompt: ~{avg_input_tokens}")
    print(
        f"Expected output tokens per prompt: ~{min_output_tokens}-{max_output_tokens}"
    )
    print(f"\nTotal input tokens estimate: ~{total_input_tokens:,}")
    print(
        f"Total output tokens estimate: ~{min_output_tokens * len(prompts):,}-{max_output_tokens * len(prompts):,}"
    )

    print(f"\n{'=' * 70}")
    print(f"MODELS TO PROCESS: {len(models)}")
    print(f"{'=' * 70}\n")

    valid_models = []
    invalid_models = []
    total_min_cost = 0.0
    total_max_cost = 0.0

    for idx, model_name in enumerate(models, 1):
        print(f"[{idx}/{len(models)}] {model_name}")

        # Verify model
        if not client.verify_model(model_name, verbose=False):
            print("  Status: ✗ NOT FOUND")
            invalid_models.append(model_name)
            print()
            continue

        valid_models.append(model_name)

        # Get model info for pricing
        model_info = client.get_model_info(model_name)
        if model_info and "pricing" in model_info:
            pricing = model_info["pricing"]
            # Pricing is returned as string values per token, not per 1M tokens
            # Convert to float and multiply by 1M to get cost per 1M tokens
            prompt_cost_per_token = float(pricing.get("prompt", "0"))
            completion_cost_per_token = float(pricing.get("completion", "0"))

            # Convert to cost per 1M tokens for display
            prompt_cost = prompt_cost_per_token * 1_000_000
            completion_cost = completion_cost_per_token * 1_000_000

            # Calculate costs using per-token prices
            input_cost = total_input_tokens * prompt_cost_per_token
            min_output_cost = (
                min_output_tokens * len(prompts)
            ) * completion_cost_per_token
            max_output_cost = (
                max_output_tokens * len(prompts)
            ) * completion_cost_per_token

            min_total = input_cost + min_output_cost
            max_total = input_cost + max_output_cost

            total_min_cost += min_total
            total_max_cost += max_total

            print("  Status: ✓ AVAILABLE")
            print(
                f"  Pricing: ${prompt_cost:.2f}/M input, ${completion_cost:.2f}/M output"
            )
            print(f"  Estimated cost: ${min_total:.4f} - ${max_total:.4f}")
        else:
            print("  Status: ✓ AVAILABLE")
            print("  Pricing: Not available")

        print()

    # Print summary
    print(f"{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Valid models: {len(valid_models)}")
    print(f"Invalid models: {len(invalid_models)}")
    print(f"Total requests: {len(prompts) * len(valid_models):,}")

    if total_min_cost > 0 or total_max_cost > 0:
        print(f"\nTotal estimated cost: ${total_min_cost:.4f} - ${total_max_cost:.4f}")

    print(f"{'=' * 70}\n")

    return valid_models, invalid_models


@app.command()
def run(
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model to use for completions (e.g., openai/gpt-4o). Mutually exclusive with --models-file.",
        ),
    ] = None,
    models_file: Annotated[
        Path,
        typer.Option(
            "--models-file",
            "-f",
            help="Path to text file with list of models (one per line). Mutually exclusive with --model.",
        ),
    ] = None,
    prompts_file: Annotated[
        Path,
        typer.Option("--prompts", "-p", help="Path to input CSV/TSV file with prompts"),
    ] = Path("prompts/v2.tsv"),
    output_dir: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for output CSV files (auto-derived from prompts file if not specified)")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Verify models and show cost estimates without running inference",
        ),
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

    # If output_dir not specified, derive from prompts_file
    if output_dir is None:
        output_dir = derive_output_dir(prompts_file)

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
                print(
                    f"\nWarning: {len(invalid_models)} model(s) not found and will be skipped."
                )
                print("Remove --dry-run to proceed with valid models only.")
                raise typer.Exit(code=1)
            else:
                print(
                    "\nAll models verified! Remove --dry-run to proceed with inference."
                )
                raise typer.Exit(code=0)

        # Process each model
        total_models = len(models)
        successful = 0
        failed = 0

        for current_model in tqdm(
            models, desc="Processing models", unit="model", leave=True
        ):
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
            print(f"\n{'=' * 60}")
            print("Summary:")
            print(f"  Total models: {total_models}")
            print(f"  Successful: {successful}")
            print(f"  Failed: {failed}")
            print(f"{'=' * 60}")

        if failed > 0 and successful == 0:
            raise typer.Exit(code=1)


@app.command("health-check")
def health_check():
    """Run a health check to verify API connectivity and configuration."""
    print("========================================")
    print("  MoralBench - Health Check")
    print("========================================\n")

    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    # Create client and run health check
    with OpenRouterClient(config) as client:
        if client.health_check():
            print("\n✓ Health check passed!")
            raise typer.Exit(code=0)
        else:
            print("\n✗ Health check failed. Please verify your setup.")
            raise typer.Exit(code=1)


@app.command()
def grade(
    results_pattern: Annotated[
        str,
        typer.Argument(
            help="Path to results CSV file(s) to grade. Supports glob patterns (e.g., results/v2/responses/*.csv). If not provided, enters interactive mode."
        ),
    ] = None,
    graders: Annotated[
        str,
        typer.Option(
            "--graders",
            "-g",
            help="Comma-separated list of graders to run: preference1, preference2, justification",
        ),
    ] = None,
    grader_model: Annotated[
        str,
        typer.Option(
            "--grader-model",
            "-m",
            help="Model to use for grading (e.g., openai/gpt-4o)",
        ),
    ] = "openai/gpt-4o",
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Directory for graded output CSV (auto-derived if not specified)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show files to be graded and estimate costs without running grading",
        ),
    ] = False,
):
    """Grade model responses using specified grader prompts.
    
    If no arguments provided, enters interactive mode to select files and graders.
    """
    import csv
    import glob

    print("========================================")
    print("  MoralBench - Grade Model Responses")
    print("========================================\n")

    custom_prompt = None

    # Interactive mode if no results_pattern provided
    if results_pattern is None:
        print("No files specified - entering interactive mode...\n")
        
        # Step 1: Select version
        version = select_version_interactive()
        
        # Step 2: Select files
        results_files = select_files_interactive(version)
        
        # Step 3: Select graders (with custom prompt support)
        grader_ids, custom_prompt = select_graders_interactive()
    else:
        # Expand glob pattern to get list of files
        matched_files = sorted(glob.glob(results_pattern))
        if not matched_files:
            # Try as literal path
            if Path(results_pattern).exists():
                matched_files = [results_pattern]
            else:
                print(f"Error: No files found matching pattern: {results_pattern}")
                raise typer.Exit(code=1)

        results_files = [Path(f) for f in matched_files]
        print(f"Found {len(results_files)} file(s) to grade:")
        for f in results_files:
            print(f"  - {f}")
        print()

        # Validate all results CSVs have required columns
        valid_files = []
        for results_file in results_files:
            is_valid, error_msg = validate_results_csv(results_file)
            if not is_valid:
                print(f"Warning: Skipping invalid CSV {results_file} - {error_msg}")
            else:
                valid_files.append(results_file)

        if not valid_files:
            print("Error: No valid results CSV files found")
            raise typer.Exit(code=1)

        results_files = valid_files

        # Grader selection
        if graders:
            try:
                grader_ids = parse_graders_from_string(graders)
            except ValueError as e:
                print(f"Error: {e}")
                raise typer.Exit(code=1)
        else:
            # Interactive selection
            grader_ids, custom_prompt = select_graders_interactive()

    # Dry-run mode: show what would be graded and estimate costs
    if dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN REPORT - GRADING")
        print("=" * 70)

        total_responses = 0
        for results_file in results_files:
            with open(results_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                count = sum(1 for _ in reader)
                total_responses += count
                print(f"  {results_file}: {count} responses")

        # Calculate total graders (built-in + custom if present)
        num_graders = len(grader_ids) + (1 if custom_prompt else 0)
        grader_names = list(grader_ids) + (["custom"] if custom_prompt else [])

        print(f"\nTotal responses to grade: {total_responses}")
        print(f"Graders to run: {', '.join(grader_names)}")
        if custom_prompt:
            print(f"Custom prompt: {custom_prompt[:100]}{'...' if len(custom_prompt) > 100 else ''}")
        print(f"Total grading calls: {total_responses * num_graders}")
        print(f"Grader model: {grader_model}")

        # Rough token estimates
        avg_input_tokens = 500  # prompt + question + response
        avg_output_tokens = 50  # just a score
        total_input = total_responses * num_graders * avg_input_tokens
        total_output = total_responses * num_graders * avg_output_tokens

        print(f"\nEstimated tokens:")
        print(f"  Input: ~{total_input:,}")
        print(f"  Output: ~{total_output:,}")
        print("=" * 70)
        print("\nRemove --dry-run to proceed with grading.")
        raise typer.Exit(code=0)

    # Derive output directory if not specified (use first file for derivation)
    if output_dir is None:
        output_dir = derive_grades_output_dir(results_files[0])

    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    # Create client and process grading
    with OpenRouterClient(config) as client:
        # Run health check
        if not client.health_check():
            print("\nHealth check failed. Please verify your setup.")
            raise typer.Exit(code=1)

        # Verify grader model exists
        print(f"\nVerifying grader model: {grader_model}...")
        if not client.verify_model(grader_model, verbose=False):
            print(f"✗ Grader model not found: {grader_model}")
            raise typer.Exit(code=1)
        print(f"✓ Grader model verified: {grader_model}")

        # Process grading for each file
        try:
            processor = GradingProcessor(client)
            for idx, results_file in enumerate(results_files, 1):
                print(f"\n[{idx}/{len(results_files)}] Grading: {results_file}")
                processor.grade_responses(
                    results_file=results_file,
                    output_dir=output_dir,
                    grader_ids=grader_ids,
                    grader_model=grader_model,
                    custom_prompt=custom_prompt,
                )
        except KeyboardInterrupt:
            print("\n\nProcess interrupted by user")
            raise typer.Exit(code=1)
        except Exception as e:
            print(f"\nError during grading: {e}")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
