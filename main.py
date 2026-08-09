"""CLI entry point for MoralBench - thin wrapper around backend services."""

import glob as glob_module
from pathlib import Path

import typer
from tqdm import tqdm
from typing_extensions import Annotated

from moral_bench import Config, OpenRouterClient, PromptProcessor, MoralBenchDB
from moral_bench.errors import setup_error_logging
from moral_bench.grading import GradingProcessor, GraderRegistry
from moral_bench.human_judge_agreement import (
    load_annotations_from_json,
    compute_agreement,
    compute_q1q4_agreement,
    compute_inter_model_agreement,
    print_agreement_report,
    print_q1q4_agreement_report,
    create_agreement_plots,
    create_agreement_table,
)
from moralbench_api.services.config_service import ConfigService
from moralbench_api.services.discovery import DiscoveryService
from moralbench_api.services.estimation import EstimationService
from moralbench_api.services.scoring import ScoringService

app = typer.Typer()
db_app = typer.Typer(help="Database operations")
app.add_typer(db_app, name="db")

# Initialize services
discovery_service = DiscoveryService()
config_service = ConfigService()
scoring_service = ScoringService()


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
    print("  9. q4_1          - Factual Depth (0/1)")
    print(" 10. q4_2          - Specificity (0/1)")
    print(" 11. q4_3          - Synthesis (0/1)")
    print(" 12. q4_4          - Consistency (0/1)")
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
        "9": "q4_1",
        "10": "q4_2",
        "11": "q4_3",
        "12": "q4_4",
        "preference1": "preference1",
        "preference2": "preference2",
        "justification": "justification",
        "custom": "custom",
        "q1": "q1",
        "q2": "q2",
        "q3": "q3",
        "q4": "q4",
        "q4_1": "q4_1",
        "q4_2": "q4_2",
        "q4_3": "q4_3",
        "q4_4": "q4_4",
        "all": ["preference1", "preference2", "justification", "q1", "q2", "q3", "q4", "q4_1", "q4_2", "q4_3", "q4_4"],
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


@app.command("compute-scores")
def compute_scores(
    summary_file: Annotated[
        Path,
        typer.Argument(help="Path to grades_summary.csv file"),
    ] = Path("grades_summary.csv"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output CSV file path"),
    ] = Path("model_scores.csv"),
    by_question: Annotated[
        bool,
        typer.Option("--by-question", "-q", help="Show comparison across models for each question"),
    ] = False,
):
    """Compute aggregate scores (mean, median, std dev) per model across Q1-Q4 criteria."""
    print("========================================")
    print("  MoralBench - Compute Model Scores")
    print("========================================\n")

    if not summary_file.exists():
        print(f"Error: File not found: {summary_file}")
        raise typer.Exit(code=1)

    if by_question:
        models, questions = scoring_service.compute_question_comparison(summary_file)
        if not questions:
            print("Error: No data found in summary file")
            raise typer.Exit(code=1)

        print(scoring_service.format_question_comparison(models, questions))
        scoring_service.write_question_comparison_csv(models, questions, output)
        print(f"\n✓ Exported {len(questions)} questions across {len(models)} models to {output}")
    else:
        scores = scoring_service.compute_scores(summary_file)
        if not scores:
            print("Error: No data found in summary file")
            raise typer.Exit(code=1)

        print(scoring_service.format_console_output(scores))
        scoring_service.write_csv(scores, output)
        print(f"\n✓ Exported scores for {len(scores)} models to {output}")


# === Database Commands ===

@db_app.command("import")
def db_import(
    file_path: Annotated[
        Path,
        typer.Argument(help="Path to CSV/TSV file with questions to import"),
    ],
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
):
    """Import questions from a CSV/TSV file into the database."""
    print("========================================")
    print("  MoralBench - Import Questions")
    print("========================================\n")

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)
    added, total = db.add_questions_from_file(file_path)
    print(f"✓ Imported {added} new questions from {total} total in {file_path}")
    
    stats = db.get_stats()
    print(f"  Database now has {stats['questions']} questions")


@db_app.command("stats")
def db_stats(
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
):
    """Show database statistics."""
    print("========================================")
    print("  MoralBench - Database Stats")
    print("========================================\n")

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        print("Run 'uv run python main.py db import <file>' to create it.")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)
    stats = db.get_stats()
    
    print(f"Questions:  {stats['questions']}")
    print(f"Responses:  {stats['responses']}")
    print(f"Grades:     {stats['grades']}")
    print(f"Models:     {stats['models']}")
    
    if stats['models'] > 0:
        print(f"\nModels with responses:")
        for model in db.get_models():
            responses = db.get_responses(model=model)
            print(f"  - {model}: {len(responses)} responses")


@db_app.command("run")
def db_run(
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Model to use for completions"),
    ],
    run_index: Annotated[
        int,
        typer.Option("--run-index", "-r", help="Run index for variance testing"),
    ] = 1,
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be processed"),
    ] = False,
):
    """Run model inference on questions missing responses."""
    print("========================================")
    print("  MoralBench - Run Model (Database)")
    print("========================================\n")

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        print("Run 'uv run python main.py db import <file>' first.")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)
    missing = db.get_missing_questions_for_model(model, run_index)
    
    print(f"Model: {model}")
    print(f"Run index: {run_index}")
    print(f"Questions to process: {len(missing)}")

    if dry_run:
        print("\n[DRY RUN] Would process these questions:")
        for q in missing[:10]:
            print(f"  - {q.topic}: {q.question_text[:60]}...")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        raise typer.Exit(code=0)

    if not missing:
        print("✓ All questions already have responses for this model/run")
        raise typer.Exit(code=0)

    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    with OpenRouterClient(config) as client:
        if not client.verify_model(model, verbose=True):
            print(f"✗ Model not found: {model}")
            raise typer.Exit(code=1)

        messages = [q.question_text for q in missing]
        print(f"\nProcessing {len(messages)} questions...\n")

        batch_results = client.batch_chat_completions(messages, model)

        success_count = 0
        error_count = 0
        for idx, message, response in batch_results:
            question = missing[idx]
            if response:
                db.add_response(question.id, model, response, run_index)
                success_count += 1
            else:
                error_count += 1

        print(f"\n✓ Complete! Success: {success_count}, Errors: {error_count}")


@db_app.command("grade")
def db_grade(
    graders: Annotated[
        str,
        typer.Option("--graders", "-g", help="Comma-separated list of graders"),
    ] = "q1,q2,q3,q4",
    grader_model: Annotated[
        str,
        typer.Option("--grader-model", "-m", help="Model to use for grading"),
    ] = "openai/gpt-4o",
    model_filter: Annotated[
        str,
        typer.Option("--model", help="Only grade responses from this model"),
    ] = None,
    annotated_only: Annotated[
        bool,
        typer.Option("--annotated-only", help="Only grade responses that have a human annotation"),
    ] = False,
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be graded"),
    ] = False,
):
    """Grade responses using specified graders."""
    print("========================================")
    print("  MoralBench - Grade Responses (Database)")
    print("========================================\n")

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)
    grader_ids = [g.strip() for g in graders.split(",")]
    grader_version = db.get_grader_version()
    
    print(f"Graders: {', '.join(grader_ids)}")
    print(f"Grader model: {grader_model}")
    print(f"Grader version: {grader_version}")
    if model_filter:
        print(f"Filtering to model: {model_filter}")
    if annotated_only:
        print("Filtering to human-annotated responses only")

    # Count ungraded for each grader
    total_to_grade = 0
    for grader_id in grader_ids:
        ungraded = db.get_ungraded_responses(grader_id, model=model_filter, annotated_only=annotated_only)
        print(f"  {grader_id}: {len(ungraded)} ungraded responses")
        total_to_grade += len(ungraded)

    if dry_run:
        print(f"\n[DRY RUN] Would grade {total_to_grade} total response-grader pairs")
        raise typer.Exit(code=0)

    if total_to_grade == 0:
        print("✓ All responses already graded")
        raise typer.Exit(code=0)

    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise typer.Exit(code=1)

    with OpenRouterClient(config) as client:
        if not client.verify_model(grader_model, verbose=False):
            print(f"✗ Grader model not found: {grader_model}")
            raise typer.Exit(code=1)

        for grader_id in grader_ids:
            grader = GraderRegistry.get_grader(grader_id)
            ungraded = db.get_ungraded_responses(grader_id, model=model_filter, annotated_only=annotated_only)
            
            if not ungraded:
                print(f"\n✓ {grader_id}: No responses to grade")
                continue

            print(f"\nGrading with {grader_id} ({len(ungraded)} responses)...")
            
            # Build prompts
            prompts = []
            for response, question in ungraded:
                prompt = grader.construct_prompt(question.question_text, response.response_text)
                prompts.append((response.id, prompt))

            # Batch grade
            messages = [p[1] for p in prompts]
            batch_results = client.batch_chat_completions(messages, grader_model)

            success_count = 0
            error_count = 0
            failures = []
            for idx, message, grader_response in tqdm(batch_results, desc=f"  {grader_id}"):
                response_id = prompts[idx][0]
                grading_prompt = prompts[idx][1]
                response, question = ungraded[idx]

                if grader_response is None:
                    error_count += 1
                    failures.append((response_id, "NO_RESPONSE"))
                    continue

                success, score, reasoning, error_msg = grader.grade(
                    question.question_text,
                    response.response_text,
                    grader_response,
                )

                if success:
                    db.add_grade(response_id, grader_id, str(score), reasoning, grader_version,
                                 grader_model=grader_model, grader_prompt=grading_prompt)
                    success_count += 1
                else:
                    # Deliberately not written to the database. A failure stored as a
                    # grade both corrupts the score column and makes the response look
                    # graded, so get_ungraded_responses would skip it on a re-run.
                    error_count += 1
                    failures.append((response_id, error_msg))

            print(f"  ✓ {grader_id}: Success: {success_count}, Errors: {error_count}")
            if failures:
                print(f"    {len(failures)} not stored (re-run to retry):")
                for response_id, error_msg in failures[:5]:
                    print(f"      response {response_id}: {error_msg[:90]}")
                if len(failures) > 5:
                    print(f"      ... and {len(failures) - 5} more")


@db_app.command("export")
def db_export(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output CSV file path"),
    ] = Path("export.csv"),
    what: Annotated[
        str,
        typer.Option("--what", "-w", help="What to export: responses or grades"),
    ] = "grades",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Filter by model"),
    ] = None,
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
):
    """Export data from database to CSV."""
    print("========================================")
    print("  MoralBench - Export Data")
    print("========================================\n")

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)
    
    if what == "responses":
        count = db.export_responses_csv(output, model=model)
    elif what == "grades":
        count = db.export_grades_csv(output, model=model)
    else:
        print(f"Error: Unknown export type '{what}'. Use 'responses' or 'grades'.")
        raise typer.Exit(code=1)

    print(f"✓ Exported {count} rows to {output}")


@db_app.command("migrate")
def db_migrate(
    results_dir: Annotated[
        Path,
        typer.Argument(help="Path to results directory (e.g., results/v2)"),
    ],
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
):
    """Migrate existing CSV results into the database."""
    print("========================================")
    print("  MoralBench - Migrate CSVs to Database")
    print("========================================\n")

    if not results_dir.exists():
        print(f"Error: Directory not found: {results_dir}")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)
    print(f"Migrating from {results_dir}...")
    
    stats = db.migrate_from_csv_dir(results_dir)
    
    print(f"\n✓ Migration complete!")
    print(f"  Files processed: {stats['files']}")
    print(f"  Questions: {stats['questions']}")
    print(f"  Responses: {stats['responses']}")
    print(f"  Grades: {stats['grades']}")


@db_app.command("agreement")
def db_agreement(
    json_path: Annotated[
        Path,
        typer.Option("--json", "-j", help="Path to annotations.json file"),
    ] = None,
    db_path: Annotated[
        Path,
        typer.Option("--db", help="Path to database file"),
    ] = Path("moralbench.db"),
    load_only: Annotated[
        bool,
        typer.Option("--load-only", help="Only load annotations, don't compute agreement"),
    ] = False,
    inter_model: Annotated[
        bool,
        typer.Option("--inter-model", "-i", help="Compute inter-model agreement"),
    ] = False,
    plots: Annotated[
        bool,
        typer.Option("--plots", "-p", help="Generate plotly visualizations"),
    ] = False,
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory for plots and reports"),
    ] = Path("results/agreement"),
    graders: Annotated[
        str,
        typer.Option("--graders", "-g", help="Comma-separated graders for inter-model analysis"),
    ] = "q1,q2,q3,q4",
):
    """Load human annotations and compute agreement with automated grades (Q1-Q4)."""
    print("========================================")
    print("  MoralBench - Human-Model Agreement")
    print("========================================\n")

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        raise typer.Exit(code=1)

    db = MoralBenchDB(db_path)

    # Load annotations if JSON path provided
    if json_path:
        if not json_path.exists():
            print(f"Error: Annotations file not found: {json_path}")
            raise typer.Exit(code=1)
        
        count = load_annotations_from_json(json_path, db)
        print(f"✓ Loaded {count} annotations from {json_path}")

    if load_only:
        annotations = db.get_annotations()
        print(f"\nTotal annotations in database: {len(annotations)}")
        raise typer.Exit(code=0)

    # Compute human-model agreement on the Q1-Q4 questions
    q1q4_agreement = compute_q1q4_agreement(db)
    if q1q4_agreement["total_annotations"] > 0:
        print_q1q4_agreement_report(q1q4_agreement)
    else:
        print("No Q1-Q4 human annotations found.\n")

    # Legacy preference/justification agreement
    human_agreement = compute_agreement(db)

    if human_agreement["total_annotations"] > 0:
        print_agreement_report(human_agreement)
    else:
        print("No human annotations with scores found.")
        print("Run with --json <path> to load annotations first.\n")

    # Compute inter-model agreement
    inter_model_results = None
    grader_list = [g.strip() for g in graders.split(",")]
    if inter_model:
        print("\n" + "=" * 60)
        print("INTER-MODEL AGREEMENT")
        print("=" * 60)
        
        inter_model_results = compute_inter_model_agreement(db, graders=grader_list)
        
        n_pairs = len(inter_model_results["model_pairs"])
        print(f"\nAnalyzed {n_pairs} model pairs")
        
        for grader_id in grader_list:
            agreements = inter_model_results["grader_agreements"].get(grader_id, [])
            if agreements:
                kappas = [a["kappa"] for a in agreements]
                avg = sum(kappas) / len(kappas)
                print(f"  {grader_id}: Mean kappa = {avg:.3f} (n={len(agreements)} pairs)")
        
        # Save markdown report
        output_dir.mkdir(parents=True, exist_ok=True)
        report = create_agreement_table(inter_model_results)
        report_path = output_dir / "inter_model_agreement.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\n✓ Saved report to {report_path}")

    # Generate plots
    if plots:
        print("\nGenerating plots...")
        if inter_model_results is None:
            inter_model_results = compute_inter_model_agreement(db, graders=grader_list)
        
        saved = create_agreement_plots(human_agreement, inter_model_results, output_dir)
        print(f"✓ Saved {len(saved)} plots to {output_dir}/")
        for p in saved:
            print(f"  - {p.name}")


if __name__ == "__main__":
    setup_error_logging()
    app()
