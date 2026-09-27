"""PATCH.MINIMAL.LIVE.3 authoritative pre-candidate binding context."""

from __future__ import annotations

import inspect
import json
import statistics
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.pipeline as pipeline
import patching.patch_gates as patch_gates
from core.agent_state import AgentState
from core.authoritative_binding_context import (
    PHASE_ID,
    AuthoritativeBindingContext,
    build_authoritative_binding_context,
    load_authoritative_binding_context,
)
from core.code_dna import _classify_indent
from core.local_binding_novelty import (
    MAX_CHANGED_LINES,
    MAX_NOVEL_LOCAL_BINDINGS,
    MAX_TOUCHED_FUNCTIONS,
    REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY,
    REASON_NOVEL_EXTERNAL_REFERENCE,
    REASON_NOVEL_IMPORT,
    REASON_UNRESOLVED_NOVEL_IDENTIFIER,
    classify_candidate_novelty,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET_FILE = "core/code_dna.py"
TARGET_SYMBOL = "_classify_indent"
TARGET_FUNCTION = inspect.getsource(_classify_indent)
TARGET_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
CORRECT_BODY = (
    "    return assess_indentation_observation(\n"
    "        observe_source_indentation(\n"
    "            text,\n"
    "            language=language,\n"
    "        )\n"
    "    ).value\n"
)
BOUND_CALL_BODY = CORRECT_BODY.replace(").value", ")")


def _gate(
    *,
    target: str,
    patched: str,
    source_path: str,
    target_symbol: str,
    context: AuthoritativeBindingContext | None = None,
    authoritative_source: str = "",
) -> dict:
    state = SimpleNamespace(
        task_info={"patch_style": "safe_minimal"},
        patch_style="safe_minimal",
        language="python",
        json_block={
            "summary": "",
            "issues": [],
            "patch_candidate": {
                "file": source_path,
                "relative_path": source_path,
                "target_node_name": target_symbol,
                "target_node_kind": "function",
                "target_snippet": target,
                "patched_snippet": patched,
            },
            "confidence": 0.9,
            "needs_escalation": False,
        },
        final_answer="",
        human_answer="",
    )
    patch_gates._enforce_safe_minimal(
        state,
        authoritative_binding_context=context,
        authoritative_source=authoritative_source,
    )
    return state.json_block


def _accepted(block: dict) -> bool:
    return isinstance(block.get("patch_candidate"), dict)


@pytest.fixture(scope="module")
def live_context():
    context, source = load_authoritative_binding_context(
        repo_root=ROOT,
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
    )
    assert context is not None
    return context, source


def test_binding_extraction_is_typed_immutable_and_baseline_only(live_context):
    context, _source = live_context
    assert context.parameter_names == ("language", "text")
    assert {"counts", "line"} <= set(context.existing_local_names)
    imports = {item.bound_name: item for item in context.repository_local_direct_imports}
    assert "assess_indentation_observation" in imports
    assert "observe_source_indentation" in imports
    assert imports["observe_source_indentation"].resolved_module_path == (
        "core/indentation_observation.py"
    )
    assert "Counter" not in context.repository_import_names
    assert "Optional" not in context.repository_import_names
    assert context.source_sha256
    assert context.target_source_sha256
    assert context.target_start_line <= context.target_end_line
    with pytest.raises((AttributeError, TypeError)):
        context.parameter_names = ()


def test_signature_kinds_cover_all_generic_parameter_forms(tmp_path):
    source = (
        "def target(pos, /, ordinary=1, *items, named=None, **options):\n"
        "    existing = ordinary\n"
        "    return existing\n"
    )
    path = tmp_path / "target.py"
    path.write_text(source, encoding="utf-8")
    context = build_authoritative_binding_context(
        repo_root=tmp_path,
        source_path="target.py",
        target_symbol="target",
        authoritative_source=source,
    )
    assert context is not None
    assert set(context.parameter_names) == {
        "pos", "ordinary", "items", "named", "options"
    }
    assert context.existing_local_names == ("existing",)


def test_body_only_parameter_and_repository_imports_are_authoritative(live_context):
    context, source = live_context
    block = _gate(
        target=TARGET_BODY.rstrip("\n"),
        patched=BOUND_CALL_BODY.rstrip("\n"),
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
        context=context,
        authoritative_source=source,
    )
    assert _accepted(block)
    assert set(block["authoritative_binding_context_reused_names"]) == {
        "assess_indentation_observation",
        "observe_source_indentation",
        "language",
    }
    assert "candidate_novelty_reason" not in block


def test_full_function_and_body_only_receive_the_same_admission(live_context):
    context, source = live_context
    full_patched = TARGET_FUNCTION.replace(TARGET_BODY, BOUND_CALL_BODY)
    body = _gate(
        target=TARGET_BODY.rstrip("\n"),
        patched=BOUND_CALL_BODY.rstrip("\n"),
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
        context=context,
        authoritative_source=source,
    )
    full = _gate(
        target=TARGET_FUNCTION.rstrip("\n"),
        patched=full_patched.rstrip("\n"),
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
        context=context,
        authoritative_source=source,
    )
    assert _accepted(body) is _accepted(full) is True
    assert set(body["authoritative_binding_context_reused_names"]) == {
        "assess_indentation_observation",
        "observe_source_indentation",
        "language",
    }
    assert set(full["authoritative_binding_context_reused_names"]) == {
        "assess_indentation_observation",
        "observe_source_indentation",
    }


def test_bare_body_only_parameter_is_no_longer_unresolved(live_context):
    context, source = live_context
    patched = '    if language == "python":\n        return None\n' + TARGET_BODY
    block = _gate(
        target=TARGET_BODY.rstrip("\n"),
        patched=patched.rstrip("\n"),
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
        context=context,
        authoritative_source=source,
    )
    assert _accepted(block)
    assert block["authoritative_binding_context_reused_names"] == ["language"]


def test_live3a_pre_measurement_stops_only_at_member_policy(live_context):
    """Preserve the measured LIVE.3A PRE with only LIVE.3B proof disabled."""

    context, source = live_context
    context = replace(context, immutable_result_proof=None)
    results = []
    for target, patched in (
        (TARGET_BODY.rstrip("\n"), CORRECT_BODY.rstrip("\n")),
        (
            TARGET_FUNCTION.rstrip("\n"),
            TARGET_FUNCTION.replace(TARGET_BODY, CORRECT_BODY).rstrip("\n"),
        ),
    ):
        block = _gate(
            target=target,
            patched=patched,
            source_path=TARGET_FILE,
            target_symbol=TARGET_SYMBOL,
            context=context,
            authoritative_source=source,
        )
        assert not _accepted(block)
        assert block["candidate_novelty_reason"] == REASON_NOVEL_EXTERNAL_REFERENCE
        assert block["candidate_novelty_blocking_reasons"] == [
            REASON_NOVEL_EXTERNAL_REFERENCE
        ]
        assert block["candidate_novelty_unexplained_identifiers"] == ["value"]
        assert {
            item["name"] for item in block["candidate_novelty_findings"]
        } == {"value"}
        results.append(block["candidate_novelty_reason"])
    assert results[0] == results[1]


def _fixture_context(tmp_path: Path, source: str):
    (tmp_path / "helper.py").write_text(
        "def existing_helper(value):\n    return value\n", encoding="utf-8"
    )
    (tmp_path / "target.py").write_text(source, encoding="utf-8")
    context = build_authoritative_binding_context(
        repo_root=tmp_path,
        source_path="target.py",
        target_symbol="target",
        authoritative_source=source,
    )
    assert context is not None
    return context


def test_repository_local_direct_import_is_generic_and_alias_aware(tmp_path):
    source = (
        "from helper import existing_helper as bound_helper\n\n"
        "def target(value):\n"
        "    return value\n"
    )
    context = _fixture_context(tmp_path, source)
    block = _gate(
        target="    return value",
        patched="    return bound_helper(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert _accepted(block)
    assert context.repository_import_names == frozenset({"bound_helper"})


def test_removing_the_baseline_import_rejects_the_same_candidate(tmp_path):
    source = "def target(value):\n    return value\n"
    context = _fixture_context(tmp_path, source)
    block = _gate(
        target="    return value",
        patched="    return existing_helper(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert block["candidate_novelty_reason"] == REASON_UNRESOLVED_NOVEL_IDENTIFIER


@pytest.mark.parametrize(
    ("import_line", "helper_name"),
    [
        ("from os import remove", "remove"),
        ("from requests import get", "get"),
    ],
)
def test_nonlocal_direct_imports_are_not_newly_admitted(
    tmp_path, import_line, helper_name
):
    source = f"{import_line}\n\ndef target(value):\n    return value\n"
    (tmp_path / "target.py").write_text(source, encoding="utf-8")
    context = build_authoritative_binding_context(
        repo_root=tmp_path,
        source_path="target.py",
        target_symbol="target",
        authoritative_source=source,
    )
    assert context is not None
    assert helper_name not in context.repository_import_names
    block = _gate(
        target="    return value",
        patched=f"    return {helper_name}(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert block["candidate_novelty_reason"] == REASON_UNRESOLVED_NOVEL_IDENTIFIER


def test_existing_module_object_does_not_grant_namespace_members(tmp_path):
    source = "import helper as helper_namespace\n\ndef target(value):\n    return value\n"
    context = _fixture_context(tmp_path, source)
    assert context.repository_import_names == frozenset()
    block = _gate(
        target="    return value",
        patched="    return helper_namespace.existing_helper(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert set(block["candidate_novelty_unexplained_identifiers"]) == {
        "existing_helper", "helper_namespace"
    }


def test_helper_elsewhere_in_repo_is_not_a_binding(tmp_path):
    source = "def target(value):\n    return value\n"
    context = _fixture_context(tmp_path, source)
    (tmp_path / "unrelated.py").write_text(
        "def elsewhere(value):\n    return value\n", encoding="utf-8"
    )
    block = _gate(
        target="    return value",
        patched="    return elsewhere(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert block["candidate_novelty_unexplained_identifiers"] == ["elsewhere"]


@pytest.mark.parametrize(
    "typo", ["observe_indentation", "observe_source_indent", "source_observer"]
)
def test_typo_and_hallucination_names_remain_unresolved(live_context, typo):
    context, source = live_context
    block = _gate(
        target=TARGET_BODY.rstrip("\n"),
        patched=f"    return {typo}(text)",
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert block["candidate_novelty_unexplained_identifiers"] == [typo]


def test_candidate_created_import_and_import_modification_remain_forbidden(tmp_path):
    source = (
        "from helper import existing_helper\n\n"
        "def target(value):\n"
        "    return value\n"
    )
    context = _fixture_context(tmp_path, source)
    block = _gate(
        target="    return value",
        patched="    from helper import existing_helper\n    return existing_helper(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert block["candidate_novelty_reason"] == REASON_NOVEL_IMPORT

    target = source
    patched = source.replace(
        "from helper import existing_helper",
        "from helper import existing_helper, added_helper",
    )
    allowed = (
        patch_gates._identifiers_in(target, language="python")
        | patch_gates._LANGUAGE_KEYWORDS
        | patch_gates._LANGUAGE_BUILTINS["python"]
    )
    classification = classify_candidate_novelty(
        target_snippet=target,
        patched_snippet=patched,
        language="python",
        allowed_identifiers=allowed,
        target_node_kind="function",
        target_node_name="target",
    )
    assert REASON_NOVEL_IMPORT in classification.blocking_reasons


def test_candidate_created_stdlib_import_and_unbound_namespace_remain_forbidden(
    tmp_path,
):
    source = "def target(value):\n    return value\n"
    context = _fixture_context(tmp_path, source)
    new_import = _gate(
        target="    return value",
        patched="    from os import remove\n    return remove(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    namespace = _gate(
        target="    return value",
        patched="    return subprocess.run(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(new_import)
    assert new_import["candidate_novelty_reason"] == REASON_NOVEL_IMPORT
    assert not _accepted(namespace)
    assert set(namespace["candidate_novelty_unexplained_identifiers"]) == {
        "run",
        "subprocess",
    }


def test_candidate_local_shadowing_wins_over_the_module_binding(tmp_path):
    source = (
        "from helper import existing_helper\n\n"
        "def target(value):\n"
        "    return value\n"
    )
    context = _fixture_context(tmp_path, source)
    block = _gate(
        target="    return value",
        patched=(
            "    existing_helper = value\n"
            "    return existing_helper"
        ),
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert _accepted(block)
    assert block["candidate_novelty_reason"] == (
        REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY
    )
    assert block["candidate_novelty_local_binding_names"] == ["existing_helper"]
    assert block["authoritative_binding_context_reused_names"] == []


def test_existing_function_local_shadows_the_same_named_module_binding(tmp_path):
    source = (
        "from helper import existing_helper\n\n"
        "def target(value):\n"
        "    existing_helper = value\n"
        "    return value\n"
    )
    context = _fixture_context(tmp_path, source)
    assert context.binding_kind("existing_helper") == "existing_local"
    block = _gate(
        target="    return value",
        patched="    return existing_helper",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=source,
    )
    assert _accepted(block)
    assert block["authoritative_binding_context_reused_names"] == [
        "existing_helper"
    ]


def test_round9_style_lstrip_member_is_not_rescued(live_context):
    context, source = live_context
    block = _gate(
        target=TARGET_BODY.rstrip("\n"),
        patched="    return text.lstrip()",
        source_path=TARGET_FILE,
        target_symbol=TARGET_SYMBOL,
        context=context,
        authoritative_source=source,
    )
    assert not _accepted(block)
    assert block["candidate_novelty_reason"] == REASON_NOVEL_EXTERNAL_REFERENCE
    assert block["candidate_novelty_unexplained_identifiers"] == ["lstrip"]


def test_stale_context_and_missing_context_fail_closed(tmp_path):
    source = (
        "from helper import existing_helper\n\n"
        "def target(value):\n"
        "    return value\n"
    )
    context = _fixture_context(tmp_path, source)
    changed_source = "# replacement\n" + source
    stale = _gate(
        target="    return value",
        patched="    return existing_helper(value)",
        source_path="target.py",
        target_symbol="target",
        context=context,
        authoritative_source=changed_source,
    )
    missing = _gate(
        target="    return value",
        patched="    return existing_helper(value)",
        source_path="target.py",
        target_symbol="target",
    )
    assert not _accepted(stale)
    assert stale["authoritative_binding_context_current"] is False
    assert not _accepted(missing)
    assert "authoritative_binding_context_phase_id" not in missing


def test_production_finalization_builds_context_only_for_control_target(live_context):
    state = AgentState(
        interface="agent",
        mode="reviewer",
        user_input="repair",
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language="python",
        task_type="bug_fix",
    )
    state.repo_path = str(ROOT)
    state.patch_style = "safe_minimal"
    state.task_info = {"patch_style": "safe_minimal"}
    state.control_result = {
        "patch_intent": {
            "target_file": TARGET_FILE,
            "target_symbol": TARGET_SYMBOL,
            "source_snippet": TARGET_FUNCTION,
        }
    }
    payload = {
        "summary": "",
        "issues": [],
        "patch_candidate": {
            "file": TARGET_FILE,
            "relative_path": TARGET_FILE,
            "target_node_name": TARGET_SYMBOL,
            "target_node_kind": "function",
            "target_snippet": TARGET_BODY.rstrip("\n"),
            "patched_snippet": BOUND_CALL_BODY.rstrip("\n"),
        },
        "confidence": 0.9,
        "needs_escalation": False,
    }
    pipeline.finalize_answer(state, json.dumps(payload))
    assert _accepted(state.json_block)
    assert state.json_block["authoritative_binding_context_current"] is True
    assert state.json_block["authoritative_binding_context_phase_id"] == PHASE_ID


def test_field_admitted_exact_candidate_never_gains_execution_authority(monkeypatch):
    state = AgentState(
        interface="agent",
        mode="reviewer",
        user_input="repair",
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language="python",
        task_type="bug_fix",
    )
    state.repo_path = str(ROOT)
    state.patch_style = "safe_minimal"
    state.task_info = {"patch_style": "safe_minimal"}
    state.control_result = {
        "patch_intent": {
            "target_file": TARGET_FILE,
            "target_symbol": TARGET_SYMBOL,
            "source_snippet": TARGET_FUNCTION,
        }
    }
    payload = {
        "summary": "",
        "issues": [],
        "patch_candidate": {
            "file": TARGET_FILE,
            "relative_path": TARGET_FILE,
            "target_node_name": TARGET_SYMBOL,
            "target_node_kind": "function",
            "target_snippet": TARGET_BODY.rstrip("\n"),
            "patched_snippet": CORRECT_BODY.rstrip("\n"),
        },
        "confidence": 0.9,
        "needs_escalation": False,
    }
    pipeline.finalize_answer(state, json.dumps(payload))
    assert state.json_block["patch_candidate"] is not None
    assert state.json_block["candidate_effect_status"] == "mutating"
    assert state.json_block["candidate_novelty_unexplained_identifiers"] == []

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert state.json_block["execution_authorized"] is False
    assert state.json_block["final_repository_changed"] is False


def test_context_cost_is_bounded_and_caps_are_unchanged():
    samples = []
    source = (ROOT / TARGET_FILE).read_text(encoding="utf-8")
    for _ in range(31):
        context = build_authoritative_binding_context(
            repo_root=ROOT,
            source_path=TARGET_FILE,
            target_symbol=TARGET_SYMBOL,
            authoritative_source=source,
        )
        assert context is not None
        samples.append(context.construction_seconds)
    assert statistics.median(samples) < 0.1
    assert (MAX_NOVEL_LOCAL_BINDINGS, MAX_TOUCHED_FUNCTIONS, MAX_CHANGED_LINES) == (
        3, 1, 24
    )
