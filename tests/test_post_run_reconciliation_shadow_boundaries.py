"""Static authority-boundary regressions for CHECK.LIVE.1.

The focused shadow suite owns behaviour.  These tests prove that the live
wiring has only the machinery needed to *observe*: it cannot decide a
reconciliation, cannot widen an authority, cannot grow a repository walk,
cannot re-run a validation or a patch, cannot reach a model or the network, and
cannot modify the frozen CHECK.1 or CHECK.2 contracts it consumes.

Honest *negative* guardrail keys are intentionally permitted as literals:
``patch_applied = False`` is a denial, not a capability.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"

_OBSERVER = _CORE_ROOT / "live_change_observation.py"
_AUTHORIZATION_PRODUCER = _CORE_ROOT / "live_execution_authorization.py"
_WORKER_DECLARATION_PRODUCER = _CORE_ROOT / "live_worker_declaration.py"
_WORKER_REPORT_PRODUCER = _CORE_ROOT / "live_worker_report.py"
_VALIDATION_PRODUCER = _CORE_ROOT / "live_validation_receipt.py"
_ORCHESTRATOR = _CORE_ROOT / "post_run_reconciliation_shadow.py"
_WIRING_SITE = _CORE_ROOT / "run_lifecycle.py"

_CHECK_LIVE_1_SOURCES = (
    _OBSERVER,
    _AUTHORIZATION_PRODUCER,
    _WORKER_DECLARATION_PRODUCER,
    _WORKER_REPORT_PRODUCER,
    _VALIDATION_PRODUCER,
    _ORCHESTRATOR,
)

#: The two frozen CHECK.1 modules and the frozen CHECK.2 module.  CHECK.LIVE.1
#: consumes the first two and must not touch any of the three.
_FROZEN_CHECK_1 = (
    _CORE_ROOT / "post_run_reconciliation.py",
    _CORE_ROOT / "post_run_observation.py",
)
_FROZEN_CHECK_2 = (_CORE_ROOT / "goal_fidelity_review.py",)


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
                qualified = f"{module}.{alias.name}" if module else alias.name
                yield qualified, node.lineno


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function {name}")


# -- No new power -------------------------------------------------------------

def test_the_live_wiring_never_mutates_the_worktree():
    """Observation only: no write, no rollback, no reset, no stash, no clean."""
    # Leaf names that can only mean a filesystem mutation.  ``replace`` and
    # ``copy`` are deliberately absent: both are ordinary ``str``/``dict``
    # methods, so they are checked by qualified name instead.
    forbidden_calls = frozenset(
        {
            "chmod",
            "cleanup_backup",
            "copytree",
            "makedirs",
            "mkdir",
            "restore_backup",
            "rmdir",
            "rmtree",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
    )
    forbidden_qualified = frozenset(
        {
            "os.chmod",
            "os.makedirs",
            "os.mkdir",
            "os.remove",
            "os.removedirs",
            "os.rename",
            "os.replace",
            "os.rmdir",
            "os.unlink",
            "shutil.copy",
            "shutil.copy2",
            "shutil.copytree",
            "shutil.move",
            "shutil.rmtree",
        }
    )
    violations: list[str] = []
    for path in _CHECK_LIVE_1_SOURCES:
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.split(".", 1)[0] in {"shutil", "tempfile"}:
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            leaf = name.rsplit(".", 1)[-1]
            if leaf in forbidden_calls or name in forbidden_qualified:
                violations.append(f"{path.name}:{call.lineno}: {name}")
    assert violations == [], violations


def test_the_live_wiring_runs_no_subprocess_git_model_or_network():
    forbidden_modules = (
        "agents",
        "aiohttp",
        "google",
        "http",
        "httpx",
        "ollama",
        "openai",
        "reasoning",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    )
    violations: list[str] = []
    for path in _CHECK_LIVE_1_SOURCES:
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.split(".", 1)[0] in forbidden_modules:
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            leaf = name.rsplit(".", 1)[-1]
            if leaf in {
                "Popen",
                "check_call",
                "check_output",
                "getoutput",
                "popen",
                "run_gemini_request",
                "run_deepseek_review",
                "system",
                "urlopen",
            }:
                violations.append(f"{path.name}:{call.lineno}: {name}")
    assert violations == [], violations


def test_the_live_wiring_never_applies_a_patch_or_runs_a_validation():
    forbidden = frozenset(
        {
            "apply_patch",
            "apply_patch_from_json",
            "apply_patch_plan",
            "run_patch_plan_with_artifacts",
            "run_safe_validation_command",
            "run_self_correct_loop",
            "run_validation_command",
        }
    )
    violations: list[str] = []
    for path in _CHECK_LIVE_1_SOURCES:
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.rsplit(".", 1)[-1] in forbidden:
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden:
                violations.append(f"{path.name}:{call.lineno}: {name}")
    assert violations == [], violations


def test_the_bounded_observer_cannot_enumerate_a_directory():
    """Enumeration needs modules the observer deliberately does not import."""
    tree = _tree(_OBSERVER)
    modules = {module for module, _line in _imported_modules(tree)}

    assert "os" not in modules
    assert "glob" not in modules
    assert "fnmatch" not in modules
    for call, name in _calls(tree):
        assert name.rsplit(".", 1)[-1] not in {
            "glob",
            "iterdir",
            "listdir",
            "rglob",
            "scandir",
            "walk",
        }, f"{call.lineno}: {name}"


def test_the_observer_reads_are_bounded_and_content_is_never_retained():
    """Digests leave the observer; file bodies do not."""
    from core.live_change_observation import (
        LiveObservedChangeSet,
        LivePathDigests,
        MAX_DIGEST_BYTES,
        MAX_OBSERVED_PATHS,
    )
    import dataclasses

    assert MAX_OBSERVED_PATHS == 256
    assert MAX_DIGEST_BYTES == 8 * 1024 * 1024

    for record in (LivePathDigests, LiveObservedChangeSet):
        for field in dataclasses.fields(record):
            assert not any(
                token in field.name
                for token in ("body", "content", "diff", "source", "text")
            ), field.name


# -- No new authority ---------------------------------------------------------

def test_the_authorization_producer_cannot_mint_a_path_expansion_receipt():
    tree = _tree(_AUTHORIZATION_PRODUCER)
    for _call, name in _calls(tree):
        assert name.rsplit(".", 1)[-1] != "PathExpansionReceipt", name

    from core.live_execution_authorization import (
        build_live_execution_authorization,
    )
    from core.post_run_reconciliation import PATH_AUTHORITY_WRITABLE

    authorization = build_live_execution_authorization(
        execution_run_id="run",
        repository_id="repo",
        task_contract_fingerprint="a" * 64,
        pre_execution_state_fingerprint="b" * 64,
        upstream_authority={"core/a.py": PATH_AUTHORITY_WRITABLE},
        upstream_authority_fingerprint="c" * 64,
    )
    assert authorization.path_expansion_receipts == ()


def test_the_authorization_producer_reuses_the_frozen_patch_safety_gate():
    tree = _tree(_AUTHORIZATION_PRODUCER)
    modules = {module for module, _line in _imported_modules(tree)}

    assert "core.post_run_observation.classify_authorized_paths" in modules
    # The gate is reached through the frozen adapter, never re-implemented.
    assert not any(
        module.startswith("core.patch_safety") for module in modules
    ), modules


def test_the_worker_declaration_contract_is_structurally_independent():
    tree = _tree(_WORKER_DECLARATION_PRODUCER)
    modules = {module for module, _line in _imported_modules(tree)}

    for forbidden in (
        "core.live_execution_authorization",
        "core.post_run_reconciliation_shadow",
        "core.live_change_observation",
    ):
        assert not any(module.startswith(forbidden) for module in modules), modules
    assert not any(module.startswith("patching") for module in modules), modules

    forbidden_names = {
        "ExecutionAuthorization",
        "ObservedPostRunFacts",
        "patch_plan",
    }
    referenced_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    overlap = referenced_names & forbidden_names
    assert referenced_names.isdisjoint(forbidden_names), overlap


def test_every_producer_declares_it_holds_no_authority():
    from core.live_change_observation import live_change_observation_guardrails
    from core.live_execution_authorization import live_authorization_guardrails
    from core.live_validation_receipt import live_validation_guardrails
    from core.live_worker_declaration import (
        worker_declaration_authority,
        worker_declaration_guardrails,
    )
    from core.live_worker_report import live_worker_report_guardrails
    from core.post_run_reconciliation_shadow import shadow_guardrails

    for guardrails in (
        live_change_observation_guardrails(),
        live_authorization_guardrails(),
        live_validation_guardrails(),
        worker_declaration_guardrails(),
        live_worker_report_guardrails(),
        shadow_guardrails(),
    ):
        assert guardrails["authoritative_effect"] is False
        assert guardrails["human_approval_required"] is True
        for denied in (
            "files_modified",
            "model_called",
            "network_call_performed",
            "patch_applied",
            "repository_traversed",
            "validation_executed",
        ):
            if denied in guardrails:
                assert guardrails[denied] is False, denied

    shadow = shadow_guardrails()
    assert shadow["shadow_only"] is True
    assert shadow["check_2_invoked"] is False
    assert shadow["check_3_implemented"] is False
    assert shadow["reconciliation_policy_reimplemented"] is False
    assert shadow["git_stash_invoked"] is False

    authority = worker_declaration_authority()
    assert authority["worker_self_report_authority"] is True
    assert authority["write_authority"] is False
    assert authority["patch_authority"] is False
    assert authority["validation_authority"] is False
    assert authority["observed_fact_authority"] is False


def test_the_shadow_receipt_cannot_claim_an_authoritative_effect():
    import dataclasses

    from core.post_run_reconciliation_shadow import ShadowPostRunCheckReceipt

    fields = {field.name for field in dataclasses.fields(ShadowPostRunCheckReceipt)}
    assert "authoritative_effect" not in fields

    receipt = ShadowPostRunCheckReceipt(
        execution_run_id="run",
        repository_id="repo",
        authoritative_run_status="success",
        shadow_outcome="evaluated",
        producer_completeness="complete",
    )
    assert receipt.authoritative_effect is False
    assert receipt.as_dict()["authoritative_effect"] is False
    assert receipt.result_metadata()[
        "post_run_reconciliation_authoritative_effect"
    ] is False


# -- CHECK.2 and CHECK.3 stay out of the live path ----------------------------

def test_check_2_is_not_reachable_from_the_live_wiring():
    violations: list[str] = []
    for path in _CHECK_LIVE_1_SOURCES + (_WIRING_SITE,):
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if "goal_fidelity" in module or "claim_assessment" in module:
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in {
                "review_goal_fidelity",
                "assess_claim",
                "reconcile_goal_fidelity",
            }:
                violations.append(f"{path.name}:{call.lineno}: {name}")
    assert violations == [], violations


def test_no_check_3_run_verdict_vocabulary_exists():
    for path in _CHECK_LIVE_1_SOURCES:
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "run_verdict",
            "merge_ready",
            "acceptance_gate",
            "goal_satisfied",
            "implementation_correct",
        ):
            assert forbidden not in source, f"{path.name}: {forbidden}"


# -- The frozen contracts stay frozen -----------------------------------------

def test_the_frozen_check_1_and_check_2_modules_declare_the_phase_that_owns_them():
    """CHECK.LIVE.1 consumes these modules; it does not own or edit them."""
    for path in _FROZEN_CHECK_1:
        assert 'PHASE_ID = "CHECK.1"' in path.read_text(encoding="utf-8"), path.name
    for path in _FROZEN_CHECK_2:
        assert 'PHASE_ID = "CHECK.2"' in path.read_text(encoding="utf-8"), path.name


def test_the_frozen_modules_have_not_gained_a_live_wiring_import():
    """The dependency runs one way: live wiring depends on CHECK.1, never back."""
    violations: list[str] = []
    for path in _FROZEN_CHECK_1 + _FROZEN_CHECK_2:
        for module, line in _imported_modules(_tree(path)):
            if module.startswith("core.live_") or module.startswith(
                "core.post_run_reconciliation_shadow"
            ):
                violations.append(f"{path.name}:{line}: import {module}")
    assert violations == [], violations


def test_the_registry_freezes_the_check_1_and_check_2_cores_for_this_phase():
    from core.phase_registry import load_phase_registry

    registry = load_phase_registry(
        str(_REPOSITORY_ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    phase = {item["phase_id"]: item for item in registry["phases"]}["CHECK.LIVE.1"]

    for frozen in (
        "core/post_run_reconciliation.py",
        "core/post_run_observation.py",
        "core/goal_fidelity_review.py",
        "core/claim_assessment.py",
        "core/patch_safety.py",
        "core/executor.py",
        "core/validation_execution.py",
    ):
        assert frozen in phase["forbidden_files"], frozen
        assert frozen not in phase["allowed_files"], frozen


# -- The wiring site itself ---------------------------------------------------

def test_the_wiring_site_touches_the_result_only_through_the_receipt():
    """The apply path may attach shadow metadata; it may not rewrite a result."""
    tree = _tree(_WIRING_SITE)
    attach = _function(tree, "_attach_shadow_post_run_reconciliation")

    updated_keys: list[str] = []
    for call, name in _calls(attach):
        if name == "result.update":
            for argument in call.args:
                source = (
                    _qualified_name(argument.func)
                    if isinstance(argument, ast.Call)
                    else _qualified_name(argument)
                )
                updated_keys.append(source or "<literal>")
            continue
        assert name.rsplit(".", 1)[-1] not in {
            "pop",
            "setdefault",
            "clear",
        }, name
    assert updated_keys == ["receipt.result_metadata"], updated_keys

    for node in ast.walk(attach):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            raise AssertionError("the shadow wiring assigns into the run result")


def test_the_wiring_site_is_guarded_by_the_default_off_flag():
    tree = _tree(_WIRING_SITE)
    entry = _function(tree, "run_patch_plan_with_artifacts")

    guarded = [
        node
        for node in ast.walk(entry)
        if isinstance(node, ast.If)
        and _qualified_name(node.test) == "shadow_enabled"
    ]
    # One pre-apply observation, two early-exit records, one terminal check.
    assert len(guarded) == 4, len(guarded)

    for call, name in _calls(entry):
        assert name.rsplit(".", 1)[-1] not in {
            "run_shadow_post_run_reconciliation",
        }, f"{call.lineno}: the unguarded entry point must not be used"


def test_the_wiring_site_uses_only_the_failure_isolated_entry_point():
    tree = _tree(_WIRING_SITE)
    modules = {module for module, _line in _imported_modules(tree)}

    assert (
        "core.post_run_reconciliation_shadow.safe_run_shadow_post_run_reconciliation"
        in modules
    )
    assert (
        "core.post_run_reconciliation_shadow.run_shadow_post_run_reconciliation"
        not in modules
    )
