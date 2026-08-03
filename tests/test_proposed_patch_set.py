"""CTX.PATCH.1 bounded minimal coherent patch-set planning tests."""

from __future__ import annotations

import copy

import pytest

from core.proposed_patch_set import build_proposed_patch_set


def _candidate(
    path: str,
    *,
    score: int = 90,
    state: str = "eligible",
    role: str = "primary_or_supporting_target",
    patch_role: str = "",
    strategy: str = "default",
    required_paths: tuple[str, ...] = (),
    validations: tuple[dict, ...] = (),
    required: bool = False,
) -> dict:
    return {
        "path": path,
        "patchability_score": score,
        "candidate_state": state,
        "role": role,
        "patch_role": patch_role,
        "strategy_id": strategy,
        "task_coverage": "complete",
        "required_paths": list(required_paths),
        "required_for_coherence": required,
        "validation_candidates": list(validations),
        "write_authority": False,
        "patch_application_authority": False,
        "human_approval_required": True,
    }


def test_minimal_coherent_candidate_set_is_preferred() -> None:
    candidates = [
        _candidate(
            "core/router.py",
            patch_role="primary",
            required_paths=("core/routes.py",),
            validations=({"target": "tests/test_router.py"},),
        ),
        _candidate(
            "core/routes.py", score=80, patch_role="required_adjacent"
        ),
        _candidate("core/unrelated.py", score=88, patch_role="optional"),
        _candidate(
            "tests/test_router.py",
            score=82,
            role="validation",
            patch_role="validation",
        ),
    ]

    result = build_proposed_patch_set(candidates)

    assert [item["path"] for item in result.implementation_candidates] == [
        "core/router.py",
        "core/routes.py",
    ]
    assert [item["path"] for item in result.validation_candidates] == [
        "tests/test_router.py"
    ]
    assert [item["path"] for item in result.supporting_context] == [
        "core/unrelated.py"
    ]
    assert result.status == "ready_with_review"


def test_source_file_limit_is_enforced_without_arbitrary_truncation() -> None:
    candidates = [
        _candidate(f"core/file_{index}.py", patch_role="primary")
        for index in range(5)
    ]

    result = build_proposed_patch_set(candidates)

    assert result.status == "human_file_selection_required"
    assert result.implementation_candidates == ()
    assert len(result.supporting_context) == 5


def test_validation_file_limit_is_enforced() -> None:
    validation_paths = tuple(f"tests/test_{index}.py" for index in range(5))
    candidates = [
        _candidate(
            "core/router.py",
            patch_role="primary",
            validations=tuple({"target": path} for path in validation_paths),
        ),
        *[
            _candidate(
                path,
                role="validation",
                patch_role="validation",
            )
            for path in validation_paths
        ],
    ]

    result = build_proposed_patch_set(candidates)

    assert result.status == "human_file_selection_required"
    assert len(result.validation_candidates) <= 4
    assert len(result.implementation_candidates) + len(
        result.validation_candidates
    ) <= 8


def test_total_file_limit_is_enforced_even_with_custom_smaller_limit() -> None:
    candidates = [
        _candidate(
            "core/router.py",
            patch_role="primary",
            required_paths=("core/routes.py",),
            validations=(
                {"target": "tests/test_router.py"},
                {"target": "tests/test_routes.py"},
            ),
        ),
        _candidate("core/routes.py", patch_role="required_adjacent"),
        _candidate(
            "tests/test_router.py", role="validation", patch_role="validation"
        ),
        _candidate(
            "tests/test_routes.py", role="validation", patch_role="validation"
        ),
    ]

    result = build_proposed_patch_set(candidates, max_total_files=3)

    assert result.status == "human_file_selection_required"
    assert len(result.paths) <= 3


def test_noncandidate_read_context_does_not_enter_proposal() -> None:
    result = build_proposed_patch_set(
        [
            _candidate("core/router.py", patch_role="primary"),
            _candidate(
                "docs/router.md",
                score=55,
                state="read_only_context",
                role="supporting_context",
            ),
        ]
    )

    assert result.paths == ("core/router.py",)
    assert [item["path"] for item in result.supporting_context] == [
        "docs/router.md"
    ]


def test_equally_plausible_unrelated_strategies_require_human_selection() -> None:
    result = build_proposed_patch_set(
        [
            _candidate("core/router_a.py", strategy="strategy-a"),
            _candidate("core/router_b.py", strategy="strategy-b"),
        ]
    )

    assert result.status == "human_file_selection_required"
    assert result.implementation_candidates == ()
    assert {item["path"] for item in result.supporting_context} == {
        "core/router_a.py",
        "core/router_b.py",
    }


def test_stronger_strategy_is_selected_without_using_path_as_tiebreaker() -> None:
    result = build_proposed_patch_set(
        [
            _candidate("core/weak.py", score=70, strategy="weak"),
            _candidate("core/strong.py", score=90, strategy="strong"),
        ]
    )

    assert result.selected_strategy_id == "strong"
    assert result.paths == ("core/strong.py",)


def test_ordering_is_deterministic_and_inputs_are_not_mutated() -> None:
    candidates = [
        _candidate("core/z.py", score=70),
        _candidate("core/a.py", score=90),
        _candidate("core/m.py", score=80),
    ]
    before = copy.deepcopy(candidates)

    first = build_proposed_patch_set(candidates)
    second = build_proposed_patch_set(reversed(copy.deepcopy(candidates)))

    assert first.as_dict() == second.as_dict()
    assert first.paths == ("core/a.py",)
    assert candidates == before


def test_hard_candidate_states_never_enter_the_patch_set() -> None:
    result = build_proposed_patch_set(
        [
            _candidate("core/router.py", patch_role="primary"),
            _candidate(".env", score=100, state="sensitive_blocked"),
            _candidate(
                "generated/client.py",
                score=100,
                state="generated_source_redirect",
            ),
            _candidate("../outside.py", score=100, state="outside_scope"),
            _candidate("private.pem", score=100, state="forbidden"),
        ]
    )

    assert result.paths == ("core/router.py",)
    assert {item["candidate_state"] for item in result.blocked_candidates} == {
        "sensitive_blocked",
        "generated_source_redirect",
        "outside_scope",
        "forbidden",
    }


def test_reread_only_plan_has_stable_reread_status() -> None:
    result = build_proposed_patch_set(
        [
            {
                **_candidate(
                    "core/router.py", score=90, state="reread_required"
                ),
                "receipt_freshness": "changed",
            }
        ]
    )

    assert result.status == "reread_required"
    assert result.paths == ()


def test_planner_rejects_any_attempt_to_escalate_authority() -> None:
    candidate = _candidate("core/router.py")
    candidate["write_authority"] = True

    with pytest.raises(ValueError, match="write authority"):
        build_proposed_patch_set([candidate])


def test_test_candidates_retain_no_automatic_authority() -> None:
    candidate = _candidate(
        "tests/test_router.py", role="validation", patch_role="validation"
    )
    result = build_proposed_patch_set(
        [
            _candidate(
                "core/router.py",
                patch_role="primary",
                validations=({"target": "tests/test_router.py"},),
            ),
            candidate,
        ]
    ).as_dict()

    selected_test = result["validation_candidates"][0]
    assert selected_test["write_authority"] is False
    assert selected_test["patch_application_authority"] is False
    assert result["human_approval_required"] is True
