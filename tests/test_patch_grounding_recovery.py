"""Phase 12.5g — grounding recovery for target_snippet drift."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent_state import AgentState
from patching.patch_gates import reject_ungrounded_patch


PRICING_TS_GOOD_TEXT = """\
import { addCents } from "./money.ts";

export type OrderLine = {
  sku: string;
  unitPriceCents: number;
  qty: number;
};

export function calculateOrderTotal(lines: OrderLine[]): number {
  let total = 0;
  for (const line of lines) {
    total = addCents(total, line.unitPriceCents);
  }
  return total;
}
"""


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


def test_grounding_recovery_succeeds_when_target_node_name_matches(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS_GOOD_TEXT)

    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            # WRONG snippet — does not exist in pricing.ts as-is.
            "target_snippet": "function calculateOrderTotal(lines) { /* stale body */ }",
            "patched_snippet": "export function calculateOrderTotal(...) { ...fixed... }",
        },
        "confidence": 0.95,
        "needs_escalation": False,
    }
    state = _make_state(tmp_path, json_block)

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    assert patch is not None
    assert "rejected" not in patch
    # target_snippet replaced with the real function body present in the file.
    recovered = patch["target_snippet"]
    assert recovered in PRICING_TS_GOOD_TEXT
    assert "calculateOrderTotal" in recovered
    assert state.json_block["confidence"] <= 0.75
    assert state.json_block.get("needs_escalation") is False


def test_target_file_missing_yields_friendly_rejection_with_no_recovery(tmp_path):
    # Note: pricing.ts is NOT created.
    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": "x",
            "patched_snippet": "y",
        },
        "confidence": 0.9,
    }
    state = _make_state(tmp_path, json_block)

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    assert patch["rejected"] is True
    assert "does not exist" in patch["reject_reason"]
    assert "Traceback" not in patch["reject_reason"]
    # No grounding_error attached because we never even reached recovery
    # (file existence check happens before).
    assert "grounding_error" not in patch
    assert state.json_block["needs_escalation"] is True
    assert state.json_block["confidence"] == 0.0


def test_path_traversal_target_is_blocked_before_any_recovery(tmp_path):
    # Set up a sibling file outside the repo that would match by name.
    outside = tmp_path.parent / "outside_secret.ts"
    outside.write_text(PRICING_TS_GOOD_TEXT, encoding="utf-8")

    json_block = {
        "patch_candidate": {
            "relative_path": "../outside_secret.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": "stale",
            "patched_snippet": "y",
        },
        "confidence": 0.9,
    }
    state = _make_state(tmp_path, json_block)

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    assert patch["rejected"] is True
    assert "outside repo" in patch["reject_reason"]
    # target_snippet must NOT be rewritten by the recovery path.
    assert patch["target_snippet"] == "stale"
    assert "grounding_error" not in patch


def test_recovery_only_reads_target_file_not_sibling_with_same_name(tmp_path):
    # Sibling file has the SAME function name but is forbidden. Recovery
    # must not read it — it must only consult the file the patch targets.
    _write(
        tmp_path,
        "pricing.ts",
        "// pricing.ts has no matching function — only an unrelated helper.\n"
        "export function unrelated(): number { return 0; }\n",
    )
    _write(
        tmp_path,
        "fixtures/pricing.ts",
        PRICING_TS_GOOD_TEXT,
    )

    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": "function calculateOrderTotal() { stale }",
            "patched_snippet": "y",
        },
        "confidence": 0.9,
    }
    state = _make_state(tmp_path, json_block)

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    # Recovery must FAIL — calculateOrderTotal does not exist in the
    # actual target file, even though a sibling has it.
    assert patch["rejected"] is True
    assert "target_snippet does not exist" in patch["reject_reason"]
    # target_snippet must not have been rewritten with the sibling's body.
    assert patch["target_snippet"] == "function calculateOrderTotal() { stale }"
    # Grounding_error attached for the agent to inspect.
    assert "grounding_error" in patch
    assert patch["grounding_error"]["target_node_name"] == "calculateOrderTotal"
    assert "symbol_lookup" in patch["grounding_error"]["tried"]


def test_original_exact_snippet_path_unchanged_when_target_present(tmp_path):
    _write(tmp_path, "pricing.ts", PRICING_TS_GOOD_TEXT)
    # target_snippet IS present exactly — no drift, no recovery should fire.
    exact = "  for (const line of lines) {\n    total = addCents(total, line.unitPriceCents);\n  }"
    assert exact in PRICING_TS_GOOD_TEXT  # sanity

    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": exact,
            "patched_snippet": "patched",
        },
        "confidence": 0.95,
        "needs_escalation": False,
    }
    state = _make_state(tmp_path, json_block)

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    assert "rejected" not in patch
    # Confidence not touched.
    assert state.json_block["confidence"] == 0.95
    assert patch["target_snippet"] == exact
    assert "grounding_error" not in patch


def test_existing_source_snippet_recovery_still_wins_when_available(tmp_path):
    """Regression: do not break the pre-existing CONTROL source_snippet recovery."""
    _write(tmp_path, "pricing.ts", PRICING_TS_GOOD_TEXT)
    control_source = "  for (const line of lines) {\n    total = addCents(total, line.unitPriceCents);\n  }"
    assert control_source in PRICING_TS_GOOD_TEXT  # sanity

    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            "target_node_name": "calculateOrderTotal",
            "target_snippet": "this snippet is not in the file",
            "patched_snippet": "patched",
        },
        "confidence": 0.95,
    }
    state = _make_state(tmp_path, json_block)
    state.control_result = {"patch_intent": {"source_snippet": control_source}}

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    assert "rejected" not in patch
    assert patch["target_snippet"] == control_source
    # CONTROL recovery caps confidence at 0.85 (not the 0.75 of the new path).
    assert state.json_block["confidence"] == 0.85


def test_grounding_error_includes_file_excerpt_when_symbol_present(tmp_path):
    # The function is in the file, but symbol parser cannot find it by name
    # because target_node_name is wrong. We still want a useful excerpt
    # pointing at the closest match in the file.
    _write(tmp_path, "pricing.ts", PRICING_TS_GOOD_TEXT)

    json_block = {
        "patch_candidate": {
            "relative_path": "pricing.ts",
            # Wrong node name on purpose: the file has "calculateOrderTotal"
            # but the agent guessed "calculateOrder".
            "target_node_name": "calculateOrder",
            "target_snippet": "stale snippet",
            "patched_snippet": "y",
        },
        "confidence": 0.9,
    }
    state = _make_state(tmp_path, json_block)

    reject_ungrounded_patch(state)

    patch = state.json_block["patch_candidate"]
    assert patch["rejected"] is True
    grounding = patch.get("grounding_error") or {}
    # Some excerpt should be present — file does contain "calculateOrder" as a
    # substring of calculateOrderTotal, so the matcher finds context.
    assert isinstance(grounding.get("file_excerpt"), str)
    assert "calculateOrder" in grounding["file_excerpt"]
