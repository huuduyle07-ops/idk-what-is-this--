"""OPS.PATCH.2 — Explicit-Change Candidate Sandbox Validation.

Four questions stay separate, and this module owns exactly one of them:

``why consider this patch?``
    ``core.patch_basis`` — the typed basis (PATCH.BASIS.LIVE.1).

``where may it operate?``
    target/source grounding in ``core.control_engine``.

``is the candidate materializable and valid?``
    **this module**.

``may it write to the real repository?``
    existing patch safety, runtime authorization and human approval.

The gap this closes was found by the post-PATCH.BASIS black-box rerun.  An
explicit-change task routed correctly, received a legitimate
``explicit_change_request`` basis, and passed target/source grounding and patch
safety — and the final two-operation plan it presented as approval-ready was
internally incoherent: ``store.py`` passed ``priority=`` into a ``Task`` whose
``models.py`` was never changed.  Applying that exact plan to a disposable copy
made every existing test fail with ``TypeError: Task.__init__() got an
unexpected keyword argument 'priority'``.  No production gate had run the plan
anywhere before describing it as ready for a human to approve.

So the final candidate now has to prove it can be materialized and validated in
isolation before anything calls it approval-ready:

* the candidate is copied into a **disposable managed sandbox** built by the
  existing ``core.sandbox_self_evolution_runner`` primitive — no ``git stash``,
  ``git reset`` or ``git clean``, and no new sandbox subsystem;
* it is applied there with the **real** production plan primitive,
  ``patching.patch_plan_executor.apply_patch_plan``, so create/replace
  interaction, multi-file coherence and OPS.PATCH.1 byte semantics are the ones
  production actually uses;
* it is validated with the **repository's own** OPS.VALIDATE.1 command, the same
  string the surrounding run already selected, never a command this module
  guessed;
* the result is bound to the candidate's fingerprint, so a later refinement
  cannot inherit an earlier candidate's validation.

What this module is not.  It adds no model call and no network call, generates
no tests, installs no dependencies, invents no score, and never mutates the real
repository.  A passing candidate validation is emphatically *not* write
authority: ``explicit_change_request`` still requires human approval, exactly as
PATCH.BASIS.LIVE.1 left it.  And passing the repository's existing tests does
not prove the user's feature request was satisfied — old tests know nothing
about a new CLI flag — so this is a coherence/regression gate, not goal fidelity.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.sandbox_self_evolution_runner import (
    cleanup_managed_sandbox,
    create_managed_sandbox,
)
from core.validation_outcome import (
    CATEGORY_NO_VALIDATION_COMMAND,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
    is_inconclusive_category,
    outcome_reason,
)


PHASE_ID = "OPS.PATCH.2"

# ── Candidate validation vocabulary ──────────────────────────────────────────
#
# Deliberately the *same* three words OPS.VALIDATE.1 already established.  A
# fourth vocabulary would have to be mapped back onto this one by every reader,
# and the mapping is where "inconclusive" quietly becomes "passed".
CANDIDATE_VALIDATION_PASSED = VALIDATION_PASSED
CANDIDATE_VALIDATION_FAILED = VALIDATION_FAILED
CANDIDATE_VALIDATION_INCONCLUSIVE = VALIDATION_INCONCLUSIVE

CANDIDATE_VALIDATION_STATUSES: tuple[str, ...] = (
    CANDIDATE_VALIDATION_PASSED,
    CANDIDATE_VALIDATION_FAILED,
    CANDIDATE_VALIDATION_INCONCLUSIVE,
)

#: A historical explicit-change artifact carries no candidate-validation
#: metadata at all.  It is not "passed"; it is a run from before the gate
#: existed, and it says so (see :func:`candidate_validation_status_of_payload`).
CANDIDATE_VALIDATION_LEGACY_UNVALIDATED = "legacy_unvalidated"

# ── Sandbox apply vocabulary ─────────────────────────────────────────────────
SANDBOX_APPLY_NOT_ATTEMPTED = "not_attempted"
SANDBOX_APPLY_APPLIED = "applied"
SANDBOX_APPLY_FAILED = "failed"
SANDBOX_APPLY_UNAVAILABLE = "sandbox_unavailable"

SANDBOX_APPLY_STATUSES: tuple[str, ...] = (
    SANDBOX_APPLY_NOT_ATTEMPTED,
    SANDBOX_APPLY_APPLIED,
    SANDBOX_APPLY_FAILED,
    SANDBOX_APPLY_UNAVAILABLE,
)

# ── Categories this module contributes on top of OPS.VALIDATE.1's ────────────
CATEGORY_SANDBOX_UNAVAILABLE = "sandbox_unavailable"
CATEGORY_CANDIDATE_APPLY_FAILED = "candidate_apply_failed"
CATEGORY_NO_CANDIDATE = "no_candidate"
CATEGORY_CANDIDATE_VALIDATION_PASSED = "candidate_validation_passed"

#: The gate deliberately did not run — patch safety already refused the
#: candidate, or there was nothing to materialize.  Distinct from a sandbox that
#: was attempted and could not be built.
CATEGORY_CANDIDATE_VALIDATION_NOT_ATTEMPTED = "candidate_validation_not_attempted"

#: Categories that mean the sandbox could not establish a result.  They join the
#: OPS.VALIDATE.1 inconclusive set rather than replacing it.
CANDIDATE_INCONCLUSIVE_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_SANDBOX_UNAVAILABLE,
        CATEGORY_NO_CANDIDATE,
        CATEGORY_CANDIDATE_VALIDATION_NOT_ATTEMPTED,
    }
)

_CANDIDATE_INCONCLUSIVE_REASONS: dict[str, str] = {
    CATEGORY_SANDBOX_UNAVAILABLE: (
        "Candidate validation inconclusive: a disposable sandbox could not be "
        "materialized, so the candidate was never executed."
    ),
    CATEGORY_NO_CANDIDATE: (
        "Candidate validation inconclusive: there was no final patch candidate "
        "to materialize."
    ),
    CATEGORY_CANDIDATE_VALIDATION_NOT_ATTEMPTED: (
        "Candidate validation inconclusive: the candidate was never materialized."
    ),
}

# ── Baseline vocabulary ──────────────────────────────────────────────────────
#
# The baseline is the *existing* validation outcome the surrounding run already
# computed — this module never runs a second baseline of its own, so it adds no
# validation cost beyond the one candidate run.
BASELINE_UNAVAILABLE = "unavailable"

#: How much validation output travels in the bounded telemetry payload.  The
#: full log stays with the caller's existing artifact conventions.
MAX_OUTPUT_EXCERPT_CHARS = 2_000


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalized_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _excerpt(text: Any, limit: int = MAX_OUTPUT_EXCERPT_CHARS) -> str:
    body = str(text or "")
    if len(body) <= limit:
        return body
    return body[-limit:]


# ── Candidate identity ───────────────────────────────────────────────────────


def normalize_plan_operation(op: Any) -> dict[str, Any]:
    """The materially-significant view of one plan operation.

    Two operations with the same normalized view write the same bytes, so they
    are the same candidate for validation purposes.  ``file`` and
    ``relative_path`` are the two spellings the executor already accepts for the
    same field and collapse to one key here.
    """

    if not isinstance(op, Mapping):
        return {"op": "", "path": "", "invalid": _canonical_json(str(op))}
    normalized: dict[str, Any] = {
        "op": str(op.get("op") or "").strip(),
        "path": _normalized_path(op.get("relative_path") or op.get("file")),
    }
    for key in ("target_snippet", "patched_snippet", "content"):
        value = op.get(key)
        if isinstance(value, str):
            normalized[key] = value
    return normalized


def normalize_candidate_plan(plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, Sequence) or isinstance(plan, (str, bytes)):
        return []
    return [normalize_plan_operation(op) for op in plan]


def patch_plan_fingerprint(plan: Any) -> str:
    """Stable identity for one final patch candidate.

    ``sha256`` over canonical JSON — the same idiom the rest of the codebase
    already uses for receipt and authority fingerprints.  No new cryptographic
    subsystem, and nothing here is a secret.
    """

    return _fingerprint(normalize_candidate_plan(plan))


def patch_candidate_as_plan(candidate: Any) -> list[dict[str, Any]]:
    """Express a single-file ``patch_candidate`` as the one-op plan it is.

    A ``patch_candidate`` is a ``replace_snippet`` with one target and one
    replacement; writing it as such lets both explicit-change handoff shapes run
    through the same real ``apply_patch_plan`` primitive instead of gaining a
    second, differently-behaved application path.
    """

    if not isinstance(candidate, Mapping):
        return []
    path = _normalized_path(
        candidate.get("relative_path") or candidate.get("file")
    )
    target = candidate.get("target_snippet")
    patched = candidate.get("patched_snippet")
    if not path or not isinstance(target, str) or not isinstance(patched, str):
        return []
    return [
        {
            "op": "replace_snippet",
            "relative_path": path,
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


def candidate_plan_from_payload(block: Any) -> list[dict[str, Any]]:
    """The final candidate carried by a writer payload, in plan form."""

    if not isinstance(block, Mapping):
        return []
    plan = block.get("patch_plan")
    if isinstance(plan, list) and plan:
        return [dict(op) for op in plan if isinstance(op, Mapping)]
    return patch_candidate_as_plan(block.get("patch_candidate"))


def candidate_fingerprint_from_payload(block: Any) -> str:
    return patch_plan_fingerprint(candidate_plan_from_payload(block))


def candidate_validation_status_of_payload(block: Any) -> str:
    """What a payload's stored candidate validation says, legacy included.

    A run recorded before OPS.PATCH.2 has no such key.  It reads back as
    ``legacy_unvalidated`` — never ``passed`` — and historical artifacts are not
    rewritten to pretend otherwise.
    """

    if not isinstance(block, Mapping):
        return CANDIDATE_VALIDATION_LEGACY_UNVALIDATED
    status = str(block.get("candidate_validation_status") or "").strip()
    if status in CANDIDATE_VALIDATION_STATUSES:
        return status
    return CANDIDATE_VALIDATION_LEGACY_UNVALIDATED


def candidate_validation_is_current(block: Any, plan: Any = None) -> bool:
    """Is a payload's stored validation still bound to its current candidate?

    A refinement that replaces the plan changes its fingerprint, so the stored
    result stops matching and is stale by construction.  There is no path here
    that lets an earlier candidate's ``passed`` be reused for a later one.
    """

    if not isinstance(block, Mapping):
        return False
    if candidate_validation_status_of_payload(block) == (
        CANDIDATE_VALIDATION_LEGACY_UNVALIDATED
    ):
        return False
    recorded = str(block.get("candidate_validation_fingerprint") or "")
    if not recorded:
        return False
    current = (
        patch_plan_fingerprint(plan)
        if plan is not None
        else candidate_fingerprint_from_payload(block)
    )
    return recorded == current


# ── Baseline ─────────────────────────────────────────────────────────────────


def normalize_baseline_validation(preflight: Any) -> dict[str, str]:
    """Read the run's *existing* baseline outcome; never run a second one.

    ``baseline = passed`` next to ``candidate = failed`` is the field test's
    case and reads as a plain regression.  ``baseline = failed`` and
    ``baseline = inconclusive`` are preserved as distinct facts rather than
    being reconciled into a "no worse than baseline" equivalence, which this
    phase deliberately does not attempt.
    """

    if not isinstance(preflight, Mapping):
        return {"status": BASELINE_UNAVAILABLE, "category": ""}
    outcome = str(preflight.get("outcome") or "").strip()
    category = str(preflight.get("category") or "").strip()
    if outcome in CANDIDATE_VALIDATION_STATUSES:
        return {"status": outcome, "category": category}
    if not preflight.get("ran"):
        return {"status": BASELINE_UNAVAILABLE, "category": category}
    if is_inconclusive_category(category):
        return {"status": CANDIDATE_VALIDATION_INCONCLUSIVE, "category": category}
    ok = preflight.get("ok")
    if ok is True:
        return {"status": CANDIDATE_VALIDATION_PASSED, "category": category}
    if ok is False:
        return {"status": CANDIDATE_VALIDATION_FAILED, "category": category}
    return {"status": BASELINE_UNAVAILABLE, "category": category}


# ── Result ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CandidateSandboxValidation:
    """One final candidate's materialization + validation facts.

    Categorical throughout.  There is no score, no confidence and no delta: the
    reader is told what happened, not how good it was.
    """

    status: str
    category: str
    command: str
    fingerprint: str
    sandbox_apply_status: str
    baseline_status: str = BASELINE_UNAVAILABLE
    baseline_category: str = ""
    inconclusive_reason: str = ""
    apply_error: str = ""
    failed_op_index: int | None = None
    output_excerpt: str = ""
    sandbox_path: str = ""
    sandbox_cleanup_ok: bool = True
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == CANDIDATE_VALIDATION_PASSED

    @property
    def failed(self) -> bool:
        return self.status == CANDIDATE_VALIDATION_FAILED

    @property
    def inconclusive(self) -> bool:
        return self.status == CANDIDATE_VALIDATION_INCONCLUSIVE

    @property
    def approval_ready(self) -> bool:
        """Only a candidate that actually validated may be called ready.

        This is not, and never becomes, write authority: an
        ``explicit_change_request`` still reaches a human, and the human still
        decides.  ``approval_ready`` says the thing on the table survived its own
        repository's checks — nothing more.
        """

        return self.passed

    @property
    def reviewable(self) -> bool:
        """A failed candidate is still worth reading.

        Diagnostics are the point of running it: the reviewer gets to see the
        ``TypeError`` rather than a candidate that silently vanished.
        """

        return True

    def as_telemetry(self) -> dict[str, Any]:
        """Bounded facts only — no secrets, no full validation log."""

        return {
            "candidate_validation_status": self.status,
            "candidate_validation_category": self.category,
            "candidate_validation_command": self.command,
            "candidate_validation_fingerprint": self.fingerprint,
            "candidate_validation_inconclusive_reason": self.inconclusive_reason,
            "candidate_validation_reviewable": self.reviewable,
            "candidate_validation_output_excerpt": self.output_excerpt,
            "candidate_validation_timings": dict(self.timings),
            "baseline_validation_status": self.baseline_status,
            "baseline_validation_category": self.baseline_category,
            "sandbox_apply_status": self.sandbox_apply_status,
            "sandbox_apply_error": self.apply_error,
            "sandbox_failed_op_index": self.failed_op_index,
            "approval_ready": self.approval_ready,
        }


def describe_candidate_validation(result: CandidateSandboxValidation) -> str:
    """Human wording that never over-claims.

    "clean", "validated", "working" and "ready to apply" belong exclusively to a
    candidate that passed.
    """

    if result.passed:
        return (
            "Candidate materialized in a disposable sandbox and passed the "
            "repository's existing validation. It has not been applied to the "
            "real repository; human approval is still required."
        )
    if result.failed:
        if result.sandbox_apply_status == SANDBOX_APPLY_FAILED:
            return (
                "Candidate could not be materialized in a disposable sandbox. "
                "It has not been applied to the real repository."
            )
        return (
            "Candidate materialized in a disposable sandbox but failed "
            "repository validation. It has not been applied to the real "
            "repository."
        )
    return (
        "Candidate validation could not establish success. "
        + (result.inconclusive_reason or "")
    ).strip()


# ── Inconclusive constructor ─────────────────────────────────────────────────


def _inconclusive(
    *,
    category: str,
    command: str,
    fingerprint: str,
    sandbox_apply_status: str,
    baseline: Mapping[str, str],
    reason: str = "",
    timings: dict[str, float] | None = None,
    sandbox_cleanup_ok: bool = True,
    apply_error: str = "",
) -> CandidateSandboxValidation:
    text = (
        reason
        or _CANDIDATE_INCONCLUSIVE_REASONS.get(category)
        or outcome_reason(
            category,
            fallback="Candidate validation could not establish success.",
        )
    )
    return CandidateSandboxValidation(
        status=CANDIDATE_VALIDATION_INCONCLUSIVE,
        category=category,
        command=command,
        fingerprint=fingerprint,
        sandbox_apply_status=sandbox_apply_status,
        baseline_status=baseline.get("status", BASELINE_UNAVAILABLE),
        baseline_category=baseline.get("category", ""),
        inconclusive_reason=text,
        apply_error=apply_error,
        sandbox_cleanup_ok=sandbox_cleanup_ok,
        timings=timings or {},
    )


# ── The gate ─────────────────────────────────────────────────────────────────


def validate_candidate_in_sandbox(
    repo_path: str | Path,
    plan: Any,
    *,
    validation_command: str | None,
    baseline_validation: Any = None,
    sandbox_parent: str | Path | None = None,
    keep_sandbox: bool = False,
) -> CandidateSandboxValidation:
    """Materialize and validate one FINAL candidate in a disposable sandbox.

    The real repository is only ever read.  Every write — the candidate itself,
    ``__pycache__``, whatever the test runner leaves behind — happens inside a
    temporary managed sandbox that is deleted afterwards and never copied back.
    A failure anywhere in here (no sandbox, failed apply, failed validation,
    failed cleanup) leaves the real worktree exactly as it was found; no
    ``git stash``, ``git reset`` or ``git clean`` is involved at any point, so
    unrelated user work in a dirty tree survives untouched.

    Callers must run patch basis, target/source grounding and patch safety
    *first*: a plan the safety gate rejected is never executed here just to see
    what it would do.
    """

    baseline = normalize_baseline_validation(baseline_validation)
    operations = [dict(op) for op in (plan or []) if isinstance(op, Mapping)]
    fingerprint = patch_plan_fingerprint(operations)
    command = str(validation_command or "").strip()
    timings: dict[str, float] = {}

    if not operations:
        return _inconclusive(
            category=CATEGORY_NO_CANDIDATE,
            command=command,
            fingerprint=fingerprint,
            sandbox_apply_status=SANDBOX_APPLY_NOT_ATTEMPTED,
            baseline=baseline,
        )

    # OPS.VALIDATE.1 already decided what "validating this repository" means.
    # With no command there is nothing to execute, and building a sandbox to run
    # nothing in would spend real time to learn nothing.
    if not command:
        return _inconclusive(
            category=CATEGORY_NO_VALIDATION_COMMAND,
            command="",
            fingerprint=fingerprint,
            sandbox_apply_status=SANDBOX_APPLY_NOT_ATTEMPTED,
            baseline=baseline,
        )

    source_repo = Path(repo_path).expanduser() if repo_path else None
    if source_repo is None or not source_repo.is_dir():
        return _inconclusive(
            category=CATEGORY_SANDBOX_UNAVAILABLE,
            command=command,
            fingerprint=fingerprint,
            sandbox_apply_status=SANDBOX_APPLY_UNAVAILABLE,
            baseline=baseline,
            reason=(
                "Candidate validation inconclusive: the repository path is not "
                "a directory, so no sandbox could represent its state."
            ),
        )

    # 1. Disposable sandbox ------------------------------------------------
    #
    # The copy is of the working tree as it stands, which is the state the
    # candidate was produced against — not an unrelated HEAD checkout.
    started = time.time()
    try:
        temp_root = Path(
            tempfile.mkdtemp(
                prefix="cattus-candidate-",
                dir=str(sandbox_parent) if sandbox_parent else None,
            )
        )
    except OSError as exc:
        return _inconclusive(
            category=CATEGORY_SANDBOX_UNAVAILABLE,
            command=command,
            fingerprint=fingerprint,
            sandbox_apply_status=SANDBOX_APPLY_UNAVAILABLE,
            baseline=baseline,
            reason=(
                "Candidate validation inconclusive: no temporary sandbox "
                f"directory could be created ({type(exc).__name__})."
            ),
            timings={"sandbox_create_sec": round(time.time() - started, 4)},
        )

    sandbox_dir = temp_root / "repo"
    try:
        info = create_managed_sandbox(source_repo, sandbox_dir)
    except Exception as exc:
        info = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    timings["sandbox_create_sec"] = round(time.time() - started, 4)

    if not info.get("ok"):
        cleanup_started = time.time()
        cleanup_ok = _discard_sandbox(sandbox_dir, temp_root, keep=False)
        timings["cleanup_sec"] = round(time.time() - cleanup_started, 4)
        timings["total_sec"] = round(sum(timings.values()), 4)
        return _inconclusive(
            category=CATEGORY_SANDBOX_UNAVAILABLE,
            command=command,
            fingerprint=fingerprint,
            sandbox_apply_status=SANDBOX_APPLY_UNAVAILABLE,
            baseline=baseline,
            reason=(
                "Candidate validation inconclusive: the disposable sandbox "
                f"could not be materialized ({info.get('error') or 'unknown error'})."
            ),
            timings=timings,
            sandbox_cleanup_ok=cleanup_ok,
        )

    sandbox_root = Path(info["sandbox_path"])

    # 2. Apply + validate with the real production primitives ---------------
    #
    # ``apply_patch_plan`` is imported here rather than at module import time so
    # this module can be read (and its identity/vocabulary helpers used) without
    # pulling in the executor's own import graph.
    from patching.patch_plan_executor import apply_patch_plan

    apply_started = time.time()
    try:
        result = apply_patch_plan(
            str(sandbox_root),
            list(operations),
            validation_command=command,
        )
    except Exception as exc:  # pragma: no cover - the primitive never raises
        timings["candidate_apply_and_validation_sec"] = round(
            time.time() - apply_started, 4
        )
        cleanup_started = time.time()
        cleanup_ok = _discard_sandbox(sandbox_root, temp_root, keep=keep_sandbox)
        timings["cleanup_sec"] = round(time.time() - cleanup_started, 4)
        timings["total_sec"] = round(sum(timings.values()), 4)
        return _inconclusive(
            category=CATEGORY_SANDBOX_UNAVAILABLE,
            command=command,
            fingerprint=fingerprint,
            sandbox_apply_status=SANDBOX_APPLY_UNAVAILABLE,
            baseline=baseline,
            reason=(
                "Candidate validation inconclusive: the sandbox apply primitive "
                f"raised {type(exc).__name__}."
            ),
            timings=timings,
            sandbox_cleanup_ok=cleanup_ok,
            apply_error=f"{type(exc).__name__}: {exc}",
        )
    # Apply and validation share one measured span because they happen inside
    # one call to the production primitive; splitting them would mean
    # re-implementing OPS.VALIDATE.1's classification here.
    timings["candidate_apply_and_validation_sec"] = round(
        time.time() - apply_started, 4
    )

    # 3. Throw the sandbox away --------------------------------------------
    #
    # Everything validation produced in there — caches, build output, temp
    # artifacts — dies with it.  Nothing is copied back.
    cleanup_started = time.time()
    cleanup_ok = _discard_sandbox(sandbox_root, temp_root, keep=keep_sandbox)
    timings["cleanup_sec"] = round(time.time() - cleanup_started, 4)
    timings["total_sec"] = round(sum(timings.values()), 4)

    return _classify_apply_result(
        result,
        command=command,
        fingerprint=fingerprint,
        baseline=baseline,
        timings=timings,
        sandbox_path="" if cleanup_ok and not keep_sandbox else str(sandbox_root),
        cleanup_ok=cleanup_ok,
    )


def _classify_apply_result(
    result: Mapping[str, Any],
    *,
    command: str,
    fingerprint: str,
    baseline: Mapping[str, str],
    timings: dict[str, float],
    sandbox_path: str,
    cleanup_ok: bool,
) -> CandidateSandboxValidation:
    """Map one ``apply_patch_plan`` result onto the three-way candidate answer.

    The executor already distinguishes a failed op from a failed validation, and
    already carries OPS.VALIDATE.1's ``validation_outcome``; this reads those
    facts rather than re-deriving them.
    """

    failed_op = result.get("failed_op")
    failed_index = result.get("failed_op_index")
    validation_stage = bool(
        isinstance(failed_op, Mapping) and failed_op.get("op") == "validation"
    )
    output_excerpt = _excerpt(result.get("validation_output"))

    common: dict[str, Any] = {
        "command": str(result.get("validation_command") or command),
        "fingerprint": fingerprint,
        "baseline_status": baseline.get("status", BASELINE_UNAVAILABLE),
        "baseline_category": baseline.get("category", ""),
        "output_excerpt": output_excerpt,
        "sandbox_path": sandbox_path,
        "sandbox_cleanup_ok": cleanup_ok,
        "timings": timings,
    }

    # The candidate could not be written into a pristine copy of its own
    # repository: a snippet that is not there verbatim, a create over an
    # existing file, a path that escapes the root.  That is a failed candidate,
    # not an infrastructure problem.
    if not result.get("success") and not validation_stage:
        return CandidateSandboxValidation(
            status=CANDIDATE_VALIDATION_FAILED,
            category=CATEGORY_CANDIDATE_APPLY_FAILED,
            sandbox_apply_status=SANDBOX_APPLY_FAILED,
            apply_error=str(result.get("error") or ""),
            failed_op_index=failed_index if isinstance(failed_index, int) else None,
            **common,
        )

    if result.get("success"):
        if result.get("validation_ok") is True:
            return CandidateSandboxValidation(
                status=CANDIDATE_VALIDATION_PASSED,
                category=CATEGORY_CANDIDATE_VALIDATION_PASSED,
                sandbox_apply_status=SANDBOX_APPLY_APPLIED,
                **common,
            )
        # A success with nothing validated establishes nothing.
        return CandidateSandboxValidation(
            status=CANDIDATE_VALIDATION_INCONCLUSIVE,
            category=CATEGORY_NO_VALIDATION_COMMAND,
            sandbox_apply_status=SANDBOX_APPLY_APPLIED,
            inconclusive_reason=outcome_reason(CATEGORY_NO_VALIDATION_COMMAND),
            **common,
        )

    # Applied, then validated — and the validation is the thing that ended it.
    info = result.get("validation_info")
    category = str(
        (info or {}).get("category") if isinstance(info, Mapping) else ""
    )
    outcome = str(result.get("validation_outcome") or "")
    if outcome not in CANDIDATE_VALIDATION_STATUSES:
        outcome = (
            CANDIDATE_VALIDATION_INCONCLUSIVE
            if is_inconclusive_category(category)
            else CANDIDATE_VALIDATION_FAILED
        )
    return CandidateSandboxValidation(
        status=outcome,
        category=category,
        sandbox_apply_status=SANDBOX_APPLY_APPLIED,
        inconclusive_reason=(
            outcome_reason(
                category,
                fallback="Candidate validation could not establish success.",
            )
            if outcome == CANDIDATE_VALIDATION_INCONCLUSIVE
            else ""
        ),
        failed_op_index=failed_index if isinstance(failed_index, int) else None,
        **common,
    )


def _discard_sandbox(sandbox_root: Path, temp_root: Path, *, keep: bool) -> bool:
    """Delete the sandbox, then its temp parent. Never touches the real repo.

    Cleanup uses the existing marker-guarded ``cleanup_managed_sandbox``, which
    refuses any directory that is not a managed sandbox.  A cleanup failure is
    recorded and otherwise ignored: a leftover temp directory is untidy, while
    reacting to it would be the only way this path could reach outside itself.
    """

    if keep:
        return True
    ok = True
    try:
        cleaned, _reason = cleanup_managed_sandbox(sandbox_root)
        ok = bool(cleaned)
    except Exception:
        ok = False
    try:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)
    except Exception:
        ok = False
    return ok and not temp_root.exists()


__all__ = [
    "PHASE_ID",
    "CANDIDATE_VALIDATION_PASSED",
    "CANDIDATE_VALIDATION_FAILED",
    "CANDIDATE_VALIDATION_INCONCLUSIVE",
    "CANDIDATE_VALIDATION_STATUSES",
    "CANDIDATE_VALIDATION_LEGACY_UNVALIDATED",
    "SANDBOX_APPLY_NOT_ATTEMPTED",
    "SANDBOX_APPLY_APPLIED",
    "SANDBOX_APPLY_FAILED",
    "SANDBOX_APPLY_UNAVAILABLE",
    "SANDBOX_APPLY_STATUSES",
    "CATEGORY_SANDBOX_UNAVAILABLE",
    "CATEGORY_CANDIDATE_APPLY_FAILED",
    "CATEGORY_NO_CANDIDATE",
    "CATEGORY_CANDIDATE_VALIDATION_PASSED",
    "CATEGORY_CANDIDATE_VALIDATION_NOT_ATTEMPTED",
    "CANDIDATE_INCONCLUSIVE_CATEGORIES",
    "BASELINE_UNAVAILABLE",
    "MAX_OUTPUT_EXCERPT_CHARS",
    "CandidateSandboxValidation",
    "normalize_plan_operation",
    "normalize_candidate_plan",
    "patch_plan_fingerprint",
    "patch_candidate_as_plan",
    "candidate_plan_from_payload",
    "candidate_fingerprint_from_payload",
    "candidate_validation_status_of_payload",
    "candidate_validation_is_current",
    "normalize_baseline_validation",
    "describe_candidate_validation",
    "validate_candidate_in_sandbox",
]
