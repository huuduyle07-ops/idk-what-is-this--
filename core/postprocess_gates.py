from __future__ import annotations

from typing import Any, Callable


RetryStructuredPatchJsonFn = Callable[[Any, str], str]
FinalizeAnswerFn = Callable[[Any, str], None]
MissingJsonCallbackFn = Callable[[Any, str], None]


def _load_patch_gates() -> dict[str, Callable[..., Any]]:
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

    gates = _load_patch_gates()
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
    gates["reject_ungrounded_patch"](state)
    gates["reject_ungrounded_candidate_quotes"](state)
    return state
