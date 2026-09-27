from __future__ import annotations

from typing import Any, Callable


RetryStructuredPatchJsonFn = Callable[[Any, str], str]
FinalizeAnswerFn = Callable[[Any, str], None]
MissingJsonCallbackFn = Callable[[Any, str], None]


def _load_patch_gates() -> dict[str, Callable[..., Any]]:
    from core.control_engine import reject_ungrounded_control_patch
    from patching.patch_gates import (
        collect_patch_repair_reasons,
        normalize_patch_plan_schema,
        promote_go_missing_import_candidate_to_patch_plan,
        promote_ts_duplicate_import_candidate_to_patch_plan,
        promote_ts_missing_import_candidate_to_patch_plan,
        reject_ungrounded_candidate_quotes,
        reject_ungrounded_patch,
    )

    return {
        "reject_ungrounded_control_patch": reject_ungrounded_control_patch,
        "collect_patch_repair_reasons": collect_patch_repair_reasons,
        "normalize_patch_plan_schema": normalize_patch_plan_schema,
        "promote_go_missing_import_candidate_to_patch_plan": (
            promote_go_missing_import_candidate_to_patch_plan
        ),
        "promote_ts_duplicate_import_candidate_to_patch_plan": (
            promote_ts_duplicate_import_candidate_to_patch_plan
        ),
        "promote_ts_missing_import_candidate_to_patch_plan": (
            promote_ts_missing_import_candidate_to_patch_plan
        ),
        "reject_ungrounded_candidate_quotes": reject_ungrounded_candidate_quotes,
        "reject_ungrounded_patch": reject_ungrounded_patch,
    }


def _apply_repaired_answer(
    state: Any,
    repaired_answer: str,
    finalize_answer_fn: FinalizeAnswerFn | None,
) -> None:
    if finalize_answer_fn is None:
        raise RuntimeError(
            "finalize_answer_fn is required when applying repaired patch JSON."
        )
    finalize_answer_fn(state, repaired_answer)


def run_postprocess_gate_battery(
    state: Any,
    *,
    reviewed_answer: str = "",
    retry_structured_patch_json_fn: RetryStructuredPatchJsonFn | None = None,
    finalize_answer_fn: FinalizeAnswerFn | None = None,
    on_missing_json_after_retries_fn: MissingJsonCallbackFn | None = None,
    mode_label: str | None = None,
) -> Any:
    """Run the shared CLI/web patch-result post-processing gate sequence.

    The order intentionally mirrors the former duplicated blocks in
    ``main.py`` and ``web/runner.py``, including the repeated TS promotion
    calls that were present around both retry branches. Model-backed retry and
    finalization stay caller-injected so this module does not import model or
    web application code.
    """
    del mode_label  # Reserved for caller diagnostics without changing behavior.

    # WAITER.LIVE.1 — this battery exists to repair, retry and promote *patch*
    # payloads.  On a read-only route there is no patch to repair, and its
    # "no JSON found -> retry structured JSON repair" branch would spend model
    # turns badgering a prose answer into a patch schema nobody asked for.
    from core.live_task_routing import route_is_read_only

    if route_is_read_only(getattr(state, "live_route", None)):
        return state

    gates = _load_patch_gates()
    from core.localization_handoff import enforce_payload_target

    enforce_payload_target(
        getattr(state, "control_result", None), getattr(state, "json_block", None),
        live_route=getattr(state, "live_route", None),
    )
    # CONTROL.SAFETY.LIVE.1: reject authority laundering before any structural
    # repair retry can spend another existing model turn on an ungrounded patch.
    gates["reject_ungrounded_control_patch"](state)
    promote_go = gates["promote_go_missing_import_candidate_to_patch_plan"]
    promote_ts_duplicate = gates[
        "promote_ts_duplicate_import_candidate_to_patch_plan"
    ]
    promote_ts_missing = gates["promote_ts_missing_import_candidate_to_patch_plan"]

    promote_go(state)
    promote_ts_duplicate(state)
    promote_ts_missing(state)

    repair_reasons = gates["collect_patch_repair_reasons"](state)
    if repair_reasons:
        print("\U0001f501 Patch issue detected \u2192 retrying JSON repair once:")
        for reason in repair_reasons:
            print(reason)

        if retry_structured_patch_json_fn is not None:
            repaired = retry_structured_patch_json_fn(
                state,
                state.final_answer + "\n\n" + "\n\n".join(repair_reasons),
            )
            _apply_repaired_answer(state, repaired, finalize_answer_fn)
            promote_go(state)

    promote_ts_duplicate(state)
    promote_ts_missing(state)

    if (
        getattr(state, "mode", None) == "reviewer"
        and not getattr(state, "json_block", None)
    ):
        print(
            "\U0001f501 No JSON found \u2192 retrying structured JSON repair once..."
        )
        if retry_structured_patch_json_fn is not None:
            repaired = retry_structured_patch_json_fn(state, reviewed_answer)
            _apply_repaired_answer(state, repaired, finalize_answer_fn)
            promote_go(state)

    promote_ts_duplicate(state)
    promote_ts_missing(state)

    if (
        not getattr(state, "json_block", None)
        and on_missing_json_after_retries_fn is not None
    ):
        on_missing_json_after_retries_fn(state, reviewed_answer)

    gates["normalize_patch_plan_schema"](state)
    enforce_payload_target(
        getattr(state, "control_result", None), getattr(state, "json_block", None),
        live_route=getattr(state, "live_route", None),
    )
    gates["reject_ungrounded_control_patch"](state)
    gates["reject_ungrounded_patch"](state)
    gates["reject_ungrounded_candidate_quotes"](state)
    return state
