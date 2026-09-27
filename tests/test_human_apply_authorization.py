"""EXEC.APPROVAL.LIVE.1 — human Apply binding and live acceptance matrix."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from flask import Flask

from core.candidate_sandbox_validation import patch_plan_fingerprint
from core.execution_eligibility_policy import (
    ELIGIBLE,
    INELIGIBLE,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
)
from core.human_apply_authorization import (
    AUTHORIZATION_AUTHORIZED,
    AUTHORIZATION_DENIED,
    DENIAL_APPROVAL_MISSING,
    DENIAL_CANDIDATE_MISMATCH,
    DENIAL_ELIGIBILITY_RECEIPT_STALE,
    DENIAL_INCONSISTENT_INPUT,
    DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE,
    DENIAL_PATCH_SAFETY_MISMATCH,
    DENIAL_REPOSITORY_IDENTITY_MISMATCH,
    DENIAL_SOURCE_STATE_STALE,
    FRESHNESS_CURRENT,
    FRESHNESS_STALE,
    HUMAN_ACTION_APPLY,
    PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
    authorize_human_apply,
    build_human_apply_review_receipt,
    eligibility_assessment_fingerprint,
    human_apply_guardrails,
)
from core.patch_safety import evaluate_patch_safety
from web.routes.patch_routes import bp as patch_routes_bp


PROBE = "1" * 64
CHECK_SET = "2" * 64


def _plan(
    target: str = "app.py", old: str = "value = 'old'\n", new: str = "value = 'new'\n"
) -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": target,
            "target_snippet": old,
            "patched_snippet": new,
        }
    ]


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _eligible_payload(repo: Path, plan: list[dict]) -> tuple[dict, dict]:
    candidate = patch_plan_fingerprint(plan)
    assessment = {
        "policy_profile": PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
        "eligibility_status": ELIGIBLE,
        "satisfied_requirements": [],
        "unsatisfied_requirements": [],
        "blocking_reasons": [],
        "accepted_conflicts": ["defect_preservation_oracle"],
        "accepted_limitations": ["full_validation_budget_exhausted"],
        "candidate_fingerprint": candidate,
        "probe_fingerprint": PROBE,
        "targeted_validation_fingerprint": CHECK_SET,
        "patch_safety_binding": candidate,
        "evidence_freshness": "current",
        "authority_effect": "none",
    }
    assessment["assessment_fingerprint"] = eligibility_assessment_fingerprint(
        assessment
    )
    payload = {
        "patch_basis": "grounded_defect",
        "patch_plan": plan,
        "execution_eligibility_profile": (
            PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW
        ),
        "execution_eligibility_status": ELIGIBLE,
        "execution_eligibility_profiles": {
            PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW: assessment
        },
        "human_review_eligible": True,
        "execution_authorized": False,
        "auto_apply_allowed": False,
        "patch_applied": False,
    }
    safety = evaluate_patch_safety(
        [op["relative_path"] for op in plan], project_root=repo
    )
    review = build_human_apply_review_receipt(
        payload=payload,
        repo_path=repo,
        patch_safety_verdict=safety,
        policy_profile=PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    )
    payload.update(review.as_payload_fields())
    return payload, safety


def _explicit_payload(repo: Path, plan: list[dict]) -> tuple[dict, dict]:
    payload = {
        "patch_basis": "explicit_change_request",
        "patch_plan": plan,
        "approval_ready": True,
        "human_review_eligible": False,
    }
    safety = evaluate_patch_safety(
        [op["relative_path"] for op in plan], project_root=repo
    )
    review = build_human_apply_review_receipt(
        payload=payload,
        repo_path=repo,
        patch_safety_verdict=safety,
        policy_profile=PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
    )
    payload.update(review.as_payload_fields())
    return payload, safety


def _authorize(payload: dict, repo: Path, safety: dict, **overrides):
    review = payload.get("human_apply_review") or {}
    values = {
        "human_action_kind": HUMAN_ACTION_APPLY,
        "approved_candidate_fingerprint": review.get(
            "candidate_fingerprint", patch_plan_fingerprint(payload["patch_plan"])
        ),
        "approved_eligibility_receipt_fingerprint": review.get(
            "eligibility_receipt_fingerprint", ""
        ),
        "allow_legacy_explicit_change": False,
    }
    values.update(overrides)
    return authorize_human_apply(
        payload=payload,
        repo_path=repo,
        patch_safety_verdict=safety,
        **values,
    )


def _app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(patch_routes_bp)
    return app


def _post_plan(client, repo: Path, payload: dict):
    review = payload.get("human_apply_review") or {}
    return client.post(
        "/apply_patch_plan",
        data={
            "repo_path": str(repo),
            "patch": json.dumps(payload),
            "apply_policy": "ask",
            "patch_style": "balanced",
            "human_action_kind": HUMAN_ACTION_APPLY,
            "approved_candidate_fingerprint": review.get(
                "candidate_fingerprint", ""
            ),
            "approved_eligibility_receipt_fingerprint": review.get(
                "eligibility_receipt_fingerprint", ""
            ),
        },
    )


def test_eligibility_without_approval_is_not_authorized(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())

    result = _authorize(payload, tmp_path, safety, human_action_kind="")

    assert payload["human_review_eligible"] is True
    assert payload["human_approval_received"] is False
    assert result.authorization_status == AUTHORIZATION_DENIED
    assert result.denial_reason == DENIAL_APPROVAL_MISSING
    assert result.authorized is False


def test_approval_with_ineligible_policy_is_denied(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())
    assessment = payload["execution_eligibility_profiles"][
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW
    ]
    assessment["eligibility_status"] = INELIGIBLE
    assessment["assessment_fingerprint"] = eligibility_assessment_fingerprint(
        assessment
    )
    payload["execution_eligibility_status"] = INELIGIBLE
    payload["human_review_eligible"] = False

    result = _authorize(payload, tmp_path, safety)

    assert result.human_approval_received is True
    assert result.authorized is False
    assert result.denial_reason == DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE


def test_eligible_approved_and_fresh_is_authorized(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())

    result = _authorize(payload, tmp_path, safety)

    assert result.authorization_status == AUTHORIZATION_AUTHORIZED
    assert result.human_approval_received is True
    assert result.freshness_status == FRESHNESS_CURRENT
    assert result.authority_source == "manual_apply_action"
    assert result.candidate_fingerprint == result.approved_candidate_fingerprint


def test_candidate_refinement_cannot_inherit_c1_approval(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())
    c1 = payload["human_apply_review"]["candidate_fingerprint"]
    payload["patch_plan"] = _plan(new="value = 'refined'\n")
    c2_safety = evaluate_patch_safety(["app.py"], project_root=tmp_path)

    result = _authorize(
        payload,
        tmp_path,
        c2_safety,
        approved_candidate_fingerprint=c1,
    )

    assert result.denial_reason == DENIAL_CANDIDATE_MISMATCH
    assert result.authorized is False
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "value = 'old'\n"


def test_eligibility_receipt_mismatch_is_denied(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())

    result = _authorize(
        payload,
        tmp_path,
        safety,
        approved_eligibility_receipt_fingerprint="0" * 64,
    )

    assert result.denial_reason == DENIAL_ELIGIBILITY_RECEIPT_STALE
    assert result.authorized is False


def test_source_changed_since_review_records_approval_but_denies_authority(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())
    _write(tmp_path, "app.py", "value = 'manual edit'\n")

    result = _authorize(payload, tmp_path, safety)

    assert result.human_approval_received is True
    assert result.freshness_status == FRESHNESS_STALE
    assert result.denial_reason == DENIAL_SOURCE_STATE_STALE
    assert result.authorized is False


def test_unrelated_repository_change_does_not_invalidate_known_path_state(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _eligible_payload(tmp_path, _plan())
    _write(tmp_path, "unrelated.txt", "new unrelated bytes\n")

    result = _authorize(payload, tmp_path, safety)

    assert result.authorized is True


def test_probe_and_targeted_check_source_bindings_are_revalidated(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    _write(tmp_path, "tests_existing.py", "def test_old():\n    assert True\n")
    _write(tmp_path, "probe_contract.txt", "expected relation v1\n")
    payload, safety = _eligible_payload(tmp_path, _plan())
    payload["check_oracle_assessments"] = [
        {"check_path": "tests_existing.py", "check_source_sha256": "3" * 64}
    ]
    review = build_human_apply_review_receipt(
        payload=payload,
        repo_path=tmp_path,
        patch_safety_verdict=safety,
        policy_profile=PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
        additional_source_paths=("probe_contract.txt",),
    )
    payload.update(review.as_payload_fields())
    _write(tmp_path, "tests_existing.py", "def test_old():\n    assert False\n")

    result = _authorize(payload, tmp_path, safety)

    assert result.denial_reason == DENIAL_SOURCE_STATE_STALE
    assert result.authorized is False


def test_repository_identity_mismatch_is_denied(tmp_path):
    reviewed = tmp_path / "reviewed"
    other = tmp_path / "other"
    reviewed.mkdir()
    other.mkdir()
    _write(reviewed, "app.py", "value = 'old'\n")
    _write(other, "app.py", "value = 'old'\n")
    payload, _ = _eligible_payload(reviewed, _plan())
    other_safety = evaluate_patch_safety(["app.py"], project_root=other)

    result = _authorize(payload, other, other_safety)

    assert result.denial_reason == DENIAL_REPOSITORY_IDENTITY_MISMATCH
    assert result.authorized is False


def test_human_apply_cannot_bypass_patch_safety(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, _ = _eligible_payload(tmp_path, _plan())
    blocked = {
        "ok": False,
        "blocked_paths": [{"path": "app.py", "category": "protected"}],
        "reasons": ["blocked"],
    }

    result = _authorize(payload, tmp_path, blocked)

    assert result.denial_reason == DENIAL_PATCH_SAFETY_MISMATCH
    assert result.authorized is False


def test_t4_explicit_change_uses_same_exact_apply_boundary_without_probe(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, safety = _explicit_payload(tmp_path, _plan())

    result = _authorize(payload, tmp_path, safety)

    assert result.authorized is True
    assert result.policy_profile == PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW
    assert result.eligibility_receipt_fingerprint == ""


def test_old_explicit_change_artifact_keeps_legacy_manual_semantics(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    plan = _plan()
    payload = {"patch_basis": "explicit_change_request", "patch_plan": plan}
    safety = evaluate_patch_safety(["app.py"], project_root=tmp_path)

    result = authorize_human_apply(
        payload=payload,
        repo_path=tmp_path,
        patch_safety_verdict=safety,
        human_action_kind=HUMAN_ACTION_APPLY,
        approved_candidate_fingerprint=patch_plan_fingerprint(plan),
        allow_legacy_explicit_change=True,
    )

    assert result.authorized is True
    assert result.legacy_compatibility is True


def test_historical_grounded_defect_cannot_bypass_bounded_receipt(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    plan = _plan()
    payload = {"patch_basis": "grounded_defect", "patch_plan": plan}
    safety = evaluate_patch_safety(["app.py"], project_root=tmp_path)

    result = authorize_human_apply(
        payload=payload,
        repo_path=tmp_path,
        patch_safety_verdict=safety,
        human_action_kind=HUMAN_ACTION_APPLY,
        approved_candidate_fingerprint=patch_plan_fingerprint(plan),
        allow_legacy_explicit_change=True,
    )

    assert result.authorized is False
    assert result.denial_reason == DENIAL_ELIGIBILITY_RECEIPT_STALE


def test_t6_bounded_review_apply_is_authorized_before_real_executor(tmp_path):
    broken = (
        "from collections import Counter\n\n"
        "def _classify_indent(text):\n"
        "    counts = Counter()\n"
        "    for line in text.splitlines():\n"
        "        if not line or line[0] not in \" \\t\":\n"
        "            continue\n"
        "        if line.startswith(\"\\t\"):\n"
        "            counts[\"tab\"] += 1\n"
        "        elif line.startswith(\"    \"):\n"
        "            counts[\"4space\"] += 1\n"
        "        elif line.startswith(\"  \"):\n"
        "            counts[\"2space\"] += 1\n"
        "    return counts.most_common(1)[0][0] if counts else None\n"
    )
    target = broken.split("\n", 2)[2]
    fixed = (
        "def _classify_indent(text):\n"
        "    counts = Counter()\n"
        "    space_widths = []\n"
        "    for line in text.splitlines():\n"
        "        if not line or line[0] not in \" \\t\":\n"
        "            continue\n"
        "        if line.startswith(\"\\t\"):\n"
        "            counts[\"tab\"] += 1\n"
        "        else:\n"
        "            space_widths.append(len(line) - len(line.lstrip(\" \")))\n"
        "    if counts[\"tab\"] > len(space_widths):\n"
        "        return \"tab\"\n"
        "    if space_widths:\n"
        "        return \"2space\" if min(space_widths) <= 2 else \"4space\"\n"
        "    return \"tab\" if counts[\"tab\"] else None\n"
    )
    _write(tmp_path, "core/code_dna.py", broken)
    _write(tmp_path, "pytest.ini", "[pytest]\n")
    _write(
        tmp_path,
        "tests/test_indent.py",
        "from core.code_dna import _classify_indent\n\n"
        "def test_nested_two_space():\n"
        "    text = 'root\\n  one\\n    two\\n      three\\n      four\\n'\n"
        "    assert _classify_indent(text) == '2space'\n",
    )
    plan = _plan("core/code_dna.py", target, fixed)
    payload, _ = _eligible_payload(tmp_path, plan)
    before = (tmp_path / "core/code_dna.py").read_bytes()

    response = _post_plan(_app().test_client(), tmp_path, payload)
    body = response.get_json()

    assert response.status_code == 200
    assert body["human_approval_received"] is True
    assert body["execution_authorized"] is True
    assert body["execution_authority_source"] == "manual_apply_action"
    assert body["execution_attempted"] is True
    assert body["mutation_observed"] is True
    assert body["patch_applied"] is True
    assert body["final_repository_changed"] is True
    assert (tmp_path / "core/code_dna.py").read_bytes() != before
    assert body["human_apply_authorization"]["authorization_status"] == (
        AUTHORIZATION_AUTHORIZED
    )
    replay = Path(body.get("replay_dir") or "")
    if replay:
        assert (replay / "human_apply_authorization.json").is_file()


def test_t6_stale_apply_does_not_enter_executor_or_mutate(tmp_path):
    _write(tmp_path, "core/code_dna.py", "value = 'old'\n")
    plan = _plan("core/code_dna.py")
    payload, _ = _eligible_payload(tmp_path, plan)
    _write(tmp_path, "core/code_dna.py", "value = 'manual edit'\n")
    before = (tmp_path / "core/code_dna.py").read_bytes()

    response = _post_plan(_app().test_client(), tmp_path, payload)
    body = response.get_json()

    assert body["human_approval_received"] is True
    assert body["execution_authorized"] is False
    assert body["execution_attempted"] is False
    assert body["human_apply_authorization_denial_reason"] == (
        DENIAL_SOURCE_STATE_STALE
    )
    assert (tmp_path / "core/code_dna.py").read_bytes() == before


def test_t6_candidate_mismatch_route_is_non_mutating(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, _ = _eligible_payload(tmp_path, _plan())
    c1 = payload["human_apply_review"]["candidate_fingerprint"]
    refined = copy.deepcopy(payload)
    refined["patch_plan"] = _plan(new="value = 'refined'\n")
    response = _app().test_client().post(
        "/apply_patch_plan",
        data={
            "repo_path": str(tmp_path),
            "patch": json.dumps(refined),
            "apply_policy": "ask",
            "patch_style": "balanced",
            "human_action_kind": HUMAN_ACTION_APPLY,
            "approved_candidate_fingerprint": c1,
            "approved_eligibility_receipt_fingerprint": refined[
                "human_apply_review"
            ]["eligibility_receipt_fingerprint"],
        },
    )
    body = response.get_json()

    assert body["execution_authorized"] is False
    assert body["human_apply_authorization_denial_reason"] == (
        DENIAL_CANDIDATE_MISMATCH
    )
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "value = 'old'\n"


def test_authorized_manual_attempt_rolls_back_when_existing_validation_fails(
    monkeypatch, tmp_path
):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, _ = _explicit_payload(tmp_path, _plan())
    monkeypatch.setattr(
        "web.routes.patch_routes.get_default_validation_command",
        lambda *_args, **_kwargs: 'python -c "import sys; sys.exit(1)"',
    )

    body = _post_plan(_app().test_client(), tmp_path, payload).get_json()

    assert body["human_approval_received"] is True
    assert body["execution_authorized"] is True
    assert body["execution_attempted"] is True
    assert body["mutation_observed"] is True
    assert body["rollback_performed"] is True
    assert body["patch_applied"] is False
    assert body["final_repository_changed"] is False
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "value = 'old'\n"


def test_manual_apply_outcome_is_persisted_for_history(
    monkeypatch, tmp_path
):
    import web.session_store as session_store

    _write(tmp_path, "app.py", "value = 'old'\n")
    payload, _ = _explicit_payload(tmp_path, _plan())
    monkeypatch.setattr(
        "web.routes.patch_routes.get_default_validation_command",
        lambda *_args, **_kwargs: None,
    )
    session_file = tmp_path / "sessions.json"
    monkeypatch.setattr(session_store, "SESSION_FILE", session_file)
    session_file.write_text(
        json.dumps(
            [
                {
                    "id": "review-1",
                    "repo_path": str(tmp_path),
                    "result": {"patch": json.dumps(payload)},
                }
            ]
        ),
        encoding="utf-8",
    )
    review = payload["human_apply_review"]

    response = _app().test_client().post(
        "/apply_patch_plan",
        data={
            "repo_path": str(tmp_path),
            "patch": json.dumps(payload),
            "apply_policy": "ask",
            "patch_style": "balanced",
            "session_id": "review-1",
            "human_action_kind": HUMAN_ACTION_APPLY,
            "approved_candidate_fingerprint": review["candidate_fingerprint"],
            "approved_eligibility_receipt_fingerprint": "",
        },
    )

    assert response.status_code == 200
    stored = json.loads(session_file.read_text(encoding="utf-8"))[0]["result"]
    stored_patch = json.loads(stored["patch"])
    assert stored_patch["human_approval_received"] is True
    assert stored_patch["execution_authorized"] is True
    assert stored_patch["patch_applied"] is True
    assert stored["manual_apply_outcome"]["final_repository_changed"] is True


def test_phase_adds_no_model_network_traversal_or_bounded_auto_apply():
    guardrails = human_apply_guardrails()
    assert guardrails["model_called"] is False
    assert guardrails["network_called"] is False
    assert guardrails["repository_traversed"] is False
    assert guardrails["bounded_auto_apply_added"] is False
    assert guardrails["authorization_created_before_mutation"] is True

    # Source pin: the boundary cannot reach a model, the network, a subprocess
    # or a directory walk, whatever the declared guardrails say.
    source = Path("core/human_apply_authorization.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imports.intersection(
        {
            "os",
            "subprocess",
            "socket",
            "requests",
            "urllib",
            "urllib.request",
            "agents",
            "core.retriever",
            "core.indexer",
            "core.validator",
            "core.validation_execution",
        }
    )
    for traversal in ("rglob", "iterdir", "os.walk", "glob("):
        assert traversal not in source, traversal


def test_analysis_route_apply_cannot_create_authority(tmp_path):
    _write(tmp_path, "app.py", "value = 'old'\n")
    payload = {
        "route": "analysis",
        "answer": "Nothing to change here.",
        "human_review_eligible": False,
    }
    safety = evaluate_patch_safety([], project_root=tmp_path)

    result = authorize_human_apply(
        payload=payload,
        repo_path=tmp_path,
        patch_safety_verdict=safety,
        human_action_kind=HUMAN_ACTION_APPLY,
        approved_candidate_fingerprint=patch_plan_fingerprint([]),
        allow_legacy_explicit_change=True,
    )

    assert result.authorized is False
    assert result.denial_reason == DENIAL_INCONSISTENT_INPUT
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == "value = 'old'\n"


def test_route_apply_on_safety_blocked_candidate_is_denied(tmp_path):
    _write(tmp_path, "tests/test_thing.py", "def test_x():\n    assert True\n")
    plan = _plan("tests/test_thing.py", "assert True\n", "assert False\n")
    payload, safety = _eligible_payload(tmp_path, plan)
    assert safety["ok"] is False
    before = (tmp_path / "tests/test_thing.py").read_bytes()

    body = _post_plan(_app().test_client(), tmp_path, payload).get_json()

    assert body["human_approval_received"] is True
    assert body["execution_authorized"] is False
    assert body["execution_attempted"] is False
    assert body["human_apply_authorization_denial_reason"] == (
        DENIAL_PATCH_SAFETY_MISMATCH
    )
    # The route keeps the safety gate's established wording and its reasons;
    # the human-Apply boundary adds the non-override sentence, never replaces it.
    assert body["message"].startswith("Patch plan blocked by safety gate: ")
    assert body["patch_safety"]["reasons"][0] in body["message"]
    assert "did not override patch safety" in body["message"]
    assert (tmp_path / "tests/test_thing.py").read_bytes() == before


def test_auto_apply_branches_never_reach_the_manual_review_receipt():
    tree = ast.parse(Path("core/pipeline.py").read_text(encoding="utf-8"))
    callers = {
        function.name
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_record_human_apply_review"
    }

    # T1/T2/T3 auto-apply reaches the executor from branches that never call
    # the no-authority handoff, so no automatic run acquires, needs or emits a
    # manual review receipt.
    assert callers == {"_record_patch_safety_handoff"}
