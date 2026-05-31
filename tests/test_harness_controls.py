"""Phase 12.15a - Harness Control Registry MVP tests.

The registry is a control surface that shows current effective harness state and
persists desired overrides to .agent/harness_overrides.json. It must:
- never write .env or docker-compose.yml (that is 12.15b / 12.15c),
- live-patch only ``editable_live`` controls (in-process config attribute),
- mark restart-required controls honestly,
- show planned + locked controls as read-only,
- import/call nothing dangerous.
"""
from __future__ import annotations

import ast
import json
import types
from pathlib import Path

import pytest

from core import harness_controls as hc


PROJECT_ROOT = Path(__file__).resolve().parent.parent

EDITABLE_WIRED = {
    "LESSON_RETRIEVAL_ENABLED",
    "MUTATION_ORACLE_ENABLED",
    "OLLAMA_ENABLED",
    "AUTO_PATCH_ENABLED",
    "DB_ENABLED",
    "EMBEDDING_PROVIDER",
}
PLANNED = {
    "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED",
    "MEMORY_TEMPERATURE_TIEBREAK_ONLY",
    "dream_create_patches",
}
LOCKED = {
    "quote_grounding",
    "patch_safety_path_traversal_guard",
    "frozen_audit_only_exclusion",
    "harness_hard_deny_path_runtime",
    "human_approval_dangerous_writes",
}

REQUIRED_FIELDS = {
    "id",
    "label",
    "env_var",
    "category",
    "control_type",
    "source_of_truth",
    "wired",
    "risk",
    "value_kind",
    "enum_options",
    "env_targets",
    "description",
    "plan_ref",
}


def _fake_config() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        LESSON_RETRIEVAL_ENABLED=False,
        MUTATION_ORACLE_ENABLED=False,
        OLLAMA_ENABLED=False,
        AUTO_PATCH_ENABLED=True,
        DB_ENABLED=True,
    )


# --------------------------------------------------------------------------
# registry shape
# --------------------------------------------------------------------------

def test_registry_has_all_expected_controls():
    ids = {c["id"] for c in hc.list_controls(overlay_path=None, config_module=_fake_config())}
    assert EDITABLE_WIRED <= ids
    assert PLANNED <= ids
    assert LOCKED <= ids


def test_every_control_has_required_fields_and_runtime_fields():
    for control in hc.list_controls(config_module=_fake_config()):
        assert REQUIRED_FIELDS <= set(control), control
        # runtime fields added by list_controls
        for rt in ("current_effective", "pending", "applied_differs"):
            assert rt in control, (control["id"], rt)


def test_control_type_and_source_of_truth_are_correct():
    by_id = {c["id"]: c for c in hc.list_controls(config_module=_fake_config())}

    for cid in EDITABLE_WIRED:
        assert by_id[cid]["control_type"] in {
            "editable_live",
            "editable_restart_required",
        }
        assert by_id[cid]["wired"] is True

    for cid in ("LESSON_RETRIEVAL_ENABLED", "MUTATION_ORACLE_ENABLED", "OLLAMA_ENABLED"):
        assert by_id[cid]["control_type"] == "editable_live"
    for cid in ("AUTO_PATCH_ENABLED", "DB_ENABLED", "EMBEDDING_PROVIDER"):
        assert by_id[cid]["control_type"] == "editable_restart_required"

    for cid in PLANNED:
        assert by_id[cid]["control_type"] == "read_only_planned"
        assert by_id[cid]["wired"] is False
        assert by_id[cid]["source_of_truth"] == "planned"

    for cid in LOCKED:
        assert by_id[cid]["control_type"] == "locked_invariant"
        assert by_id[cid]["source_of_truth"] == "locked_invariant"
        # Locked invariants always render on.
        assert str(by_id[cid]["current_effective"]).lower() in {"on", "true", "locked"}

    assert by_id["EMBEDDING_PROVIDER"]["value_kind"] == "enum"
    assert tuple(by_id["EMBEDDING_PROVIDER"]["enum_options"]) == ("off", "local_minilm", "gemini")


def test_docker_compose_apply_not_implemented_yet():
    # docker-compose writing is Phase 12.15c; it must not exist yet.
    assert not hasattr(hc, "apply_compose_patch")
    assert not hasattr(hc, "preview_compose_patch")


# --------------------------------------------------------------------------
# overlay round-trip + fail-soft
# --------------------------------------------------------------------------

def test_overlay_round_trip(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    hc.save_overlay({"MUTATION_ORACLE_ENABLED": "true"}, overlay_path=overlay)
    assert hc.load_overlay(overlay_path=overlay) == {"MUTATION_ORACLE_ENABLED": "true"}


def test_malformed_overlay_fail_softs_to_empty(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    overlay.write_text("{not valid json", encoding="utf-8")
    assert hc.load_overlay(overlay_path=overlay) == {}


def test_missing_overlay_is_empty(tmp_path):
    overlay = tmp_path / "does_not_exist.json"
    assert hc.load_overlay(overlay_path=overlay) == {}


# --------------------------------------------------------------------------
# set_override behavior
# --------------------------------------------------------------------------

def test_editable_live_control_patches_config_attribute(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    cfg = _fake_config()
    result = hc.set_override(
        "LESSON_RETRIEVAL_ENABLED", "true", overlay_path=overlay, config_module=cfg
    )
    # config attribute changed in-process...
    assert cfg.LESSON_RETRIEVAL_ENABLED is True
    # ...overlay persisted...
    assert hc.load_overlay(overlay_path=overlay)["LESSON_RETRIEVAL_ENABLED"] == "true"
    # ...and the result reports a live effect.
    assert result["applied_live"] is True
    assert result["restart_required"] is False


def test_restart_required_control_does_not_claim_live_effect(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    cfg = _fake_config()
    before = cfg.AUTO_PATCH_ENABLED
    result = hc.set_override(
        "AUTO_PATCH_ENABLED", "false", overlay_path=overlay, config_module=cfg
    )
    # The desired value is persisted to the overlay...
    assert hc.load_overlay(overlay_path=overlay)["AUTO_PATCH_ENABLED"] == "false"
    # ...but the in-process config attribute is NOT mutated (restart required)...
    assert cfg.AUTO_PATCH_ENABLED == before
    assert result["applied_live"] is False
    assert result["restart_required"] is True


def test_enum_control_validates_member(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    cfg = _fake_config()
    hc.set_override("EMBEDDING_PROVIDER", "gemini", overlay_path=overlay, config_module=cfg)
    assert hc.load_overlay(overlay_path=overlay)["EMBEDDING_PROVIDER"] == "gemini"
    with pytest.raises(hc.HarnessControlError):
        hc.set_override("EMBEDDING_PROVIDER", "not_a_provider", overlay_path=overlay, config_module=cfg)


def test_planned_control_cannot_be_set(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    with pytest.raises(hc.HarnessControlError):
        hc.set_override(
            "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED", "true",
            overlay_path=overlay, config_module=_fake_config(),
        )
    # nothing written
    assert hc.load_overlay(overlay_path=overlay) == {}


def test_locked_invariant_cannot_be_mutated(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    with pytest.raises(hc.HarnessControlError):
        hc.set_override(
            "quote_grounding", "false",
            overlay_path=overlay, config_module=_fake_config(),
        )
    assert hc.load_overlay(overlay_path=overlay) == {}


def test_unknown_control_is_rejected(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    with pytest.raises(hc.HarnessControlError):
        hc.set_override("NOPE", "true", overlay_path=overlay, config_module=_fake_config())


def test_pending_and_applied_differs_reflect_overlay(tmp_path):
    overlay = tmp_path / "harness_overrides.json"
    cfg = _fake_config()  # MUTATION_ORACLE_ENABLED defaults False
    hc.save_overlay({"MUTATION_ORACLE_ENABLED": "true"}, overlay_path=overlay)
    by_id = {c["id"]: c for c in hc.list_controls(overlay_path=overlay, config_module=cfg)}
    entry = by_id["MUTATION_ORACLE_ENABLED"]
    assert entry["pending"] == "true"
    assert entry["current_effective"] == "false"
    assert entry["applied_differs"] is True


# --------------------------------------------------------------------------
# AST guard
# --------------------------------------------------------------------------

def _imports_and_calls(path: Path) -> tuple[list[str], list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return imported, calls


def test_module_has_no_forbidden_imports_or_calls():
    imported, calls = _imports_and_calls(PROJECT_ROOT / "core" / "harness_controls.py")

    forbidden_areas = ("patching", "validation", "validator", "run_benchmarks", "model", "api")
    for imp in imported:
        parts = imp.split(".")
        for area in forbidden_areas:
            assert not any(p == area for p in parts), imp

    forbidden_top = {
        "requests", "httpx", "urllib", "aiohttp", "socket", "subprocess",
        "openai", "psycopg", "psycopg2", "sqlite3", "sqlalchemy", "database",
    }
    assert forbidden_top.isdisjoint(p.split(".")[0] for p in imported)

    forbidden_calls = {
        "call_model", "call_api", "run_gemini_request", "validate",
        "run_benchmarks", "start_benchmark_run_async", "connect",
    }
    assert forbidden_calls.isdisjoint(calls)
