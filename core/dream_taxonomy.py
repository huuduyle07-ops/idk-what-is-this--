"""Phase 4.7a — Dream queue taxonomy.

Replaces the overlapping `kind` + `mode` fields with `dream_type` (the kind of
work being queued) and `action_level` (how aggressive Dream should be on it).

This module is taxonomy + validation only. It does NOT change patch behavior,
run benchmarks, or add new model calls; the legacy execution code keeps
reading `kind` / `mode` and the queue layer maps the new fields onto the old
ones for now.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DREAM_TYPES: tuple[str, ...] = (
    "bug_investigation",
    "debt_cleanup",
    "idea_trial",
    "research_study",
    "reference_study",
    "case_idea_research",
)

ACTION_LEVELS: tuple[str, ...] = (
    "report_only",
    "plan_only",
    "proposal_draft",
    "patch_if_safe",
)

ALLOWED_COMBINATIONS: dict[str, tuple[str, ...]] = {
    "bug_investigation": ("plan_only", "patch_if_safe"),
    "debt_cleanup": ("plan_only", "proposal_draft"),
    "idea_trial": ("report_only", "proposal_draft"),
    "research_study": ("report_only",),
    "reference_study": ("report_only", "case_idea_research"),
    "case_idea_research": ("report_only",),
}

# Default action_level per dream_type, used by the legacy mapper when an old
# `mode` does not translate to a legal level for the chosen dream_type.
_DEFAULT_LEVEL_FOR_TYPE: dict[str, str] = {
    "bug_investigation": "plan_only",
    "debt_cleanup": "plan_only",
    "idea_trial": "report_only",
    "research_study": "report_only",
    "reference_study": "report_only",
    "case_idea_research": "report_only",
}

DEFAULT_DREAM_TYPE: str = "bug_investigation"
DEFAULT_ACTION_LEVEL: str = "plan_only"


def allowed_action_levels(dream_type: str) -> tuple[str, ...]:
    """Levels that are legal for `dream_type`. Empty tuple for unknown types."""
    return ALLOWED_COMBINATIONS.get(dream_type, ())


def validate(dream_type: str, action_level: str) -> str | None:
    """Return an error message for an invalid combo, or None when valid.

    `ALLOWED_COMBINATIONS` is the single source of truth: an action_level is
    "valid" if it appears in some dream_type's allowed tuple. This lets
    specialty levels like `case_idea_research` (only used by reference_study)
    coexist with the four standard action_levels listed in `ACTION_LEVELS`.

    The message names the offending value and (for combo errors) the levels
    that ARE allowed for the chosen dream_type, so the UI / API can surface a
    user-fixable hint without re-deriving the rules.
    """
    if dream_type not in ALLOWED_COMBINATIONS:
        return (
            f"Unknown dream_type {dream_type!r}. "
            f"Valid values: {', '.join(DREAM_TYPES)}."
        )
    allowed = ALLOWED_COMBINATIONS[dream_type]
    if action_level in allowed:
        return None
    all_known_levels = {lvl for levels in ALLOWED_COMBINATIONS.values() for lvl in levels}
    if action_level not in all_known_levels:
        return (
            f"Unknown action_level {action_level!r}. "
            f"Valid values: {', '.join(sorted(all_known_levels))}."
        )
    return (
        f"action_level {action_level!r} is not allowed for "
        f"dream_type {dream_type!r}. Allowed: {', '.join(allowed)}."
    )


# ---------------------------------------------------------------------------
# Legacy mapping
# ---------------------------------------------------------------------------
#
# Old queue items carry `kind` (bug / debt / idea / research / reference_study)
# and the run carries `mode` (plan_only / patch_if_safe / research /
# case_idea_research). The mapper turns those into a (dream_type, action_level)
# pair that is guaranteed to be valid per `validate()`.

_KIND_ALIASES: dict[str, str] = {
    "": DEFAULT_DREAM_TYPE,
    "bug": "bug_investigation",
    "bugs": "bug_investigation",
    "bug_investigation": "bug_investigation",
    "debt": "debt_cleanup",
    "debt_cleanup": "debt_cleanup",
    "idea": "idea_trial",
    "ideas": "idea_trial",
    "idea_trial": "idea_trial",
    "research": "research_study",
    "research_study": "research_study",
    "reference study": "reference_study",
    "reference_study": "reference_study",
    "case_idea_research": "case_idea_research",
}

_MODE_ALIASES: dict[str, str] = {
    "": DEFAULT_ACTION_LEVEL,
    "plan": "plan_only",
    "plan_only": "plan_only",
    "planonly": "plan_only",
    "safe": "patch_if_safe",
    "patch": "patch_if_safe",
    "patch_if_safe": "patch_if_safe",
    "research": "report_only",
    "design": "report_only",
    "proposal": "proposal_draft",
    "proposal_draft": "proposal_draft",
    "report_only": "report_only",
    "report": "report_only",
    "reference_study": "case_idea_research",
    "case_idea": "case_idea_research",
    "case_idea_research": "case_idea_research",
}


# dream_type → legacy `kind` value. The run-time code in
# `core/sleeping_consultant.py` still branches on `kind`, so the queue layer
# round-trips through this mapping when storing new items. Phase 4.7a is
# taxonomy cleanup only; it does NOT change patch / proposal execution.
_LEGACY_KIND_FOR_TYPE: dict[str, str] = {
    "bug_investigation": "bug",
    "debt_cleanup": "debt",
    "idea_trial": "idea",
    "research_study": "research",
    "reference_study": "reference_study",
    "case_idea_research": "case_idea_research",
}


def legacy_kind_for_dream_type(dream_type: str) -> str:
    """Return the legacy `kind` value paired with a canonical dream_type."""
    return _LEGACY_KIND_FOR_TYPE.get(dream_type, "bug")


def normalize_legacy(kind: str | None, mode: str | None) -> tuple[str, str]:
    """Best-effort mapping from legacy (kind, mode) to (dream_type, action_level).

    Always returns a pair that satisfies `validate()`. Unknown inputs fall
    back to the default dream_type / action_level so historical queue items
    and Dream reports keep loading after the taxonomy change.
    """
    kind_key = (kind or "").strip().lower()
    mode_key = (mode or "").strip().lower()

    dream_type = _KIND_ALIASES.get(kind_key, DEFAULT_DREAM_TYPE)
    candidate_level = _MODE_ALIASES.get(mode_key, _DEFAULT_LEVEL_FOR_TYPE[dream_type])

    if candidate_level not in ALLOWED_COMBINATIONS[dream_type]:
        candidate_level = _DEFAULT_LEVEL_FOR_TYPE[dream_type]

    return dream_type, candidate_level
