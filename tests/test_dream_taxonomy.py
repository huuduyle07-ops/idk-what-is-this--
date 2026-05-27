"""Phase 4.7a — Dream type / action level taxonomy.

Pure-Python tests for the new taxonomy module that normalizes the previous
overlapping `kind` + `mode` fields into `dream_type` + `action_level`, plus
validates the allowed combinations.
"""
from __future__ import annotations

import pytest

from core import dream_taxonomy as dt


# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

def test_dream_types_match_phase_spec():
    """The six dream_type values from the Phase 4.7a brief are exposed."""
    assert set(dt.DREAM_TYPES) == {
        "bug_investigation",
        "debt_cleanup",
        "idea_trial",
        "research_study",
        "reference_study",
        "case_idea_research",
    }


def test_action_levels_match_phase_spec():
    """The four action_level values from the Phase 4.7a brief are exposed."""
    assert set(dt.ACTION_LEVELS) == {
        "report_only",
        "plan_only",
        "proposal_draft",
        "patch_if_safe",
    }


def test_allowed_combinations_match_phase_spec():
    """The allowed (dream_type → action_level) matrix matches the brief exactly."""
    expected = {
        "bug_investigation": {"plan_only", "patch_if_safe"},
        "debt_cleanup": {"plan_only", "proposal_draft"},
        "idea_trial": {"report_only", "proposal_draft"},
        "research_study": {"report_only"},
        "reference_study": {"report_only", "case_idea_research"},
        "case_idea_research": {"report_only"},
    }
    actual = {k: set(v) for k, v in dt.ALLOWED_COMBINATIONS.items()}
    assert actual == expected


# ---------------------------------------------------------------------------
# validate(dream_type, action_level)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dream_type,action_level", [
    ("bug_investigation", "plan_only"),
    ("bug_investigation", "patch_if_safe"),
    ("debt_cleanup", "plan_only"),
    ("debt_cleanup", "proposal_draft"),
    ("idea_trial", "report_only"),
    ("idea_trial", "proposal_draft"),
    ("research_study", "report_only"),
    ("reference_study", "report_only"),
    ("reference_study", "case_idea_research"),
    ("case_idea_research", "report_only"),
])
def test_validate_accepts_every_allowed_combo(dream_type, action_level):
    assert dt.validate(dream_type, action_level) is None


def test_validate_rejects_unknown_dream_type_with_friendly_error():
    err = dt.validate("not_a_real_type", "plan_only")
    assert err is not None
    assert "not_a_real_type" in err


def test_validate_rejects_unknown_action_level_with_friendly_error():
    err = dt.validate("bug_investigation", "not_a_real_level")
    assert err is not None
    assert "not_a_real_level" in err


def test_validate_rejects_disallowed_combo_with_friendly_error():
    # case_idea_research is only valid for reference_study, never for research_study.
    err = dt.validate("research_study", "case_idea_research")
    assert err is not None
    assert "research_study" in err
    assert "case_idea_research" in err
    # Error names the levels that ARE allowed for this dream_type, so the user
    # can pick something legal without guessing.
    assert "report_only" in err


def test_validate_rejects_research_study_with_plan_only():
    # research_study is report_only only.
    err = dt.validate("research_study", "plan_only")
    assert err is not None


def test_validate_rejects_bug_investigation_with_report_only():
    # bug_investigation is plan_only or patch_if_safe — never report_only.
    err = dt.validate("bug_investigation", "report_only")
    assert err is not None


# ---------------------------------------------------------------------------
# allowed_action_levels(dream_type) — the UI/JS uses this to gate the dropdown
# ---------------------------------------------------------------------------

def test_allowed_action_levels_for_known_type_returns_tuple_of_strings():
    levels = dt.allowed_action_levels("bug_investigation")
    assert set(levels) == {"plan_only", "patch_if_safe"}
    assert all(isinstance(level, str) for level in levels)


def test_allowed_action_levels_for_unknown_type_returns_empty():
    assert dt.allowed_action_levels("not_a_real_type") == ()


# ---------------------------------------------------------------------------
# normalize_legacy(kind, mode) — backward-compat mapping
# ---------------------------------------------------------------------------

def test_legacy_bug_plan_only_maps_to_bug_investigation_plan_only():
    assert dt.normalize_legacy("bug", "plan_only") == ("bug_investigation", "plan_only")


def test_legacy_bug_patch_if_safe_maps_to_bug_investigation_patch_if_safe():
    assert dt.normalize_legacy("bug", "patch_if_safe") == (
        "bug_investigation",
        "patch_if_safe",
    )


def test_legacy_debt_plan_only_maps_to_debt_cleanup_plan_only():
    assert dt.normalize_legacy("debt", "plan_only") == ("debt_cleanup", "plan_only")


def test_legacy_idea_maps_to_idea_trial_with_valid_default_level():
    dream_type, action_level = dt.normalize_legacy("idea", "plan_only")
    assert dream_type == "idea_trial"
    # The level chosen must be one of idea_trial's legal levels (report_only
    # or proposal_draft). plan_only is illegal for idea_trial — the mapper has
    # to substitute a sensible default, not produce an invalid combo.
    assert dt.validate(dream_type, action_level) is None


def test_legacy_research_kind_maps_to_research_study():
    dream_type, action_level = dt.normalize_legacy("research", "research")
    assert dream_type == "research_study"
    assert dt.validate(dream_type, action_level) is None


def test_legacy_reference_study_maps_to_reference_study():
    dream_type, action_level = dt.normalize_legacy("reference_study", "plan_only")
    assert dream_type == "reference_study"
    assert dt.validate(dream_type, action_level) is None


def test_legacy_reference_study_with_case_idea_mode_keeps_case_idea_level():
    """Old usage: reference_study + mode=case_idea_research is the case-idea flow."""
    assert dt.normalize_legacy("reference_study", "case_idea_research") == (
        "reference_study",
        "case_idea_research",
    )


def test_legacy_reference_study_alias_with_space_is_accepted():
    """The UI label used 'reference study' (space) — make sure the mapper
    treats it the same as 'reference_study'."""
    dream_type, _ = dt.normalize_legacy("reference study", "plan_only")
    assert dream_type == "reference_study"


def test_legacy_unknown_kind_falls_back_to_default_dream_type():
    """Robustness: unknown kind values from old queues must still produce a
    valid (dream_type, action_level) pair so historical reports keep loading."""
    dream_type, action_level = dt.normalize_legacy("totally_unknown_kind", "plan_only")
    assert dream_type in dt.DREAM_TYPES
    assert dt.validate(dream_type, action_level) is None


def test_legacy_empty_inputs_produce_valid_defaults():
    dream_type, action_level = dt.normalize_legacy("", "")
    assert dream_type in dt.DREAM_TYPES
    assert action_level in dt.ACTION_LEVELS
    assert dt.validate(dream_type, action_level) is None
