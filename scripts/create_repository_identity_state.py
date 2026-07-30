"""Create or advance the explicit INDEX.1D.2B identity-state artifact.

The command changes only ``identity_state.json`` plus its zero-content,
OS-coordinated ``.identity_state.lock`` sibling. It does not scan source files,
invoke indexers or graph builders, access a database or manifest, call a model,
migrate legacy namespaces, or run Activation Graph behavior.

No timestamp or human decision is inferred.  A confirmation or architecture
epoch therefore requires explicit ``--confirmed-at``, ``--confirmed-by``,
``--reason``, and decision arguments.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.repository_identity_state import (  # noqa: E402
    DECISION_NEW_ARCHITECTURE_EPOCH,
    DEFAULT_REPOSITORY_INTELLIGENCE_ROOT,
    HUMAN_IDENTITY_DECISIONS,
    IDENTITY_STATUS_UNINITIALIZED,
    IdentityStateError,
    append_legacy_namespace_warnings,
    apply_human_identity_decision,
    apply_major_change_candidate,
    classify_major_change_candidate,
    initialize_repository_identity_state,
    load_repository_identity_state,
    save_repository_identity_state,
)


def _failure(
    *,
    action: str,
    errors: list[str] | tuple[str, ...],
    state_result: Any = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "action": action,
        "errors": list(errors),
        "result": (
            state_result.to_dict()
            if hasattr(state_result, "to_dict")
            else state_result
        ),
    }


def run_create_repository_identity_state(
    *,
    repo_path: str,
    repository_intelligence_root: str = str(
        DEFAULT_REPOSITORY_INTELLIGENCE_ROOT
    ),
    candidate_project_tag: str | None = None,
    legacy_namespace_evidence: tuple[str, ...] = (),
    decision: str | None = None,
    project_tag: str | None = None,
    confirmed_at: str | None = None,
    confirmed_by: str | None = None,
    reason: str | None = None,
    new_architecture_epoch: int | None = None,
    declare_major_change: bool = False,
    major_change_signals: tuple[str, ...] = (),
    major_change_evidence: tuple[str, ...] = (),
    minimum_signal_count: int | None = None,
    detected_at: str | None = None,
) -> dict[str, Any]:
    """Create the confirmation gate or apply one explicit safe transition."""
    actions: list[str] = []
    loaded = load_repository_identity_state(
        repo_path,
        repository_intelligence_root=repository_intelligence_root,
    )
    if not loaded.valid:
        return _failure(
            action="load_blocked",
            errors=loaded.errors,
            state_result=loaded,
        )

    current = loaded.state
    initialized_here = loaded.status == IDENTITY_STATUS_UNINITIALIZED
    if initialized_here:
        try:
            initial = initialize_repository_identity_state(
                repo_path,
                candidate_project_tag=candidate_project_tag,
                legacy_namespace_evidence=legacy_namespace_evidence,
            )
        except (
            IdentityStateError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            return _failure(
                action="initialization_failed",
                errors=[str(exc)],
                state_result=current,
            )
        saved = save_repository_identity_state(
            initial,
            identity=repo_path,
            repository_intelligence_root=repository_intelligence_root,
            expected_revision=0,
        )
        if not saved.ok:
            return _failure(
                action="initialize_failed",
                errors=saved.errors,
                state_result=saved,
        )
        actions.append("initial_confirmation_required")
        if legacy_namespace_evidence:
            actions.append("legacy_namespace_warnings_recorded")
        current = initial

    if legacy_namespace_evidence and not initialized_here:
        warning_transition = append_legacy_namespace_warnings(
            current,
            legacy_namespace_evidence,
        )
        if not warning_transition.valid:
            return _failure(
                action="legacy_namespace_warning_failed",
                errors=(
                    warning_transition.errors
                    or (warning_transition.reason,)
                ),
                state_result=warning_transition,
            )
        if warning_transition.applied:
            saved = save_repository_identity_state(
                warning_transition.state,
                identity=repo_path,
                repository_intelligence_root=(
                    repository_intelligence_root
                ),
                expected_revision=current.state_revision,
            )
            if not saved.ok:
                return _failure(
                    action="legacy_namespace_warning_save_failed",
                    errors=saved.errors,
                    state_result=saved,
                )
            current = warning_transition.state
        actions.append(warning_transition.outcome)

    if declare_major_change:
        if not detected_at:
            return _failure(
                action="major_change_declaration_failed",
                errors=[
                    "detected_at is required for a major-change declaration"
                ],
                state_result=current,
            )
        thresholds = (
            {"minimum_signal_count": minimum_signal_count}
            if minimum_signal_count is not None
            else None
        )
        classification = classify_major_change_candidate(
            signals=major_change_signals,
            thresholds=thresholds,
        )
        transition = apply_major_change_candidate(
            current,
            classification,
            detected_at=detected_at,
            evidence=major_change_evidence,
        )
        if not transition.valid:
            return _failure(
                action="major_change_declaration_failed",
                errors=transition.errors or (transition.reason,),
                state_result=transition,
            )
        if transition.applied:
            saved = save_repository_identity_state(
                transition.state,
                identity=repo_path,
                repository_intelligence_root=(
                    repository_intelligence_root
                ),
                expected_revision=current.state_revision,
            )
            if not saved.ok:
                return _failure(
                    action="major_change_save_failed",
                    errors=saved.errors,
                    state_result=saved,
                )
            actions.append(
                "major_change_confirmation_required"
            )
            current = transition.state
        else:
            actions.append("no_major_change_candidate")

    if decision is not None:
        transition = apply_human_identity_decision(
            current,
            decision,
            confirmed_at=confirmed_at,
            confirmed_by=confirmed_by,
            reason=reason,
            confirmed_project_tag=project_tag,
            new_architecture_epoch=new_architecture_epoch,
        )
        if not transition.valid:
            return _failure(
                action="human_decision_failed",
                errors=transition.errors or (transition.reason,),
                state_result=transition,
            )
        if transition.applied:
            saved = save_repository_identity_state(
                transition.state,
                identity=repo_path,
                repository_intelligence_root=(
                    repository_intelligence_root
                ),
                expected_revision=current.state_revision,
            )
            if not saved.ok:
                return _failure(
                    action="human_decision_save_failed",
                    errors=saved.errors,
                    state_result=saved,
                )
            actions.append(transition.outcome)
            current = transition.state
        else:
            # new_project and reject_or_defer are report-only outcomes.
            actions.append(transition.outcome)
            return {
                "ok": True,
                "actions": actions,
                "artifact_changed_by_decision": False,
                "rebinding_required": transition.rebinding_required,
                "path": loaded.path,
                "state": current.to_dict(),
                "decision_report": transition.to_dict(),
            }

    final = load_repository_identity_state(
        repo_path,
        repository_intelligence_root=repository_intelligence_root,
    )
    return {
        "ok": final.valid,
        "actions": actions,
        "artifact_changed_by_decision": bool(
            decision is not None
            and actions
            and actions[-1]
            not in {
                "repository_identity_rebinding_required",
                "confirmation_deferred",
            }
        ),
        "rebinding_required": False,
        "path": final.path,
        "state": final.state.to_dict(),
        "errors": list(final.errors),
    }


def _print_summary(result: dict[str, Any]) -> None:
    print("INDEX.1D.2B - Repository Identity State")
    print("=" * 44)
    print(f"OK      : {result.get('ok', False)}")
    print(f"Actions : {', '.join(result.get('actions') or []) or '(none)'}")
    print(f"Path    : {result.get('path') or '(none)'}")
    state = result.get("state") or {}
    if state:
        print(f"Status  : {state.get('identity_status')}")
        print(f"Epoch   : {state.get('architecture_epoch')}")
        print(f"Scope   : {state.get('active_index_scope')}")
    for error in result.get("errors") or []:
        print(f"Error   : {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create or advance the human-confirmed canonical identity state. "
            "No indexing, graph runtime, DB, manifest, model, or migration "
            "operation is performed."
        )
    )
    parser.add_argument("--repo-path", required=True)
    parser.add_argument(
        "--repository-intelligence-root",
        default=str(DEFAULT_REPOSITORY_INTELLIGENCE_ROOT),
    )
    parser.add_argument("--candidate-project-tag")
    parser.add_argument(
        "--legacy-namespace",
        action="append",
        default=[],
        dest="legacy_namespaces",
    )
    parser.add_argument(
        "--decision",
        choices=HUMAN_IDENTITY_DECISIONS,
    )
    parser.add_argument("--project-tag")
    parser.add_argument("--confirmed-at")
    parser.add_argument("--confirmed-by")
    parser.add_argument("--reason")
    parser.add_argument("--new-architecture-epoch", type=int)
    parser.add_argument("--declare-major-change", action="store_true")
    parser.add_argument(
        "--major-change-signal",
        action="append",
        default=[],
        dest="major_change_signals",
    )
    parser.add_argument(
        "--major-change-evidence",
        action="append",
        default=[],
        dest="major_change_evidence",
    )
    parser.add_argument("--minimum-signal-count", type=int)
    parser.add_argument("--detected-at")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if (
        args.decision == DECISION_NEW_ARCHITECTURE_EPOCH
        and args.new_architecture_epoch is None
    ):
        parser.error(
            "--new-architecture-epoch is required for that decision"
        )
    result = run_create_repository_identity_state(
        repo_path=args.repo_path,
        repository_intelligence_root=(
            args.repository_intelligence_root
        ),
        candidate_project_tag=args.candidate_project_tag,
        legacy_namespace_evidence=tuple(args.legacy_namespaces),
        decision=args.decision,
        project_tag=args.project_tag,
        confirmed_at=args.confirmed_at,
        confirmed_by=args.confirmed_by,
        reason=args.reason,
        new_architecture_epoch=args.new_architecture_epoch,
        declare_major_change=args.declare_major_change,
        major_change_signals=tuple(args.major_change_signals),
        major_change_evidence=tuple(args.major_change_evidence),
        minimum_signal_count=args.minimum_signal_count,
        detected_at=args.detected_at,
    )
    if args.json:
        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        _print_summary(result)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
