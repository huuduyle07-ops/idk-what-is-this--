"""Tests for MODEL.2 — Driver Classifier Baseline (report-only).

MODEL.2 consumes the MODEL.1 JSONL artifact dataset and builds a small offline
baseline classifier/evaluator. It may train and evaluate a pure-stdlib baseline and
produce advisory predictions in a report. It must not route live tasks, override the
deterministic Driver, call model APIs / LLMs / embeddings, write to a database, run
validation or benchmarks, launch workers, or merge. Predictions are advisory only
and grant no execution authority.

Covers the prescribed cases:
1.  missing dataset writes a blocked deterministic report, not a crash.
2.  a malformed JSONL row is skipped with a warning.
3.  an empty dataset produces an insufficient-data blocker.
4.  a single-class dataset produces a majority baseline report.
5.  a multi-class dataset produces metrics and a confusion matrix.
6.  the train/test split is deterministic.
7.  target-field selection works.
8.  fallback target selection works.
9.  prediction rows include advisory_only authority.
10. confidence is deterministic and bounded 0 to 1.
11. metrics are correct on a small known fixture.
12. macro precision / recall / F1 handle zero divisions safely.
13. predictions JSONL is deterministic with a fixed report_id / created_at.
14. the report counts the target distribution correctly.
15. the feature schema contains the expected feature names.
16. Markdown contains all required sections and boundaries.
17. CLI writes JSON + Markdown + predictions JSONL.
18. CLI --json prints summary JSON.
19. the source dataset is not modified.
20. source contains no forbidden live-routing / model-api / LLM / embedding / network /
    patch / validation / benchmark / worker / DB / merge behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.driver_classifier_baseline import (
    DRIVER_CLASSIFIER_GUARDRAIL_NOTE,
    FALLBACK_TARGET_FIELDS,
    FEATURE_NAMES,
    PREDICTIONS_NAME,
    REPORT_JSON_NAME,
    REPORT_KIND,
    REPORT_MD_NAME,
    build_baseline_result,
    build_report,
    deterministic_split,
    load_dataset,
    render_driver_classifier_baseline_markdown,
    write_driver_classifier_baseline,
)
import scripts.run_driver_classifier_baseline as script


# ── synthetic MODEL.1-shaped row builder ───────────────────────────────────────

def _row(
    row_id="r1",
    artifact_kind="goal_brief",
    target_label="prepare_worker_assignment",
    dataset_task="routing_or_policy_learning",
    risk_level="low",
    automation_level="local",
    final_verdict="",
    recommended_vehicle="",
    recommended_next_step="",
    has_remote_component=False,
    has_patch_candidate=False,
    has_visual_issue=False,
    has_human_gate=True,
    **over,
):
    row = {
        "row_id": row_id,
        "artifact_kind": artifact_kind,
        "artifact_path": f".agent/x/{row_id}.json",
        "created_at": "t",
        "source_id": row_id,
        "task_title": "",
        "task_summary": "",
        "mode": "",
        "risk_level": risk_level,
        "automation_level": automation_level,
        "human_approval_required": has_human_gate,
        "allowed_actions": [],
        "blocked_actions": [],
        "labels": {
            "recommended_vehicle": recommended_vehicle,
            "final_verdict": final_verdict,
            "recommended_next_step": recommended_next_step,
        },
        "features": {
            "has_validation": False,
            "has_visual_issue": has_visual_issue,
            "has_security_sensitive_claim": False,
            "has_remote_component": has_remote_component,
            "has_patch_candidate": has_patch_candidate,
            "has_human_gate": has_human_gate,
        },
        "target": {
            "dataset_task": dataset_task,
            "target_label": target_label,
            "authority": "advisory_only",
        },
        "quality": {"parse_status": "ok", "missing_fields": [], "warnings": []},
    }
    row.update(over)
    return row


def _write_dataset(path: Path, rows) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    return path


def _multi_class_rows(n_each: int = 4):
    rows = []
    for i in range(n_each):
        rows.append(_row(row_id=f"a{i}", artifact_kind="goal_brief", target_label="alpha"))
        rows.append(_row(row_id=f"b{i}", artifact_kind="driver_decision", target_label="beta"))
        rows.append(_row(row_id=f"c{i}", artifact_kind="telegram_evidence_contract", target_label="gamma",
                         has_remote_component=True))
    return rows


# ── 1. missing dataset → blocked deterministic report ──────────────────────────

def test_missing_dataset_writes_blocked_report(tmp_path):
    out = tmp_path / "out"
    result = write_driver_classifier_baseline(
        str(tmp_path / "nope.jsonl"), str(out), report_id="r", created_at="t"
    )
    assert result["ok"] is True
    report = result["report"]
    assert report["row_count"] == 0
    assert report["metrics"] is None
    assert report["blockers"]
    assert any("not found" in b.lower() or "dataset" in b.lower() for b in report["blockers"])
    assert (out / REPORT_JSON_NAME).is_file()
    assert (out / REPORT_MD_NAME).is_file()
    assert (out / PREDICTIONS_NAME).is_file()


# ── 2. malformed JSONL row skipped with warning ────────────────────────────────

def test_malformed_jsonl_row_is_skipped_with_warning(tmp_path):
    path = tmp_path / "ds.jsonl"
    good = json.dumps(_row(row_id="r1", target_label="alpha"), sort_keys=True)
    path.write_text(good + "\n{ this is not valid json\n" + json.dumps(_row(row_id="r2", target_label="beta")) + "\n", encoding="utf-8")
    loaded = load_dataset(str(path))
    assert len(loaded["rows"]) == 2
    assert loaded["skipped"] == 1
    assert loaded["warnings"]


def test_non_object_jsonl_row_is_skipped(tmp_path):
    path = tmp_path / "ds.jsonl"
    path.write_text(json.dumps(_row()) + "\n[1, 2, 3]\n", encoding="utf-8")
    loaded = load_dataset(str(path))
    assert len(loaded["rows"]) == 1
    assert loaded["skipped"] == 1


# ── 3. empty dataset → insufficient-data blocker ───────────────────────────────

def test_empty_dataset_produces_insufficient_data_blocker(tmp_path):
    path = _write_dataset(tmp_path / "ds.jsonl", [])
    result = write_driver_classifier_baseline(str(path), str(tmp_path / "out"), report_id="r", created_at="t")
    report = result["report"]
    assert report["row_count"] == 0
    assert report["metrics"] is None
    assert any("insufficient" in b.lower() or "no rows" in b.lower() or "empty" in b.lower() for b in report["blockers"])


# ── 4. single-class dataset → majority baseline report ─────────────────────────

def test_single_class_dataset_produces_majority_baseline():
    rows = [_row(row_id=f"r{i}", target_label="solo") for i in range(5)]
    result = build_baseline_result(rows, target_field="target.target_label", test_ratio=0.3)
    assert result["baseline_kind"] == "majority_class"
    assert result["majority_label"] == "solo"
    assert result["metrics"] is not None
    assert any("insufficient_class_diversity" in b for b in result["blockers"])


# ── 5. multi-class dataset → metrics + confusion matrix ────────────────────────

def test_multi_class_dataset_produces_metrics_and_confusion_matrix():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    metrics = result["metrics"]
    assert metrics is not None
    for key in ("accuracy", "correct", "total", "macro_precision", "macro_recall", "macro_f1"):
        assert key in metrics, key
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert result["confusion_matrix"]


# ── 6. deterministic train/test split ──────────────────────────────────────────

def test_train_test_split_is_deterministic():
    rows = _multi_class_rows()
    a_train, a_test = deterministic_split(rows, test_ratio=0.3)
    b_train, b_test = deterministic_split(rows, test_ratio=0.3)
    assert a_train == b_train
    assert a_test == b_test
    assert set(a_train) | set(a_test) == {r["row_id"] for r in rows}
    assert not (set(a_train) & set(a_test))


# ── 7. target-field selection ──────────────────────────────────────────────────

def test_target_field_selection_uses_requested_field():
    rows = [
        _row(row_id="r1", artifact_kind="goal_brief", target_label="same"),
        _row(row_id="r2", artifact_kind="driver_decision", target_label="same"),
    ]
    result = build_baseline_result(rows, target_field="artifact_kind", test_ratio=0.3)
    assert result["target_field"] == "artifact_kind"
    assert result["target_field_was_fallback"] is False
    assert set(result["target_distribution"]) == {"goal_brief", "driver_decision"}


# ── 8. fallback target selection ───────────────────────────────────────────────

def test_fallback_target_selection_when_primary_is_single_class():
    rows = [
        _row(row_id="r1", target_label="same", recommended_next_step="step_a"),
        _row(row_id="r2", target_label="same", recommended_next_step="step_b"),
    ]
    result = build_baseline_result(rows, target_field="target.target_label", test_ratio=0.3)
    assert result["target_field"] == "labels.recommended_next_step"
    assert result["target_field_was_fallback"] is True
    assert any("fall" in w.lower() for w in result["warnings"])


# ── 9. predictions carry advisory_only authority ───────────────────────────────

def test_predictions_carry_advisory_only_authority():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    assert result["predictions"]
    for pred in result["predictions"]:
        assert pred["authority"] == "advisory_only"
        for key in ("row_id", "artifact_kind", "true_label", "predicted_label", "confidence", "prediction_source", "correct", "features_used"):
            assert key in pred, key


# ── 10. confidence deterministic + bounded [0, 1] ──────────────────────────────

def test_confidence_is_deterministic_and_bounded():
    rows = _multi_class_rows()
    r1 = build_baseline_result(rows, target_field="target.target_label", test_ratio=0.3)
    r2 = build_baseline_result(rows, target_field="target.target_label", test_ratio=0.3)
    conf1 = [p["confidence"] for p in r1["predictions"]]
    conf2 = [p["confidence"] for p in r2["predictions"]]
    assert conf1 == conf2
    for c in conf1:
        assert 0.0 <= c <= 1.0


# ── 11. metrics correct on a small known majority fixture ──────────────────────

def test_metrics_correct_on_known_majority_fixture():
    # 4 rows, identical features, labels alpha/alpha/beta/gamma -> majority "alpha".
    # test_ratio=1.0 means every row is in test; with no train rows the baseline
    # falls back to learning on all rows, so this is a deterministic in-sample eval.
    rows = [
        _row(row_id="r1", target_label="alpha"),
        _row(row_id="r2", target_label="alpha"),
        _row(row_id="r3", target_label="beta"),
        _row(row_id="r4", target_label="gamma"),
    ]
    result = build_baseline_result(rows, target_field="target.target_label", test_ratio=1.0)
    assert result["baseline_kind"] == "majority_class"
    assert result["majority_label"] == "alpha"
    metrics = result["metrics"]
    assert metrics["total"] == 4
    assert metrics["correct"] == 2
    assert metrics["accuracy"] == 0.5
    assert round(metrics["macro_precision"], 4) == 0.1667
    assert round(metrics["macro_recall"], 4) == 0.3333
    assert round(metrics["macro_f1"], 4) == 0.2222
    cm = result["confusion_matrix"]
    assert cm["alpha"]["alpha"] == 2
    assert cm["beta"]["alpha"] == 1
    assert cm["gamma"]["alpha"] == 1


def test_one_rule_baseline_uses_predictive_feature():
    # artifact_kind perfectly separates the labels, so the OneR baseline beats majority.
    rows = [
        _row(row_id="r1", artifact_kind="goal_brief", target_label="alpha"),
        _row(row_id="r2", artifact_kind="goal_brief", target_label="alpha"),
        _row(row_id="r3", artifact_kind="driver_decision", target_label="beta"),
        _row(row_id="r4", artifact_kind="driver_decision", target_label="beta"),
    ]
    result = build_baseline_result(rows, target_field="target.target_label", test_ratio=1.0)
    assert result["baseline_kind"] == "one_rule"
    assert result["chosen_feature"] == "artifact_kind"
    assert result["metrics"]["accuracy"] == 1.0
    for pred in result["predictions"]:
        assert pred["correct"] is True
        assert pred["confidence"] == 1.0
        assert pred["prediction_source"].startswith("rule:")
        assert pred["features_used"] == ["artifact_kind"]


# ── 12. macro metrics handle zero division safely ──────────────────────────────

def test_macro_metrics_handle_zero_division():
    # beta / gamma are never predicted -> their precision is 0/0; must not raise.
    rows = [
        _row(row_id="r1", target_label="alpha"),
        _row(row_id="r2", target_label="alpha"),
        _row(row_id="r3", target_label="beta"),
        _row(row_id="r4", target_label="gamma"),
    ]
    result = build_baseline_result(rows, target_field="target.target_label", test_ratio=1.0)
    metrics = result["metrics"]
    for key in ("macro_precision", "macro_recall", "macro_f1"):
        assert isinstance(metrics[key], float)
        assert 0.0 <= metrics[key] <= 1.0


# ── 13. predictions JSONL deterministic ────────────────────────────────────────

def test_predictions_jsonl_is_deterministic(tmp_path):
    path = _write_dataset(tmp_path / "ds.jsonl", _multi_class_rows())

    def run(name: str) -> str:
        res = write_driver_classifier_baseline(
            str(path), str(tmp_path / name), report_id="fixed", created_at="2026-06-20T00:00:00+00:00"
        )
        return Path(res["predictions_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


# ── 14. target distribution counts ─────────────────────────────────────────────

def test_target_distribution_counts_are_correct():
    rows = [
        _row(row_id="r1", target_label="alpha"),
        _row(row_id="r2", target_label="alpha"),
        _row(row_id="r3", target_label="beta"),
    ]
    result = build_baseline_result(rows, target_field="target.target_label", test_ratio=0.3)
    assert result["target_distribution"] == {"alpha": 2, "beta": 1}


# ── 15. feature schema names ───────────────────────────────────────────────────

def test_feature_schema_contains_expected_names():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    report = build_report(result, report_id="r", created_at="t", dataset_path="d.jsonl", output_dir="o", predictions_path="p.jsonl")
    schema = report["feature_schema"]
    for name in (
        "artifact_kind",
        "dataset_task",
        "risk_level",
        "automation_level",
        "has_remote_component",
        "has_patch_candidate",
        "has_visual_issue",
        "has_human_gate",
        "final_verdict",
        "recommended_vehicle",
    ):
        assert name in schema, name
    assert set(FEATURE_NAMES) <= set(schema) or set(schema) == set(FEATURE_NAMES)


# ── 16. Markdown sections + boundaries ─────────────────────────────────────────

def test_markdown_contains_all_sections():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    report = build_report(result, report_id="r", created_at="t", dataset_path="d.jsonl", output_dir="o", predictions_path="p.jsonl")
    md = render_driver_classifier_baseline_markdown(report)
    assert "# Driver Classifier Baseline Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## dataset",
        "## target distribution",
        "## feature schema",
        "## baseline",
        "## metrics",
        "## confusion matrix",
        "## prediction preview",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    report = build_report(result, report_id="r", created_at="t", dataset_path="d.jsonl", output_dir="o", predictions_path="p.jsonl")
    low = render_driver_classifier_baseline_markdown(report).lower()
    assert "does not route live tasks" in low
    assert "does not override the deterministic driver" in low
    assert "does not call model apis" in low
    assert "does not call llms" in low
    assert "does not call embeddings" in low
    assert "does not write to databases" in low
    assert "does not apply patches" in low
    assert "does not run validation or benchmarks" in low
    assert "does not launch workers" in low
    assert "advisory only" in low
    assert "no execution authority" in low


def test_guardrail_note_is_report_only():
    assert "report-only" in DRIVER_CLASSIFIER_GUARDRAIL_NOTE.lower()


def test_guardrails_all_false():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    report = build_report(result, report_id="r", created_at="t", dataset_path="d.jsonl", output_dir="o", predictions_path="p.jsonl")
    guardrails = report["guardrails"]
    for key in (
        "live_routing_performed",
        "driver_override_performed",
        "model_api_call_performed",
        "llm_call_performed",
        "embedding_call_performed",
        "training_requires_external_model",
        "database_write_performed",
        "network_call_performed",
        "patch_applied",
        "validation_run",
        "benchmark_run",
        "worker_launch_performed",
        "merge_performed",
    ):
        assert guardrails[key] is False, key


def test_report_has_all_required_fields():
    result = build_baseline_result(_multi_class_rows(), target_field="target.target_label", test_ratio=0.3)
    report = build_report(result, report_id="rid", created_at="2026-06-20", dataset_path="d.jsonl", output_dir="o", predictions_path="p.jsonl")
    for key in (
        "report_id",
        "created_at",
        "dataset_path",
        "output_dir",
        "row_count",
        "train_count",
        "test_count",
        "target_field",
        "target_distribution",
        "feature_schema",
        "baseline_kind",
        "majority_label",
        "metrics",
        "confusion_matrix",
        "prediction_preview",
        "warnings",
        "blockers",
        "guardrails",
    ):
        assert key in report, key
    assert report["report_id"] == "rid"
    assert report["report_kind"] == REPORT_KIND


# ── 17-18. CLI ─────────────────────────────────────────────────────────────────

def test_cli_writes_json_markdown_and_predictions(tmp_path):
    path = _write_dataset(tmp_path / "ds.jsonl", _multi_class_rows())
    out = tmp_path / "out"
    res = script.run_driver_classifier_baseline(
        dataset_path=str(path), output_root=str(out), report_id="cli", created_at="2026-06-20T00:00:00+00:00"
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).name == REPORT_JSON_NAME
    assert Path(res["md_path"]).name == REPORT_MD_NAME
    assert Path(res["predictions_path"]).name == PREDICTIONS_NAME
    assert (out / REPORT_JSON_NAME).is_file()
    assert (out / REPORT_MD_NAME).is_file()
    assert (out / PREDICTIONS_NAME).is_file()
    report = json.loads((out / REPORT_JSON_NAME).read_text(encoding="utf-8"))
    assert report["report_id"] == "cli"


def test_cli_main_smoke(tmp_path):
    path = _write_dataset(tmp_path / "ds.jsonl", _multi_class_rows())
    out = tmp_path / "out"
    code = script.main(
        ["--dataset-path", str(path), "--output-root", str(out), "--report-id", "s", "--created-at", "t"]
    )
    assert code == 0
    assert (out / REPORT_JSON_NAME).is_file()
    assert (out / PREDICTIONS_NAME).is_file()


def test_cli_json_flag_prints_summary(tmp_path, capsys):
    path = _write_dataset(tmp_path / "ds.jsonl", _multi_class_rows())
    out = tmp_path / "out"
    code = script.main(
        ["--dataset-path", str(path), "--output-root", str(out), "--report-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "j"
    assert printed["report_kind"] == REPORT_KIND


def test_cli_target_field_and_test_ratio(tmp_path):
    path = _write_dataset(tmp_path / "ds.jsonl", _multi_class_rows())
    out = tmp_path / "out"
    code = script.main(
        [
            "--dataset-path", str(path),
            "--output-root", str(out),
            "--report-id", "x",
            "--created-at", "t",
            "--target-field", "artifact_kind",
            "--test-ratio", "0.5",
        ]
    )
    assert code == 0
    report = json.loads((out / REPORT_JSON_NAME).read_text(encoding="utf-8"))
    assert report["target_field"] == "artifact_kind"


def test_cli_missing_dataset_is_not_a_crash(tmp_path):
    out = tmp_path / "out"
    code = script.main(["--dataset-path", str(tmp_path / "nope.jsonl"), "--output-root", str(out), "--report-id", "x", "--created-at", "t"])
    assert code == 0
    report = json.loads((out / REPORT_JSON_NAME).read_text(encoding="utf-8"))
    assert report["row_count"] == 0
    assert report["blockers"]


# ── 19. source dataset is not modified ─────────────────────────────────────────

def test_source_dataset_is_not_modified(tmp_path):
    path = _write_dataset(tmp_path / "ds.jsonl", _multi_class_rows())
    before = path.read_bytes()
    write_driver_classifier_baseline(str(path), str(tmp_path / "out"), report_id="r", created_at="t")
    assert path.read_bytes() == before


# ── constants ───────────────────────────────────────────────────────────────────

def test_fallback_target_fields_constant():
    assert FALLBACK_TARGET_FIELDS[0] == "target.target_label"
    assert "labels.recommended_next_step" in FALLBACK_TARGET_FIELDS
    assert "labels.final_verdict" in FALLBACK_TARGET_FIELDS
    assert "artifact_kind" in FALLBACK_TARGET_FIELDS
    assert "target.dataset_task" in FALLBACK_TARGET_FIELDS


# ── 20. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "driver_classifier_baseline.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "run_driver_classifier_baseline.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "json", "pathlib", "typing", "hashlib"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            assert top != "core", f"MODEL.2 core must not import other core modules: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_model_clients_or_training():
    # Bare "model"/"classifier"/"train"/"predict" are required domain words; only the
    # client / library inference / fit shapes are forbidden.
    for bad in (
        "anthropic",
        "openai",
        "litellm",
        "ollama",
        "bedrock",
        "generativeai",
        "claude",
        "codex",
        "gemini",
        "deepseek",
        "sklearn",
        "tensorflow",
        "lightgbm",
        "xgboost",
        "joblib",
        "call_model(",
        "llm_call(",
        ".fit(",
        ".predict(",
        ".train(",
        "model.predict(",
        "model.fit(",
    ):
        assert bad not in _BOTH, f"Found model client/training token {bad!r}"


def test_no_embedding_calls():
    for bad in (
        "embed_query(",
        "embed_documents(",
        "embeddings.create",
        "OpenAIEmbeddings",
        "SentenceTransformer",
        "embedding_model(",
        "get_embedding(",
    ):
        assert bad not in _BOTH, f"Found embedding token {bad!r}"


def test_no_live_routing_or_driver_override():
    for bad in (
        "route_live(",
        "live_route(",
        "perform_routing(",
        "router.route(",
        "override_driver(",
        "driver.override(",
        "perform_driver_override(",
        "apply_route(",
    ):
        assert bad not in _BOTH, f"Found live-routing / Driver-override token {bad!r}"


def test_no_database_writes():
    for bad in (
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "pymongo",
        "chromadb",
        "pinecone",
        "qdrant",
        "weaviate",
        "faiss",
        "INSERT INTO",
        "conn.execute(",
        "cursor.execute(",
        "session.add(",
    ):
        assert bad not in _BOTH, f"Found database token {bad!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "check_output", "check_call", "shutil", "copytree", "os.popen"):
        assert bad not in _BOTH, f"Found execution primitive token {bad!r}"


def test_no_validation_or_benchmark_execution():
    for bad in (
        "run_safe_validation",
        "SafeValidationCommand",
        "validation_execution",
        "run_benchmarks",
        "create_managed_sandbox",
        "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found validation/benchmark execution token {bad!r}"


def test_no_patch_generation_or_apply():
    for bad in ("generate_patch", "apply_patch", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_network_remote_send_or_git_behaviour():
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "n8n.cloud",
        "execute_workflow(",
        "api.telegram.org",
        "sendMessage",
        "send_message(",
        "bot_token",
        "api.github.com",
        "PyGithub",
        "from github",
        "import github",
        "gh pr",
        "git push",
        "git checkout",
        "git commit",
        "git merge",
        "git clone",
    ):
        assert bad not in _BOTH, f"Found network/remote/git token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "launch_worker(", "worker_launch(", "spawn_worker", "run_worker("):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_auto_merge_execution():
    for bad in ("auto_merge(", "perform_merge", "perform_auto_merge", "merge_to_real", "git_merge"):
        assert bad not in _BOTH, f"Found auto-merge token {bad!r}"
