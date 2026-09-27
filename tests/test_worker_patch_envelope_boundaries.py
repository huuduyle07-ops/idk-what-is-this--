"""Static boundary regressions for WORKER.DECL.2A.

The focused suite owns behaviour.  These tests prove the strict envelope has
only the machinery needed to *refuse*: it cannot reach a model, a provider SDK,
the network, a subprocess or the filesystem; it cannot recover JSON from prose
by any of the four techniques the legacy extractor uses; it cannot truncate; it
cannot carry authority; and it cannot change which patch a run applies.

Honest *negative* guardrail keys are intentionally permitted as literals:
``model_called = False`` is a denial, not a capability.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from core.worker_patch_envelope import (
    ALLOWED_ENVELOPE_KEYS,
    ALLOWED_OPERATION_KEYS,
    FORBIDDEN_AUTHORITY_KEYS,
    OPERATION_CREATE_FILE,
    OPERATION_REPLACE_SNIPPET,
    worker_patch_envelope_guardrails,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"

_ENVELOPE = _CORE_ROOT / "worker_patch_envelope.py"
_WIRING_SITE = _CORE_ROOT / "run_lifecycle.py"
_LEGACY_EXTRACTOR = _CORE_ROOT / "json_utils.py"
_EXECUTOR = _REPOSITORY_ROOT / "patching" / "patch_plan_executor.py"

#: Producer sites that measure a real worker response.
_PRODUCER_SITES = (
    _CORE_ROOT / "pipeline.py",
    _CORE_ROOT / "sleeping_consultant.py",
    _REPOSITORY_ROOT / "scripts" / "run_patch_proposal_queue.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _imported_modules(tree: ast.AST) -> Iterable[tuple[str, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module, node.lineno
            for alias in node.names:
                yield (f"{module}.{alias.name}" if module else alias.name), node.lineno


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


# ── The strict parser cannot recover JSON from prose ──────────────────────────

def test_the_envelope_owns_none_of_the_legacy_recovery_machinery():
    """The four techniques the legacy extractor uses are all absent here.

    ``extract_json_block`` finds fenced blocks with a regular expression and
    then walks the text brace by brace.  If any of that appeared in this module
    the strict channel would be a second heuristic reader wearing a contract's
    name.
    """
    tree = _tree(_ENVELOPE)
    modules = {name for name, _line in _imported_modules(tree)}

    assert "re" not in modules
    assert not {name for name in modules if name.startswith("core.json_utils")}
    assert "core.json_utils" not in modules

    source = _ENVELOPE.read_text(encoding="utf-8")
    for technique in ("re.findall", "re.search", "re.finditer", "re.compile"):
        assert technique not in source, technique
    for call, name in _calls(tree):
        assert name != "extract_json_block", call.lineno

    # And the one decoder entry point that could recover a prefix is used only
    # to classify a rejection: it appears exactly once, inside the helper whose
    # return type is a status string.
    assert source.count("raw_decode") == 1
    classifier = next(
        function
        for function in _functions(tree)
        if function.name == "_rejection_status_for_undecodable"
    )
    assert any(name.endswith("raw_decode") for _call, name in _calls(classifier))
    for node in ast.walk(classifier):
        if isinstance(node, ast.Return):
            # Every exit hands back a bounded status name, never a decoded value.
            assert isinstance(node.value, ast.Name)


def test_the_envelope_reaches_no_model_provider_network_or_subprocess():
    tree = _tree(_ENVELOPE)
    modules = {name for name, _line in _imported_modules(tree)}

    for forbidden in (
        "agents",
        "google",
        "google.genai",
        "genai",
        "ollama",
        "requests",
        "httpx",
        "urllib",
        "urllib.request",
        "socket",
        "subprocess",
        "shutil",
        "pathlib",
        "core.pipeline",
        "core.executor",
        "core.self_correct_loop",
        "patching",
        "patching.patch_plan_executor",
    ):
        assert not any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for module in modules
        ), forbidden

    for _call, name in _calls(tree):
        assert name not in {
            "open",
            "run",
            "Popen",
            "check_output",
            "walk",
            "rglob",
            "iterdir",
            "read_text",
            "write_text",
            "generate_content",
        }, name


def test_the_envelope_touches_the_environment_only_through_its_own_flag():
    tree = _tree(_ENVELOPE)
    getenv_calls = [
        call for call, name in _calls(tree) if name in {"getenv", "os.getenv"}
    ]
    assert len(getenv_calls) == 1
    only = getenv_calls[0]
    assert len(only.args) == 1
    assert isinstance(only.args[0], ast.Name)
    assert only.args[0].id == "ENVIRONMENT_FLAG"


def test_the_envelope_imports_no_checker_module():
    """The worker protocol is upstream of every CHECK phase and stays that way."""
    modules = {name for name, _line in _imported_modules(_tree(_ENVELOPE))}
    for checker in (
        "core.post_run_reconciliation",
        "core.post_run_observation",
        "core.post_run_reconciliation_shadow",
        "core.goal_fidelity_review",
        "core.claim_assessment",
        "core.live_worker_declaration",
        "core.live_worker_report",
    ):
        assert not any(
            module == checker or module.startswith(f"{checker}.")
            for module in modules
        ), checker


# ── The contract cannot carry authority, and cannot truncate ──────────────────

def test_no_allow_listed_key_could_assert_a_decision():
    allowed = set(ALLOWED_ENVELOPE_KEYS)
    for keys in ALLOWED_OPERATION_KEYS.values():
        allowed |= set(keys)

    assert not allowed & set(FORBIDDEN_AUTHORITY_KEYS)
    for key in allowed:
        lowered = key.lower()
        for word in ("authority", "approve", "approved", "allowed", "merge"):
            assert word not in lowered, key


def test_the_operation_allow_lists_match_the_existing_executor_vocabulary():
    """§7: this is a mirror of the apply engine's table, not a new dialect."""
    executor_source = _EXECUTOR.read_text(encoding="utf-8")
    # EXEC.PLAN.1 moved raw schema parsing to the preparation owner.
    executor_source += (_EXECUTOR.parent / "patch_plan_transaction.py").read_text(encoding="utf-8")
    assert 'op_type == "create_file"' in executor_source
    assert 'op_type == "replace_snippet"' in executor_source
    assert "allowed: create_file, replace_snippet" in executor_source

    assert set(ALLOWED_OPERATION_KEYS) == {
        OPERATION_CREATE_FILE,
        OPERATION_REPLACE_SNIPPET,
    }
    # Every field name in the allow-lists is one the executor actually reads.
    for keys in ALLOWED_OPERATION_KEYS.values():
        for key in keys:
            if key == "op":
                continue
            assert f'"{key}"' in executor_source or f"'{key}'" in executor_source, key


def test_the_parser_never_shortens_a_plan_or_a_payload():
    """§11: over a bound is invalid, never trimmed.

    A slice or a truncation helper anywhere in the parse path could silently
    change what a patch means, so none exists.
    """
    source = _ENVELOPE.read_text(encoding="utf-8")
    for technique in ("[:MAX_ENVELOPE_OPERATIONS", "[:MAX_OPERATION_PAYLOAD_CHARS"):
        assert technique not in source, technique

    tree = _tree(_ENVELOPE)
    parser = next(
        function
        for function in _functions(tree)
        if function.name == "parse_strict_worker_patch_envelope"
    )
    for node in ast.walk(parser):
        assert not isinstance(node, ast.Subscript) or not isinstance(
            node.slice, ast.Slice
        ), "the strict parser must not slice its input"


def test_every_declined_power_is_declared():
    guardrails = worker_patch_envelope_guardrails()
    for declined in (
        "prose_parsed",
        "fenced_block_extracted",
        "balanced_brace_scanned",
        "first_object_selected",
        "regular_expression_used",
        "markdown_repaired",
        "output_truncated",
        "model_called",
        "model_repair_requested",
        "provider_sdk_imported",
        "network_call_performed",
        "repository_traversed",
        "source_content_read",
        "validation_executed",
        "patch_applied",
        "patch_semantics_changed",
        "patch_selection_changed",
        "files_modified",
        "authoritative_effect",
    ):
        assert guardrails[declined] is False, declined
    assert guardrails["strict_one_object_protocol"] is True
    assert guardrails["human_approval_required"] is True


# ── The wiring observes and nothing more ──────────────────────────────────────

def test_the_wiring_site_persists_the_record_and_never_reads_it_back():
    """The lifecycle writes one artifact; no branch downstream consults it."""
    tree = _tree(_WIRING_SITE)
    source = _WIRING_SITE.read_text(encoding="utf-8")

    assert source.count("ENVELOPE_ARTIFACT_NAME") == 2  # the import and the write
    assert "worker_patch_response" in source

    # The record reaches exactly one sink: the additive replay artifact.
    for call, name in _calls(tree):
        if name != "safe_write_json":
            continue
        first = call.args[0]
        if isinstance(first, ast.Name) and first.id == "ENVELOPE_ARTIFACT_NAME":
            break
    else:  # pragma: no cover - the assertion below reports the real failure
        raise AssertionError("the envelope record is never persisted")

    # Nothing derives a plan, an authority or a run outcome from the record.
    for forbidden in (
        "patch_plan_operations",
        "parse_strict_worker_patch_envelope",
        "compare_strict_and_legacy",
    ):
        assert forbidden not in source, forbidden


def test_the_wiring_site_is_guarded_by_the_default_off_flag():
    tree = _tree(_WIRING_SITE)
    guarded = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and any(
            _qualified_name(call.func) == "is_strict_worker_patch_envelope_shadow_enabled"
            for call, _name in _calls(node.test)
        )
    ]
    assert len(guarded) == 1
    body = ast.dump(guarded[0])
    assert "ENVELOPE_ARTIFACT_NAME" in body


def test_the_lifecycle_argument_defaults_to_absent():
    """An existing caller that knows nothing of this phase behaves identically."""
    tree = _tree(_WIRING_SITE)
    entry = next(
        function
        for function in _functions(tree)
        if function.name == "run_patch_plan_with_artifacts"
    )
    names = [argument.arg for argument in entry.args.args]
    assert "worker_patch_response" in names
    # The claim is that the argument is optional and absent by default, not
    # that it is the final parameter: a later phase threading another bounded
    # observation through the same entry point must not break this test, and
    # WORKER.DECL.2A.1's `strict_envelope_emission` is exactly that case.
    offset = len(names) - len(entry.args.defaults)
    default = entry.args.defaults[names.index("worker_patch_response") - offset]
    assert isinstance(default, ast.Constant) and default.value is None


def test_the_wiring_site_only_accepts_an_already_typed_record():
    """A raw mapping is never laundered into a record at the persistence site."""
    tree = _tree(_WIRING_SITE)
    renderer = next(
        function
        for function in _functions(tree)
        if function.name == "_worker_patch_envelope_record"
    )
    checks = [
        call
        for call, name in _calls(renderer)
        if name == "isinstance"
    ]
    assert len(checks) == 1
    assert isinstance(checks[0].args[1], ast.Name)
    assert checks[0].args[1].id == "WorkerPatchResponseCompatibility"


def test_every_producer_site_measures_behind_the_flag_and_changes_no_plan():
    """§16/§22: measurement is guarded, and the applied plan is untouched."""
    for path in _PRODUCER_SITES:
        source = path.read_text(encoding="utf-8")
        assert "safe_compare_strict_and_legacy" in source, path.name
        assert "is_strict_worker_patch_envelope_shadow_enabled" in source, path.name
        # The unguarded, raising entry point never appears on a live path.
        assert "compare_strict_and_legacy(" in source
        assert " compare_strict_and_legacy(" not in source.replace(
            "safe_compare_strict_and_legacy(", "safe_compare("
        ), path.name

        tree = _tree(path)
        for call, name in _calls(tree):
            if name != "safe_compare_strict_and_legacy":
                continue
            # Measured, then handed on: it is never assigned into a plan.
            assert len(call.args) == 2, path.name

        # No producer builds an envelope and applies it.
        assert "patch_plan_operations" not in source, path.name
        assert "parse_strict_worker_patch_envelope" not in source, path.name


def test_the_legacy_extractor_is_untouched_by_this_phase():
    """The legacy channel keeps working exactly as it did, prose and all."""
    source = _LEGACY_EXTRACTOR.read_text(encoding="utf-8")
    assert "WORKER.DECL" not in source
    assert "worker_patch_envelope" not in source
    assert "_find_balanced_json_objects" in source
    assert "def extract_json_block" in source
