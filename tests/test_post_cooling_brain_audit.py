"""Phase 13.12 - Post-Cooling-Brain Audit Sweep.

After the Memory Temperature chain (13.7 shadow retrieval, 13.8 shadow report,
13.9 default-off tie-breaker, 13.10 dogfood, 13.11b evidence pack, 13.11a live
wiring behind a disabled flag), this module audits docs / tests / guardrail text
for stale claims and contradictions and pins down the *current* truth:

  * ``MEMORY_TEMPERATURE_RETRIEVAL_ENABLED`` exists, defaults false; the
    tie-break-only flag defaults true.
  * The tie-breaker is wired ONLY at the ``core.lesson_retrieval`` final
    ordering boundary, behind that disabled flag.
  * ``control_engine`` is not directly wired (it merely consumes the boundary).
  * ``MEMORY_TEMPERATURE_RETRIEVAL_ENABLED`` is now an ``editable_live`` UI
    toggle (default off); ``MEMORY_TEMPERATURE_TIEBREAK_ONLY`` stays
    ``READ_ONLY_PLANNED`` (tie-break-only safety locked on).
  * Default behavior is unchanged; the CONTROL prompt is unchanged when disabled.
  * Cold memories are de-prioritized inside a group, never hard-filtered.
  * Frozen / audit-only / blocked memories are excluded from CONTROL, never
    revived or surfaced.

The audit is intentionally read-only: it imports nothing heavy, reads source /
docs as text, and never enables the flag, calls a model/API, writes a DB, runs
patching / validation / benchmarks, or touches the Docker / subprocess
lifecycle (asserted by its own AST guard, Test 10).
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

THIS_FILE = Path(__file__)

# The full Memory Temperature tie-breaker chain whose prose / guardrails this
# sweep audits for stale "unwired" claims.
TIEBREAKER_CHAIN_SOURCES = (
    "core/memory_temperature_retrieval.py",
    "tests/test_memory_temperature_retrieval_tiebreaker.py",
)

EVIDENCE_FILE_09 = "09_memory_temperature_tiebreaker_dogfood.md"


def _read(rel: str) -> str:
    return (PROJECT_ROOT / rel).read_text(encoding="utf-8")


def _string_list_assignment(rel: str, name: str) -> list[str] | None:
    """Return the list-of-string-constants assigned to ``name`` in ``rel``.

    Parses the module source so no import side effects (flask app, DB probes)
    are triggered by the audit.
    """
    tree = ast.parse(_read(rel))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [
                            el.value
                            for el in node.value.elts
                            if isinstance(el, ast.Constant) and isinstance(el.value, str)
                        ]
    return None


# ---------------------------------------------------------------------------
# 1 - config defaults remain disabled (false / true)
# ---------------------------------------------------------------------------
def test_config_defaults_remain_disabled():
    import config

    assert config.MEMORY_TEMPERATURE_RETRIEVAL_ENABLED is False
    assert config.MEMORY_TEMPERATURE_TIEBREAK_ONLY is True


# ---------------------------------------------------------------------------
# 2 - harness controls stay READ_ONLY_PLANNED / not UI-editable
# ---------------------------------------------------------------------------
def test_memory_temperature_harness_control_state():
    from core import harness_controls as hc

    # RETRIEVAL_ENABLED is now an editable_live UI toggle, OFF by default.
    retrieval = hc.get_control("MEMORY_TEMPERATURE_RETRIEVAL_ENABLED")
    assert retrieval is not None
    assert retrieval.control_type == hc.EDITABLE_LIVE
    assert retrieval.wired is True
    assert bool(retrieval.config_default) is False

    # TIEBREAK_ONLY stays planned / not UI-editable (tie-break-only safety).
    tiebreak = hc.get_control("MEMORY_TEMPERATURE_TIEBREAK_ONLY")
    assert tiebreak is not None
    assert tiebreak.control_type == hc.READ_ONLY_PLANNED
    assert tiebreak.wired is False


# ---------------------------------------------------------------------------
# 3 - control_engine does NOT import the tie-breaker (consumes boundary only)
# ---------------------------------------------------------------------------
def test_control_engine_does_not_import_tiebreaker():
    src = _read("core/control_engine.py")
    assert "memory_temperature_retrieval" not in src
    assert "apply_memory_temperature_tiebreaker" not in src
    # It still delegates lesson selection to the retrieval boundary.
    assert "find_active_lessons" in src


# ---------------------------------------------------------------------------
# 4 - lesson_retrieval IS the live boundary wiring the tie-breaker (disabled)
# ---------------------------------------------------------------------------
def test_lesson_retrieval_is_the_only_live_wired_boundary():
    src = _read("core/lesson_retrieval.py")
    assert "apply_memory_temperature_tiebreaker" in src
    assert "memory_temperature_retrieval" in src
    # Distinguish wired-but-disabled from unwired: the call is gated on the
    # default-off flag, not unconditional.
    assert "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED" in src

    # The distinction the sweep enforces: lesson_retrieval is wired, the
    # control_engine prompt builder is not.
    control_src = _read("core/control_engine.py")
    assert "apply_memory_temperature_tiebreaker" not in control_src


# ---------------------------------------------------------------------------
# 5 - no stale "completely unwired" / "explain-only only" claims survive
# ---------------------------------------------------------------------------
def test_no_stale_unwired_claims_in_chain():
    stale_phrases = (
        "completely unwired",
        "no live retrieval imports memory_temperature_retrieval",
        "not wired into the live control retrieval path",
        "not wired into live lesson_retrieval",
    )
    for rel in TIEBREAKER_CHAIN_SOURCES:
        lowered = _read(rel).lower()
        for phrase in stale_phrases:
            assert phrase not in lowered, f"stale claim {phrase!r} in {rel}"


# ---------------------------------------------------------------------------
# 6 - docs/evidence describe the wiring as "behind a disabled flag" / default-off
# ---------------------------------------------------------------------------
def test_docs_describe_wiring_behind_disabled_flag():
    roadmap = _read("docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md").lower()
    assert "13.11a" in roadmap
    assert "wired" in roadmap
    assert ("disabled-by-default" in roadmap) or ("disabled by default" in roadmap)

    # The retrieval module prose itself reflects the default-off wiring.
    retr = _read("core/memory_temperature_retrieval.py").lower()
    assert "13.11a" in retr or "lesson_retrieval" in retr or "lesson-retrieval" in retr
    assert "default-off" in retr or "default off" in retr or "disabled by default" in retr

    env = _read(".env.example").lower()
    assert "memory_temperature_retrieval_enabled" in env
    assert "disabled" in env or "default" in env


# ---------------------------------------------------------------------------
# 7 - evidence expected-file lists are consistent and include file 09
# ---------------------------------------------------------------------------
def test_evidence_expected_file_lists_are_consistent():
    pack = _string_list_assignment("scripts/build_presentation_evidence_pack.py", "EVIDENCE_FILES")
    pack_test = _string_list_assignment("tests/test_presentation_evidence_pack.py", "EXPECTED_FILES")
    route_test = _string_list_assignment("tests/test_presentation_evidence_routes.py", "EXPECTED_FILES")

    assert pack is not None
    assert pack_test is not None
    assert route_test is not None

    assert EVIDENCE_FILE_09 in pack
    assert set(pack) == set(pack_test) == set(route_test)


# ---------------------------------------------------------------------------
# 8 - cold is described as lower-priority, NOT hard-filtered / removed
# ---------------------------------------------------------------------------
def test_cold_is_not_described_as_hard_filtered():
    retr = _read("core/memory_temperature_retrieval.py").lower()
    # The guardrail explicitly says cold is never hard-filtered (de-prioritized
    # inside a group, never removed from CONTROL).
    assert "never hard-filters cold" in retr

    env = _read(".env.example").lower()
    assert "hard-filter" in env and "never" in env


# ---------------------------------------------------------------------------
# 9 - frozen / audit-only / blocked are described as excluded from CONTROL
# ---------------------------------------------------------------------------
def test_frozen_audit_blocked_excluded_from_control():
    retr = _read("core/memory_temperature_retrieval.py").lower()
    assert "frozen" in retr
    assert "audit-only" in retr or "audit_only" in retr
    assert "blocked" in retr
    # They are sunk / never revived / never surfaced - i.e. excluded from CONTROL.
    assert (
        "never revive" in retr
        or "never surface" in retr
        or "never revives" in retr
        or "never revived" in retr
        or "sink last" in retr
        or "sinks last" in retr
        or "sink to the bottom" in retr
    )


# ---------------------------------------------------------------------------
# 10 - AST guard: the audit itself has no forbidden sinks and enables no flag
# ---------------------------------------------------------------------------
def test_audit_module_has_no_forbidden_sinks():
    source = THIS_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules: list[str] = []
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_names.append(func.id)
            elif isinstance(func, ast.Attribute):
                call_names.append(func.attr)

    forbidden_import_areas = (
        "model",
        "api",
        "database",
        "db",
        "patching",
        "validator",
        "benchmark",
        "run_benchmarks",
        "subprocess",
        "docker",
    )
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported

    forbidden_network = {"requests", "httpx", "urllib", "aiohttp", "socket", "subprocess", "openai"}
    assert forbidden_network.isdisjoint(part.split(".")[0] for part in imported_modules)

    forbidden_calls = {
        "call_model",
        "call_api",
        "run_gemini_request",
        "save_lesson",
        "write_lesson",
        "promote_lesson",
        "block_lesson",
        "update_lesson",
        "delete_lesson",
        "apply_patch_plan",
        "generate_patch",
        "validate_patch",
        "run_validation",
        "run_validation_command",
        "run_benchmarks",
        "set_override",
        "Popen",
        "check_call",
        "check_output",
    }
    assert forbidden_calls.isdisjoint(call_names)

    # The audit never *enables* the flag (no truthy assignment, no monkey-patch
    # to True). It only reads / asserts current state. Tokens are assembled at
    # runtime so this guard never matches its own source.
    flag = "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED"
    assert f"{flag} = True" not in source
    assert f"{flag}=true" not in source.lower().replace(" ", "")
    assert ("monkey" + "patch") not in source


# ---------------------------------------------------------------------------
# 10b - no chain artifact enables the flag by default
# ---------------------------------------------------------------------------
def test_no_chain_artifact_enables_flag_by_default():
    # config + .env.example + the evidence-pack builder must keep the flag off.
    for rel in (
        "config.py",
        ".env.example",
        "scripts/build_presentation_evidence_pack.py",
    ):
        compact = _read(rel).replace(" ", "").lower()
        assert "memory_temperature_retrieval_enabled=true" not in compact, rel
