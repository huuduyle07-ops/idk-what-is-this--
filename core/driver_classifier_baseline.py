"""MODEL.2 — Driver Classifier Baseline (report-only).

Consumes the MODEL.1 JSONL artifact dataset and builds a small offline baseline
classifier/evaluator. It learns a pure-stdlib, deterministic baseline (a single-rule
"OneR" over the dataset features, falling back to a majority-class baseline) and
produces an advisory evaluation report plus a prediction preview.

MODEL.2 builds an offline baseline only. It does not route live tasks, does not
override the deterministic Driver, does not call model APIs, does not call LLMs, does
not call embeddings, does not write to a database, does not apply patches, does not
run validation or a benchmark check, and does not launch workers. Every prediction
carries ``authority="advisory_only"`` and grants no execution authority.

This module is stdlib-only. The dataset is read once; the report builder is pure and
never mutates the dataset rows. Only the writer touches the filesystem, and only
under the chosen output directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "driver_classifier_baseline"

DEFAULT_TARGET_FIELD = "target.target_label"

#: Ordered target-field candidates. The first with >= 2 distinct classes is used.
FALLBACK_TARGET_FIELDS: tuple[str, ...] = (
    "target.target_label",
    "labels.recommended_next_step",
    "labels.final_verdict",
    "artifact_kind",
    "target.dataset_task",
)

#: Deterministic feature schema: (name, dotted source path, type).
FEATURE_SCHEMA: tuple[tuple[str, str, str], ...] = (
    ("artifact_kind", "artifact_kind", "categorical"),
    ("dataset_task", "target.dataset_task", "categorical"),
    ("risk_level", "risk_level", "categorical"),
    ("automation_level", "automation_level", "categorical"),
    ("final_verdict", "labels.final_verdict", "categorical"),
    ("recommended_vehicle", "labels.recommended_vehicle", "categorical"),
    ("has_remote_component", "features.has_remote_component", "boolean"),
    ("has_patch_candidate", "features.has_patch_candidate", "boolean"),
    ("has_visual_issue", "features.has_visual_issue", "boolean"),
    ("has_human_gate", "features.has_human_gate", "boolean"),
)

FEATURE_NAMES: tuple[str, ...] = tuple(name for name, _, _ in FEATURE_SCHEMA)

BASELINE_MAJORITY = "majority_class"
BASELINE_ONE_RULE = "one_rule"

#: Output artifact filenames.
REPORT_JSON_NAME = "driver_classifier_baseline_report.json"
REPORT_MD_NAME = "driver_classifier_baseline_report.md"
PREDICTIONS_NAME = "driver_classifier_predictions.jsonl"

DRIVER_CLASSIFIER_GUARDRAIL_NOTE = (
    "Driver Classifier Baseline is report-only: it reads the MODEL.1 artifact dataset "
    "and learns a small offline, pure-stdlib baseline (a single-rule classifier with a "
    "majority-class fallback) to produce an advisory evaluation report. It does not route "
    "live tasks, override the deterministic Driver, call model APIs, call LLMs, call "
    "embeddings, write to a database, apply patches, run validation or a benchmark check, "
    "or launch workers. Predictions are advisory only and grant no execution authority."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _norm_path(value: Any) -> str:
    return str(value).replace("\\", "/").strip()


def _get_path(row: dict[str, Any], dotted: str) -> Any:
    node: Any = row
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _feature_value(row: dict[str, Any], source: str, kind: str) -> str:
    value = _get_path(row, source)
    if kind == "boolean":
        return "true" if value is True else "false"
    return "" if value is None else str(value)


def _counts(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def _majority_label(labels: list[str]) -> str:
    """Most frequent label; ties broken by sorted order for determinism."""
    counts = _counts(labels)
    if not counts:
        return ""
    best = max(counts.values())
    return sorted(k for k, v in counts.items() if v == best)[0]


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _hash_bucket(row_id: str) -> float:
    digest = hashlib.sha256(row_id.encode("utf-8")).hexdigest()[:8]
    return (int(digest, 16) % 1000) / 1000.0


# ── Dataset loading ─────────────────────────────────────────────────────────────

def load_dataset(dataset_path: str | Path) -> dict[str, Any]:
    """Read a MODEL.1 JSONL dataset.

    Returns ``{rows, warnings, skipped, present}``. A missing file yields
    ``present=False`` and an empty row list; malformed or non-object lines are
    skipped with a warning rather than raising.
    """
    path = Path(dataset_path)
    if not path.exists():
        return {"rows": [], "warnings": [f"dataset not found at {_norm_path(dataset_path)}"], "skipped": 0, "present": False}

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"rows": [], "warnings": [f"could not read dataset at {_norm_path(dataset_path)}: {exc}"], "skipped": 0, "present": False}

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            skipped += 1
            warnings.append(f"skipped malformed JSONL line {lineno}")
            continue
        if not isinstance(obj, dict):
            skipped += 1
            warnings.append(f"skipped non-object JSONL line {lineno}")
            continue
        rows.append(obj)
    return {"rows": rows, "warnings": warnings, "skipped": skipped, "present": True}


# ── Target selection + examples ─────────────────────────────────────────────────

def _distinct_labels(rows: list[dict[str, Any]], field: str) -> set[str]:
    return {str(_get_path(r, field)) for r in rows if _get_path(r, field) not in (None, "")}


def _select_target_field(rows: list[dict[str, Any]], requested: str) -> tuple[str, bool]:
    """Pick the first target field with >= 2 classes, starting with ``requested``."""
    chain = [requested] + [f for f in FALLBACK_TARGET_FIELDS if f != requested]
    for field in chain:
        if len(_distinct_labels(rows, field)) >= 2:
            return field, field != requested
    return requested, False


def _extract_examples(rows: list[dict[str, Any]], target_field: str) -> tuple[list[dict[str, Any]], int]:
    """Build labeled examples; rows with an empty target are dropped (counted)."""
    examples: list[dict[str, Any]] = []
    dropped = 0
    for row in rows:
        label = _get_path(row, target_field)
        if label is None or str(label) == "":
            dropped += 1
            continue
        features = {name: _feature_value(row, source, kind) for name, source, kind in FEATURE_SCHEMA}
        examples.append(
            {
                "row_id": str(row.get("row_id") or ""),
                "artifact_kind": str(row.get("artifact_kind") or ""),
                "label": str(label),
                "features": features,
            }
        )
    return examples, dropped


def deterministic_split(rows: list[dict[str, Any]], test_ratio: float) -> tuple[list[str], list[str]]:
    """Split row ids into (train, test) by a stable per-row-id hash bucket.

    A row is a test row when ``hash_bucket(row_id) < test_ratio``. The split depends
    only on the row id, so it is stable regardless of dataset ordering.
    """
    train: list[str] = []
    test: list[str] = []
    for row in rows:
        row_id = str(row.get("row_id") or "")
        if _hash_bucket(row_id) < test_ratio:
            test.append(row_id)
        else:
            train.append(row_id)
    return sorted(train), sorted(test)


# ── Baseline learning + classification ──────────────────────────────────────────

def _learn_baseline(train: list[dict[str, Any]]) -> dict[str, Any]:
    """Learn a single-rule (OneR) baseline with a majority-class fallback.

    Returns a plain-dict model: the global majority label, the best single feature
    (when it strictly beats the majority on the training rows) and its per-value label
    map, plus the chosen ``baseline_kind``.
    """
    labels = [ex["label"] for ex in train]
    majority = _majority_label(labels)
    total = len(train)
    majority_correct = sum(1 for ex in train if ex["label"] == majority)

    best_feature = ""
    best_correct = majority_correct
    best_value_map: dict[str, str] = {}
    best_value_conf: dict[str, float] = {}

    for name in FEATURE_NAMES:
        by_value: dict[str, list[str]] = {}
        for ex in train:
            by_value.setdefault(ex["features"].get(name, ""), []).append(ex["label"])
        value_map: dict[str, str] = {}
        value_conf: dict[str, float] = {}
        correct = 0
        for value, value_labels in by_value.items():
            local_majority = _majority_label(value_labels)
            value_map[value] = local_majority
            value_conf[value] = _safe_div(
                sum(1 for lbl in value_labels if lbl == local_majority), len(value_labels)
            )
            correct += sum(1 for lbl in value_labels if lbl == local_majority)
        if correct > best_correct:
            best_correct = correct
            best_feature = name
            best_value_map = value_map
            best_value_conf = value_conf

    baseline_kind = BASELINE_ONE_RULE if best_feature else BASELINE_MAJORITY
    return {
        "baseline_kind": baseline_kind,
        "majority_label": majority,
        "majority_confidence": _safe_div(majority_correct, total),
        "chosen_feature": best_feature,
        "value_map": best_value_map,
        "value_confidence": best_value_conf,
    }


def _classify(model: dict[str, Any], example: dict[str, Any]) -> dict[str, Any]:
    """Apply the learned baseline to one example (advisory only)."""
    feature = model.get("chosen_feature") or ""
    if feature:
        value = example["features"].get(feature, "")
        if value in model["value_map"]:
            return {
                "predicted_label": model["value_map"][value],
                "confidence": round(float(model["value_confidence"].get(value, 0.0)), 6),
                "prediction_source": f"rule:{feature}",
                "features_used": [feature],
            }
        return {
            "predicted_label": model["majority_label"],
            "confidence": round(float(model["majority_confidence"]), 6),
            "prediction_source": "rule_fallback_majority",
            "features_used": [feature],
        }
    return {
        "predicted_label": model["majority_label"],
        "confidence": round(float(model["majority_confidence"]), 6),
        "prediction_source": BASELINE_MAJORITY,
        "features_used": [],
    }


# ── Metrics ──────────────────────────────────────────────────────────────────

def _confusion_matrix(predictions: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for pred in predictions:
        row = matrix.setdefault(pred["true_label"], {})
        row[pred["predicted_label"]] = row.get(pred["predicted_label"], 0) + 1
    return matrix


def _metrics(predictions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not predictions:
        return None
    total = len(predictions)
    correct = sum(1 for pred in predictions if pred["correct"])
    classes = sorted(
        {pred["true_label"] for pred in predictions} | {pred["predicted_label"] for pred in predictions}
    )
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    for cls in classes:
        tp = sum(1 for p in predictions if p["true_label"] == cls and p["predicted_label"] == cls)
        fp = sum(1 for p in predictions if p["true_label"] != cls and p["predicted_label"] == cls)
        fn = sum(1 for p in predictions if p["true_label"] == cls and p["predicted_label"] != cls)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
    n_classes = len(classes)
    return {
        "accuracy": round(_safe_div(correct, total), 6),
        "correct": correct,
        "total": total,
        "macro_precision": round(_safe_div(sum(precisions), n_classes), 6),
        "macro_recall": round(_safe_div(sum(recalls), n_classes), 6),
        "macro_f1": round(_safe_div(sum(f1s), n_classes), 6),
    }


# ── Result assembly ─────────────────────────────────────────────────────────────

def build_baseline_result(
    rows: Any,
    *,
    target_field: str = DEFAULT_TARGET_FIELD,
    test_ratio: float = 0.3,
    limit: Any = None,
) -> dict[str, Any]:
    """Build the deterministic baseline evaluation from already-parsed dataset rows.

    Pure: never mutates ``rows``. Returns a result dict with the chosen target field,
    train/test counts, target distribution, learned baseline, metrics (or ``None``),
    confusion matrix, the full prediction list, warnings, and blockers.
    """
    row_list = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    if isinstance(limit, int) and limit >= 0:
        row_list = sorted(row_list, key=lambda r: str(r.get("row_id") or ""))[:limit]

    warnings: list[str] = []
    blockers: list[str] = []

    chosen_field, was_fallback = _select_target_field(row_list, target_field)
    if was_fallback:
        warnings.append(
            f"primary target field '{target_field}' had fewer than 2 classes; "
            f"using fallback target field '{chosen_field}'"
        )

    examples, dropped = _extract_examples(row_list, chosen_field)
    if dropped:
        warnings.append(f"{dropped} row(s) had no '{chosen_field}' value and were dropped")

    target_distribution = _counts([ex["label"] for ex in examples])

    if not examples:
        blockers.append("insufficient_data: no rows have a usable target label")
        return _empty_result(row_list, chosen_field, was_fallback, target_distribution, warnings, blockers)

    if len(target_distribution) < 2:
        blockers.append(
            f"insufficient_class_diversity: only {len(target_distribution)} distinct target class"
        )

    # ── Deterministic split with safe fallbacks for tiny datasets ──────────────
    ratio = min(1.0, max(0.0, float(test_ratio)))
    train_ids, test_ids = deterministic_split(examples, ratio)
    train_set, test_set = set(train_ids), set(test_ids)
    train_examples = [ex for ex in examples if ex["row_id"] in train_set]
    test_examples = [ex for ex in examples if ex["row_id"] in test_set]

    if not train_examples:
        warnings.append("no training rows after split; learning the baseline on all rows")
        train_examples = list(examples)
    if not test_examples:
        warnings.append("no test rows after split; evaluating the baseline in-sample")
        test_examples = list(examples)

    model = _learn_baseline(train_examples)

    predictions: list[dict[str, Any]] = []
    for example in sorted(test_examples, key=lambda ex: ex["row_id"]):
        outcome = _classify(model, example)
        predictions.append(
            {
                "row_id": example["row_id"],
                "artifact_kind": example["artifact_kind"],
                "true_label": example["label"],
                "predicted_label": outcome["predicted_label"],
                "confidence": outcome["confidence"],
                "prediction_source": outcome["prediction_source"],
                "correct": example["label"] == outcome["predicted_label"],
                "features_used": outcome["features_used"],
                "authority": "advisory_only",
            }
        )

    return {
        "row_count": len(row_list),
        "examples_count": len(examples),
        "train_count": len(train_examples),
        "test_count": len(test_examples),
        "target_field": chosen_field,
        "target_field_was_fallback": was_fallback,
        "target_distribution": target_distribution,
        "baseline_kind": model["baseline_kind"],
        "majority_label": model["majority_label"],
        "chosen_feature": model["chosen_feature"],
        "metrics": _metrics(predictions),
        "confusion_matrix": _confusion_matrix(predictions),
        "predictions": predictions,
        "warnings": warnings,
        "blockers": blockers,
    }


def _empty_result(
    row_list: list[dict[str, Any]],
    chosen_field: str,
    was_fallback: bool,
    target_distribution: dict[str, int],
    warnings: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "row_count": len(row_list),
        "examples_count": 0,
        "train_count": 0,
        "test_count": 0,
        "target_field": chosen_field,
        "target_field_was_fallback": was_fallback,
        "target_distribution": target_distribution,
        "baseline_kind": BASELINE_MAJORITY,
        "majority_label": "",
        "chosen_feature": "",
        "metrics": None,
        "confusion_matrix": {},
        "predictions": [],
        "warnings": warnings,
        "blockers": blockers,
    }


# ── Report assembly ─────────────────────────────────────────────────────────────

def _guardrails() -> dict[str, bool]:
    """This tool performs none of these actions."""
    return {
        "live_routing_performed": False,
        "driver_override_performed": False,
        "model_api_call_performed": False,
        "llm_call_performed": False,
        "embedding_call_performed": False,
        "training_requires_external_model": False,
        "database_write_performed": False,
        "network_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


def build_report(
    result: dict[str, Any],
    *,
    report_id: str = "",
    created_at: str = "",
    dataset_path: str = "",
    output_dir: str = "",
    predictions_path: str = "",
    preview_size: int = 10,
) -> dict[str, Any]:
    """Assemble the spec report record from a baseline result."""
    predictions = result.get("predictions") or []
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": DRIVER_CLASSIFIER_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "dataset_path": _norm_path(dataset_path) if dataset_path else "",
        "output_dir": _norm_path(output_dir) if output_dir else "",
        "predictions_path": _norm_path(predictions_path) if predictions_path else "",
        "row_count": result.get("row_count", 0),
        "train_count": result.get("train_count", 0),
        "test_count": result.get("test_count", 0),
        "target_field": result.get("target_field", DEFAULT_TARGET_FIELD),
        "target_field_was_fallback": result.get("target_field_was_fallback", False),
        "target_distribution": dict(result.get("target_distribution") or {}),
        "feature_schema": list(FEATURE_NAMES),
        "baseline_kind": result.get("baseline_kind", BASELINE_MAJORITY),
        "majority_label": result.get("majority_label", ""),
        "chosen_feature": result.get("chosen_feature", ""),
        "metrics": result.get("metrics"),
        "confusion_matrix": dict(result.get("confusion_matrix") or {}),
        "prediction_preview": [dict(p) for p in predictions[:preview_size]],
        "warnings": list(result.get("warnings") or []),
        "blockers": list(result.get("blockers") or []),
        "guardrails": _guardrails(),
    }


# ── Markdown rendering ──────────────────────────────────────────────────────────

def render_driver_classifier_baseline_markdown(report: dict[str, Any]) -> str:
    """Render the baseline report as one operator-readable Markdown document."""
    metrics = report.get("metrics")
    lines: list[str] = [
        "# Driver Classifier Baseline Report",
        "",
        f"> {report.get('guardrail_note', DRIVER_CLASSIFIER_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.2 learns a small offline, pure-stdlib baseline over the MODEL.1 "
        "dataset and reports advisory predictions. It changes no routing and grants no "
        "execution authority._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Baseline:** `{_md(report.get('baseline_kind'))}`",
        f"- **Majority label:** `{_md(report.get('majority_label') or '(none)')}`",
        f"- **Chosen feature:** `{_md(report.get('chosen_feature') or '(none)')}`",
        "",
        "## Dataset",
        "",
        f"- **Dataset path:** `{_md(report.get('dataset_path') or '(none)')}`",
        f"- **Row count:** {report.get('row_count', 0)}",
        f"- **Train count:** {report.get('train_count', 0)}",
        f"- **Test count:** {report.get('test_count', 0)}",
        f"- **Target field:** `{_md(report.get('target_field'))}`"
        + (" _(fallback)_" if report.get("target_field_was_fallback") else ""),
        "",
    ]

    # Target distribution
    lines += ["## Target Distribution", ""]
    distribution = report.get("target_distribution") or {}
    if distribution:
        lines += ["| Label | Count |", "| --- | --- |"]
        for label in sorted(distribution):
            lines.append(f"| `{_md(label)}` | {distribution[label]} |")
    else:
        lines.append("_None — no labeled rows._")
    lines.append("")

    # Feature schema
    lines += ["## Feature Schema", ""]
    for name in report.get("feature_schema") or []:
        lines.append(f"- `{_md(name)}`")
    lines.append("")

    # Baseline
    lines += ["## Baseline", ""]
    lines.append(f"- **Kind:** `{_md(report.get('baseline_kind'))}`")
    lines.append(f"- **Majority label:** `{_md(report.get('majority_label') or '(none)')}`")
    lines.append(f"- **Chosen feature:** `{_md(report.get('chosen_feature') or '(none)')}`")
    lines.append("")

    # Metrics
    lines += ["## Metrics", ""]
    if isinstance(metrics, dict):
        for key in ("accuracy", "correct", "total", "macro_precision", "macro_recall", "macro_f1"):
            lines.append(f"- **{key}:** {metrics.get(key)}")
    else:
        lines.append("_Unavailable — see blockers below._")
    lines.append("")

    # Confusion matrix
    lines += ["## Confusion Matrix", ""]
    matrix = report.get("confusion_matrix") or {}
    if matrix:
        pred_labels = sorted({p for row in matrix.values() for p in row})
        header = "| true \\\\ pred | " + " | ".join(f"`{_md(p)}`" for p in pred_labels) + " |"
        lines.append(header)
        lines.append("| --- | " + " | ".join("---" for _ in pred_labels) + " |")
        for true_label in sorted(matrix):
            cells = " | ".join(str(matrix[true_label].get(p, 0)) for p in pred_labels)
            lines.append(f"| `{_md(true_label)}` | {cells} |")
    else:
        lines.append("_None — no predictions were made._")
    lines.append("")

    # Prediction preview
    lines += ["## Prediction Preview", ""]
    preview = report.get("prediction_preview") or []
    if preview:
        lines += [
            "| Row id | Kind | True | Predicted | Confidence | Source | Correct |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for pred in preview:
            lines.append(
                f"| `{_md(pred.get('row_id'))}` | {_md(pred.get('artifact_kind'))} | "
                f"{_md(pred.get('true_label'))} | {_md(pred.get('predicted_label'))} | "
                f"{_md(pred.get('confidence'))} | {_md(pred.get('prediction_source'))} | "
                f"{str(bool(pred.get('correct'))).lower()} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Blockers
    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None — the baseline evaluated cleanly._")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- MODEL.2 does not route live tasks.",
        "- MODEL.2 does not override the deterministic Driver.",
        "- MODEL.2 does not call model APIs.",
        "- MODEL.2 does not call LLMs.",
        "- MODEL.2 does not call embeddings.",
        "- MODEL.2 does not write to databases.",
        "- MODEL.2 does not apply patches.",
        "- MODEL.2 does not run validation or benchmarks.",
        "- MODEL.2 does not launch workers.",
        "- MODEL.2 predictions are advisory only and grant no execution authority.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Writing ──────────────────────────────────────────────────────────────────

def _render_predictions_jsonl(predictions: list[dict[str, Any]]) -> str:
    if not predictions:
        return ""
    lines = [json.dumps(pred, ensure_ascii=False, sort_keys=True) for pred in predictions]
    return "\n".join(lines) + "\n"


def write_driver_classifier_baseline(
    dataset_path: str | Path,
    output_dir: str | Path,
    *,
    target_field: str = DEFAULT_TARGET_FIELD,
    test_ratio: float = 0.3,
    report_id: str = "",
    created_at: str = "",
    limit: Any = None,
) -> dict[str, Any]:
    """Read the dataset, learn the baseline, and write JSON + Markdown + predictions.

    Returns ``{ok, json_path, md_path, predictions_path, report, result}``. The source
    dataset is read only; nothing outside ``output_dir`` is written.
    """
    loaded = load_dataset(dataset_path)
    result = build_baseline_result(loaded["rows"], target_field=target_field, test_ratio=test_ratio, limit=limit)
    result["warnings"] = list(loaded["warnings"]) + list(result["warnings"])
    if not loaded["present"]:
        result["blockers"] = [f"dataset not found at {_norm_path(dataset_path)}"] + list(result["blockers"])

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / REPORT_JSON_NAME
    md_path = out_dir / REPORT_MD_NAME
    predictions_path = out_dir / PREDICTIONS_NAME

    report = build_report(
        result,
        report_id=report_id,
        created_at=created_at,
        dataset_path=str(dataset_path),
        output_dir=str(out_dir),
        predictions_path=str(predictions_path),
    )

    predictions_path.write_text(_render_predictions_jsonl(result["predictions"]), encoding="utf-8")
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_driver_classifier_baseline_markdown(report), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "predictions_path": str(predictions_path),
        "report": report,
        "result": result,
    }
