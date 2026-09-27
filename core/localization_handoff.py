"""Keep CONTROL's concrete target through payload and display handoffs.

Only an existing, current CONTROL failure binding can replace it. Model
payloads and answer-entity existence receipts are never replacement evidence.
This module acquires no source and grants no patch or execution authority.
"""
from __future__ import annotations

import hashlib
import json

from core.live_task_routing import route_is_explicit_change, route_is_read_only
from core.defect_probe import (
    attach_probe_telemetry_to_payload,
    reproduced_probe_target,
)
from core.validation_outcome import is_executed_failure_evidence


def _identity(file: str, symbol: str) -> str:
    file = str(file or "").replace("\\", "/")
    return f"{file}::{symbol or ''}"


def current_target_receipt(control: dict | None, *, live_route=None) -> dict | None:
    if not isinstance(control, dict) or not control.get("localization_candidates"):
        return None
    route = live_route or control.get("live_route")
    if route_is_explicit_change(route) or route_is_read_only(route):
        return None
    top = control.get("top_hypothesis") or {}
    original = top.get("symbol") or ""
    if "::" not in original:
        return None
    target = original
    replacement = None
    grounded = control.get("grounded_hypothesis") or {}
    intent = control.get("patch_intent") or {}
    basis = control.get("patch_candidate_state") or {}
    binding = basis.get("candidate_binding") or {}
    proposed = grounded.get("symbol")
    supported = (
        basis.get("patch_basis") == "grounded_defect"
        and basis.get("exact_source_grounded") is True
        and proposed == _identity(binding.get("file", ""), binding.get("symbol", ""))
        and proposed == intent.get("target_symbol_full")
        and grounded.get("defect_grounding") == basis.get("defect_grounding")
    )
    if proposed and proposed != original and supported:
        preflight = control.get("preflight_validation") or {}
        probe = control.get("defect_probe") or {}
        evidence = basis.get("defect_grounding") or []
        executed = bool(
            preflight.get("ran") and preflight.get("ok") is False
            and is_executed_failure_evidence(preflight.get("category"))
            and basis.get("failure_binding_kind") in {
                "direct_location", "direct_executed_reference",
            }
            and any(row.get("kind") == "executed_validation_failure" for row in evidence)
        )
        reproduced = bool(
            reproduced_probe_target(probe) is not None
            and any(row.get("kind") == "bounded_defect_reproduction" for row in evidence)
        )
        if executed or reproduced:
            target = proposed
            replacement = {
                "previous_target": original,
                "replacement_target": target,
                "replacement_basis": basis.get("failure_binding_kind"),
                "evidence_source": basis.get("patch_basis_source"),
                "freshness": "current_control_receipt",
                "evidence_fingerprint": hashlib.sha256(json.dumps(
                    [preflight, probe, evidence, intent.get("source_snippet")],
                    sort_keys=True, default=str,
                ).encode()).hexdigest(),
            }
    return {
        "localized_target": target,
        "control_target": original,
        "replacement_receipt": replacement,
        "semantics": "navigation target; localization alone establishes no defect or authority",
    }


def enforce_payload_target(control: dict | None, block: dict | None, *, live_route=None) -> None:
    """Refuse a primary candidate substitution before existing safety gates."""
    # DEFECT.FACT.LIVE.1: additive read-only diagnostics, copied from the
    # receipt CONTROL already recorded. It runs before the target check so an
    # unavailable probe is still visible on a payload this seam does not touch.
    attach_probe_telemetry_to_payload(control, block)
    receipt = current_target_receipt(control, live_route=live_route)
    if receipt is None or not isinstance(block, dict):
        return
    target = receipt["localized_target"]
    file, _, symbol = target.partition("::")
    candidate = block.get("patch_candidate")
    plan = block.get("patch_plan")
    operations = plan if isinstance(plan, list) else [candidate] if isinstance(candidate, dict) else []
    if not operations:
        return
    source = (control.get("patch_intent") or {}).get("source_snippet") or ""
    contains_target = False
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        path = str(operation.get("relative_path") or operation.get("file") or "").replace("\\", "/")
        name = operation.get("target_node_name") or operation.get("target_symbol") or ""
        full = operation.get("target_symbol_full")
        quote = operation.get("target_snippet") or ""
        if path.casefold() == file.casefold() and (not name or name == symbol) and (not full or full == target):
            # An unnamed snippet must belong to the already-loaded localized
            # body. File equality alone does not bind another function in it.
            contains_target |= bool(name == symbol or (quote and source and quote in source))
    if not contains_target:
        block["patch_candidate"] = None
        block["patch_plan"] = None
        block["localization_target_rejected"] = True
        block["localization_target_reject_reason"] = (
            "Candidate does not include the CONTROL-localized target; no typed stronger replacement evidence."
        )
    else:
        block.pop("localization_target_rejected", None)
        block.pop("localization_target_reject_reason", None)
    block["localization_handoff"] = receipt


def _annotate_text(value: str, target: str) -> str:
    from core.answer_entity_grounding import extract_repository_entities
    from core.repository_symbol_membership import extract_symbol_claims

    file, _, symbol = target.partition("::")
    refs = extract_repository_entities(value)
    positions = {
        ref.end for ref in refs
        if not ref.hypothetical and (
            ref.path.casefold() != file.casefold()
            or (ref.symbol and ref.symbol != symbol)
        )
    }
    for claim in extract_symbol_claims(value, exclude_spans=[(ref.start, ref.end) for ref in refs]):
        if claim.member != symbol and claim.raw.strip("`()") != symbol:
            positions.add(claim.end)
    marker = " (context reference; not the localized target)"
    for end in sorted(positions, reverse=True):
        # Keep closing code/link punctuation intact; insertion is idempotent.
        while end < len(value) and value[end] in "`)]":
            end += 1
        if not value[end:].startswith(marker):
            value = value[:end] + marker + value[end:]
    return value


def _display_payload(value, target: str):
    if isinstance(value, str):
        return _annotate_text(value, target)
    if isinstance(value, list):
        return [_display_payload(item, target) for item in value]
    if not isinstance(value, dict):
        return value
    # Execution receipts, patch bytes and entity-grounding facts remain exact.
    result = dict(value)
    for key in ("summary", "analysis", "root_cause", "reason", "fix", "explanation", "issues", "recommendations", "target", "target_file", "target_symbol", "target_symbol_full", "symbol", "file"):
        if key in result:
            result[key] = _display_payload(result[key], target)
    path = value.get("target_file") or value.get("file")
    name = value.get("target_symbol") or value.get("symbol")
    if path or name:
        expected_file, _, expected_symbol = target.partition("::")
        if (path and path != expected_file) or (name and name != expected_symbol):
            result["localization_status"] = "context_reference_not_localized_target"
    return result


def ground_answer_for_display(state, answer, json_block=None):
    """Run frozen entity grounding, then the separate target-consistency seam."""
    from core.answer_entity_grounding import ground_answer_for_display as ground_entities

    final, human, block, grounding = ground_entities(state, answer, json_block)
    control = getattr(state, "control_result", None)
    receipt = current_target_receipt(
        control, live_route=getattr(state, "live_route", None),
    )
    if receipt is None:
        # ANSWER.GROUND.LIVE.3: the answer string and the patch payload are one
        # grounded copy. This branch has already serialized the answer, so it
        # may not touch the block — a telemetry key added here would show up in
        # the patch and not in the answer. The probe receipt reaches the payload
        # earlier, in ``enforce_payload_target``, where both still agree.
        return final, human, block, grounding
    target = receipt["localized_target"]
    if isinstance(block, dict):
        block = _display_payload(block, target)
        block["localization_handoff"] = receipt
        attach_probe_telemetry_to_payload(
            getattr(state, "control_result", None), block
        )
        final = human = json.dumps(block, ensure_ascii=False, indent=2)
    else:
        final = human = _annotate_text(human, target)
        notice = f"CONTROL localization target: `{target}`. Other references do not replace this target without typed stronger evidence."
        if notice not in final:
            final = human = final.rstrip() + "\n\n" + notice
    return final, human, block, grounding


def ground_state_answer(state):
    final, human, block, grounding = ground_answer_for_display(
        state, getattr(state, "human_answer", "") or getattr(state, "final_answer", ""),
        getattr(state, "json_block", None),
    )
    state.final_answer = final
    state.human_answer = human
    if block is not None:
        state.json_block = block
    state.answer_entity_grounding = grounding
    return grounding
