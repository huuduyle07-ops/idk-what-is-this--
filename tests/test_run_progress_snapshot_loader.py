"""Tests for UX.RUN.2 - Run Progress Snapshot Loader.

UX.RUN.2 may load existing run-progress snapshot/report artifacts through a
GET-only/read-only interface. It must not create live progress, poll running
jobs, change execution behavior, launch workers, call models, apply patches, run
validation, run benchmarks, or trigger actions.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.phase_registry import load_phase_registry, validate_phase_registry
from core.run_progress_snapshot_loader import (
    BLOCKED,
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    LOADED_WITH_WARNINGS,
    MALFORMED,
    MD_NAME,
    NOT_FOUND,
    REQUIRED_SNAPSHOT_FIELDS,
    load_run_progress_snapshot,
    write_run_progress_snapshot_loader_report,
)
from core.run_progress_visibility import write_run_progress_visibility_report
from scripts.create_run_progress_snapshot_loader_report import (
    run_create_run_progress_snapshot_loader_report,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_snapshot_loader.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_run_progress_snapshot_loader_report.py"
WEB_APP = PROJECT_ROOT / "web" / "app.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _loader_route_source() -> str:
    return _between(
        WEB_APP.read_text(encoding="utf-8"),
        "# UX.RUN.2 GET-only Run Progress Snapshot Loader",
        "# /UX.RUN.2 GET-only Run Progress Snapshot Loader",
    )


def _snapshot(**overrides) -> dict:
    data = {
        "snapshot_id": "safe-run",
        "snapshot_status": "run_progress_snapshot_available",
        "source_contract_phase": "UX.RUN.1",
        "stages": [
            {
                "stage_id": "request_received",
                "label": "Request received",
                "is_runtime_authority": False,
                "may_trigger_action": False,
                "safe_to_display": True,
            }
        ],
        "current_stage_id": "request_received",
        "completed_stage_ids": [],
        "pending_stage_ids": ["request_received"],
        "warning_stage_ids": [],
        "error_stage_ids": [],
        "progress_notice": "No live progress stream yet.",
        "simulated_only": True,
        "live_stream_enabled": False,
        "polling_enabled": False,
        "runtime_behavior_changed": False,
        "actions_available": [],
        "warnings": [],
        "blocked_reasons": [],
        "recommended_next_phase": {
            "phase_id": "UX.RUN.3",
            "title": "Run Progress UI Panel Stub",
        },
    }
    data.update(overrides)
    return data


def _write_snapshot(root: Path, snapshot_id: str, data: dict | str) -> Path:
    path = root / ".agent" / "ux" / "run_progress_snapshots" / f"{snapshot_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_loads_default_ux_run_1_report_as_safe_snapshot(tmp_path):
    source_dir = tmp_path / ".agent" / "ux" / "run_progress_visibility"
    write_run_progress_visibility_report(
        output_dir=source_dir,
        report_id="ux-run-1-fixture",
        created_at="2026-07-10T00:00:00+09:00",
    )

    result = load_run_progress_snapshot(repo_root=tmp_path)

    assert result["loader_status"] == LOADED_WITH_WARNINGS
    assert result["snapshot_id"] == "default"
    assert result["source_path"].endswith(
        ".agent/ux/run_progress_visibility/run_progress_visibility_report.json"
    )
    assert result["snapshot"]["source_contract_phase"] == "UX.RUN.1"
    assert result["snapshot"]["live_stream_enabled"] is False
    assert result["snapshot"]["polling_enabled"] is False
    assert result["snapshot"]["runtime_behavior_changed"] is False
    assert result["snapshot"]["actions_available"] == []
    assert result["blocked_reasons"] == []
    assert result["recommended_next_phase"]["phase_id"] == "UX.RUN.3"


def test_loads_safe_snapshot_id_read_only(tmp_path):
    path = _write_snapshot(tmp_path, "run-20260710", _snapshot(snapshot_id="run-20260710"))
    before = path.read_text(encoding="utf-8")

    result = load_run_progress_snapshot("run-20260710", repo_root=tmp_path)

    assert result["loader_status"] == LOADED_WITH_WARNINGS
    assert result["snapshot_id"] == "run-20260710"
    assert result["source_path"].endswith(".agent/ux/run_progress_snapshots/run-20260710.json")
    assert "No live progress stream yet" in " ".join(result["warnings"])
    assert path.read_text(encoding="utf-8") == before


def test_loads_safe_snapshot_id_with_json_extension(tmp_path):
    path = _write_snapshot(tmp_path, "named", _snapshot(snapshot_id="named"))
    explicit = path.with_name("named.json")

    result = load_run_progress_snapshot("named.json", repo_root=tmp_path)

    assert result["loader_status"] == LOADED_WITH_WARNINGS
    assert result["source_path"].endswith(".agent/ux/run_progress_snapshots/named.json")
    assert explicit.read_text(encoding="utf-8").strip().startswith("{")


@pytest.mark.parametrize("bad_id", ["../secret", "..\\secret", ".", "..", "bad id", "C:\\secret", "/secret"])
def test_rejects_traversal_absolute_and_unsafe_snapshot_ids(tmp_path, bad_id):
    result = load_run_progress_snapshot(bad_id, repo_root=tmp_path)

    assert result["loader_status"] == BLOCKED
    assert result["snapshot"] is None
    assert result["blocked_reasons"]


def test_rejects_unsafe_extension(tmp_path):
    result = load_run_progress_snapshot("run-20260710.txt", repo_root=tmp_path)

    assert result["loader_status"] == BLOCKED
    assert "extension" in result["blocked_reasons"][0]["reason"]


def test_missing_safe_snapshot_returns_not_found_without_creating_files(tmp_path):
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())

    result = load_run_progress_snapshot("missing-safe-run", repo_root=tmp_path)

    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert result["loader_status"] == NOT_FOUND
    assert result["snapshot"] is None
    assert before == after == []


def test_malformed_json_returns_safe_error_and_preserves_file(tmp_path):
    path = _write_snapshot(tmp_path, "bad-json", "{not-json")

    result = load_run_progress_snapshot("bad-json", repo_root=tmp_path)

    assert result["loader_status"] == MALFORMED
    assert result["snapshot"] is None
    assert path.read_text(encoding="utf-8") == "{not-json"


def test_missing_required_fields_is_malformed(tmp_path):
    _write_snapshot(tmp_path, "missing-fields", {"snapshot_id": "missing-fields"})

    result = load_run_progress_snapshot("missing-fields", repo_root=tmp_path)

    assert result["loader_status"] == MALFORMED
    assert any("required" in item["reason"] for item in result["blocked_reasons"])


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("live_stream_enabled", True, "live_stream_enabled"),
        ("polling_enabled", True, "polling_enabled"),
        ("runtime_behavior_changed", True, "runtime_behavior_changed"),
        ("actions_available", ["rerun"], "actions_available"),
    ],
)
def test_blocks_live_polling_runtime_and_action_claims(tmp_path, field, value, reason):
    _write_snapshot(tmp_path, "blocked", _snapshot(**{field: value}))

    result = load_run_progress_snapshot("blocked", repo_root=tmp_path)

    assert result["loader_status"] == BLOCKED
    assert any(reason in item["reason"] for item in result["blocked_reasons"])


def test_blocks_snapshot_that_claims_runtime_authority(tmp_path):
    _write_snapshot(
        tmp_path,
        "authority",
        _snapshot(
            stages=[
                {
                    "stage_id": "request_received",
                    "label": "Request received",
                    "is_runtime_authority": True,
                    "may_trigger_action": False,
                    "safe_to_display": True,
                }
            ],
        ),
    )

    result = load_run_progress_snapshot("authority", repo_root=tmp_path)

    assert result["loader_status"] == BLOCKED
    assert any("runtime_authority" in item["reason"] for item in result["blocked_reasons"])


def test_loader_report_writes_only_loader_artifacts(tmp_path):
    source_dir = tmp_path / ".agent" / "ux" / "run_progress_visibility"
    output_dir = tmp_path / ".agent" / "ux" / "run_progress_snapshot_loader"
    write_run_progress_visibility_report(output_dir=source_dir, report_id="fixture", created_at="t")

    result = write_run_progress_snapshot_loader_report(
        repo_root=tmp_path,
        output_dir=output_dir,
        report_id="ux-run-2",
        created_at="2026-07-10T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    report = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    assert report["report_kind"] == "run_progress_snapshot_loader"
    assert report["loader_result"]["loader_status"] == LOADED_WITH_WARNINGS
    assert report["recommended_next_phase"]["phase_id"] == "UX.RUN.3"
    assert "No live progress stream yet" in (output_dir / MD_NAME).read_text(encoding="utf-8")


def test_script_creates_loader_report_summary(tmp_path):
    source_dir = tmp_path / ".agent" / "ux" / "run_progress_visibility"
    output_dir = tmp_path / "out"
    write_run_progress_visibility_report(output_dir=source_dir, report_id="fixture", created_at="t")

    result = run_create_run_progress_snapshot_loader_report(
        repo_root=tmp_path,
        output_dir=output_dir,
        report_id="script-run",
        created_at="2026-07-10T00:00:00+09:00",
    )

    assert result["summary"]["report_kind"] == "run_progress_snapshot_loader"
    assert result["summary"]["loader_status"] == LOADED_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "UX.RUN.3"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


@pytest.fixture
def client(tmp_path, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    web_app.app.config["TESTING"] = True
    source_dir = tmp_path / ".agent" / "ux" / "run_progress_visibility"
    write_run_progress_visibility_report(output_dir=source_dir, report_id="fixture", created_at="t")
    with web_app.app.test_client() as test_client:
        yield test_client


def test_get_route_loads_snapshot_read_only(client):
    response = client.get("/ux/run-progress/snapshot/default")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["status"] == LOADED_WITH_WARNINGS
    assert body["snapshot_id"] == "default"
    assert body["result"]["snapshot"]["live_stream_enabled"] is False
    assert body["result"]["recommended_next_phase"]["phase_id"] == "UX.RUN.3"


@pytest.mark.parametrize("bad_id", ["..%2Fsecret", "..%5Csecret", "bad%20id", "safe.txt"])
def test_get_route_blocks_unsafe_snapshot_ids(client, bad_id):
    response = client.get(f"/ux/run-progress/snapshot/{bad_id}")

    assert response.status_code == 400
    body = response.get_json()
    assert body["ok"] is False
    assert body["status"] == BLOCKED


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_loader_route_is_get_only(client, method):
    response = getattr(client, method)("/ux/run-progress/snapshot/default")

    assert response.status_code == 405


def test_loader_route_source_is_read_only_and_does_not_generate_or_execute():
    route = _loader_route_source()

    assert '@app.route("/ux/run-progress/snapshot/<path:snapshot_id>", methods=["GET"])' in route
    assert "request.values" not in route
    assert "request.form" not in route
    assert ".write_text" not in route
    assert ".mkdir" not in route
    for forbidden in (
        "run_create_run_progress_snapshot_loader_report",
        "create_run_progress_snapshot",
        "run_benchmarks",
        "run_validation",
        "run_agent_web",
        "run_patch_plan",
        "subprocess",
    ):
        assert forbidden not in route


def test_loader_source_contains_no_execution_or_generation_hooks():
    combined = CORE_PATH.read_text(encoding="utf-8") + "\n" + SCRIPT_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "requests",
        "socket",
        "run_agent_web",
        "start_overnight",
        "run_control",
        "run_gemini",
        "run_deepseek",
        "run_patch_plan",
        "apply_patch",
        "run_benchmarks(",
        "pytest.main",
        "Popen",
        "check_call",
        "check_output",
    ):
        assert forbidden not in combined


def test_required_snapshot_schema_is_explicit():
    assert set(REQUIRED_SNAPSHOT_FIELDS) == {
        "snapshot_id",
        "snapshot_status",
        "source_contract_phase",
        "stages",
        "current_stage_id",
        "completed_stage_ids",
        "pending_stage_ids",
        "warning_stage_ids",
        "error_stage_ids",
        "progress_notice",
        "simulated_only",
        "live_stream_enabled",
        "polling_enabled",
        "runtime_behavior_changed",
        "actions_available",
        "warnings",
        "blocked_reasons",
        "recommended_next_phase",
    }


def test_default_output_root_matches_required_artifact_location():
    assert DEFAULT_OUTPUT_ROOT.as_posix() == ".agent/ux/run_progress_snapshot_loader"
    assert JSON_NAME == "run_progress_snapshot_loader_report.json"
    assert MD_NAME == "run_progress_snapshot_loader_report.md"


def test_registry_marks_ux_run_2_complete_and_adds_ux_run_3():
    data = load_phase_registry(REGISTRY_PATH)
    result = validate_phase_registry(data)
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert result["is_valid"] is True, result["errors"]
    assert by_id["UX.RUN.2"]["status"] == "complete"
    assert by_id["UX.RUN.2"]["expected_artifacts"] == [
        ".agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.json",
        ".agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.md",
    ]
    assert by_id["UX.RUN.3"]["status"] == "proposed"
    assert by_id["UX.RUN.3"]["title"] == "Run Progress UI Panel Stub"
    assert by_id["UX.RUN.3"]["prerequisites"] == ["UX.RUN.2"]


def test_phase_picker_recommends_ux_run_3_after_loader():
    data = load_phase_registry(REGISTRY_PATH)
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="r", created_at="t")

    assert report["top_recommendation"]["phase_id"] == "UX.RUN.3"
    safe_ids = [phase["phase_id"] for phase in report["safe_to_prepare"]]
    assert safe_ids[:2] == ["UX.RUN.3", "MIRROR.13"]
