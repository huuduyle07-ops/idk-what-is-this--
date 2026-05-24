"""Phase 12.5h — promote TS/JS patch_candidate to patch_plan when
patched_snippet contains an import that would duplicate an existing one.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent_state import AgentState
from patching.patch_gates import (
    promote_ts_duplicate_import_candidate_to_patch_plan,
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

CALC_TARGET = (
    'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
    '  let total = 0;\n'
    '  for (const line of lines) {\n'
    '    total = addCents(total, line.unitPriceCents);\n'
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


def test_duplicate_import_with_new_specifier_is_promoted_to_patch_plan(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS)
    patched = (
        'import { addCents, multiplyCents } from "./money.ts";\n'
        '\n'
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    total = addCents(total, multiplyCents(line.unitPriceCents, line.qty));\n'
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

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    block = state.json_block
    assert block["patch_candidate"] is None
    plan = block["patch_plan"]
    assert isinstance(plan, list) and len(plan) == 2

    import_op = plan[0]
    assert import_op["op"] == "replace_snippet"
    assert import_op["relative_path"] == "pricing.ts"
    assert import_op["target_snippet"] == 'import { addCents } from "./money.ts";'
    # New import line must include BOTH the pre-existing addCents and the new
    # multiplyCents — order doesn't matter for the test, just both present.
    assert "addCents" in import_op["patched_snippet"]
    assert "multiplyCents" in import_op["patched_snippet"]
    assert 'from "./money.ts"' in import_op["patched_snippet"]

    fn_op = plan[1]
    assert fn_op["op"] == "replace_snippet"
    assert fn_op["target_snippet"] == CALC_TARGET
    # The duplicate import line must be stripped from the function snippet.
    assert "import {" not in fn_op["patched_snippet"]
    assert "multiplyCents" in fn_op["patched_snippet"]
    # Confidence capped, no escalation triggered by this promotion alone.
    assert block["confidence"] <= 0.85
    assert block["needs_escalation"] is False


def test_brand_new_import_module_is_left_alone(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS)
    # Snippet pulls in an unrelated module not in the file — no duplicate risk.
    patched = (
        'import { roundCents } from "./rounding.ts";\n'
        '\n'
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 0;\n'
        '  for (const line of lines) {\n'
        '    total = addCents(total, roundCents(line.unitPriceCents));\n'
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

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    # No promotion: still patch_candidate, no patch_plan field added.
    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)
    assert state.json_block["confidence"] == 1.0


def test_pure_duplicate_import_is_stripped_without_import_op(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS)
    # Snippet redeclares the SAME identifiers — no new specifiers, just a
    # duplicate-binding error if applied. Strip from snippet, no import op.
    patched = (
        'import { addCents } from "./money.ts";\n'
        '\n'
        'export function calculateOrderTotal(lines: OrderLine[]): number {\n'
        '  let total = 1;\n'
        '  for (const line of lines) {\n'
        '    total = addCents(total, line.unitPriceCents * line.qty);\n'
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

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    block = state.json_block
    plan = block.get("patch_plan")
    assert isinstance(plan, list) and len(plan) == 1
    fn_op = plan[0]
    assert fn_op["target_snippet"] == CALC_TARGET
    assert "import {" not in fn_op["patched_snippet"]
    # Body change preserved.
    assert "let total = 1" in fn_op["patched_snippet"]


def test_non_ts_js_file_is_ignored(tmp_path):
    _write(tmp_path, "main.py", "def foo():\n    pass\n")
    json_block = {
        "patch_candidate": {
            "relative_path": "main.py",
            "target_node_name": "foo",
            "target_snippet": "def foo():\n    pass",
            "patched_snippet": 'import { x } from "./y.ts";\ndef foo():\n    return 1',
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    # Untouched — this helper is for TS/JS only.
    assert state.json_block["patch_candidate"]["patched_snippet"].startswith("import {")
    assert state.json_block.get("patch_plan") in (None, [], False)


def test_existing_patch_plan_is_not_overwritten(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS)
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
            "patched_snippet": (
                'import { addCents, multiplyCents } from "./money.ts";\n'
                + CALC_TARGET
            ),
        },
        "patch_plan": existing_plan,
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    # Caller-provided patch_plan must win.
    assert state.json_block["patch_plan"] == existing_plan


def test_target_snippet_drift_is_left_for_grounding_recovery(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS)
    # target_snippet does NOT match the file — let reject_ungrounded_patch
    # and its grounding recovery handle it; this helper must not act.
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": "function calculateOrderTotal() { /* drift */ }",
            "patched_snippet": (
                'import { addCents, multiplyCents } from "./money.ts";\n'
                + CALC_TARGET
            ),
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    # No promotion happened.
    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)


def test_missing_target_file_is_safely_ignored(tmp_path):
    # File doesn't exist on disk — let reject_ungrounded_patch handle.
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": CALC_TARGET,
            "patched_snippet": (
                'import { addCents, multiplyCents } from "./money.ts";\n'
                + CALC_TARGET
            ),
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    assert state.json_block["patch_candidate"] is not None
    assert state.json_block.get("patch_plan") in (None, [], False)


def test_js_cjs_require_style_not_affected(tmp_path):
    # CommonJS `require` is not in scope — only ES `import { x } from "y"`
    # is handled. Snippet uses ESM-style imports, file uses ESM-style too.
    file_text = (
        'import { existing } from "./mod.js";\n'
        '\n'
        'export function f() { return existing(); }\n'
    )
    _write(tmp_path, "x.js", file_text)
    target = 'export function f() { return existing(); }'
    patched = (
        'import { existing, fresh } from "./mod.js";\n'
        'export function f() { return existing() + fresh(); }'
    )
    json_block = {
        "patch_candidate": {
            "relative_path": "x.js",
            "target_node_name": "f",
            "target_snippet": target,
            "patched_snippet": patched,
        },
        "confidence": 1.0,
    }
    state = _make_state(tmp_path, json_block)

    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    block = state.json_block
    plan = block.get("patch_plan")
    assert isinstance(plan, list) and len(plan) == 2
    # JS file extension is handled the same as TS for ESM imports.
    assert plan[0]["target_snippet"] == 'import { existing } from "./mod.js";'
    assert "fresh" in plan[0]["patched_snippet"]


def test_main_pipeline_calls_ts_dedup_helper(monkeypatch):
    """Wire-up check: the main pipeline must call the new helper alongside
    the existing Go helper. Fails if the new helper is not imported / called.
    """
    import main as main_mod

    assert hasattr(main_mod, "promote_ts_duplicate_import_candidate_to_patch_plan"), (
        "main.py must import promote_ts_duplicate_import_candidate_to_patch_plan"
    )


def test_web_runner_calls_ts_dedup_helper():
    """Same wire-up check for the web runner code path."""
    from web import runner as web_runner

    assert hasattr(web_runner, "promote_ts_duplicate_import_candidate_to_patch_plan"), (
        "web/runner.py must import promote_ts_duplicate_import_candidate_to_patch_plan"
    )
