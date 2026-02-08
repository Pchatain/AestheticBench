"""CLI entry point for MoralBench - thin wrapper around backend services."""

import glob as glob_module
from pathlib import Path

import typer
from tqdm import tqdm
from typing_extensions import Annotated

from moral_bench import Config, OpenRouterClient, PromptProcessor
from moral_bench.errors import setup_error_logging
from moral_bench.grading import GradingProcessor
from moralbench_api.services.config_service import ConfigService
from moralbench_api.services.discovery import DiscoveryService
from moralbench_api.services.estimation import EstimationService

app = typer.Typer()

# Initialize services
discovery_service = DiscoveryService()
config_service = ConfigService()


def _print_run_estimate(estimate) -> None:
    """Print inference dry-run estimate."""
    print("\n" + "=" * 70)
    print("DRY RUN REPORT")
    print("=" * 70)

    print(f"\nPrompts to process: {estimate.prompts_count}")
    print(f"Total input tokens estimate: ~{estimate.total_input_tokens:,}")
    print(
        f"Expected output tokens per prompt: ~{estimate.min_output_tokens_per_prompt}-{estimate.max_output_tokens_per_prompt}"
    )

    print(f"\n{'=' * 70}")
    print(f"MODELS TO PROCESS: {len(estimate.models)}")
    print(f"{'=' * 70}\n")

    for idx, model in enumerate(estimate.models, 1):
        print(f"[{idx}/{len(estimate.models)}] {model.model}")
        if model.available:
            print("  Status: ✓ AVAILABLE")
            if model.input_cost_per_m is not None:
                print(
                    f"  Pricing: ${model.input_cost_per_m:.2f}/M input, ${model.output_cost_per_m:.2f}/M output"
                )
                print(
                    f"  Estimated cost: ${model.estimated_min_cost:.4f} - ${model.estimated_max_cost:.4f}"
                )
            else:
                print(f"  Pricing: {model.error or 'Not available'}")
        else:
            print(f"  Status: ✗ NOT FOUND ({model.error})")
        print()

    print(f"{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Valid models: {len(estimate.valid_models)}")
    print(f"Invalid models: {len(estimate.invalid_models)}")
    print(f"Total requests: {estimate.prompts_count * len(estimate.valid_models):,}")

    if estimate.total_min_cost > 0 or estimate.total_max_cost > 0:
        print(
            f"\nTotal estimated cost: ${estimate.total_min_cost:.4f} - ${estimate.total_max_cost:.4f}"
        )
    print(f"{'=' * 70}\n")


def _print_grading_estimate(estimate) -> None:
    """Print grading dry-run estimate."""
    print("\n" + "=" * 70)
    print("DRY RUN REPORT - GRADING")
    print("=" * 70)

    for f in estimate.files:
        print(f"  {f.filename}: {f.response_count} responses")

    print(f"\nTotal responses to grade: {estimate.total_responses}")
    grader_names = list(estimate.graders)
    if estimate.custom_prompt_included:
        grader_names.append("custom")
    print(f"Graders to run: {', '.join(grader_names)}")
    print(f"Total grading calls: {estimate.total_grading_calls}")
    print(f"Grader model: {estimate.grader_model}")

    print(f"\nEstimated tokens:")
    print(f"  Input: ~{estimate.estimated_input_tokens:,}")
    print(f"  Output: ~{estimate.estimated_output_tokens:,}")
    print("=" * 70)
    print("\nRemove --dry-run to proceed with grading.")


def _select_version_interactive() -> str:
    """Prompt user to select a version."""
    versions = discovery_service.discover_versions()

    if not versions:
        print("Error: No result versions found in results/ directory")
        raise typer.Exit(code=1)

    print("\n" + "=" * 70)
    print("SELECT VERSION")
    print("=" * 70)
    print("\nAvailable versions (newest first):")

    for idx, version in enumerate(versions, 1):
        print(f"  {idx}. {version.name} ({version.response_count} response files)")

    print()
    selection = typer.prompt("Select version (number or name)")

    # Try as number first
    try:
        idx = int(selection) - 1
        if 0 <= idx < len(versions):
            selected = versions[idx].name
            print(f"\nSelected: {selected}")
            return selected
    except ValueError:
        pass

    # Try as name
    version_names = [v.name for v in versions]
    if selection in version_names:
        print(f"\nSelected: {selection}")
        return selection

    print(f"Error: Invalid selection '{selection}'")
    raise typer.Exit(code=1)


def _select_files_interactive(version: str) -> list[Path]:
    """Prompt user to select files from a version."""
    files = discovery_service.list_response_files(version)

    if not files:
        print(f"Error: No response files found in {version}")
        raise typer.Exit(code=1)

    print("\n" + "=" * 70)
    print(f"SELECT RESPONSE FILES ({version})")
    print("=" * 70)
    print("\nAvailable response files:")

    max_model = min(max(len(f.model) for f in files), 45)

    for idx, f in enumerate(files, 1):
        model = f.model[:45]
        print(f"  {idx:2}. {model:<{max_model}}  {f.date}  ({f.size})")

    print("\nEnter file numbers (comma-separated) or 'all'")
    print("Examples: '1,3,5' or '1-3' or 'all'\n")

    selection = typer.prompt("Select files")

    selected_indices = set()
    if selection.strip().lower() == "all":
        selected_indices = set(range(len(files)))
    else:
        for part in selection.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-")
                    for i in range(int(start) - 1, int(end)):
                        if 0 <= i < len(files):
                            selected_indices.add(i)
                except ValueError:
                    print(f"Warning: Invalid range '{part}', skipping...")
            else:
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(files):
                        selected_indices.add(idx)
                except ValueError:
                    print(f"Warning: Invalid selection '{part}', skipping...")

    if not selected_indices:
        print("Error: No valid files selected")
        raise typer.Exit(code=1)

    selected_files = [Path(files[i].path) for i in sorted(selected_indices)]
    print(f"\nSelected {len(selected_files)} file(s):")
    for f in selected_files:
        print(f"  - {f.name}")

    return selected_files


def _select_graders_interactive() -> tuple[list[str], str | None]:
    """Prompt user to select graders or write a custom prompt."""
    print("\n" + "=" * 70)
    print("SELECT GRADERS")
    print("=" * 70)
    print("\nAvailable graders:")
    print("  1. preference1   - Categorical (-1, 0, 1) preference scoring")
    print("  2. preference2   - Continuous [-1, 1] preference scoring")
    print("  3. justification - Quality of justification (1-5 scale) [requires preference1]")
    print("  4. custom        - Write your own grader prompt")
    print("  5. q1            - Relativism check (0=no, 1=yes)")
    print("  6. q2            - Preference (-1, 0, 1)")
    print("  7. q3            - Evidence evaluation (-1, 0, 1)")
    print("  8. q4            - Justification quality (1-5)")
    print("\nYou can select multiple graders (comma-separated).")
    print("Examples: '1,3' or 'preference1,justification' or 'all' or 'q1,q2,q3,q4'\n")

    grader_map = {
        "1": "preference1",
        "2": "preference2",
        "3": "justification",
        "4": "custom",
        "5": "q1",
        "6": "q2",
        "7": "q3",
        "8": "q4",
        "preference1": "preference1",
        "preference2": "preference2",
        "justification": "justification",
        "custom": "custom",
        "q1": "q1",
        "q2": "q2",
        "q3": "q3",
        "q4": "q4",
        "all": ["preference1", "preference2", "justification", "q1", "q2", "q3", "q4"],
    }

    selection = typer.prompt("Select graders")

    if selection.strip().lower() == "all":
        return grader_map["all"], None

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

    selected = list(dict.fromkeys(selected))

    custom_prompt = None
    if has_custom:
        print("\n" + "-" * 70)
        print("CUSTOM GRADER PROMPT")
        print("-" * 70)
        print("Enter your custom grading prompt. (Press Enter twice to finish)\n")

        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                lines.pop()
                break
            lines.append(line)

        custom_prompt = "\n".join(lines)
        if custom_prompt.strip():
            print(f"\nCustom prompt set ({len(custom_prompt)} chars)")
        else:
            custom_prompt = None

    if not selected and not custom_prompt:
        print("Error: No valid graders selected")
        raise typer.Exit(code=1)

    # Ensure dependencies
    validation = config_service.validate_graders(selected, custom_prompt)
    if validation.warnings:
        for warning in validation.warnings:
            print(f"Note: {warning}")

    print(f"\nSelected graders: {', '.join(validation.grader_ids)}")
    return validation.grader_ids, custom_prompt


@app.command()
def run(
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Model to use for completions"),
    ] = None,
    models_file: Annotated[
        Path,
        typer.Option("--models-file", "-f", help="Path to text file with list of models"),
    ] = None,
    prompts_file: Annotated[
        Path,
        typer.Option("--prompts", "-p", help="Path to input CSV/TSV file with prompts"),
    ] = Path("prompts/v2.tsv"),
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Directory for output CSV files"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Verify models and show cost estimates"),
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
        models = config_service.read_models_from_file(models_file)
        print(f"Loaded {len(models)} models from {models_file}")
    elif model:
        models = [model]
    else:
        models = ["openai/gpt-4o"]
        print("No model specified, using default: openai/gpt-4o")

    # Derive output directory if not specified
    if output_dir is None:
        output_dir = discovery_service.derive_output_dir(prompts_file)

    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    with OpenRouterClient(config) as client:
        if not client.health_check():
            print("\nHealth check failed. Please verify your setup.")
            raise typer.Exit(code=1)

        if dry_run:
            estimation_service = EstimationService(client)
            estimate = estimation_service.estimate_run(models, prompts_file)
            _print_run_estimate(estimate)

            if estimate.invalid_models:
                print(f"\nWarning: {len(estimate.invalid_models)} model(s) not found.")
                raise typer.Exit(code=1)
            else:
                print("All models verified! Remove --dry-run to proceed.")
                raise typer.Exit(code=0)

        # Process each model
        total_models = len(models)
        successful = 0
        failed = 0

        for current_model in tqdm(models, desc="Processing models", unit="model"):
            if not client.verify_model(current_model):
                tqdm.write(f"\nModel verification failed for: {current_model}")
                failed += 1
                continue

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
                failed += 1

        if total_models > 1:
            print(f"\n{'=' * 60}")
            print(f"Summary: {successful} successful, {failed} failed")
            print(f"{'=' * 60}")

        if failed > 0 and successful == 0:
            raise typer.Exit(code=1)


@app.command("health-check")
def health_check():
    """Run a health check to verify API connectivity and configuration."""
    print("========================================")
    print("  MoralBench - Health Check")
    print("========================================\n")

    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    with OpenRouterClient(config) as client:
        if client.health_check():
            print("\n✓ Health check passed!")
            raise typer.Exit(code=0)
        else:
            print("\n✗ Health check failed.")
            raise typer.Exit(code=1)


@app.command()
def grade(
    results_pattern: Annotated[
        str,
        typer.Argument(help="Path to results CSV file(s). Supports glob patterns."),
    ] = None,
    graders: Annotated[
        str,
        typer.Option("--graders", "-g", help="Comma-separated list of graders"),
    ] = None,
    grader_model: Annotated[
        str,
        typer.Option("--grader-model", "-m", help="Model to use for grading"),
    ] = "openai/gpt-4o",
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Directory for graded output CSV"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show files and estimate costs"),
    ] = False,
):
    """Grade model responses using specified grader prompts."""
    print("========================================")
    print("  MoralBench - Grade Model Responses")
    print("========================================\n")

    custom_prompt = None

    # Interactive mode if no results_pattern provided
    if results_pattern is None:
        print("No files specified - entering interactive mode...\n")
        version = _select_version_interactive()
        results_files = _select_files_interactive(version)
        grader_ids, custom_prompt = _select_graders_interactive()
    else:
        matched_files = sorted(glob_module.glob(results_pattern))
        if not matched_files:
            if Path(results_pattern).exists():
                matched_files = [results_pattern]
            else:
                print(f"Error: No files found matching pattern: {results_pattern}")
                raise typer.Exit(code=1)

        results_files = [Path(f) for f in matched_files]
        print(f"Found {len(results_files)} file(s) to grade")

        # Validate files
        validation = config_service.validate_files([str(f) for f in results_files])
        if not validation.valid:
            for error in validation.errors:
                print(f"Warning: {error}")

        results_files = [Path(f) for f in validation.valid_files]

        if not results_files:
            print("Error: No valid results CSV files found")
            raise typer.Exit(code=1)

        # Grader selection
        if graders:
            grader_ids = config_service.parse_graders(graders)
            grader_ids = config_service.ensure_dependencies(grader_ids)
        else:
            grader_ids, custom_prompt = _select_graders_interactive()

    # Dry-run mode
    if dry_run:
        try:
            config = Config.from_env()
        except ValueError as e:
            print(f"Configuration error: {e}")
            raise typer.Exit(code=1)

        with OpenRouterClient(config) as client:
            estimation_service = EstimationService(client)
            estimate = estimation_service.estimate_grading(
                results_files, grader_ids, grader_model, custom_prompt
            )
            _print_grading_estimate(estimate)
            raise typer.Exit(code=0)

    # Derive output directory
    if output_dir is None:
        output_dir = discovery_service.derive_grades_output_dir(results_files[0])

    # Load configuration and run grading
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    with OpenRouterClient(config) as client:
        if not client.health_check():
            print("\nHealth check failed.")
            raise typer.Exit(code=1)

        print(f"\nVerifying grader model: {grader_model}...")
        if not client.verify_model(grader_model, verbose=False):
            print(f"✗ Grader model not found: {grader_model}")
            raise typer.Exit(code=1)
        print(f"✓ Grader model verified: {grader_model}")

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


@app.command("export-grades")
def export_grades(
    files: Annotated[
        list[str],
        typer.Argument(help="Graded CSV files to export"),
    ],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output CSV file path"),
    ] = "grades_summary.csv",
):
    """Export Q1-Q4 grade scores from graded result files to a summary CSV."""
    import csv
    import re

    print("========================================")
    print("  MoralBench - Export Grades Summary")
    print("========================================\n")

    rows = []
    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            print(f"Warning: File not found: {filepath}")
            continue

        # Extract model name from filename (e.g., "anthropic_claude-opus-4.5" from path)
        filename = path.stem
        match = re.match(r"^([^_]+_[^_]+)", filename)
        model_name = match.group(1) if match else filename.split("_")[0]

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Find Q1-Q4 score columns
            score_cols = {}
            for h in headers:
                for q in ["Q1", "Q2", "Q3", "Q4"]:
                    if h.startswith(f"{q}_") and h.endswith("_Score"):
                        score_cols[q] = h
                        break

            if len(score_cols) < 4:
                print(f"Warning: {filepath} missing some Q1-Q4 score columns, found: {list(score_cols.keys())}")

            def clean_score(val):
                """Return score or n/a if it's an error/non-numeric."""
                if not val or val.startswith("PARSE_ERROR") or val.startswith("ERROR"):
                    return "n/a"
                return val

            for row in reader:
                rows.append({
                    "Model": model_name,
                    "Topic": row.get("Topic", ""),
                    "Question": row.get("Question", ""),
                    "Q1_Score": clean_score(row.get(score_cols.get("Q1", ""), "")),
                    "Q2_Score": clean_score(row.get(score_cols.get("Q2", ""), "")),
                    "Q3_Score": clean_score(row.get(score_cols.get("Q3", ""), "")),
                    "Q4_Score": clean_score(row.get(score_cols.get("Q4", ""), "")),
                })

        print(f"  Loaded {filepath}: {model_name}")

    if not rows:
        print("Error: No data to export")
        raise typer.Exit(code=1)

    # Write output CSV
    output_path = Path(output)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Model", "Topic", "Question", "Q1_Score", "Q2_Score", "Q3_Score", "Q4_Score"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ Exported {len(rows)} rows to {output_path}")


@app.command("export-stats")
def export_stats(
    files: Annotated[
        list[str],
        typer.Argument(help="Graded CSV files to export"),
    ],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output CSV file path"),
    ] = "grades_stats.csv",
):
    """Export Q1-Q4 grade statistics (counts per rating) from graded result files."""
    import csv
    import re
    from collections import Counter

    print("========================================")
    print("  MoralBench - Export Grade Statistics")
    print("========================================\n")

    model_stats = {}

    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            print(f"Warning: File not found: {filepath}")
            continue

        filename = path.stem
        match = re.match(r"^([^_]+_[^_]+)", filename)
        model_name = match.group(1) if match else filename.split("_")[0]

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            score_cols = {}
            for h in headers:
                for q in ["Q1", "Q2", "Q3", "Q4"]:
                    if h.startswith(f"{q}_") and h.endswith("_Score"):
                        score_cols[q] = h
                        break

            counters = {q: Counter() for q in ["Q1", "Q2", "Q3", "Q4"]}

            for row in reader:
                for q in ["Q1", "Q2", "Q3", "Q4"]:
                    val = row.get(score_cols.get(q, ""), "")
                    if val and not val.startswith("PARSE_ERROR") and not val.startswith("ERROR"):
                        counters[q][val] += 1
                    else:
                        counters[q]["n/a"] += 1

            model_stats[model_name] = counters
            print(f"  Loaded {filepath}: {model_name}")

    if not model_stats:
        print("Error: No data to export")
        raise typer.Exit(code=1)

    # Build stats rows
    rows = []
    for model_name, counters in model_stats.items():
        row = {"Model": model_name}
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            for val, count in sorted(counters[q].items(), key=lambda x: (x[0] == "n/a", x[0])):
                row[f"{q}_{val}"] = count
        rows.append(row)

    # Collect all columns
    all_cols = {"Model"}
    for row in rows:
        all_cols.update(row.keys())
    
    # Sort columns: Model first, then Q1_*, Q2_*, Q3_*, Q4_*
    def col_sort_key(c):
        if c == "Model":
            return (0, "")
        parts = c.split("_", 1)
        q_order = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get(parts[0], 5)
        val = parts[1] if len(parts) > 1 else ""
        if val == "n/a":
            return (q_order, 999)
        try:
            return (q_order, int(val))
        except ValueError:
            return (q_order, 998)
    
    fieldnames = sorted(all_cols, key=col_sort_key)

    output_path = Path(output)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, 0) for k in fieldnames})

    print(f"\n✓ Exported stats for {len(model_stats)} models to {output_path}")


if __name__ == "__main__":
    setup_error_logging()
    app()
