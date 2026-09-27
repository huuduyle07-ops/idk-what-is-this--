"""OPS.VALIDATE.3 — bounded existing-check evidence for one exact candidate.

Whole-repository validation, bounded defect reproduction, and targeted
repository validation answer different questions.  This module implements only
the third one: given an already-loaded repository graph and an exact localized
target, which *existing repository-owned* pytest checks are structurally
related, and do the same checks pass before and after an exact sandboxed
candidate?

There is deliberately no model call, semantic-similarity selector, test
generation, repository discovery walk, confidence score, or authority result.
The graph is input data.  Selection is a deterministic scan of its existing
``resolved_call`` and ``imports`` edges.  Both validation runs use the existing
safe argv runner, which also supplies OPS.VALIDATE.2's isolated Python bytecode
cache and timeout semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.candidate_sandbox_validation import patch_plan_fingerprint
from core.repository_identity import derive_repository_id
from core.sandbox_self_evolution_runner import (
    cleanup_managed_sandbox,
    create_managed_sandbox,
)
from core.validation_execution import SafeValidationCommand, run_safe_validation_command
from core.validation_outcome import (
    CATEGORY_NO_TESTS_COLLECTED,
    CATEGORY_UNSAFE_VALIDATION_COMMAND,
    CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
    budget_exhausted_info,
    outcome_reason,
    validation_outcome,
)
from core.validator import classify_validation_output, detect_no_tests_collected


PHASE_ID = "OPS.VALIDATE.3"

DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS = 20
MAX_TARGETED_VALIDATION_BUDGET_SECONDS = 30
DEFAULT_MAX_TARGETED_TEST_FILES = 3
DEFAULT_MAX_TARGETED_TEST_NODES = 8
MAX_SELECTED_CHECK_IDENTIFIERS = 8
MAX_OUTPUT_EXCERPT_CHARS = 2_000

SIDE_EFFECT_SANDBOX_ONLY = "disposable_sandbox_no_copy_back"

SELECTION_EXPLICIT_USER_CHECK = "preserved_user_supplied_pytest_selector"
SELECTION_DIRECT_SYMBOL_CALL = "test_symbol_resolved_call_to_changed_symbol"
SELECTION_MODULE_DEPENDENCY = "test_module_imports_changed_module"

CATEGORY_TARGETED_CHECKS_PASSED = "targeted_checks_passed"
CATEGORY_TARGETED_DEFECT_REPAIRED = "targeted_defect_repaired"
CATEGORY_CHECKS_SELECTED = "checks_selected"
CATEGORY_NO_RELEVANT_EXISTING_CHECKS = "no_relevant_existing_checks"
CATEGORY_SELECTION_BUDGET_EXCEEDED = "selection_budget_exceeded"
CATEGORY_SELECTION_METADATA_UNAVAILABLE = "targeted_selection_metadata_unavailable"
CATEGORY_SELECTED_CHECK_MODIFIED = "selected_validation_check_modified"
CATEGORY_CANDIDATE_FINGERPRINT_STALE = "candidate_fingerprint_stale"
CATEGORY_REPOSITORY_IDENTITY_MISMATCH = "repository_identity_mismatch"
CATEGORY_BASELINE_TARGETED_FAILED = "baseline_targeted_failed"
CATEGORY_BASELINE_TARGETED_INCONCLUSIVE = "baseline_targeted_inconclusive"
CATEGORY_CANDIDATE_APPLY_FAILED = "candidate_apply_failed"
CATEGORY_SANDBOX_UNAVAILABLE = "sandbox_unavailable"
CATEGORY_TARGETED_VALIDATION_UNAVAILABLE = "targeted_validation_unavailable"
CATEGORY_TARGETED_VALIDATION_NOT_RUN = "targeted_validation_not_run"

_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+\.py$")
_SAFE_TEST_NAME_RE = re.compile(r"^test_[A-Za-z0-9_]+$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _node_file(graph: Any, node_id: str) -> str:
    node = getattr(graph, "nodes", {}).get(node_id)
    metadata = getattr(node, "metadata", {}) if node is not None else {}
    if isinstance(metadata, Mapping) and metadata.get("file"):
        return _normalize_path(metadata.get("file"))
    if "::" in node_id and not node_id.startswith("call::"):
        return _normalize_path(node_id.split("::", 1)[0])
    return _normalize_path(node_id)


def _is_test_file(path: str) -> bool:
    normalized = _normalize_path(path)
    if not normalized.endswith(".py"):
        return False
    name = Path(normalized).name
    return name.startswith("test_") or name.endswith("_test.py")


def _safe_selector(path: str, test_name: str = "") -> str:
    normalized = _normalize_path(path)
    if (
        not normalized
        or normalized.startswith("/")
        or ".." in Path(normalized).parts
        or not _SAFE_PATH_RE.fullmatch(normalized)
        or not _is_test_file(normalized)
    ):
        return ""
    if test_name:
        if not _SAFE_TEST_NAME_RE.fullmatch(test_name):
            return ""
        return f"{normalized}::{test_name}"
    return normalized


@dataclass(frozen=True, slots=True)
class TargetedCheck:
    """One existing repository check selected from structural metadata."""

    identifier: str
    path: str
    provenance: str
    source_node: str
    relation_target: str

    def as_dict(self) -> dict[str, str]:
        return {
            "identifier": self.identifier,
            "path": self.path,
            "provenance": self.provenance,
            "source_node": self.source_node,
            "relation_target": self.relation_target,
        }


@dataclass(frozen=True, slots=True)
class TargetedCheckSelection:
    checks: tuple[TargetedCheck, ...]
    complete: bool
    reason: str
    category: str
    elapsed_seconds: float
    related_check_count: int = 0


@dataclass(frozen=True, slots=True)
class TargetedValidationRequest:
    """Immutable identity, target, check-set, budget and side-effect contract."""

    repository_identity: str
    candidate_fingerprint: str
    changed_paths: tuple[str, ...]
    changed_symbols: tuple[str, ...]
    selected_checks: tuple[TargetedCheck, ...]
    selection_provenance: tuple[str, ...]
    selection_complete: bool
    selection_reason: str
    selection_category: str
    selection_elapsed_seconds: float
    related_check_count: int
    budget_seconds: int = DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS
    max_test_files: int = DEFAULT_MAX_TARGETED_TEST_FILES
    max_test_nodes: int = DEFAULT_MAX_TARGETED_TEST_NODES
    side_effect_policy: str = SIDE_EFFECT_SANDBOX_ONLY

    def __post_init__(self) -> None:
        if not self.repository_identity:
            raise ValueError("repository_identity must be non-empty")
        if len(self.candidate_fingerprint) != 64:
            raise ValueError("candidate_fingerprint must be a sha256 hex digest")
        if not isinstance(self.selected_checks, tuple):
            raise TypeError("selected_checks must be an immutable tuple")
        if not isinstance(self.selection_provenance, tuple):
            raise TypeError("selection_provenance must be an immutable tuple")
        if (
            not isinstance(self.budget_seconds, int)
            or isinstance(self.budget_seconds, bool)
            or not 0 < self.budget_seconds <= MAX_TARGETED_VALIDATION_BUDGET_SECONDS
        ):
            raise ValueError("targeted validation budget is outside its bounded range")
        if not 0 < self.max_test_files <= DEFAULT_MAX_TARGETED_TEST_FILES:
            raise ValueError("max_test_files exceeds the production cap")
        if not 0 < self.max_test_nodes <= DEFAULT_MAX_TARGETED_TEST_NODES:
            raise ValueError("max_test_nodes exceeds the production cap")

    @property
    def check_set_fingerprint(self) -> str:
        return _fingerprint(
            [
                {
                    "identifier": check.identifier,
                    "path": check.path,
                    "provenance": check.provenance,
                }
                for check in self.selected_checks
            ]
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "repository_identity": self.repository_identity,
            "candidate_fingerprint": self.candidate_fingerprint,
            "changed_paths": list(self.changed_paths),
            "changed_symbols": list(self.changed_symbols),
            "selected_checks": [check.as_dict() for check in self.selected_checks],
            "selection_provenance": list(self.selection_provenance),
            "selection_complete": self.selection_complete,
            "selection_reason": self.selection_reason,
            "selection_category": self.selection_category,
            "related_check_count": self.related_check_count,
            "check_set_fingerprint": self.check_set_fingerprint,
            "budget_seconds": self.budget_seconds,
            "max_test_files": self.max_test_files,
            "max_test_nodes": self.max_test_nodes,
            "side_effect_policy": self.side_effect_policy,
        }


@dataclass(frozen=True, slots=True)
class TargetedCheckRun:
    outcome: str
    category: str
    attempted: bool
    completed: bool
    timed_out: bool
    checks_executed: tuple[str, ...]
    output_excerpt: str = ""
    python_bytecode_cache_isolated: bool = False
    concrete_cases: tuple[tuple[str, str], ...] = ()
    oracle_source_fingerprint: str = ""
    oracle_unchanged: bool = False


@dataclass(frozen=True, slots=True)
class TargetedValidationResult:
    status: str
    category: str
    request: TargetedValidationRequest
    baseline_outcome: str = CATEGORY_TARGETED_VALIDATION_NOT_RUN
    baseline_category: str = ""
    candidate_outcome: str = CATEGORY_TARGETED_VALIDATION_NOT_RUN
    candidate_category: str = ""
    baseline_checks_executed: tuple[str, ...] = ()
    candidate_checks_executed: tuple[str, ...] = ()
    pre_patch_probe_result: str = ""
    reason: str = ""
    output_excerpt: str = ""
    timings: dict[str, float] = field(default_factory=dict)
    sandbox_cleanup_ok: bool = True
    baseline_python_bytecode_cache_isolated: bool = False
    candidate_python_bytecode_cache_isolated: bool = False
    baseline_concrete_cases: tuple[tuple[str, str], ...] = ()
    candidate_concrete_cases: tuple[tuple[str, str], ...] = ()
    oracle_source_unchanged: bool = False

    @property
    def checks_executed(self) -> tuple[str, ...]:
        return self.candidate_checks_executed or self.baseline_checks_executed

    def as_telemetry(self) -> dict[str, Any]:
        selected = [check.identifier for check in self.request.selected_checks]
        return {
            "targeted_validation_status": self.status,
            "targeted_validation_category": self.category,
            "checks_selected": selected,
            "checks_executed": list(self.checks_executed),
            "selected_check_count": len(selected),
            "selected_checks": selected[:MAX_SELECTED_CHECK_IDENTIFIERS],
            "selection_complete": self.request.selection_complete,
            "selection_reason": self.request.selection_reason,
            "selection_provenance": list(self.request.selection_provenance),
            "baseline_targeted_outcome": self.baseline_outcome,
            "baseline_targeted_category": self.baseline_category,
            "baseline_concrete_cases": [list(case) for case in self.baseline_concrete_cases],
            "candidate_concrete_cases": [list(case) for case in self.candidate_concrete_cases],
            "targeted_oracle_source_unchanged": self.oracle_source_unchanged,
            "baseline_checks_executed": list(self.baseline_checks_executed),
            "candidate_targeted_outcome": self.candidate_outcome,
            "candidate_targeted_category": self.candidate_category,
            "candidate_checks_executed": list(self.candidate_checks_executed),
            "targeted_validation_budget": self.request.budget_seconds,
            "candidate_fingerprint": self.request.candidate_fingerprint,
            "targeted_check_set_fingerprint": self.request.check_set_fingerprint,
            "targeted_validation_reason": self.reason,
            "targeted_validation_timings": dict(self.timings),
            "pre_patch_probe_result": self.pre_patch_probe_result,
            "targeted_validation_sandbox_cleanup_ok": self.sandbox_cleanup_ok,
            "baseline_python_bytecode_cache_isolated": (
                self.baseline_python_bytecode_cache_isolated
            ),
            "candidate_python_bytecode_cache_isolated": (
                self.candidate_python_bytecode_cache_isolated
            ),
            "targeted_validation_authority_effect": "none",
            "targeted_validation_model_calls": 0,
            "targeted_validation_network_calls": 0,
            "targeted_validation_selection_traversals": 0,
        }


def _bounded_selection(
    checks: Sequence[TargetedCheck],
    *,
    reason: str,
    started: float,
    max_test_files: int,
    max_test_nodes: int,
) -> TargetedCheckSelection:
    unique: dict[str, TargetedCheck] = {}
    for check in sorted(checks, key=lambda item: (item.path, item.identifier, item.source_node)):
        unique.setdefault(check.identifier, check)
    selected = tuple(unique.values())
    files = {check.path for check in selected}
    elapsed = round(time.monotonic() - started, 6)
    if len(selected) > max_test_nodes or len(files) > max_test_files:
        return TargetedCheckSelection(
            checks=(),
            complete=False,
            reason=(
                f"{reason}; {len(selected)} related checks across {len(files)} files "
                f"exceed caps of {max_test_nodes} checks/{max_test_files} files"
            ),
            category=CATEGORY_SELECTION_BUDGET_EXCEEDED,
            elapsed_seconds=elapsed,
            related_check_count=len(selected),
        )
    return TargetedCheckSelection(
        checks=selected,
        complete=True,
        reason=reason,
        category=(CATEGORY_CHECKS_SELECTED if selected else CATEGORY_NO_RELEVANT_EXISTING_CHECKS),
        elapsed_seconds=elapsed,
        related_check_count=len(selected),
    )


def _explicit_pytest_checks(graph: Any, command_text: str) -> list[TargetedCheck]:
    """Read only bounded pytest selectors from preserved user command text."""

    text = str(command_text or "").strip()
    if not text:
        return []
    try:
        argv = shlex.split(text, posix=True)
    except ValueError:
        return []
    if not argv:
        return []
    tool = Path(argv[0]).name.lower().removesuffix(".exe")
    rest: list[str]
    if tool == "pytest":
        rest = argv[1:]
    elif (
        tool in {"python", "python3", "py"}
        and len(argv) >= 3
        and argv[1] == "-m"
        and argv[2] == "pytest"
    ):
        rest = argv[3:]
    else:
        return []

    graph_nodes = getattr(graph, "nodes", {})
    checks: list[TargetedCheck] = []
    index = 0
    while index < len(rest):
        token = rest[index]
        if token in {"-q", "--quiet", "-x", "--disable-warnings"}:
            index += 1
            continue
        if token == "-p":
            if index + 1 >= len(rest) or rest[index + 1] != "no:cacheprovider":
                return []
            index += 2
            continue
        if token.startswith("--maxfail="):
            if not token.partition("=")[2].isdigit():
                return []
            index += 1
            continue
        if token.startswith("-"):
            return []
        # Consume every selector before any rejection can continue the loop.
        index += 1
        path, separator, test_name = token.partition("::")
        selector = _safe_selector(path, test_name if separator else "")
        if not selector:
            continue
        normalized = _normalize_path(path)
        if normalized not in graph_nodes:
            continue
        source_node = selector if separator else normalized
        if separator and source_node not in graph_nodes:
            continue
        checks.append(
            TargetedCheck(
                identifier=selector,
                path=normalized,
                provenance=SELECTION_EXPLICIT_USER_CHECK,
                source_node=source_node,
                relation_target="preserved_user_command",
            )
        )
    return checks


def select_targeted_checks(
    graph: Any,
    *,
    changed_paths: Sequence[str],
    changed_symbols: Sequence[str],
    preserved_user_command: str = "",
    max_test_files: int = DEFAULT_MAX_TARGETED_TEST_FILES,
    max_test_nodes: int = DEFAULT_MAX_TARGETED_TEST_NODES,
) -> TargetedCheckSelection:
    """Select one strongest deterministic relation tier from a loaded graph."""

    started = time.monotonic()
    if graph is None or not hasattr(graph, "nodes") or not hasattr(graph, "edges"):
        return TargetedCheckSelection(
            checks=(),
            complete=False,
            reason="already-loaded graph metadata is unavailable",
            category=CATEGORY_SELECTION_METADATA_UNAVAILABLE,
            elapsed_seconds=round(time.monotonic() - started, 6),
        )

    explicit = _explicit_pytest_checks(graph, preserved_user_command)
    if explicit:
        return _bounded_selection(
            explicit,
            reason="used preserved safe user-supplied existing pytest selectors",
            started=started,
            max_test_files=max_test_files,
            max_test_nodes=max_test_nodes,
        )

    target_symbols = {_normalize_path(item) for item in changed_symbols if str(item).strip()}
    target_paths = {_normalize_path(item) for item in changed_paths if str(item).strip()}
    direct: list[TargetedCheck] = []
    for edge in sorted(
        graph.edges,
        key=lambda item: (str(item.type), str(item.source), str(item.target)),
    ):
        if edge.type != "resolved_call" or _normalize_path(edge.target) not in target_symbols:
            continue
        source = str(edge.source)
        source_path = _node_file(graph, source)
        test_name = source.rsplit("::", 1)[-1] if "::" in source else ""
        selector = _safe_selector(source_path, test_name)
        if not selector:
            continue
        direct.append(
            TargetedCheck(
                identifier=selector,
                path=source_path,
                provenance=SELECTION_DIRECT_SYMBOL_CALL,
                source_node=source,
                relation_target=str(edge.target),
            )
        )
    if direct:
        return _bounded_selection(
            direct,
            reason="selected existing test symbols with direct resolved-call edges to the changed symbol",
            started=started,
            max_test_files=max_test_files,
            max_test_nodes=max_test_nodes,
        )

    dependent: list[TargetedCheck] = []
    for edge in sorted(
        graph.edges,
        key=lambda item: (str(item.type), str(item.source), str(item.target)),
    ):
        if edge.type != "imports" or _normalize_path(edge.target) not in target_paths:
            continue
        source_path = _normalize_path(edge.source)
        selector = _safe_selector(source_path)
        if not selector:
            continue
        dependent.append(
            TargetedCheck(
                identifier=selector,
                path=source_path,
                provenance=SELECTION_MODULE_DEPENDENCY,
                source_node=source_path,
                relation_target=str(edge.target),
            )
        )
    if dependent:
        return _bounded_selection(
            dependent,
            reason="selected existing test modules with direct import/dependency edges to the changed module",
            started=started,
            max_test_files=max_test_files,
            max_test_nodes=max_test_nodes,
        )

    return TargetedCheckSelection(
        checks=(),
        complete=True,
        reason="no trustworthy existing check is structurally related to the localized target",
        category=CATEGORY_NO_RELEVANT_EXISTING_CHECKS,
        elapsed_seconds=round(time.monotonic() - started, 6),
        related_check_count=0,
    )


def build_targeted_validation_request(
    *,
    repo_path: str | Path,
    candidate_plan: Sequence[Mapping[str, Any]],
    graph: Any,
    changed_symbols: Sequence[str],
    preserved_user_command: str = "",
    budget_seconds: int = DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS,
    max_test_files: int = DEFAULT_MAX_TARGETED_TEST_FILES,
    max_test_nodes: int = DEFAULT_MAX_TARGETED_TEST_NODES,
) -> TargetedValidationRequest:
    plan = [dict(operation) for operation in candidate_plan]
    if not plan:
        raise ValueError("targeted validation requires an exact non-empty candidate")
    changed_paths = tuple(
        sorted(
            {
                _normalize_path(operation.get("relative_path") or operation.get("file"))
                for operation in plan
                if _normalize_path(operation.get("relative_path") or operation.get("file"))
            }
        )
    )
    normalized_symbols = tuple(sorted({_normalize_path(item) for item in changed_symbols if str(item).strip()}))
    selection = select_targeted_checks(
        graph,
        changed_paths=changed_paths,
        changed_symbols=normalized_symbols,
        preserved_user_command=preserved_user_command,
        max_test_files=max_test_files,
        max_test_nodes=max_test_nodes,
    )
    provenance = tuple(sorted({check.provenance for check in selection.checks}))
    return TargetedValidationRequest(
        repository_identity=derive_repository_id(repo_path),
        candidate_fingerprint=patch_plan_fingerprint(plan),
        changed_paths=changed_paths,
        changed_symbols=normalized_symbols,
        selected_checks=selection.checks,
        selection_provenance=provenance,
        selection_complete=selection.complete,
        selection_reason=selection.reason,
        selection_category=selection.category,
        selection_elapsed_seconds=selection.elapsed_seconds,
        related_check_count=selection.related_check_count,
        budget_seconds=budget_seconds,
        max_test_files=max_test_files,
        max_test_nodes=max_test_nodes,
    )


def targeted_validation_is_current(payload: Any, plan: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    recorded = str(payload.get("candidate_fingerprint") or "")
    return bool(recorded and recorded == patch_plan_fingerprint(plan))


def _output_excerpt(value: Any) -> str:
    text = str(value or "")
    return text if len(text) <= MAX_OUTPUT_EXCERPT_CHARS else text[-MAX_OUTPUT_EXCERPT_CHARS:]


def _oracle_source_fingerprint(root: Path, request: TargetedValidationRequest) -> str:
    """Bind checks to bytes, including pytest configuration affecting collection."""
    for check in request.selected_checks:
        path = Path(check.path)
        if path.is_absolute() or path.anchor or ".." in path.parts:
            return ""
    paths = {check.path for check in request.selected_checks}
    for check in request.selected_checks:
        parent = Path(check.path).parent
        while True:
            for name in ("conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"):
                paths.add((parent / name).as_posix())
            if parent == Path("."):
                break
            parent = parent.parent
    try:
        resolved_root = root.resolve()
        if any(not (root / path).resolve().is_relative_to(resolved_root) for path in paths):
            return ""
        return _fingerprint({path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                             if (root / path).is_file() else None for path in sorted(paths)})
    except OSError:
        return ""


def _concrete_case_results(report: Path) -> tuple[tuple[str, str], ...]:
    """Read machine-reported executed cases; missing/duplicate reports prove nothing."""
    try:
        if report.stat().st_size > 2_000_000:
            return ()
        tree = ET.parse(report)
        cases: dict[str, str] = {}
        for node in tree.iter("testcase"):
            identity = str(node.get("classname") or "") + "::" + str(node.get("name") or "")
            if identity == "::" or identity in cases:
                return ()
            status = "passed"
            if node.find("error") is not None:
                status = "error"
            elif node.find("skipped") is not None:
                status = "skipped"
            elif node.find("failure") is not None:
                failure = node.find("failure")
                content = (failure.text or "") + str(failure.get("message") or "")
                status = "assertion_failed" if "AssertionError" in content or "assert " in content else "failed"
            cases[identity] = status
        return tuple(sorted(cases.items()))
    except (OSError, ET.ParseError, ValueError):
        return ()


def _reproduced_checks_repaired(baseline: TargetedCheckRun, candidate: TargetedCheckRun,
                               pre_patch_probe_result: str) -> bool:
    before, after = dict(baseline.concrete_cases), dict(candidate.concrete_cases)
    return bool(
        pre_patch_probe_result == "reproduced"
        and baseline.completed and candidate.completed
        and baseline.outcome == VALIDATION_FAILED and candidate.outcome == VALIDATION_PASSED
        and baseline.category in {"test_failure", "assertion_failure"}
        and before and before.keys() == after.keys()
        and "assertion_failed" in before.values()
        and set(before.values()) <= {"passed", "assertion_failed"}
        and set(after.values()) == {"passed"}
        and baseline.oracle_unchanged and candidate.oracle_unchanged
        and baseline.oracle_source_fingerprint
        and baseline.oracle_source_fingerprint == candidate.oracle_source_fingerprint
    )


def _run_check_set(
    root: Path,
    request: TargetedValidationRequest,
    *,
    timeout_seconds: int,
) -> TargetedCheckRun:
    identifiers = tuple(check.identifier for check in request.selected_checks)
    report = root / ".cattus-targeted-results.xml"
    report.unlink(missing_ok=True)
    oracle_before = _oracle_source_fingerprint(root, request)
    command = SafeValidationCommand(
        command=[
            "python",
            "-m",
            "pytest",
            *identifiers,
            "-q",
            "-p",
            "no:cacheprovider",
            "--junitxml=" + str(report),
        ],
        cwd=root,
        timeout_sec=timeout_seconds,
        env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    run = run_safe_validation_command(command)
    output = run.output or run.block_reason
    command_label = "python -m pytest <bounded-existing-selectors>"
    no_tests = bool(
        run.ok
        and detect_no_tests_collected(
            output,
            exit_code=run.exit_code,
            command=command_label,
        )
    )
    if run.blocked:
        category = CATEGORY_UNSAFE_VALIDATION_COMMAND
    elif run.timed_out:
        category = CATEGORY_VALIDATION_BUDGET_EXHAUSTED
    elif no_tests:
        category = CATEGORY_NO_TESTS_COLLECTED
    elif run.ok:
        category = CATEGORY_TARGETED_CHECKS_PASSED
    else:
        info = classify_validation_output(
            output,
            exit_code=run.exit_code,
            command=command_label,
            timed_out=run.timed_out,
            timeout_seconds=run.timeout_sec,
        )
        category = str(info.get("category") or CATEGORY_TARGETED_VALIDATION_UNAVAILABLE)
    outcome = validation_outcome(category=category, ok=(run.ok and not no_tests))
    executed = (
        identifiers
        if run.exit_code is not None and category != CATEGORY_NO_TESTS_COLLECTED
        else ()
    )
    return TargetedCheckRun(
        outcome=outcome,
        category=category,
        attempted=not run.blocked,
        completed=not run.timed_out and run.exit_code is not None,
        timed_out=run.timed_out,
        checks_executed=executed,
        output_excerpt=_output_excerpt(output),
        python_bytecode_cache_isolated=run.python_bytecode_cache_isolated,
        concrete_cases=_concrete_case_results(report),
        oracle_source_fingerprint=oracle_before,
        oracle_unchanged=bool(oracle_before and oracle_before == _oracle_source_fingerprint(root, request)),
    )


def _make_sandbox(source_repo: Path, *, label: str) -> tuple[Path | None, Path | None, str]:
    try:
        temp_root = Path(tempfile.mkdtemp(prefix=f"cattus-targeted-{label}-"))
    except OSError as exc:
        return None, None, f"{type(exc).__name__}: {exc}"
    sandbox = temp_root / "repo"
    try:
        info = create_managed_sandbox(source_repo, sandbox)
    except Exception as exc:  # defensive isolation around the existing primitive
        info = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if not info.get("ok"):
        shutil.rmtree(temp_root, ignore_errors=True)
        return None, None, str(info.get("error") or "sandbox creation failed")
    return Path(info["sandbox_path"]), temp_root, ""


def _cleanup_sandbox(sandbox: Path | None, temp_root: Path | None) -> bool:
    ok = True
    if sandbox is not None and sandbox.exists():
        try:
            cleaned, _reason = cleanup_managed_sandbox(sandbox)
            ok = bool(cleaned)
        except Exception:
            ok = False
    if temp_root is not None and temp_root.exists():
        try:
            shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            ok = False
    return ok and (temp_root is None or not temp_root.exists())


def _remaining_timeout(deadline: float) -> int:
    remaining = deadline - time.monotonic()
    if remaining < 1.0:
        return 0
    return max(1, int(remaining))


def _early_result(
    request: TargetedValidationRequest,
    *,
    category: str,
    reason: str,
    pre_patch_probe_result: str,
    timings: Mapping[str, float] | None = None,
) -> TargetedValidationResult:
    return TargetedValidationResult(
        status=VALIDATION_INCONCLUSIVE,
        category=category,
        request=request,
        pre_patch_probe_result=pre_patch_probe_result,
        reason=reason,
        timings=dict(timings or {"selection_seconds": request.selection_elapsed_seconds}),
    )


def validate_targeted_candidate(
    *,
    repo_path: str | Path,
    candidate_plan: Sequence[Mapping[str, Any]],
    request: TargetedValidationRequest,
    pre_patch_probe_result: str = "",
) -> TargetedValidationResult:
    """Run one immutable existing-check set in baseline and candidate sandboxes."""

    started = time.monotonic()
    timings: dict[str, float] = {"selection_seconds": request.selection_elapsed_seconds}
    plan = [dict(operation) for operation in candidate_plan]

    if patch_plan_fingerprint(plan) != request.candidate_fingerprint:
        return _early_result(
            request,
            category=CATEGORY_CANDIDATE_FINGERPRINT_STALE,
            reason="targeted validation request does not describe the current candidate",
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )
    try:
        source_repo = Path(repo_path).resolve()
        current_repository_identity = derive_repository_id(source_repo)
    except (OSError, ValueError, TypeError, NotADirectoryError):
        current_repository_identity = ""
        source_repo = Path(repo_path)
    if current_repository_identity != request.repository_identity:
        return _early_result(
            request,
            category=CATEGORY_REPOSITORY_IDENTITY_MISMATCH,
            reason="targeted validation request is bound to a different repository",
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )
    if not request.selection_complete:
        return _early_result(
            request,
            category=request.selection_category,
            reason=request.selection_reason,
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )
    if not request.selected_checks:
        return _early_result(
            request,
            category=CATEGORY_NO_RELEVANT_EXISTING_CHECKS,
            reason="no relevant existing check was selected; absence is not a pass",
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )

    changed = set(request.changed_paths)
    selected_test_paths = {check.path for check in request.selected_checks}
    modified_oracles = tuple(sorted(changed & selected_test_paths))
    if modified_oracles:
        return _early_result(
            request,
            category=CATEGORY_SELECTED_CHECK_MODIFIED,
            reason=(
                "candidate modifies selected validation evidence: "
                + ", ".join(modified_oracles)
            ),
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )

    deadline = started + request.budget_seconds
    cleanup_ok = True

    # Baseline: a disposable copy of the current candidate-source state.
    stage = time.monotonic()
    baseline_root, baseline_temp, error = _make_sandbox(source_repo, label="baseline")
    timings["baseline_sandbox_create_seconds"] = round(time.monotonic() - stage, 6)
    if baseline_root is None:
        return _early_result(
            request,
            category=CATEGORY_SANDBOX_UNAVAILABLE,
            reason=f"baseline sandbox unavailable: {error}",
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )
    timeout = _remaining_timeout(deadline)
    if timeout == 0:
        cleanup_ok = _cleanup_sandbox(baseline_root, baseline_temp)
        return _early_result(
            request,
            category=CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
            reason=budget_exhausted_info(request.budget_seconds)["reason"],
            pre_patch_probe_result=pre_patch_probe_result,
            timings=timings,
        )
    stage = time.monotonic()
    baseline = _run_check_set(baseline_root, request, timeout_seconds=timeout)
    timings["baseline_targeted_validation_seconds"] = round(time.monotonic() - stage, 6)
    stage = time.monotonic()
    cleanup_ok = _cleanup_sandbox(baseline_root, baseline_temp) and cleanup_ok
    timings["baseline_cleanup_seconds"] = round(time.monotonic() - stage, 6)

    if baseline.timed_out or _remaining_timeout(deadline) == 0:
        timings["total_seconds"] = round(time.monotonic() - started, 6)
        return TargetedValidationResult(
            status=VALIDATION_INCONCLUSIVE,
            category=CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
            request=request,
            baseline_outcome=baseline.outcome,
            baseline_category=baseline.category,
            baseline_checks_executed=baseline.checks_executed,
            pre_patch_probe_result=pre_patch_probe_result,
            reason=budget_exhausted_info(request.budget_seconds)["reason"],
            output_excerpt=baseline.output_excerpt,
            timings=timings,
            sandbox_cleanup_ok=cleanup_ok,
            baseline_python_bytecode_cache_isolated=(
                baseline.python_bytecode_cache_isolated
            ),
        )

    # Candidate: a fresh disposable copy, exact candidate apply, same check set.
    stage = time.monotonic()
    candidate_root, candidate_temp, error = _make_sandbox(source_repo, label="candidate")
    timings["candidate_sandbox_create_seconds"] = round(time.monotonic() - stage, 6)
    if candidate_root is None:
        timings["total_seconds"] = round(time.monotonic() - started, 6)
        return TargetedValidationResult(
            status=VALIDATION_INCONCLUSIVE,
            category=CATEGORY_SANDBOX_UNAVAILABLE,
            request=request,
            baseline_outcome=baseline.outcome,
            baseline_category=baseline.category,
            baseline_checks_executed=baseline.checks_executed,
            pre_patch_probe_result=pre_patch_probe_result,
            reason=f"candidate sandbox unavailable: {error}",
            output_excerpt=baseline.output_excerpt,
            timings=timings,
            sandbox_cleanup_ok=cleanup_ok,
            baseline_python_bytecode_cache_isolated=(
                baseline.python_bytecode_cache_isolated
            ),
        )
    stage = time.monotonic()
    try:
        from patching.patch_plan_executor import apply_patch_plan

        apply_result = apply_patch_plan(str(candidate_root), plan, validation_command=None)
    except Exception as exc:  # defensive isolation around the existing primitive
        apply_result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    timings["candidate_apply_seconds"] = round(time.monotonic() - stage, 6)

    if not apply_result.get("success"):
        stage = time.monotonic()
        cleanup_ok = _cleanup_sandbox(candidate_root, candidate_temp) and cleanup_ok
        timings["candidate_cleanup_seconds"] = round(time.monotonic() - stage, 6)
        timings["total_seconds"] = round(time.monotonic() - started, 6)
        return TargetedValidationResult(
            status=VALIDATION_FAILED,
            category=CATEGORY_CANDIDATE_APPLY_FAILED,
            request=request,
            baseline_outcome=baseline.outcome,
            baseline_category=baseline.category,
            baseline_checks_executed=baseline.checks_executed,
            candidate_outcome=VALIDATION_FAILED,
            candidate_category=CATEGORY_CANDIDATE_APPLY_FAILED,
            pre_patch_probe_result=pre_patch_probe_result,
            reason="exact candidate could not be materialized in its disposable sandbox",
            output_excerpt=_output_excerpt(apply_result.get("error")),
            timings=timings,
            sandbox_cleanup_ok=cleanup_ok,
            baseline_python_bytecode_cache_isolated=(
                baseline.python_bytecode_cache_isolated
            ),
        )

    timeout = _remaining_timeout(deadline)
    if timeout == 0:
        candidate = TargetedCheckRun(
            outcome=VALIDATION_INCONCLUSIVE,
            category=CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
            attempted=False,
            completed=False,
            timed_out=True,
            checks_executed=(),
        )
    else:
        stage = time.monotonic()
        candidate = _run_check_set(candidate_root, request, timeout_seconds=timeout)
        timings["candidate_targeted_validation_seconds"] = round(time.monotonic() - stage, 6)
    stage = time.monotonic()
    cleanup_ok = _cleanup_sandbox(candidate_root, candidate_temp) and cleanup_ok
    timings["candidate_cleanup_seconds"] = round(time.monotonic() - stage, 6)
    timings["total_seconds"] = round(time.monotonic() - started, 6)

    if candidate.timed_out or timings["total_seconds"] > request.budget_seconds:
        status = VALIDATION_INCONCLUSIVE
        category = CATEGORY_VALIDATION_BUDGET_EXHAUSTED
        reason = budget_exhausted_info(request.budget_seconds)["reason"]
    elif _reproduced_checks_repaired(baseline, candidate, pre_patch_probe_result):
        status = VALIDATION_PASSED
        category = CATEGORY_TARGETED_DEFECT_REPAIRED
        reason = ("the same unchanged existing assertions changed from failure to pass; "
                  "every baseline passing case also passed, with an independently reproduced defect")
    elif baseline.outcome == VALIDATION_FAILED:
        status = VALIDATION_INCONCLUSIVE
        category = CATEGORY_BASELINE_TARGETED_FAILED
        reason = "selected existing checks already fail on the baseline; no delta score is inferred"
    elif baseline.outcome == VALIDATION_INCONCLUSIVE:
        status = VALIDATION_INCONCLUSIVE
        category = CATEGORY_BASELINE_TARGETED_INCONCLUSIVE
        reason = "baseline targeted checks did not establish a pass/fail verdict"
    elif candidate.outcome == VALIDATION_FAILED:
        status = VALIDATION_FAILED
        category = candidate.category
        reason = "the candidate failed at least one unchanged existing targeted check"
    elif candidate.outcome == VALIDATION_INCONCLUSIVE:
        status = VALIDATION_INCONCLUSIVE
        category = candidate.category
        reason = outcome_reason(
            candidate.category,
            fallback="candidate targeted checks did not establish a verdict",
        )
    else:
        status = VALIDATION_PASSED
        category = CATEGORY_TARGETED_CHECKS_PASSED
        reason = "the bounded relevant checks passed on baseline and exact candidate"

    return TargetedValidationResult(
        status=status,
        category=category,
        request=request,
        baseline_outcome=baseline.outcome,
        baseline_category=baseline.category,
        candidate_outcome=candidate.outcome,
        candidate_category=candidate.category,
        baseline_checks_executed=baseline.checks_executed,
        candidate_checks_executed=candidate.checks_executed,
        baseline_concrete_cases=baseline.concrete_cases,
        candidate_concrete_cases=candidate.concrete_cases,
        oracle_source_unchanged=bool(baseline.oracle_unchanged and candidate.oracle_unchanged
                                     and baseline.oracle_source_fingerprint == candidate.oracle_source_fingerprint),
        pre_patch_probe_result=pre_patch_probe_result,
        reason=reason,
        output_excerpt=(candidate.output_excerpt or baseline.output_excerpt),
        timings=timings,
        sandbox_cleanup_ok=cleanup_ok,
        baseline_python_bytecode_cache_isolated=(
            baseline.python_bytecode_cache_isolated
        ),
        candidate_python_bytecode_cache_isolated=(
            candidate.python_bytecode_cache_isolated
        ),
    )


def describe_targeted_validation(result: TargetedValidationResult) -> str:
    if result.status == VALIDATION_PASSED:
        return (
            "The bounded relevant checks passed. Whole-repository validation "
            "remains a separate fact and has not been rewritten."
        )
    if result.status == VALIDATION_FAILED:
        return (
            "At least one bounded relevant existing check failed for the exact "
            "sandboxed candidate."
        )
    return f"Targeted repository validation was inconclusive: {result.reason}"


def targeted_validation_guardrails() -> dict[str, bool]:
    return {
        "existing_repository_checks_only": True,
        "same_check_set_before_after": True,
        "candidate_fingerprint_bound": True,
        "candidate_sandboxed": True,
        "real_repository_candidate_write": False,
        "zero_checks_can_pass": False,
        "modified_test_can_validate_itself": False,
        "model_generated_tests_accepted": False,
        "probe_overrides_targeted_failure": False,
        "targeted_rewrites_full_validation": False,
        "execution_authority_granted": False,
        "model_called": False,
        "network_called": False,
        "repository_traversal_added": False,
        "global_timeout_changed": False,
    }


__all__ = [
    "PHASE_ID",
    "DEFAULT_TARGETED_VALIDATION_BUDGET_SECONDS",
    "MAX_TARGETED_VALIDATION_BUDGET_SECONDS",
    "DEFAULT_MAX_TARGETED_TEST_FILES",
    "DEFAULT_MAX_TARGETED_TEST_NODES",
    "SIDE_EFFECT_SANDBOX_ONLY",
    "SELECTION_EXPLICIT_USER_CHECK",
    "SELECTION_DIRECT_SYMBOL_CALL",
    "SELECTION_MODULE_DEPENDENCY",
    "CATEGORY_TARGETED_CHECKS_PASSED",
    "CATEGORY_CHECKS_SELECTED",
    "CATEGORY_NO_RELEVANT_EXISTING_CHECKS",
    "CATEGORY_SELECTION_BUDGET_EXCEEDED",
    "CATEGORY_SELECTION_METADATA_UNAVAILABLE",
    "CATEGORY_SELECTED_CHECK_MODIFIED",
    "CATEGORY_CANDIDATE_FINGERPRINT_STALE",
    "CATEGORY_REPOSITORY_IDENTITY_MISMATCH",
    "CATEGORY_BASELINE_TARGETED_FAILED",
    "CATEGORY_BASELINE_TARGETED_INCONCLUSIVE",
    "CATEGORY_CANDIDATE_APPLY_FAILED",
    "CATEGORY_SANDBOX_UNAVAILABLE",
    "CATEGORY_TARGETED_VALIDATION_UNAVAILABLE",
    "TargetedCheck",
    "TargetedCheckSelection",
    "TargetedValidationRequest",
    "TargetedCheckRun",
    "TargetedValidationResult",
    "select_targeted_checks",
    "build_targeted_validation_request",
    "targeted_validation_is_current",
    "validate_targeted_candidate",
    "describe_targeted_validation",
    "targeted_validation_guardrails",
]
