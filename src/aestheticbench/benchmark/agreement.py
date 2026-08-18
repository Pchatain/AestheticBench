"""Human judge agreement analysis for AestheticBench annotations."""

import json
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Optional

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from ..store.database import AestheticBenchDB
from .rubric import SPECS


def load_annotations_from_json(json_path: Path, db: AestheticBenchDB) -> int:
    """Load annotations from JSON file into database.
    
    Maps result_uid from JSON to response_id in database.
    
    Args:
        json_path: Path to annotations.json file
        db: AestheticBenchDB instance
        
    Returns:
        Count of loaded annotations
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Annotations file not found: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        annotations_data = json.load(f)
    
    count = 0
    for ann_id, ann in annotations_data.items():
        result_uid = ann.get("result_uid")
        if result_uid is None:
            continue
        
        created_at = None
        updated_at = None
        if ann.get("created_at"):
            try:
                created_at = datetime.fromisoformat(ann["created_at"].rstrip("Z"))
            except ValueError:
                pass
        if ann.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(ann["updated_at"].rstrip("Z"))
            except ValueError:
                pass
        
        db.add_annotation(
            annotation_id=ann_id,
            response_id=result_uid,
            model=ann.get("model", ""),
            notes=ann.get("notes"),
            preference_reasoning=ann.get("preference_reasoning"),
            preference_score=ann.get("preference_score"),
            justification_reasoning=ann.get("justification_reasoning"),
            justification_score=ann.get("justification_score"),
            created_at=created_at,
            updated_at=updated_at,
        )
        count += 1
    
    return count


def _discretize_preference(score: Optional[float]) -> Optional[int]:
    """Convert continuous preference score to discrete category for kappa."""
    if score is None:
        return None
    if score < -0.33:
        return -1
    elif score > 0.33:
        return 1
    return 0


def _parse_q2_score(score_str: Optional[str]) -> Optional[int]:
    """Parse q2 score string to integer (-1, 0, 1)."""
    if score_str is None:
        return None
    try:
        val = int(score_str)
        if val in (-1, 0, 1):
            return val
    except (ValueError, TypeError):
        pass
    return None


def _parse_q4_score(score_str: Optional[str]) -> Optional[int]:
    """Parse q4 score string to integer (1-5)."""
    if score_str is None:
        return None
    try:
        val = int(score_str)
        if 1 <= val <= 5:
            return val
    except (ValueError, TypeError):
        pass
    return None


def _parse_preference1_score(score_str: Optional[str]) -> Optional[int]:
    """Parse preference1 score string to integer (-1, 0, 1)."""
    if score_str is None:
        return None
    try:
        val = int(score_str)
        if val in (-1, 0, 1):
            return val
    except (ValueError, TypeError):
        pass
    return None


def _parse_justification_score(score_str: Optional[str]) -> Optional[int]:
    """Parse justification score string to integer (1-5)."""
    if score_str is None:
        return None
    try:
        val = int(score_str)
        if 1 <= val <= 5:
            return val
    except (ValueError, TypeError):
        pass
    return None


def _parse_yes_no(value) -> Optional[int]:
    """Parse a human Q1 answer to 0/1.

    The TUI writes "Yes"/"No" strings into q1_score even though the column is
    declared INTEGER, and SQLite keeps them as text.
    """
    if value is None:
        return None
    if isinstance(value, str):
        val = value.strip().lower()
        if val in ("yes", "y", "1"):
            return 1
        if val in ("no", "n", "0"):
            return 0
        return None
    try:
        val = int(value)
    except (ValueError, TypeError):
        return None
    return val if val in (0, 1) else None


def _parse_in_range(value, allowed: tuple[int, ...]) -> Optional[int]:
    """Parse a score to an int, returning None unless it lands in `allowed`."""
    if value is None:
        return None
    try:
        val = int(str(value).strip())
    except (ValueError, TypeError):
        return None
    return val if val in allowed else None


# Scales come from rubric.SPECS so they cannot drift from the graders.
# q1 needs its own parser because the TUI stores the human answer as "Yes"/"No"
# text while the grader emits 0/1.
Q1Q4_SPECS = {
    grader_id: {
        "name": spec.name,
        "labels": spec.allowed,
        "ordinal": spec.ordinal,
        **({"parse": _parse_yes_no} if grader_id == "q1" else {}),
    }
    for grader_id, spec in SPECS.items()
    if spec.generation == "current"
}


def compute_q1q4_agreement(db: AestheticBenchDB, valid_only: bool = True) -> dict:
    """Compute Cohen's kappa between human Q1-Q4 annotations and LLM grades.

    Unlike compute_agreement, which only covers the legacy preference and
    justification scores, this covers all eight Q1-Q4 questions including the
    Q4.1-Q4.4 sub-questions.

    Args:
        db: AestheticBenchDB instance
        valid_only: Drop annotations whose response_id points at another model's
            response (the miscsaved legacy import). Defaults to True.

    Returns:
        Dictionary keyed by question id with kappa, n, and confusion matrix.
    """
    data = db.get_annotations_with_grades(valid_only=valid_only)

    results = {}
    for qid, spec in Q1Q4_SPECS.items():
        labels = spec["labels"]
        parse = spec.get("parse") or (lambda v, _a=labels: _parse_in_range(v, _a))

        human_scores = []
        auto_scores = []
        for row in data:
            human = parse(row.get(f"human_{qid}"))
            auto = parse(row.get(f"{qid}_score"))
            if human is not None and auto is not None:
                human_scores.append(human)
                auto_scores.append(auto)

        entry = {
            "name": spec["name"],
            "kappa": None,
            "kappa_quadratic": None,
            "n_samples": len(human_scores),
            "human_scores": human_scores,
            "auto_scores": auto_scores,
            "labels": list(labels),
            "confusion_matrix": None,
            "percent_agreement": None,
        }

        if human_scores:
            matches = sum(h == a for h, a in zip(human_scores, auto_scores))
            entry["percent_agreement"] = matches / len(human_scores)

        if len(human_scores) >= 2:
            cm = confusion_matrix(human_scores, auto_scores, labels=list(labels))
            entry["confusion_matrix"] = cm.tolist()
            # cohen_kappa_score is undefined (nan) when both raters are constant
            # and identical; leave kappa as None rather than emitting nan.
            kappa = cohen_kappa_score(human_scores, auto_scores, labels=list(labels))
            if kappa == kappa:
                entry["kappa"] = float(kappa)
            if spec["ordinal"]:
                weighted = cohen_kappa_score(
                    human_scores, auto_scores, labels=list(labels), weights="quadratic"
                )
                if weighted == weighted:
                    entry["kappa_quadratic"] = float(weighted)

        results[qid] = entry

    results["total_annotations"] = len(data)
    return results


def print_q1q4_agreement_report(agreement: dict) -> None:
    """Print a human-readable Q1-Q4 human/judge agreement report."""
    print("\n" + "=" * 70)
    print("  HUMAN vs LLM JUDGE AGREEMENT (Q1-Q4)")
    print("=" * 70)
    print(f"\nAnnotations considered: {agreement.get('total_annotations', 0)}\n")

    header = f"{'Question':<22} {'n':>4} {'kappa':>8} {'weighted':>9} {'% agree':>8}"
    print(header)
    print("-" * len(header))

    for qid, spec in Q1Q4_SPECS.items():
        entry = agreement.get(qid)
        if not entry:
            continue
        kappa = entry["kappa"]
        weighted = entry["kappa_quadratic"]
        pct = entry["percent_agreement"]
        print(
            f"{qid + ' ' + spec['name']:<22} {entry['n_samples']:>4} "
            f"{(f'{kappa:.3f}' if kappa is not None else '-'):>8} "
            f"{(f'{weighted:.3f}' if weighted is not None else '-'):>9} "
            f"{(f'{pct:.0%}' if pct is not None else '-'):>8}"
        )

    print()
    for qid in Q1Q4_SPECS:
        entry = agreement.get(qid)
        if entry and entry["kappa"] is not None:
            print(f"  {qid}: {_interpret_kappa(entry['kappa'])}")

    unscored = [q for q in Q1Q4_SPECS if agreement.get(q, {}).get("n_samples", 0) == 0]
    if unscored:
        print(f"\nNo overlapping human+LLM scores for: {', '.join(unscored)}")
    print()


def compute_agreement(db: AestheticBenchDB) -> dict:
    """Compute Cohen's kappa between human annotations and automated grades.
    
    Compares:
    - Human preference_score vs q2 (preference) or preference1 automated grade
    - Human justification_score vs q4 or justification automated grade
    
    Args:
        db: AestheticBenchDB instance
        
    Returns:
        Dictionary with agreement metrics for each comparison
    """
    data = db.get_annotations_with_grades()
    
    # Try multiple graders for preference (q2, preference1)
    preference_human = []
    preference_auto = []
    preference_grader_used = None
    
    # Try multiple graders for justification (q4, justification)
    justification_human = []
    justification_auto = []
    justification_grader_used = None
    
    for row in data:
        human_pref = row.get("human_preference")
        
        if human_pref is not None:
            discretized = _discretize_preference(human_pref)
            if discretized is not None:
                # Try q2 first, then preference1
                q2_score = _parse_q2_score(row.get("q2_score"))
                pref1_score = _parse_preference1_score(row.get("preference1_score"))
                
                if q2_score is not None:
                    preference_human.append(discretized)
                    preference_auto.append(q2_score)
                    preference_grader_used = "q2"
                elif pref1_score is not None:
                    preference_human.append(discretized)
                    preference_auto.append(pref1_score)
                    preference_grader_used = "preference1"
        
        human_just = row.get("human_justification")
        
        if human_just is not None:
            # Try q4 first, then justification
            q4_score = _parse_q4_score(row.get("q4_score"))
            just_score = _parse_justification_score(row.get("justification_auto_score"))
            
            if q4_score is not None:
                justification_human.append(human_just)
                justification_auto.append(q4_score)
                justification_grader_used = "q4"
            elif just_score is not None:
                justification_human.append(human_just)
                justification_auto.append(just_score)
                justification_grader_used = "justification"
    
    result = {
        "preference": {
            "kappa": None,
            "n_samples": len(preference_human),
            "human_scores": preference_human,
            "auto_scores": preference_auto,
            "confusion_matrix": None,
            "grader_used": preference_grader_used,
        },
        "justification": {
            "kappa": None,
            "n_samples": len(justification_human),
            "human_scores": justification_human,
            "auto_scores": justification_auto,
            "confusion_matrix": None,
            "grader_used": justification_grader_used,
        },
        "total_annotations": len(data),
    }
    
    if len(preference_human) >= 2:
        try:
            kappa = cohen_kappa_score(preference_human, preference_auto)
            result["preference"]["kappa"] = float(kappa)
            cm = confusion_matrix(preference_human, preference_auto, labels=[-1, 0, 1])
            result["preference"]["confusion_matrix"] = cm.tolist()
        except Exception:
            pass
    
    if len(justification_human) >= 2:
        try:
            kappa = cohen_kappa_score(justification_human, justification_auto)
            result["justification"]["kappa"] = float(kappa)
            cm = confusion_matrix(justification_human, justification_auto, labels=[1, 2, 3, 4, 5])
            result["justification"]["confusion_matrix"] = cm.tolist()
        except Exception:
            pass
    
    return result


def print_agreement_report(agreement: dict) -> None:
    """Print a formatted agreement report."""
    print("\n" + "=" * 60)
    print("HUMAN-MODEL AGREEMENT REPORT")
    print("=" * 60)
    print(f"\nTotal annotations analyzed: {agreement['total_annotations']}")
    
    pref = agreement["preference"]
    grader = pref.get("grader_used", "q2") or "q2"
    print(f"\n--- Preference Agreement (human vs {grader}) ---")
    print(f"  Samples with both scores: {pref['n_samples']}")
    if pref["kappa"] is not None:
        print(f"  Cohen's Kappa: {pref['kappa']:.3f}")
        print(f"  Interpretation: {_interpret_kappa(pref['kappa'])}")
        if pref["confusion_matrix"]:
            print(f"  Confusion Matrix (rows=human, cols=auto):")
            print(f"         -1    0    1")
            for i, label in enumerate([-1, 0, 1]):
                row = pref["confusion_matrix"][i]
                print(f"    {label:2d}  {row[0]:3d}  {row[1]:3d}  {row[2]:3d}")
    else:
        print("  Not enough samples to compute kappa")
    
    just = agreement["justification"]
    grader = just.get("grader_used", "q4") or "q4"
    print(f"\n--- Justification Agreement (human vs {grader}) ---")
    print(f"  Samples with both scores: {just['n_samples']}")
    if just["kappa"] is not None:
        print(f"  Cohen's Kappa: {just['kappa']:.3f}")
        print(f"  Interpretation: {_interpret_kappa(just['kappa'])}")
        if just["confusion_matrix"]:
            print(f"  Confusion Matrix (rows=human, cols=auto):")
            print(f"          1    2    3    4    5")
            for i, label in enumerate([1, 2, 3, 4, 5]):
                row = just["confusion_matrix"][i]
                print(f"    {label:2d}  {row[0]:3d}  {row[1]:3d}  {row[2]:3d}  {row[3]:3d}  {row[4]:3d}")
    else:
        print("  Not enough samples to compute kappa")
    
    print("\n" + "=" * 60)


def _interpret_kappa(kappa: float) -> str:
    """Interpret kappa value according to Landis & Koch guidelines."""
    if kappa < 0:
        return "Poor (less than chance)"
    elif kappa < 0.21:
        return "Slight agreement"
    elif kappa < 0.41:
        return "Fair agreement"
    elif kappa < 0.61:
        return "Moderate agreement"
    elif kappa < 0.81:
        return "Substantial agreement"
    else:
        return "Almost perfect agreement"


def compute_inter_model_agreement(db: AestheticBenchDB, graders: list[str] = None) -> dict:
    """Compute Cohen's kappa between different models' automated grades.
    
    For each pair of models, computes agreement on specified graders
    for questions they both answered.
    
    Args:
        db: AestheticBenchDB instance
        graders: List of grader IDs to analyze. Defaults to the current q-series.
    
    Returns:
        Dictionary with inter-model agreement metrics
    """
    if graders is None:
        graders = ["q1_1", "q1_2", "q2", "q3", "q4"]
    
    models = db.get_models()
    
    # Get all grades grouped by response
    grader_placeholders = ",".join(["?" for _ in graders])
    with db._connect() as conn:
        cursor = conn.execute(
            f"""SELECT r.question_id, r.model, g.grader_id, g.score
               FROM grades g
               JOIN responses r ON g.response_id = r.id
               WHERE g.grader_id IN ({grader_placeholders})
               ORDER BY r.question_id, r.model, g.grader_id""",
            graders
        )
        rows = cursor.fetchall()
    
    # Build model->question->grader->score mapping
    model_grades = {}
    for row in rows:
        q_id, model, grader_id, score = row
        if model not in model_grades:
            model_grades[model] = {}
        if q_id not in model_grades[model]:
            model_grades[model][q_id] = {}
        model_grades[model][q_id][grader_id] = score
    
    results = {
        "model_pairs": [],
        "grader_agreements": {g: [] for g in graders},
    }
    
    # Compare each pair of models
    for model_a, model_b in combinations(models, 2):
        if model_a not in model_grades or model_b not in model_grades:
            continue
        
        # Find common questions
        common_qs = set(model_grades[model_a].keys()) & set(model_grades[model_b].keys())
        if len(common_qs) < 2:
            continue
        
        pair_result = {
            "model_a": model_a,
            "model_b": model_b,
            "n_common": len(common_qs),
            "graders": {},
        }
        
        for grader_id in graders:
            scores_a = []
            scores_b = []
            
            for q_id in common_qs:
                score_a = model_grades[model_a][q_id].get(grader_id)
                score_b = model_grades[model_b][q_id].get(grader_id)
                
                if score_a is not None and score_b is not None:
                    # Skip error scores
                    if "ERROR" in str(score_a) or "ERROR" in str(score_b):
                        continue
                    scores_a.append(score_a)
                    scores_b.append(score_b)
            
            if len(scores_a) >= 2:
                try:
                    kappa = cohen_kappa_score(scores_a, scores_b)
                    pair_result["graders"][grader_id] = {
                        "kappa": float(kappa),
                        "n_samples": len(scores_a),
                    }
                    results["grader_agreements"][grader_id].append({
                        "model_a": model_a,
                        "model_b": model_b,
                        "kappa": float(kappa),
                        "n_samples": len(scores_a),
                    })
                except Exception:
                    pass
        
        if pair_result["graders"]:
            results["model_pairs"].append(pair_result)
    
    return results


def create_agreement_plots(
    human_agreement: dict,
    inter_model_agreement: dict,
    output_dir: Path,
) -> list[Path]:
    """Create plotly visualizations for agreement analysis.
    
    Returns list of saved plot paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_plots = []
    
    # 1. Inter-model agreement heatmap for each grader
    all_graders = list(inter_model_agreement["grader_agreements"].keys())
    for grader_id in all_graders:
        agreements = inter_model_agreement["grader_agreements"].get(grader_id, [])
        if not agreements:
            continue
        
        # Get unique models
        models = sorted(set(
            [a["model_a"] for a in agreements] + [a["model_b"] for a in agreements]
        ))
        
        # Build matrix
        n = len(models)
        matrix = [[1.0 if i == j else None for j in range(n)] for i in range(n)]
        
        model_idx = {m: i for i, m in enumerate(models)}
        for a in agreements:
            i, j = model_idx[a["model_a"]], model_idx[a["model_b"]]
            matrix[i][j] = a["kappa"]
            matrix[j][i] = a["kappa"]
        
        # Shorten model names for display
        short_names = [m.split("/")[-1][:20] for m in models]
        
        fig = go.Figure(data=go.Heatmap(
            z=matrix,
            x=short_names,
            y=short_names,
            colorscale="RdYlGn",
            zmin=-1,
            zmax=1,
            text=[[f"{v:.2f}" if v is not None else "" for v in row] for row in matrix],
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="Model A: %{y}<br>Model B: %{x}<br>Kappa: %{z:.3f}<extra></extra>",
        ))
        
        grader_names = {gid: spec.name for gid, spec in SPECS.items()}
        fig.update_layout(
            title=f"Inter-Model Agreement - {grader_names.get(grader_id, grader_id)} ({grader_id})",
            xaxis_title="Model",
            yaxis_title="Model",
            width=800,
            height=700,
        )
        fig.update_xaxes(tickangle=45)
        
        path = output_dir / f"inter_model_agreement_{grader_id}.html"
        fig.write_html(str(path))
        saved_plots.append(path)
    
    # 2. Average kappa per model pair across all graders
    pair_avg_kappas = []
    for pair in inter_model_agreement["model_pairs"]:
        kappas = [g["kappa"] for g in pair["graders"].values()]
        if kappas:
            pair_avg_kappas.append({
                "pair": f"{pair['model_a'].split('/')[-1][:15]} vs {pair['model_b'].split('/')[-1][:15]}",
                "avg_kappa": sum(kappas) / len(kappas),
                "n_graders": len(kappas),
            })
    
    if pair_avg_kappas:
        pair_avg_kappas.sort(key=lambda x: x["avg_kappa"], reverse=True)
        
        fig = px.bar(
            pair_avg_kappas[:20],  # Top 20
            x="pair",
            y="avg_kappa",
            title="Top 20 Model Pairs by Average Agreement (across Q1-Q4)",
            labels={"pair": "Model Pair", "avg_kappa": "Average Cohen's Kappa"},
            color="avg_kappa",
            color_continuous_scale="RdYlGn",
            range_color=[-1, 1],
        )
        fig.update_layout(xaxis_tickangle=45, width=1000, height=500)
        
        path = output_dir / "model_pair_avg_agreement.html"
        fig.write_html(str(path))
        saved_plots.append(path)
    
    # 3. Distribution of kappa values per grader
    grader_kappas = []
    for grader_id, agreements in inter_model_agreement["grader_agreements"].items():
        for a in agreements:
            grader_kappas.append({
                "grader": grader_id,
                "kappa": a["kappa"],
            })
    
    if grader_kappas:
        fig = px.box(
            grader_kappas,
            x="grader",
            y="kappa",
            title="Distribution of Inter-Model Agreement by Grader",
            labels={"grader": "Grader", "kappa": "Cohen's Kappa"},
            color="grader",
        )
        fig.add_hline(y=0.6, line_dash="dash", line_color="green", 
                      annotation_text="Substantial agreement threshold")
        fig.add_hline(y=0.4, line_dash="dash", line_color="orange",
                      annotation_text="Moderate agreement threshold")
        fig.update_layout(width=700, height=500)
        
        path = output_dir / "kappa_distribution_by_grader.html"
        fig.write_html(str(path))
        saved_plots.append(path)
    
    # 4. Human vs automated agreement (if data exists)
    pref = human_agreement.get("preference", {})
    just = human_agreement.get("justification", {})
    
    if pref.get("n_samples", 0) > 0 or just.get("n_samples", 0) > 0:
        human_data = []
        if pref.get("kappa") is not None:
            human_data.append({"comparison": "Human vs Q2 (Preference)", "kappa": pref["kappa"], "n": pref["n_samples"]})
        if just.get("kappa") is not None:
            human_data.append({"comparison": "Human vs Q4 (Justification)", "kappa": just["kappa"], "n": just["n_samples"]})
        
        if human_data:
            fig = px.bar(
                human_data,
                x="comparison",
                y="kappa",
                title="Human-Model Agreement",
                labels={"comparison": "Comparison", "kappa": "Cohen's Kappa"},
                color="kappa",
                color_continuous_scale="RdYlGn",
                range_color=[-1, 1],
                text="n",
            )
            fig.update_traces(texttemplate="n=%{text}", textposition="outside")
            fig.update_layout(width=600, height=400)
            
            path = output_dir / "human_model_agreement.html"
            fig.write_html(str(path))
            saved_plots.append(path)
    
    # 5. Confusion matrices for human agreement
    if pref.get("confusion_matrix"):
        cm = pref["confusion_matrix"]
        labels = ["-1", "0", "1"]
        fig = go.Figure(data=go.Heatmap(
            z=cm,
            x=labels,
            y=labels,
            colorscale="Blues",
            text=cm,
            texttemplate="%{text}",
            hovertemplate="Human: %{y}<br>Auto (Q2): %{x}<br>Count: %{z}<extra></extra>",
        ))
        fig.update_layout(
            title="Confusion Matrix: Human Preference vs Q2 Auto",
            xaxis_title="Automated (Q2)",
            yaxis_title="Human",
            width=500,
            height=450,
        )
        path = output_dir / "confusion_matrix_preference.html"
        fig.write_html(str(path))
        saved_plots.append(path)
    
    if just.get("confusion_matrix"):
        cm = just["confusion_matrix"]
        labels = ["1", "2", "3", "4", "5"]
        fig = go.Figure(data=go.Heatmap(
            z=cm,
            x=labels,
            y=labels,
            colorscale="Blues",
            text=cm,
            texttemplate="%{text}",
            hovertemplate="Human: %{y}<br>Auto (Q4): %{x}<br>Count: %{z}<extra></extra>",
        ))
        fig.update_layout(
            title="Confusion Matrix: Human Justification vs Q4 Auto",
            xaxis_title="Automated (Q4)",
            yaxis_title="Human",
            width=500,
            height=450,
        )
        path = output_dir / "confusion_matrix_justification.html"
        fig.write_html(str(path))
        saved_plots.append(path)
    
    return saved_plots


def create_agreement_table(inter_model_agreement: dict) -> str:
    """Create a markdown table summarizing inter-model agreement."""
    lines = ["# Inter-Model Agreement Summary\n"]
    
    grader_names = {
        **{gid: spec.name for gid, spec in SPECS.items()},
        "preference1": "Preference (Categorical)",
        "preference2": "Preference (Continuous)",
        "justification": "Justification (Legacy)",
    }
    
    for grader_id in inter_model_agreement["grader_agreements"].keys():
        agreements = inter_model_agreement["grader_agreements"].get(grader_id, [])
        
        if not agreements:
            continue
        
        kappas = [a["kappa"] for a in agreements]
        avg_kappa = sum(kappas) / len(kappas)
        min_kappa = min(kappas)
        max_kappa = max(kappas)
        
        lines.append(f"\n## {grader_names.get(grader_id, grader_id.title())} ({grader_id})")
        lines.append(f"\n- **Mean Kappa**: {avg_kappa:.3f} ({_interpret_kappa(avg_kappa)})")
        lines.append(f"- **Min Kappa**: {min_kappa:.3f}")
        lines.append(f"- **Max Kappa**: {max_kappa:.3f}")
        lines.append(f"- **Model Pairs**: {len(agreements)}")
        
        # Top 5 most agreeing pairs
        sorted_agreements = sorted(agreements, key=lambda x: x["kappa"], reverse=True)[:5]
        lines.append("\n### Top 5 Most Agreeing Pairs")
        lines.append("| Model A | Model B | Kappa | Samples |")
        lines.append("|---------|---------|-------|---------|")
        for a in sorted_agreements:
            lines.append(f"| {a['model_a'].split('/')[-1]} | {a['model_b'].split('/')[-1]} | {a['kappa']:.3f} | {a['n_samples']} |")
        
        # Bottom 5 least agreeing pairs
        sorted_agreements = sorted(agreements, key=lambda x: x["kappa"])[:5]
        lines.append("\n### Top 5 Least Agreeing Pairs")
        lines.append("| Model A | Model B | Kappa | Samples |")
        lines.append("|---------|---------|-------|---------|")
        for a in sorted_agreements:
            lines.append(f"| {a['model_a'].split('/')[-1]} | {a['model_b'].split('/')[-1]} | {a['kappa']:.3f} | {a['n_samples']} |")
    
    return "\n".join(lines)
