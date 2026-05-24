"""Phase 12.5i — promote TS/JS patch_candidate to patch_plan when
patched_snippet uses an identifier that a sibling module exports but the
target file does not yet import.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent_state import AgentState
from patching.patch_gates import (
    promote_ts_missing_import_candidate_to_patch_plan,
)


PRICING_TS = (
    'import { addCents } from "./money.ts";\n'
    '\n'
    'export type OrderLine = {\n'
    '  sku: string;\n'
    '  unitPriceCents: number;\n'
    '  qty: number;\n'
    '};\n'
    '\n'
    'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
    '  let total = 0;\n'
    '  for (const line of lines) {\n'
    '    total = addCents(total, line.unitPriceCents);\n'
    '  }\n'
    '  return total;\n'
    '}\n'
)

MONEY_TS = (
    'export function toCents(dollars: number): number {\n'
    '  return Math.round(dollars * 100);\n'
    '}\n'
    '\n'
    'export function addCents(a: number, b: number): number {\n'
    '  return a + b;\n'
    '}\n'
    '\n'
    'export function multiplyCents(unitCents: number, count: number): number {\n'
    '  return unitCents * count;\n'
    '}\n'
)

CALC_TARGET = (
    'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
    '  let total = 0;\n'
    '  for (const line of lines) {\n'
    '    total = addCents(total, line.unitPriceCents);\n'
    '  }\n'
    '  return total;\n'
    '}'
)

CALC_PATCHED_NO_IMPORT = (
    'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
    '  let total = 0;\n'
    '  for (const line of lines) {\n'
    '    total = addCents(total, multiplyCents(line.unitPriceCents, line.qty));\n'
    '  }\n'
    '  return total;\n'
    '}'
)


def _make_state(repo_path: Path, json_block: dict) -> AgentState:
    return AgentState(
        interface="cli",
        mode="reviewer",
        user_input="",
        file_paths=[],
        primary_file=None,
        input_mode="repo",
        language="typescript",
        task_type="patch",
        repo_path=str(repo_path),
        project_tag="test",
        json_block=json_block,
    )


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_new_identifier_merges_into_existing_import(tmp_path):
    """multiplyCents is exported by ./money.ts; pricing.ts already imports
    addCents from ./money.ts. Expect a merged import line, not a separate one.
    """
    _write(tmp_path, "pricing.ts", PRICING_TS)
    _write(tmp_path, "money.ts", MONEY_TS)
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": CALC_PATCHED_NO_IMPORT,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    block = state.json_block
    assert block["patch_candidate"] is None
    plan = block["patch_plan"]
    assert isinstance(plan, list) and len(plan) == 2

    import_op = plan[0]
    assert import_op["op"] == "replace_snippet"
    assert import_op["relative_path"] == "pricing.ts"
    assert import_op["target_snippet"] == 'import { addCents } from "./money.ts";'
    assert "addCents" in import_op["patched_snippet"]
    assert "multiplyCents" in import_op["patched_snippet"]
    assert 'from "./money.ts"' in import_op["patched_snippet"]
    # Single line, no duplicate imports.
    assert import_op["patched_snippet"].count("import {") == 1

    fn_op = plan[1]
    assert fn_op["op"] == "replace_snippet"
    assert fn_op["target_snippet"] == CALC_TARGET
    assert fn_op["patched_snippet"] == CALC_PATCHED_NO_IMPORT

    assert block["confidence"] <= 0.85
    assert block["needs_escalation"] is False


def test_new_identifier_inserts_fresh_import_when_module_has_no_existing_import(tmp_path):
    """File has no import from ./money.ts at all. Helper must insert one."""
    pricing_no_import = (
        'export type OrderLine = {\n'
        '  sku: string;\n'
        '  unitPriceCents: number;\n'
        '  qty: number;\n'
        '};\n'
        '\n'
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    total = total + line.unitPriceCents;\n'
        '  }\n'
        '  return total;\n'
        '}\n'
    )
    target = (
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    total = total + line.unitPriceCents;\n'
        '  }\n'
        '  return total;\n'
        '}'
    )
    patched = (
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    total = total + multiplyCents(line.unitPriceCents, line.qty);\n'
        '  }\n'
        '  return total;\n'
        '}'
    )
    _write(tmp_path, "pricing.ts", pricing_no_import)
    _write(tmp_path, "money.ts", MONEY_TS)
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": target,
            "patched_snippet": patched,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    block = state.json_block
    assert block["patch_candidate"] is None
    plan = block["patch_plan"]
    assert isinstance(plan, list) and len(plan) == 2

    import_op = plan[0]
    assert import_op["op"] == "replace_snippet"
    # The anchor is the first non-blank line of the original file.
    assert import_op["target_snippet"] == "export type OrderLine = {"
    # The patched_snippet must begin with a new import line, then the anchor.
    assert import_op["patched_snippet"].startswith(
        'import { multiplyCents } from "./money.ts";\n'
    )
    assert import_op["patched_snippet"].endswith("export type OrderLine = {")

    fn_op = plan[1]
    assert fn_op["target_snippet"] == target
    assert fn_op["patched_snippet"] == patched


def test_existing_imported_symbol_is_not_duplicated(tmp_path):
    """patched_snippet uses addCents (already imported) plus multiplyCents.
    Only multiplyCents should land in a patch_plan — addCents stays as-is.
    """
    _write(tmp_path, "pricing.ts", PRICING_TS)
    _write(tmp_path, "money.ts", MONEY_TS)
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": CALC_PATCHED_NO_IMPORT,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    block = state.json_block
    plan = block.get("patch_plan") or []
    import_op = plan[0]
    new_import = import_op["patched_snippet"]
    # addCents appears once (carried over) and multiplyCents appears once (added).
    assert new_import.count("addCents") == 1
    assert new_import.count("multiplyCents") == 1


def test_identifier_with_no_local_export_does_not_invent_import(tmp_path):
    """patched_snippet uses someUnknownHelper, which no sibling exports.
    The helper must NOT promote — patch_candidate is left untouched.
    """
    _write(tmp_path, "pricing.ts", PRICING_TS)
    _write(tmp_path, "money.ts", MONEY_TS)
    patched = (
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    total = addCents(total, someUnknownHelper(line.unitPriceCents));\n'
        '  }\n'
        '  return total;\n'
        '}'
    )
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": patched,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)
    assert state.json_block["confidence"] == 1.0


def test_normal_patch_without_new_identifiers_is_unchanged(tmp_path):
    """patched_snippet only uses identifiers already present in target_snippet.
    No new imports needed — leave patch_candidate alone.
    """
    _write(tmp_path, "pricing.ts", PRICING_TS)
    _write(tmp_path, "money.ts", MONEY_TS)
    patched = (
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    // Tiny refactor — same identifiers, cleaner body.\n'
        '    total = addCents(total, line.unitPriceCents);\n'
        '  }\n'
        '  return total;\n'
        '}'
    )
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": patched,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)
    assert state.json_block["confidence"] == 1.0


def test_ts_nested_dispatch_root_cause_fixture_repairs_addcents_plus_multiplycents(tmp_path):
    """Drop the actual ts_nested_dispatch_root_cause buggy_repo files into the
    sandbox and run the helper end-to-end. Must produce a 2-op plan that
    merges multiplyCents alongside addCents and replaces the function body.
    """
    fixture_root = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "cases"
        / "typescript"
        / "ts_nested_dispatch_root_cause"
        / "buggy_repo"
    )
    for src in fixture_root.iterdir():
        if src.is_file():
            (tmp_path / src.name).write_text(
                src.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    target = (tmp_path / "pricing.ts").read_text(encoding="utf-8")
    # Slice the function body out exactly as the model would copy it.
    fn_start = target.index("export function calculateOrderTotal")
    fn_end = target.index("\n}\n", fn_start) + len("\n}")
    target_snippet = target[fn_start:fn_end]

    patched_snippet = target_snippet.replace(
        "total = addCents(total, line.unitPriceCents);",
        "total = addCents(total, multiplyCents(line.unitPriceCents, line.qty));",
    )

    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": target_snippet,
            "patched_snippet": patched_snippet,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    block = state.json_block
    plan = block.get("patch_plan")
    assert isinstance(plan, list) and len(plan) == 2

    import_op, fn_op = plan
    assert import_op["target_snippet"] == 'import { addCents } from "./money.ts";'
    assert (
        import_op["patched_snippet"]
        == 'import { addCents, multiplyCents } from "./money.ts";'
    )
    assert fn_op["target_snippet"] == target_snippet
    assert fn_op["patched_snippet"] == patched_snippet


def test_non_ts_js_file_is_ignored(tmp_path):
    """A .py target must not trigger Phase 12.5i."""
    _write(tmp_path, "main.py", "def foo():\n    pass\n")
    _write(tmp_path, "helpers.py", "def multiplyCents(a, b):\n    return a * b\n")
    json_block = {
        "patch_candidate": {
            "relative_path": "main.py",
            "target_node_name": "foo",
            "target_snippet": "def foo():\n    pass",
            "patched_snippet": "def foo():\n    return multiplyCents(1, 2)",
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)


def test_existing_patch_plan_is_not_overwritten(tmp_path):
    """Caller-provided patch_plan wins; helper must not touch it."""
    _write(tmp_path, "pricing.ts", PRICING_TS)
    _write(tmp_path, "money.ts", MONEY_TS)
    existing_plan = [{
        "op": "replace_snippet",
        "relative_path": "pricing.ts",
        "target_snippet": "foo",
        "patched_snippet": "bar",
    }]
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": CALC_PATCHED_NO_IMPORT,
        },
        "patch_plan": existing_plan,
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_plan"] == existing_plan


def test_target_snippet_drift_is_left_for_grounding_recovery(tmp_path):
    """target_snippet does not appear in the file — leave for grounding."""
    _write(tmp_path, "pricing.ts", PRICING_TS)
    _write(tmp_path, "money.ts", MONEY_TS)
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": "function calculateOrderTotal() { /* drift */ }",
            "patched_snippet": CALC_PATCHED_NO_IMPORT,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)


def test_missing_target_file_is_safely_ignored(tmp_path):
    """File does not exist on disk — let reject_ungrounded_patch handle it."""
    _write(tmp_path, "money.ts", MONEY_TS)
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": CALC_PATCHED_NO_IMPORT,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_missing_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)


def test_path_traversal_in_relative_path_is_refused(tmp_path):
    """relative_path that resolves outside the repo must be rejected."""
    outside = tmp_path.parent / "evil_pricing.ts"
    outside.write_text(PRICING_TS, encoding="utf-8")
    try:
        json_block = {
            "patch_candidate": {
                "relative_path": "../evil_pricing.ts",
                "target_node_name": "calculateOrderTotal",
                "target_snippet": CALC_TARGET,
                "patched_snippet": CALC_PATCHED_NO_IMPORT,
            },
            "confidence": 1.0,
        }
        state = _make_state(tmp_path, json_block)

        promote_ts_missing_import_candidate_to_patch_plan(state)

        assert state.json_block["patch_candidate"] is not None
        assert state.json_block.get("patch_plan") in (None, [], False)
    finally:
        if outside.exists():
            outside.unlink()


def test_main_pipeline_calls_ts_missing_import_helper():
    """Wire-up check: the main pipeline must import the new helper."""
    import main as main_mod

    assert hasattr(main_mod, "promote_ts_missing_import_candidate_to_patch_plan"), (
        "main.py must import promote_ts_missing_import_candidate_to_patch_plan"
    )


def test_web_runner_calls_ts_missing_import_helper():
    """Same wire-up check for the web runner code path."""
    from web import runner as web_runner

    assert hasattr(web_runner, "promote_ts_missing_import_candidate_to_patch_plan"), (
        "web/runner.py must import promote_ts_missing_import_candidate_to_patch_plan"
    )
