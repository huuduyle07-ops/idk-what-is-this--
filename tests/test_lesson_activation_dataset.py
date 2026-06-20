"""Tests for MODEL.3 - Lesson Graph Activation Dataset (report-only).

MODEL.3 reads the MODEL.1 artifact dataset plus lesson / anti-lesson candidates
and emits advisory activation rows for future scoring. It must not change live
retrieval, inject lessons, call models or embeddings, write databases, run
validation or benchmarks, launch workers, apply patches, promote/merge/block
lessons, or perform network work.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.lesson_activation_dataset import (
    JSONL_NAME,
    REPORT_JSON_NAME,
    REPORT_KIND,
    REPORT_MD_NAME,
    build_activation_rows,
    build_lesson_activation_report,
    load_model1_dataset,
    render_lesson_activation_markdown,
    scan_lesson_candidates,
    write_lesson_activation_dataset,
)
import scripts.build_lesson_activation_dataset as script


def _artifact_row(
    row_id: str = "q1",
    artifact_kind: str = "worker_assignment",
    task_title: str = "Validate worker assignment routing",
    task_summary: str = "Use validation planning before worker review",
    risk_level: str = "medium",
    dataset_task: str = "routing_or_policy_learning",
    artifact_path: str | None = None,
) -> dict:
    return {
        "row_id": row_id,
        "artifact_kind": artifact_kind,
        "artifact_path": artifact_path or f".agent/worker_assignments/{row_id}/worker_assignment.json",
        "task_title": task_title,
        "task_summary": task_summary,
        "risk_level": risk_level,
        "target": {"dataset_task": dataset_task, "authority": "advisory_only"},
        "quality": {"parse_status": "ok", "missing_fields": [], "warnings": []},
    }


def _lesson(
    lesson_id: str = "lesson-1",
    *,
    kind: str = "lesson",
    title: str = "Use validation planning for worker assignment routing",
    summary: str = "When assignment routing changes, validate the worker review path.",
    status: str = "active",
    scope: str = "global",
    confidence: float = 0.9,
    tags: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    **extra,
) -> dict:
    data = {
        "id": lesson_id,
        "kind": kind,
        "title": title,
        "summary": summary,
        "status": status,
        "scope": scope,
        "confidence": confidence,
        "tags": tags if tags is not None else ["validation", "worker"],
        "evidence_refs": evidence_refs or [],
    }
    data.update(extra)
    return data


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _write_lesson(path: Path, lesson: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lesson, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_missing_model1_dataset_produces_empty_report_with_warning(tmp_path):
    result = write_lesson_activation_dataset(
        tmp_path,
        tmp_path / "out",
        artifact_dataset_path=tmp_path / "missing.jsonl",
        report_id="r",
        created_at="t",
    )
    report = result["report"]
    assert report["query_artifact_count"] == 0
    assert report["row_count"] == 0
    assert any("model.1" in w.lower() or "dataset" in w.lower() for w in report["warnings"])


def test_malformed_model1_jsonl_row_is_skipped_with_warning(tmp_path):
    path = tmp_path / ".agent/model_lab/artifact_dataset/artifact_dataset.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_artifact_row()) + "\n{bad json\n", encoding="utf-8")
    loaded = load_model1_dataset(path)
    assert len(loaded["rows"]) == 1
    assert loaded["skipped"] == 1
    assert loaded["warnings"]


def test_missing_lesson_sources_warn_not_crash(tmp_path):
    scan = scan_lesson_candidates(tmp_path)
    assert scan["candidates"] == []
    assert scan["warnings"]
    assert any("lesson" in w.lower() for w in scan["warnings"])


def test_normal_active_lesson_candidate_becomes_candidate_row(tmp_path):
    query = _artifact_row()
    rows = build_activation_rows([query], [_lesson()], min_overlap=1)
    assert len(rows) == 1
    assert rows[0]["lesson_candidate"]["lesson_id"] == "lesson-1"
    assert rows[0]["lesson_candidate"]["kind"] == "lesson"


def test_anti_lesson_candidate_sets_is_anti_lesson_true():
    rows = build_activation_rows([_artifact_row()], [_lesson(kind="anti_lesson")], min_overlap=1)
    assert rows[0]["lesson_candidate"]["kind"] == "anti_lesson"
    assert rows[0]["activation_features"]["is_anti_lesson"] is True


def test_archived_or_superseded_lesson_produces_suppress_label():
    archived = _lesson(lesson_id="arch", status="archived")
    superseded = _lesson(lesson_id="sup", status="superseded")
    rows = build_activation_rows([_artifact_row()], [archived, superseded], min_overlap=1)
    assert {row["target"]["activation_label"] for row in rows} == {"suppress"}


def test_active_overlapping_lesson_produces_activate_label():
    rows = build_activation_rows([_artifact_row()], [_lesson()], min_overlap=1)
    assert rows[0]["target"]["activation_label"] == "activate"
    assert rows[0]["target"]["target_source"] == "heuristic"


def test_active_non_overlapping_lesson_produces_ignore_label():
    lesson = _lesson(
        title="CSS color palette decision",
        summary="Select interface colors for a visual layout.",
        tags=["colors"],
    )
    rows = build_activation_rows([_artifact_row()], [lesson], min_overlap=1)
    assert rows[0]["target"]["activation_label"] == "ignore"


def test_explicit_evidence_reference_produces_activate_label():
    query = _artifact_row(row_id="q-ref", artifact_path=".agent/evidence/q-ref.json")
    lesson = _lesson(
        title="Different words",
        summary="Unrelated text",
        tags=[],
        evidence_refs=[".agent/evidence/q-ref.json"],
    )
    rows = build_activation_rows([query], [lesson], min_overlap=99)
    assert rows[0]["activation_features"]["has_evidence_refs"] is True
    assert rows[0]["target"]["activation_label"] == "activate"
    assert rows[0]["target"]["target_source"] == "explicit"


def test_unknown_partial_lesson_produces_best_effort_unknown_row():
    partial = {"id": "partial"}
    rows = build_activation_rows([_artifact_row(task_title="", task_summary="")], [partial], min_overlap=1)
    assert len(rows) == 1
    assert rows[0]["lesson_candidate"]["lesson_id"] == "partial"
    assert rows[0]["target"]["activation_label"] == "unknown"
    assert rows[0]["quality"]["warnings"]


def test_row_ids_are_deterministic():
    query = _artifact_row()
    lesson = _lesson()
    a = build_activation_rows([query], [lesson])
    b = build_activation_rows([query], [lesson])
    assert [r["row_id"] for r in a] == [r["row_id"] for r in b]


def test_jsonl_output_is_deterministic_with_fixed_metadata(tmp_path):
    dataset = _write_jsonl(tmp_path / "dataset.jsonl", [_artifact_row()])
    _write_lesson(tmp_path / ".agent/lessons/active/l1.json", _lesson())

    def run(name: str) -> str:
        res = write_lesson_activation_dataset(
            tmp_path,
            tmp_path / name,
            artifact_dataset_path=dataset,
            report_id="fixed",
            created_at="2026-06-20T00:00:00+00:00",
        )
        return Path(res["jsonl_path"]).read_text(encoding="utf-8")

    assert run("a") == run("b")


def test_counts_by_lesson_kind_are_correct():
    rows = build_activation_rows(
        [_artifact_row()],
        [_lesson(lesson_id="l1"), _lesson(lesson_id="a1", kind="anti_lesson")],
    )
    report = build_lesson_activation_report(
        repo_path="repo",
        rows=rows,
        query_artifact_count=1,
        lesson_candidate_count=2,
        scanned_paths=[],
        skipped_files=[],
        warnings=[],
        report_id="r",
        created_at="t",
        output_dir="out",
        jsonl_path="out/data.jsonl",
    )
    assert report["counts_by_lesson_kind"] == {"anti_lesson": 1, "lesson": 1}


def test_counts_by_activation_label_are_correct():
    rows = build_activation_rows(
        [_artifact_row()],
        [
            _lesson(lesson_id="on"),
            _lesson(lesson_id="off", title="No shared text", summary="Other domain", tags=["colors"]),
            _lesson(lesson_id="arch", status="archived"),
        ],
    )
    report = build_lesson_activation_report(
        repo_path="repo",
        rows=rows,
        query_artifact_count=1,
        lesson_candidate_count=3,
        scanned_paths=[],
        skipped_files=[],
        warnings=[],
        report_id="r",
        created_at="t",
        output_dir="out",
        jsonl_path="out/data.jsonl",
    )
    assert report["counts_by_activation_label"] == {"activate": 1, "ignore": 1, "suppress": 1}


def test_counts_by_query_artifact_kind_are_correct():
    rows = build_activation_rows(
        [
            _artifact_row(row_id="q1", artifact_kind="worker_assignment"),
            _artifact_row(row_id="q2", artifact_kind="goal_brief"),
        ],
        [_lesson()],
    )
    report = build_lesson_activation_report(
        repo_path="repo",
        rows=rows,
        query_artifact_count=2,
        lesson_candidate_count=1,
        scanned_paths=[],
        skipped_files=[],
        warnings=[],
        report_id="r",
        created_at="t",
        output_dir="out",
        jsonl_path="out/data.jsonl",
    )
    assert report["counts_by_query_artifact_kind"] == {"goal_brief": 1, "worker_assignment": 1}


def test_limit_works_deterministically():
    queries = [_artifact_row(row_id="q2"), _artifact_row(row_id="q1")]
    lessons = [_lesson(lesson_id="b"), _lesson(lesson_id="a")]
    rows = build_activation_rows(queries, lessons, limit=2)
    assert len(rows) == 2
    assert [row["row_id"] for row in rows] == [row["row_id"] for row in build_activation_rows(queries, lessons, limit=2)]


def test_min_overlap_affects_activation_labels_deterministically():
    lesson = _lesson(title="Validate assignment", summary="", tags=[])
    low = build_activation_rows([_artifact_row(task_title="Validate assignment", task_summary="")], [lesson], min_overlap=1)
    high = build_activation_rows([_artifact_row(task_title="Validate assignment", task_summary="")], [lesson], min_overlap=3)
    assert low[0]["target"]["activation_label"] == "activate"
    assert high[0]["target"]["activation_label"] == "ignore"


def test_source_artifacts_are_not_modified(tmp_path):
    dataset = _write_jsonl(tmp_path / "dataset.jsonl", [_artifact_row()])
    lesson_path = _write_lesson(tmp_path / ".agent/lessons/active/l1.json", _lesson())
    before_dataset = dataset.read_bytes()
    before_lesson = lesson_path.read_bytes()
    write_lesson_activation_dataset(tmp_path, tmp_path / "out", artifact_dataset_path=dataset, report_id="r", created_at="t")
    assert dataset.read_bytes() == before_dataset
    assert lesson_path.read_bytes() == before_lesson


def test_markdown_contains_required_sections_and_boundaries():
    rows = build_activation_rows([_artifact_row()], [_lesson()])
    report = build_lesson_activation_report(
        repo_path="repo",
        rows=rows,
        query_artifact_count=1,
        lesson_candidate_count=1,
        scanned_paths=[],
        skipped_files=[],
        warnings=[],
        report_id="r",
        created_at="t",
        output_dir="out",
        jsonl_path="out/data.jsonl",
    )
    md = render_lesson_activation_markdown(report)
    assert "# Lesson Graph Activation Dataset Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## dataset files",
        "## query artifacts",
        "## lesson candidates",
        "## counts by lesson kind",
        "## counts by activation label",
        "## counts by query artifact kind",
        "## counts by target source",
        "## skipped files",
        "## warnings",
        "## sample rows",
        "## boundaries",
    ):
        assert section in low, section
    for boundary in (
        "model.3 does not change lesson retrieval",
        "model.3 does not inject lessons into prompts",
        "model.3 does not promote lessons",
        "model.3 does not merge or block lessons",
        "model.3 does not call models",
        "model.3 does not call embeddings",
        "model.3 does not write to databases",
        "model.3 does not apply patches",
        "model.3 does not run validation or benchmarks",
        "model.3 does not launch workers",
        "advisory only and grant no execution authority",
    ):
        assert boundary in low, boundary


def test_cli_writes_jsonl_json_and_markdown(tmp_path):
    dataset = _write_jsonl(tmp_path / "dataset.jsonl", [_artifact_row()])
    _write_lesson(tmp_path / ".agent/lessons/active/l1.json", _lesson())
    out = tmp_path / "out"
    res = script.run_build_lesson_activation_dataset(
        repo_path=str(tmp_path),
        output_root=str(out),
        artifact_dataset=str(dataset),
        report_id="cli",
        created_at="2026-06-20T00:00:00+00:00",
    )
    assert res["ok"] is True
    assert Path(res["jsonl_path"]).name == JSONL_NAME
    assert Path(res["json_path"]).name == REPORT_JSON_NAME
    assert Path(res["md_path"]).name == REPORT_MD_NAME
    assert (out / JSONL_NAME).is_file()
    assert (out / REPORT_JSON_NAME).is_file()
    assert (out / REPORT_MD_NAME).is_file()


def test_cli_json_flag_prints_summary_json(tmp_path, capsys):
    dataset = _write_jsonl(tmp_path / "dataset.jsonl", [_artifact_row()])
    _write_lesson(tmp_path / ".agent/lessons/active/l1.json", _lesson())
    code = script.main(
        [
            "--repo-path", str(tmp_path),
            "--output-root", str(tmp_path / "out"),
            "--artifact-dataset", str(dataset),
            "--report-id", "j",
            "--created-at", "t",
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "j"
    assert printed["report_kind"] == REPORT_KIND


def test_guardrails_are_all_false():
    rows = build_activation_rows([_artifact_row()], [_lesson()])
    report = build_lesson_activation_report(
        repo_path="repo",
        rows=rows,
        query_artifact_count=1,
        lesson_candidate_count=1,
        scanned_paths=[],
        skipped_files=[],
        warnings=[],
        report_id="r",
        created_at="t",
        output_dir="out",
        jsonl_path="out/data.jsonl",
    )
    for key, value in report["guardrails"].items():
        assert value is False, key


_CORE = Path(__file__).parent.parent / "core" / "lesson_activation_dataset.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "build_lesson_activation_dataset.py"


def _source_text() -> str:
    return _CORE.read_text(encoding="utf-8") + "\n" + _SCRIPT.read_text(encoding="utf-8")


def test_core_imports_are_stdlib_only():
    src = _CORE.read_text(encoding="utf-8")
    allowed_top = {"__future__", "hashlib", "json", "pathlib", "re", "typing"}
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {node.module!r}"
            assert top != "core", f"MODEL.3 core must not import other core modules: {node.module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_source_contains_no_forbidden_execution_or_integration_behavior():
    src = _source_text()
    for bad in (
        "subprocess",
        "Popen",
        "os.system",
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "api.telegram.org",
        "api.github.com",
        "gh pr",
        "git push",
        "run_safe_validation",
        "SafeValidationCommand",
        "validation_execution",
        "run_benchmarks",
        "generate_patch",
        "apply_patch",
        "patch_apply",
        "run_patch",
        "create_managed_sandbox",
        "apply_candidate_in_sandbox",
        "Dream execution",
        "Project Evolution execution",
        "promote_lesson",
        "create_merge",
        "block_lesson",
        "proposal import",
        "worker launch",
        "auto merge",
    ):
        assert bad not in src, f"Found forbidden token {bad!r}"
