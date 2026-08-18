"""Service for computing aggregate scores across Q1-Q4 criteria."""

import csv
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QuestionScores:
    """Scores for a single question across all models."""
    topic: str
    question: str
    model_scores: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class CriterionStats:
    """Statistics for a single criterion (Q1-Q4)."""
    mean: float
    median: float
    std_dev: float
    count: int
    error_count: int
    error_rate: float


@dataclass
class ModelScores:
    """Aggregate scores for a single model across all criteria."""
    model: str
    q1: CriterionStats
    q2: CriterionStats
    q3: CriterionStats
    q4: CriterionStats


class ScoringService:
    """Service for computing and exporting model scores."""

    def compute_scores(self, summary_file: Path) -> list[ModelScores]:
        """Read grades_summary.csv and compute aggregate stats per model."""
        model_data: dict[str, dict[str, list]] = {}

        with open(summary_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                model = row.get("Model", "")
                if not model:
                    continue

                if model not in model_data:
                    model_data[model] = {
                        "Q1": [], "Q2": [], "Q3": [], "Q4": [],
                        "Q1_errors": 0, "Q2_errors": 0, "Q3_errors": 0, "Q4_errors": 0,
                    }

                for q in ["Q1", "Q2", "Q3", "Q4"]:
                    val = row.get(f"{q}_Score", "")
                    if val == "n/a" or val == "" or val.startswith("PARSE_ERROR") or val.startswith("ERROR"):
                        model_data[model][f"{q}_errors"] += 1
                    else:
                        try:
                            model_data[model][q].append(float(val))
                        except ValueError:
                            model_data[model][f"{q}_errors"] += 1

        results = []
        for model, data in sorted(model_data.items()):
            stats = {}
            for q in ["Q1", "Q2", "Q3", "Q4"]:
                values = data[q]
                error_count = data[f"{q}_errors"]
                total = len(values) + error_count

                if values:
                    mean = statistics.mean(values)
                    median = statistics.median(values)
                    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
                else:
                    mean = median = std_dev = 0.0

                stats[q] = CriterionStats(
                    mean=mean,
                    median=median,
                    std_dev=std_dev,
                    count=len(values),
                    error_count=error_count,
                    error_rate=error_count / total if total > 0 else 0.0,
                )

            results.append(ModelScores(
                model=model,
                q1=stats["Q1"],
                q2=stats["Q2"],
                q3=stats["Q3"],
                q4=stats["Q4"],
            ))

        return results

    def format_console_output(self, scores: list[ModelScores]) -> str:
        """Format scores as a pretty-printed table for console output."""
        lines = []
        lines.append("=" * 100)
        lines.append("MODEL SCORES SUMMARY")
        lines.append("=" * 100)
        lines.append("")

        for model_scores in scores:
            lines.append(f"Model: {model_scores.model}")
            lines.append("-" * 80)
            lines.append(f"{'Criterion':<12} {'Mean':>8} {'Median':>8} {'StdDev':>8} {'Count':>8} {'Errors':>8} {'ErrRate':>8}")
            lines.append("-" * 80)

            for q_name, stats in [
                ("Q1 (Relat.)", model_scores.q1),
                ("Q2 (Pref.)", model_scores.q2),
                ("Q3 (Evid.)", model_scores.q3),
                ("Q4 (Just.)", model_scores.q4),
            ]:
                lines.append(
                    f"{q_name:<12} {stats.mean:>8.3f} {stats.median:>8.3f} "
                    f"{stats.std_dev:>8.3f} {stats.count:>8} {stats.error_count:>8} "
                    f"{stats.error_rate:>7.1%}"
                )

            lines.append("")

        lines.append("=" * 100)
        return "\n".join(lines)

    def write_csv(self, scores: list[ModelScores], output_path: Path) -> None:
        """Write scores to a CSV file."""
        fieldnames = ["Model"]
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            fieldnames.extend([
                f"{q}_Mean", f"{q}_Median", f"{q}_StdDev",
                f"{q}_Count", f"{q}_ErrorCount", f"{q}_ErrorRate"
            ])

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for model_scores in scores:
                row = {"Model": model_scores.model}
                for q, stats in [
                    ("Q1", model_scores.q1),
                    ("Q2", model_scores.q2),
                    ("Q3", model_scores.q3),
                    ("Q4", model_scores.q4),
                ]:
                    row[f"{q}_Mean"] = f"{stats.mean:.4f}"
                    row[f"{q}_Median"] = f"{stats.median:.4f}"
                    row[f"{q}_StdDev"] = f"{stats.std_dev:.4f}"
                    row[f"{q}_Count"] = stats.count
                    row[f"{q}_ErrorCount"] = stats.error_count
                    row[f"{q}_ErrorRate"] = f"{stats.error_rate:.4f}"

                writer.writerow(row)

    def compute_question_comparison(self, summary_file: Path) -> tuple[list[str], list[QuestionScores]]:
        """Read grades_summary.csv and organize scores by question for cross-model comparison.
        
        Returns:
            Tuple of (list of model names, list of QuestionScores)
        """
        questions: dict[str, QuestionScores] = {}
        models: set[str] = set()

        with open(summary_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                model = row.get("Model", "")
                topic = row.get("Topic", "")
                question = row.get("Question", "")
                if not model or not question:
                    continue

                models.add(model)
                key = question

                if key not in questions:
                    questions[key] = QuestionScores(topic=topic, question=question)

                questions[key].model_scores[model] = {
                    "Q1": row.get("Q1_Score", ""),
                    "Q2": row.get("Q2_Score", ""),
                    "Q3": row.get("Q3_Score", ""),
                    "Q4": row.get("Q4_Score", ""),
                }

        return sorted(models), list(questions.values())

    def format_question_comparison(self, models: list[str], questions: list[QuestionScores]) -> str:
        """Format question comparison as console output."""
        lines = []
        lines.append("=" * 120)
        lines.append("QUESTION-LEVEL MODEL COMPARISON")
        lines.append("=" * 120)
        lines.append(f"Models: {', '.join(models)}")
        lines.append("")

        for q in questions:
            lines.append(f"[{q.topic}] {q.question[:80]}{'...' if len(q.question) > 80 else ''}")
            
            header = f"{'Model':<30}"
            for criterion in ["Q1", "Q2", "Q3", "Q4"]:
                header += f" {criterion:>6}"
            lines.append(header)
            lines.append("-" * 60)

            for model in models:
                scores = q.model_scores.get(model, {})
                row = f"{model[:30]:<30}"
                for criterion in ["Q1", "Q2", "Q3", "Q4"]:
                    val = scores.get(criterion, "n/a")
                    row += f" {val:>6}"
                lines.append(row)
            lines.append("")

        return "\n".join(lines)

    def write_question_comparison_csv(self, models: list[str], questions: list[QuestionScores], output_path: Path) -> None:
        """Write question comparison to CSV with models as columns."""
        fieldnames = ["Topic", "Question"]
        for model in models:
            for q in ["Q1", "Q2", "Q3", "Q4"]:
                fieldnames.append(f"{model}_{q}")

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for q in questions:
                row = {"Topic": q.topic, "Question": q.question}
                for model in models:
                    scores = q.model_scores.get(model, {})
                    for criterion in ["Q1", "Q2", "Q3", "Q4"]:
                        row[f"{model}_{criterion}"] = scores.get(criterion, "n/a")
                writer.writerow(row)
