"""PREFLIGHT.REQUEST.1 - typed diagnostic evidence requests and the one Java compile adapter.

CONTROL.BOOTSTRAP.1 ends with a schema-valid CONTROL whose ``evidence_gaps`` name
semantic needs over grounded evidence targets.  This module owns the next
transition, and only that one:

    typed evidence gap (CONTROL.BOOTSTRAP.1's own {need, detail, targets} record)
        -> EvidenceNeed: kind, exact targets, language, provenance, CONTROL and repository binding
        -> a pure policy: supported kind?  authorized targets?  budget?  language?  adapter?
        -> the harness-owned adapter the policy names (javac here; never a tool CONTROL names)
        -> DiagnosticEvidenceReceipt: measured, bounded, provenance-bound, authority-free
        -> CONTROL's existing ``preflight_validation`` field, which the unchanged
           DEFECT.FACT / PATCH.BASIS reasoning (``refresh_control_safety``) already reads

The model asks WHAT evidence is needed; the harness alone decides HOW.  Nothing a
model or CONTROL wrote is ever executed: a need is a kind and a list of evidence
targets, every other key of a gap is ignored unread, and the adapter builds its own
argument vector.  Diagnostic capability is not mutation authority, and a measured
compiler failure is not patch, write or approval authority.  A request runs at most
one bounded diagnostic cycle; nothing here loops back to a model.

Only ``compile_evidence`` over Java sources is executable.  Every other need (tests,
runtime, container status, MCP/plugin/skill health) is typed
``unsupported_evidence_need``: a future adapter is one more ``ADAPTER_REGISTRY``
entry, and discovering, connecting or authorizing external capabilities belongs to
CAPABILITY.BROKER.1, not to this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Callable, Mapping

from config import LANGUAGE_MAP
from core.credential_redaction import redact_credentials
from core.direct_read_receipt import DirectReadFileIdentity, verify_direct_read_receipt
from core.repository_identity import canonicalize_repository_root, derive_repository_id_from_canonical_root
from web import control_context
from web.control_bootstrap import (
    EVIDENCE_GAP_FIELDS,
    EVIDENCE_NEEDS,
    MAX_EVIDENCE_GAPS,
    MAX_SOURCE_BYTES_PER_FILE,
    MAX_TARGET_FILES,
    MAX_TEXT_CHARS,
    control_fingerprint,
)

PHASE_ID = "PREFLIGHT.REQUEST.1"
RECEIPT_SCHEMA_VERSION = "preflight_request_v1"
#: The answer key that carries this phase's receipt, beside CONTROL.BOOTSTRAP.1's.
RESULT_FIELD = "preflight_request"
#: The existing CONTROL field the DEFECT.FACT / PATCH.BASIS boundary reads.  Measured
#: evidence reaches reasoning through it and through nothing else.
HANDOFF_FIELD = "preflight_validation"

COMPILE_EVIDENCE = "compile_evidence"
#: Needs CONTROL.BOOTSTRAP.1 admits that ask for context, not for a measurement.
_NON_DIAGNOSTIC_NEEDS = frozenset({"additional_source", "user_clarification"})

# -- policy decisions (closed) ---------------------------------------------------------------------
ADMITTED = "admitted"
UNSUPPORTED_EVIDENCE_NEED = "unsupported_evidence_need"
UNAUTHORIZED_TARGET = "unauthorized_target"
LANGUAGE_UNSUPPORTED = "language_unsupported"
TARGET_BUDGET_EXCEEDED = "target_budget_exceeded"
MALFORMED_EVIDENCE_NEED = "malformed_evidence_need"

# -- diagnostic outcomes (closed; a non-zero exit is never simply "defect") ------------------------
COMPILE_PASSED = "compile_passed"
COMPILE_FAILED = "compile_failed"
TOOL_UNAVAILABLE = "tool_unavailable"
DIAGNOSTIC_TIMEOUT = "diagnostic_timeout"
DIAGNOSTIC_INCONCLUSIVE = "diagnostic_inconclusive"
ADAPTER_ERROR = "adapter_error"
DIAGNOSTIC_OUTCOMES = (
    COMPILE_PASSED,
    COMPILE_FAILED,
    TOOL_UNAVAILABLE,
    DIAGNOSTIC_TIMEOUT,
    DIAGNOSTIC_INCONCLUSIVE,
    ADAPTER_ERROR,
)

# -- cycle statuses ---------------------------------------------------------------------------------
NO_EVIDENCE_NEED = "no_evidence_need"
NO_ADMITTED_NEED = "no_admitted_need"
EVIDENCE_MEASURED = "evidence_measured"
PREFLIGHT_SOURCE_CHANGED = "preflight_source_changed"
PREFLIGHT_BINDING_MISMATCH = "preflight_binding_mismatch"

JAVA_COMPILE_ADAPTER_ID = "java_compile_diagnostic"
JAVA_COMPILE_ADAPTER_VERSION = "1"
#: Adapter selection is harness policy, keyed by (evidence kind, language).  CONTROL may
#: ask for ``compile_evidence``; it can never name javac, a build tool or a container.
ADAPTER_REGISTRY: Mapping[tuple[str, str], str] = MappingProxyType({
    (COMPILE_EVIDENCE, "java"): JAVA_COMPILE_ADAPTER_ID,
})

_MAX_KIND_CHARS = 64
_MAX_IGNORED_KEYS = 16
_MAX_IGNORED_KEY_CHARS = 64
_MAX_TARGETS_PER_GAP = 64
_MAX_TARGET_CHARS = 1024
_MAX_MESSAGE_CHARS = 500
_MAX_DIAGNOSTIC_TEXT_CHARS = 1000
_MAX_HANDOFF_OUTPUT_CHARS = 6000
_MAX_HANDOFF_LOCATIONS = 16

AUTHORITY = MappingProxyType({
    "write_authority": False,
    "patch_authority": False,
    "execution_authorized": False,
    "patch_applied": False,
    "human_approval_granted": False,
})
SEMANTICS = (
    "compile_passed proves only that a target compiled under the recorded javac invocation and "
    "environment; it does not establish behavioral correctness, test results or patch correctness. "
    "compile_failed proves only that compilation failed under that invocation; it does not decide "
    "which change is correct. Neither grants patch, write, execution or approval authority."
)

_MESSAGES = {
    PREFLIGHT_SOURCE_CHANGED: (
        "Fresh start: {detail} changed after its first CONTROL was authored ({reason}), so no compile "
        "evidence was bound to it and the request stopped. Generate again."
    ),
    PREFLIGHT_BINDING_MISMATCH: (
        "Fresh start: the diagnostic request did not match its CONTROL or repository ({reason}); "
        "nothing was measured."
    ),
}


# == the EvidenceNeed contract ======================================================================

@dataclass(frozen=True)
class EvidenceNeed:
    """What CONTROL asked to know and where, bound to it and its repository - never how to measure it."""

    kind: str
    targets: tuple[str, ...]
    language: str
    reason: str
    provenance: str
    control_sha256: str
    repository_id: str

    @property
    def identity(self) -> str:
        # The same kind over the same target set is one need, however it was worded or ordered.
        canonical = json.dumps(
            [self.kind, sorted(self.targets), self.language, self.control_sha256, self.repository_id],
            separators=(",", ":"), ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "targets": list(self.targets),
            "language": self.language,
            "reason": self.reason,
            "provenance": self.provenance,
            "control_sha256": self.control_sha256,
            "repository_id": self.repository_id,
            "identity": self.identity,
        }


@dataclass(frozen=True)
class NeedDerivation:
    """One CONTROL evidence gap read as a need, or the structural reason it is not one."""

    provenance: str
    need: EvidenceNeed | None = None
    code: str | None = None
    field: str | None = None
    ignored_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopedSource:
    """One evidence target CONTROL was authored from: its exact digest and CTX.READ.1 receipt."""

    path: str
    language: str
    sha256: str
    size_bytes: int
    receipt: Any = field(repr=False, compare=False)


@dataclass(frozen=True)
class PreflightScope:
    """The authorized evidence scope: one repository, one CONTROL, the exact sources it was built from."""

    canonical_root: str
    repository_id: str
    control_sha256: str
    sources: tuple[ScopedSource, ...]

    @property
    def evidence_targets(self) -> tuple[str, ...]:
        return tuple(source.path for source in self.sources)


def scope_from_bootstrap(result: Any) -> PreflightScope:
    """The only production scope: a bootstrapped CONTROL and the sources CONTROL.BOOTSTRAP.1 read."""
    if not getattr(result, "bootstrapped", False) or getattr(result, "control", None) is None:
        raise ValueError("only a bootstrapped CONTROL has a preflight evidence scope")
    return PreflightScope(
        canonical_root=result.repository_root,
        repository_id=result.repository_id,
        control_sha256=control_fingerprint(result.control),
        sources=tuple(
            ScopedSource(source.path, source.language, source.sha256, source.size_bytes, source.receipt)
            for source in result.sources
        ),
    )


def _language_of(targets: tuple[str, ...]) -> str:
    languages = {LANGUAGE_MAP.get(PurePosixPath(target).suffix.lower(), "unknown") for target in targets}
    return languages.pop() if len(languages) == 1 else "mixed"


def _malformed(where: str, field_name: str, ignored: tuple[str, ...] = ()) -> NeedDerivation:
    return NeedDerivation(where, code=MALFORMED_EVIDENCE_NEED, field=field_name, ignored_keys=ignored)


def derive_evidence_needs(control: Mapping[str, Any], scope: PreflightScope) -> tuple[NeedDerivation, ...]:
    """Read CONTROL's evidence gaps as typed needs.  Pure: no file, process or model."""
    gaps = control.get("evidence_gaps") if isinstance(control, Mapping) else None
    if gaps is None:
        return ()
    if not isinstance(gaps, list) or len(gaps) > MAX_EVIDENCE_GAPS:
        return (_malformed("evidence_gaps", "evidence_gaps"),)
    return tuple(_derive(index, item, scope) for index, item in enumerate(gaps))


def _derive(index: int, item: Any, scope: PreflightScope) -> NeedDerivation:
    where = f"evidence_gaps[{index}]"
    if not isinstance(item, dict):
        return _malformed(where, where)
    # The need is the whole record: other keys (a command, argv, tool, adapter, environment,
    # script...) are recorded by a bounded name and never read.
    ignored = tuple(sorted(str(key)[:_MAX_IGNORED_KEY_CHARS] for key in item
                           if key not in EVIDENCE_GAP_FIELDS))[:_MAX_IGNORED_KEYS]
    kind = item.get("need")
    if not isinstance(kind, str) or not kind or len(kind) > _MAX_KIND_CHARS:
        return _malformed(where, f"{where}.need", ignored)
    raw = item.get("targets")
    if (not isinstance(raw, list) or not raw or len(raw) > _MAX_TARGETS_PER_GAP or not all(
            isinstance(value, str) and value and len(value) <= _MAX_TARGET_CHARS for value in raw)):
        return _malformed(where, f"{where}.targets", ignored)
    detail = item.get("detail", "")
    if not isinstance(detail, str) or len(detail) > MAX_TEXT_CHARS:
        return _malformed(where, f"{where}.detail", ignored)
    targets = tuple(dict.fromkeys(raw))  # a repeated spelling counts once, in first-written order
    need = EvidenceNeed(
        kind=kind, targets=targets, language=_language_of(targets), reason=detail, provenance=where,
        control_sha256=scope.control_sha256, repository_id=scope.repository_id,
    )
    return NeedDerivation(where, need=need, ignored_keys=ignored)


# == the policy: supported, authorized, bounded, compatible, adaptable ===============================

@dataclass(frozen=True)
class PolicyDecision:
    provenance: str
    decision: str
    reason: str
    need: EvidenceNeed | None = None
    adapter_id: str | None = None

    @property
    def admitted(self) -> bool:
        return self.decision == ADMITTED

    def as_dict(self) -> dict[str, Any]:
        return {
            "provenance": self.provenance,
            "identity": self.need.identity if self.need is not None else None,
            "kind": self.need.kind if self.need is not None else None,
            "decision": self.decision,
            "reason": self.reason,
            "adapter": self.adapter_id,
        }


def decide_evidence_need(need: EvidenceNeed, scope: PreflightScope) -> PolicyDecision:
    """Deterministic admission of one need.  Pure: it reads nothing and starts nothing."""
    where = need.provenance
    if need.kind not in {kind for kind, _ in ADAPTER_REGISTRY}:
        if need.kind in _NON_DIAGNOSTIC_NEEDS:
            reason = "not_a_diagnostic_measurement"
        elif need.kind in EVIDENCE_NEEDS:
            reason = "deferred"
        else:
            reason = "unknown_evidence_kind"
        return PolicyDecision(where, UNSUPPORTED_EVIDENCE_NEED, reason, need)
    if len(need.targets) > MAX_TARGET_FILES:
        return PolicyDecision(where, TARGET_BUDGET_EXCEEDED,
                              f"{len(need.targets)} targets; at most {MAX_TARGET_FILES}", need)
    evidence = {source.path: source for source in scope.sources}
    for target in need.targets:
        # Only the exact evidence spelling is authorized: no normalization, so no alias.
        if target not in evidence:
            return PolicyDecision(where, UNAUTHORIZED_TARGET, target, need)
    languages = {evidence[target].language for target in need.targets}
    language = languages.pop() if len(languages) == 1 else "mixed"
    adapter_id = ADAPTER_REGISTRY.get((need.kind, language))
    if adapter_id is None:
        return PolicyDecision(where, LANGUAGE_UNSUPPORTED, language, need)
    return PolicyDecision(where, ADMITTED, "", need, adapter_id)


# == measured evidence records ========================================================================

@dataclass(frozen=True)
class DiagnosticLimits:
    """Explicit bounds for one diagnostic cycle; the target count is the direct-context bound."""

    process_timeout_seconds: float = 60.0
    version_probe_timeout_seconds: float = 30.0
    cycle_budget_seconds: float = 180.0
    max_output_bytes: int = 65_536
    max_evidence_chars: int = 8_000
    max_diagnostics: int = 32


@dataclass(frozen=True)
class DiagnosticPlan:
    """What the policy admitted, bound to one adapter: exact sources, CONTROL and repository."""

    adapter_id: str
    kind: str
    language: str
    sources: tuple[ScopedSource, ...]
    need_identities: tuple[str, ...]
    control_sha256: str
    repository_id: str
    canonical_root: str

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(source.path for source in self.sources)


@dataclass(frozen=True)
class CompilerDiagnostic:
    """One compiler diagnostic: structured location fields beside its bounded raw text."""

    file: str | None
    reported_file: str
    line: int
    column: int | None
    severity: str
    message: str
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"file": self.file, "reported_file": self.reported_file, "line": self.line, "column": self.column,
                "severity": self.severity, "message": self.message, "text": self.text}


@dataclass(frozen=True)
class CapturedStream:
    bytes_total: int = 0
    bytes_captured: int = 0
    truncated: bool = False
    sha256: str = hashlib.sha256(b"").hexdigest()
    text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"bytes_total": self.bytes_total, "bytes_captured": self.bytes_captured, "truncated": self.truncated,
                "sha256": self.sha256, "text": self.text}


@dataclass(frozen=True)
class TargetMeasurement:
    path: str
    source_sha256: str
    attempted: bool
    outcome: str
    reason: str = ""
    compile_mode: str = "none"
    group: tuple[str, ...] = ()
    independent_outcome: str | None = None
    exit_status: int | None = None
    timed_out: bool = False
    elapsed_ms: float = 0.0
    diagnostics: tuple[CompilerDiagnostic, ...] = ()
    stdout: CapturedStream = CapturedStream()
    stderr: CapturedStream = CapturedStream()
    invocation: str = ""

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.diagnostics if item.file == self.path and item.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.diagnostics if item.file == self.path and item.severity == "warning")

    def fingerprint_material(self) -> dict[str, Any]:
        return {
            "path": self.path, "source_sha256": self.source_sha256, "attempted": self.attempted,
            "outcome": self.outcome, "reason": self.reason, "compile_mode": self.compile_mode,
            "group": list(self.group), "independent_outcome": self.independent_outcome,
            "exit_status": self.exit_status, "timed_out": self.timed_out, "invocation": self.invocation,
            "diagnostics": [[item.file, item.line, item.column, item.severity, item.message]
                            for item in self.diagnostics],
            "stdout_sha256": self.stdout.sha256, "stderr_sha256": self.stderr.sha256,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "language": "java",
            "source_sha256": self.source_sha256,
            "attempted": self.attempted,
            "outcome": self.outcome,
            "reason": self.reason,
            "compile_mode": self.compile_mode,
            "group": list(self.group),
            "independent_outcome": self.independent_outcome,
            "exit_status": self.exit_status,
            "timed_out": self.timed_out,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
            "stdout": self.stdout.as_dict(),
            "stderr": self.stderr.as_dict(),
            "invocation": self.invocation,
        }


@dataclass(frozen=True)
class DiagnosticEvidenceReceipt:
    """The measured result of one plan: provenance-bound, bounded, and without authority."""

    evidence_kind: str
    adapter_id: str
    adapter_version: str
    tool: str
    tool_version: str | None
    tool_available: bool
    attempted: bool
    outcome: str
    reason: str
    repository_id: str
    control_sha256: str
    need_identities: tuple[str, ...]
    targets: tuple[TargetMeasurement, ...]
    version_probe: Mapping[str, Any]
    environment_keys: tuple[str, ...]
    timing_ms: Mapping[str, float]
    operational_warnings: tuple[str, ...] = ()
    process_timeout_seconds: float = 0.0

    @property
    def exit_statuses(self) -> dict[str, int | None]:
        return {target.path: target.exit_status for target in self.targets}

    @property
    def evidence_fingerprint(self) -> str:
        # What was measured, where, how and with what result; never timings or cleanup notes.
        material = {
            "schema_version": RECEIPT_SCHEMA_VERSION, "evidence_kind": self.evidence_kind,
            "adapter": [self.adapter_id, self.adapter_version], "tool": self.tool,
            "tool_version": self.tool_version, "tool_available": self.tool_available,
            "attempted": self.attempted, "outcome": self.outcome, "reason": self.reason,
            "repository_id": self.repository_id, "control_sha256": self.control_sha256,
            "need_identities": sorted(self.need_identities), "environment_keys": list(self.environment_keys),
            "targets": [target.fingerprint_material() for target in self.targets],
        }
        canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "phase_id": PHASE_ID,
            "evidence_kind": self.evidence_kind,
            "adapter": {"id": self.adapter_id, "version": self.adapter_version},
            "tool": self.tool,
            "tool_version": self.tool_version,
            "tool_available": self.tool_available,
            "attempted": self.attempted,
            "outcome": self.outcome,
            "reason": self.reason,
            "repository_id": self.repository_id,
            "control_sha256": self.control_sha256,
            "need_identities": list(self.need_identities),
            "compile_mode": "independent_per_target",
            "working_directory": "repository_root",
            "environment_keys": list(self.environment_keys),
            "version_probe": dict(self.version_probe),
            "targets": [target.as_dict() for target in self.targets],
            "exit_statuses": self.exit_statuses,
            "process_timeout_seconds": self.process_timeout_seconds,
            "timing_ms": {key: round(value, 3) for key, value in self.timing_ms.items()},
            "operational_warnings": list(self.operational_warnings),
            "semantics": SEMANTICS,
            "authority": dict(AUTHORITY),
            "evidence_fingerprint": self.evidence_fingerprint,
        }


# == javac diagnostics: structured fields beside bounded raw text =====================================

_DIAGNOSTIC_HEADER = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<severity>error|warning): (?P<message>.*)$")
_BLOCK_END = re.compile(r"^(?:\d+ (?:error|warning)s?$|Note: |error: |warning: )")
#: The whole unresolved-reference vocabulary: names the compiler could not see, which may live
#: outside the explicit targets.  No other diagnostic is interpreted.
_UNRESOLVED_REFERENCE = re.compile(r"^(?:cannot find symbol\b|package \S+ does not exist$|cannot access \S)")
_GROUPING_CONFLICT = re.compile(r"^duplicate class: ")
_VERSION = re.compile(r"^javac\s+(\S+)", re.MULTILINE)


def _path_key(path: str) -> str:
    text = path.replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.casefold() if os.name == "nt" else text


def parse_javac_diagnostics(text: str, targets: tuple[str, ...], *, limit: int = 32) -> tuple[CompilerDiagnostic, ...]:
    """Split normalized javac output into located diagnostics, each attributed to an exact target."""
    lookup = {_path_key(target): target for target in targets}
    blocks: list[tuple[re.Match[str], list[str]]] = []
    current: list[str] | None = None
    for line in text.split("\n"):
        header = _DIAGNOSTIC_HEADER.match(line)
        if header is not None:
            current = [line]
            blocks.append((header, current))
        elif current is not None:
            if _BLOCK_END.match(line):
                current = None
            else:
                current.append(line)
    diagnostics = []
    for header, lines in blocks[:limit]:
        column = None
        for line in lines[1:]:
            caret = line.rstrip()
            if caret.endswith("^") and not caret[:-1].strip():
                column = len(caret)  # the 1-based character column the caret marks
                break
        reported = header["file"]
        diagnostics.append(CompilerDiagnostic(
            file=lookup.get(_path_key(reported)), reported_file=reported, line=int(header["line"]),
            column=column, severity=header["severity"], message=header["message"][:_MAX_MESSAGE_CHARS],
            text="\n".join(lines).rstrip()[:_MAX_DIAGNOSTIC_TEXT_CHARS],
        ))
    return tuple(diagnostics)


def _relativize(text: str, root: Path, workspace: Path) -> str:
    """Remove host paths: the isolated workspace becomes a placeholder, repository paths become relative."""
    flags = re.IGNORECASE if os.name == "nt" else 0
    for base, prefixed, bare in ((workspace, "<isolated>/", "<isolated>"), (root, "", ".")):
        for spelling in dict.fromkeys((str(base), str(base).replace("\\", "/"))):
            text = re.sub(re.escape(spelling) + r"[\\/]", prefixed, text, flags=flags)
            # The bare directory only: a sibling such as "<root>-other" is a different path.
            text = re.sub(re.escape(spelling) + r"(?![\w.\-])", bare, text, flags=flags)
    return text


# == the one process launch site ======================================================================

def _start(argv: list[str], *, cwd: str, env: dict[str, str], stdout: Any, stderr: Any) -> subprocess.Popen:
    """Start an argument vector the adapter built: never a shell, never text from CONTROL or a model."""
    return subprocess.Popen(
        argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, shell=False,
        close_fds=True, start_new_session=(os.name != "nt"),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _system_tool(name: str) -> str | None:
    base = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or ""
    candidate = Path(base, "System32", name) if base else None
    return str(candidate) if candidate is not None and candidate.is_absolute() and candidate.is_file() else None


def _terminate(process: subprocess.Popen, *, cwd: str, env: dict[str, str]) -> None:
    """Stop a timed-out launcher and whatever it started, best effort, then reap it."""
    if os.name == "nt":
        taskkill = _system_tool("taskkill.exe")
        if taskkill is not None:
            argv = [taskkill, "/F", "/T", "/PID", str(process.pid)]
            try:
                killer = _start(argv, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                killer.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


@dataclass(frozen=True)
class _ProcessRun:
    exit_status: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes
    stdout_total: int
    stderr_total: int
    launch_ms: float
    wait_ms: float
    launch_error: str | None = None


def _read_bounded(path: Path, limit: int) -> tuple[bytes, int]:
    try:
        total = path.stat().st_size
        with open(path, "rb") as handle:
            return handle.read(limit), total
    except OSError:
        return b"", 0


def _run_bounded(argv: list[str], *, cwd: str, env: dict[str, str], workspace: Path, label: str,
                 timeout: float, limits: DiagnosticLimits) -> _ProcessRun:
    out_path, err_path = workspace / f"{label}.stdout", workspace / f"{label}.stderr"
    with open(out_path, "wb") as stdout, open(err_path, "wb") as stderr:
        began = time.perf_counter()
        try:
            process = _start(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        except FileNotFoundError:
            return _ProcessRun(None, False, b"", b"", 0, 0, (time.perf_counter() - began) * 1000, 0.0, "not_found")
        except PermissionError:
            return _ProcessRun(None, False, b"", b"", 0, 0, (time.perf_counter() - began) * 1000, 0.0,
                               "not_permitted")
        except OSError:
            return _ProcessRun(None, False, b"", b"", 0, 0, (time.perf_counter() - began) * 1000, 0.0, "os_error")
        launched = time.perf_counter()
        timed_out = False
        try:
            exit_status: int | None = process.wait(timeout=max(timeout, 0.001))
        except subprocess.TimeoutExpired:
            timed_out, exit_status = True, None
            _terminate(process, cwd=str(workspace), env=env)
        finished = time.perf_counter()
    stdout_raw, stdout_total = _read_bounded(out_path, limits.max_output_bytes)
    stderr_raw, stderr_total = _read_bounded(err_path, limits.max_output_bytes)
    return _ProcessRun(exit_status, timed_out, stdout_raw, stderr_raw, stdout_total, stderr_total,
                       (launched - began) * 1000, (finished - launched) * 1000)


# == the Java compile adapter =========================================================================

#: Deterministic English diagnostics and no JVM performance-data files.
_JAVAC_RUNTIME_OPTIONS = ("-J-Duser.language=en", "-J-Duser.country=US", "-J-XX:-UsePerfData")
_JAVAC_OUTPUT_OPTIONS = ("-J-Dstdout.encoding=UTF-8", "-J-Dstderr.encoding=UTF-8")
#: The only inherited variables.  JAVA_TOOL_OPTIONS, _JAVA_OPTIONS, JDK_JAVA_OPTIONS,
#: JDK_JAVAC_OPTIONS, CLASSPATH, credentials and every other variable stay behind.
_INHERITED_ENVIRONMENT = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR")


def _executable_names(stem: str) -> tuple[str, ...]:
    if os.name != "nt":
        return (stem,)
    # Only real executables: a .bat or .cmd wrapper would put a command interpreter in the path.
    extensions = [ext for ext in os.environ.get("PATHEXT", ".COM;.EXE").split(os.pathsep)
                  if ext.upper() in (".EXE", ".COM")]
    return tuple(stem + ext for ext in extensions) or (stem + ".exe",)


def _is_within(path: Path, root: Path) -> bool:
    try:
        resolved, base = os.path.normcase(str(path.resolve())), os.path.normcase(str(root.resolve()))
    except (OSError, RuntimeError):
        return True  # an unresolvable location is treated as inside: fail closed
    return resolved == base or resolved.startswith(base.rstrip("\\/") + os.sep)


def resolve_javac(excluded_root: Path | None = None) -> str | None:
    """The first ``javac`` executable in an absolute PATH directory outside the repository.

    A bounded lookup: PATH entries only (not the working directory), nothing is
    downloaded, installed or configured, and a repository can never supply its own compiler.
    """
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isabs(entry):
            continue
        for name in _executable_names("javac"):
            candidate = os.path.join(entry, name)
            if not os.path.isfile(candidate) or (os.name != "nt" and not os.access(candidate, os.X_OK)):
                continue
            if excluded_root is not None and _is_within(Path(candidate), excluded_root):
                continue
            return candidate
    return None


def _child_environment(workspace: Path) -> dict[str, str]:
    env = {name: os.environ[name] for name in _INHERITED_ENVIRONMENT if os.environ.get(name)}
    for name in ("TEMP", "TMP", "TMPDIR"):
        env[name] = str(workspace)
    return env


def _version_argv(tool: str) -> list[str]:
    return [tool, *_JAVAC_RUNTIME_OPTIONS, "-version"]


def _javac_argv(tool: str, empty: Path, output: Path, targets: tuple[str, ...]) -> list[str]:
    # An explicitly empty source path and class path: javac resolves nothing from the
    # repository beyond the exact targets, so no neighbouring file is ever read or compiled.
    return [
        tool, *_JAVAC_RUNTIME_OPTIONS, *_JAVAC_OUTPUT_OPTIONS,
        "-encoding", "UTF-8", "-proc:none", "-implicit:none",
        "-sourcepath", str(empty), "-classpath", str(empty), "-d", str(output),
        "-Xmaxerrs", "100", "-Xmaxwarns", "100", *targets,
    ]


def _display(argv: list[str], empty: Path, output: Path) -> str:
    placeholders = {str(empty): "<isolated-empty>", str(output): "<isolated-output>"}
    shown = ["javac"] + [placeholders.get(argument, argument) for argument in argv[1:]]
    return " ".join(f'"{item}"' if " " in item else item for item in shown)


def _remove_tree(path: Path) -> bool:
    for attempt in range(3):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(0.05 * (attempt + 1))
    return not path.exists()


def _unsupported_target_reason(target: str) -> str | None:
    if target.startswith(("-", "@")):
        return "target_not_argv_safe"  # would read as a javac option or argument file
    if PurePosixPath(target).name == "module-info.java":
        return "module_descriptor_requires_build_context"
    return None


class JavaCompileDiagnosticAdapter:
    """The one owner of a javac invocation.  CONTROL and the model never construct argv.

    Working directory: the canonical repository root, so each exact repository-relative
    target resolves where the author read it; javac gets an empty isolated source and class
    path, so nothing else in the repository is consulted, and writes class files only
    under an isolated temporary directory outside the repository, removed afterwards.
    Each target is compiled on its own; targets whose only errors are unresolved names
    get one grouped compile with the other explicit targets that compiled, never more.
    """

    adapter_id = JAVA_COMPILE_ADAPTER_ID
    version = JAVA_COMPILE_ADAPTER_VERSION
    tool = "javac"

    def __init__(self, *, limits: DiagnosticLimits | None = None,
                 resolve_tool: Callable[[Path], str | None] | None = None) -> None:
        self.limits = limits or DiagnosticLimits()
        self._resolve_tool = resolve_tool or resolve_javac

    # -- orchestration ------------------------------------------------------------------------------

    def measure(self, plan: DiagnosticPlan) -> DiagnosticEvidenceReceipt:
        began = time.perf_counter()
        timing = dict.fromkeys(("adapter_construction", "tool_probe", "process_launch", "process_wait",
                                "normalization", "cleanup"), 0.0)
        root = Path(plan.canonical_root)
        receipt = dict(
            evidence_kind=plan.kind, adapter_id=self.adapter_id, adapter_version=self.version, tool=self.tool,
            tool_version=None, tool_available=False, attempted=False, repository_id=plan.repository_id,
            control_sha256=plan.control_sha256, need_identities=plan.need_identities,
            version_probe={"attempted": False, "exit_status": None, "timed_out": False, "elapsed_ms": 0.0},
            environment_keys=(), process_timeout_seconds=self.limits.process_timeout_seconds,
        )

        def everywhere(outcome, reason):
            targets = [TargetMeasurement(source.path, source.sha256, False, outcome, reason)
                       for source in plan.sources]
            return targets, outcome, reason

        warnings: list[str] = []
        tool = self._resolve_tool(root)
        if tool is None:
            targets, outcome, reason = everywhere(TOOL_UNAVAILABLE, "javac_not_found")
        else:
            workspace = Path(tempfile.mkdtemp(prefix="cattus-preflight-")).resolve()
            try:
                if _is_within(workspace, root):
                    targets, outcome, reason = everywhere(ADAPTER_ERROR, "isolated_output_inside_repository")
                else:
                    targets, outcome, reason = self._measure_in(plan, tool, root, workspace, receipt, timing, began,
                                                                everywhere)
            finally:
                # Every outcome - pass, failure, timeout, error - removes the isolated output.
                cleanup_began = time.perf_counter()
                if not _remove_tree(workspace):
                    warnings.append("isolated_output_cleanup_failed")
                timing["cleanup"] = (time.perf_counter() - cleanup_began) * 1000
        if outcome is None:
            outcome, reason = _aggregate(targets)
        timing["total"] = (time.perf_counter() - began) * 1000
        return DiagnosticEvidenceReceipt(outcome=outcome, reason=reason or "", targets=tuple(targets),
                                         timing_ms=dict(timing), operational_warnings=tuple(warnings), **receipt)

    def _measure_in(self, plan, tool, root, workspace, receipt, timing, began, everywhere):
        empty = workspace / "empty"
        empty.mkdir()
        env = _child_environment(workspace)
        receipt["environment_keys"] = tuple(sorted(env))
        timing["adapter_construction"] = (time.perf_counter() - began) * 1000
        deadline = began + self.limits.cycle_budget_seconds

        probe = _run_bounded(_version_argv(tool), cwd=str(workspace), env=env, workspace=workspace, label="version",
                             timeout=min(self.limits.version_probe_timeout_seconds, deadline - time.perf_counter()),
                             limits=self.limits)
        timing["tool_probe"] = probe.launch_ms + probe.wait_ms
        receipt["version_probe"] = {"attempted": probe.launch_error is None, "exit_status": probe.exit_status,
                                    "timed_out": probe.timed_out, "elapsed_ms": round(timing["tool_probe"], 3)}
        if probe.launch_error is not None:
            return everywhere(TOOL_UNAVAILABLE, f"javac_not_launchable_{probe.launch_error}")
        if probe.timed_out:
            return everywhere(DIAGNOSTIC_TIMEOUT, "version_probe_timeout")
        version = _VERSION.search((probe.stdout + b"\n" + probe.stderr).decode("utf-8", "replace"))
        if probe.exit_status != 0 or version is None:
            return everywhere(TOOL_UNAVAILABLE, "version_probe_failed")
        receipt.update(tool_available=True, tool_version=f"javac {version.group(1)}")

        measurements = [self._independent(index, source, tool, root, workspace, empty, env, deadline, timing)
                        for index, source in enumerate(plan.sources)]
        measurements = self._disambiguate(measurements, tool, root, workspace, empty, env, deadline, timing)
        receipt["attempted"] = any(item.attempted for item in measurements)
        return measurements, None, None

    # -- one compile ----------------------------------------------------------------------------------

    def _compile(self, label, targets, tool, root, workspace, empty, env, deadline, timing):
        output = workspace / f"classes-{label}"
        output.mkdir()
        argv = _javac_argv(tool, empty, output, targets)
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return None, _display(argv, empty, output)
        run = _run_bounded(argv, cwd=str(root), env=env, workspace=workspace, label=f"compile-{label}",
                           timeout=min(self.limits.process_timeout_seconds, remaining), limits=self.limits)
        timing["process_launch"] += run.launch_ms
        timing["process_wait"] += run.wait_ms
        return run, _display(argv, empty, output)

    def _normalize(self, run, targets, root, workspace, timing):
        began = time.perf_counter()
        streams = []
        for raw, total in ((run.stdout, run.stdout_total), (run.stderr, run.stderr_total)):
            text = raw.decode("utf-8", "replace").replace("\r\n", "\n")
            text = redact_credentials(_relativize(text, root, workspace))
            streams.append((text, CapturedStream(
                bytes_total=total, bytes_captured=len(raw), truncated=total > len(raw),
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), text=text[:self.limits.max_evidence_chars],
            )))
        (_, stdout), (stderr_text, stderr) = streams
        diagnostics = parse_javac_diagnostics(stderr_text, targets, limit=self.limits.max_diagnostics)
        timing["normalization"] += (time.perf_counter() - began) * 1000
        return stdout, stderr, diagnostics

    def _independent(self, index, source, tool, root, workspace, empty, env, deadline, timing):
        unsupported = _unsupported_target_reason(source.path)
        if unsupported is not None:
            return TargetMeasurement(source.path, source.sha256, False, DIAGNOSTIC_INCONCLUSIVE, unsupported)
        run, invocation = self._compile(str(index), (source.path,), tool, root, workspace, empty, env, deadline,
                                        timing)
        if run is None:
            return TargetMeasurement(source.path, source.sha256, False, DIAGNOSTIC_INCONCLUSIVE,
                                     "cycle_budget_exhausted", invocation=invocation)
        outcome, reason, stdout, stderr, diagnostics = self._settle(run, source.path, (source.path,), root,
                                                                    workspace, timing, grouped=False)
        return TargetMeasurement(
            source.path, source.sha256, run.launch_error is None, outcome, reason, "independent", (),
            None, run.exit_status, run.timed_out, run.launch_ms + run.wait_ms, diagnostics, stdout, stderr,
            invocation,
        )

    def _settle(self, run, target, targets, root, workspace, timing, *, grouped):
        if run.launch_error is not None:
            reason = f"javac_not_launchable_{run.launch_error}"
            outcome = TOOL_UNAVAILABLE if run.launch_error == "not_found" else ADAPTER_ERROR
            return outcome, reason, CapturedStream(), CapturedStream(), ()
        stdout, stderr, diagnostics = self._normalize(run, targets, root, workspace, timing)
        if run.timed_out:
            return DIAGNOSTIC_TIMEOUT, "grouped_compile_timeout" if grouped else "compile_timeout", stdout, stderr, ()
        own = [item for item in diagnostics if item.file == target and item.severity == "error"]
        if run.exit_status == 0:
            outcome, reason = COMPILE_PASSED, ""
        elif not own:
            outcome, reason = DIAGNOSTIC_INCONCLUSIVE, (
                "grouped_compile_failed_elsewhere" if grouped else "compiler_reported_no_source_diagnostic")
        elif grouped and any(_GROUPING_CONFLICT.match(item.message) for item in own):
            outcome, reason = DIAGNOSTIC_INCONCLUSIVE, "grouped_compile_conflict"
        elif all(_UNRESOLVED_REFERENCE.match(item.message) for item in own):
            outcome, reason = DIAGNOSTIC_INCONCLUSIVE, (
                "unresolved_reference_outside_explicit_targets" if grouped else "unresolved_reference")
        else:
            outcome, reason = COMPILE_FAILED, ""
        attributed = tuple(item for item in diagnostics if item.file == target or not grouped)
        return outcome, reason, stdout, stderr, attributed

    # -- one bounded grouped compile for names the explicit targets may resolve -----------------------

    def _disambiguate(self, measurements, tool, root, workspace, empty, env, deadline, timing):
        unresolved = [item for item in measurements
                      if item.outcome == DIAGNOSTIC_INCONCLUSIVE and item.reason == "unresolved_reference"]
        group = tuple(item.path for item in measurements
                      if item in unresolved or item.outcome == COMPILE_PASSED)
        if not unresolved or len(group) < 2:
            return measurements
        run, invocation = self._compile("group", group, tool, root, workspace, empty, env, deadline, timing)
        settled = []
        for item in measurements:
            if item not in unresolved:
                settled.append(item)
            elif run is None:
                settled.append(replace(item, reason="cycle_budget_exhausted"))
            else:
                outcome, reason, stdout, stderr, diagnostics = self._settle(run, item.path, group, root, workspace,
                                                                            timing, grouped=True)
                settled.append(replace(
                    item, outcome=outcome, reason=reason, compile_mode="grouped", group=group,
                    independent_outcome=item.outcome, exit_status=run.exit_status, timed_out=run.timed_out,
                    elapsed_ms=item.elapsed_ms + run.launch_ms + run.wait_ms, diagnostics=diagnostics,
                    stdout=stdout, stderr=stderr, invocation=invocation,
                ))
        return settled


def _aggregate(targets: list[TargetMeasurement]) -> tuple[str, str]:
    outcomes = [target.outcome for target in targets]
    if COMPILE_FAILED in outcomes:
        return COMPILE_FAILED, ""
    if outcomes and all(outcome == COMPILE_PASSED for outcome in outcomes):
        return COMPILE_PASSED, ""
    for outcome in (DIAGNOSTIC_TIMEOUT, TOOL_UNAVAILABLE, ADAPTER_ERROR, DIAGNOSTIC_INCONCLUSIVE):
        first = next((target for target in targets if target.outcome == outcome), None)
        if first is not None:
            return outcome, first.reason
    return DIAGNOSTIC_INCONCLUSIVE, "no_target_measured"


# == the handoff: measured evidence into the existing defect-fact boundary ============================

_INCONCLUSIVE_CATEGORIES = {
    TOOL_UNAVAILABLE: "validation_tool_unavailable",
    DIAGNOSTIC_TIMEOUT: "validation_budget_exhausted",
}


def _failure_output(target: TargetMeasurement) -> str:
    """The compiler output a defect may bind to: this target's own, never another target's."""
    if target.compile_mode == "independent":
        return target.stderr.text  # javac's exact output for this one file
    # A grouped compile printed every member's diagnostics; keep only the blocks attributed here.
    return "\n".join(item.text for item in target.diagnostics if item.file == target.path)


def compile_evidence_handoff(receipt: DiagnosticEvidenceReceipt) -> dict[str, Any]:
    """The receipt as CONTROL's ``preflight_validation`` record, which DEFECT.FACT already reads.

    Only a target that failed with a source diagnostic contributes output and typed
    ``compiler_error`` locations; a passing target is summarized, never named in the
    output a defect could bind to.  Host paths are already placeholders.
    """
    failed = [target for target in receipt.targets if target.outcome == COMPILE_FAILED]
    passed = [target.path for target in receipt.targets if target.outcome == COMPILE_PASSED]
    if failed:
        outcome, category, ok = "failed", "build_error", False
        reason = ("Compilation failed under the recorded javac invocation for: "
                  + ", ".join(target.path for target in failed) + ".")
        if passed:
            reason += " Compiled without errors (compile only; behavior not verified): " + ", ".join(passed) + "."
    elif receipt.outcome == COMPILE_PASSED:
        outcome, category, ok = "passed", "passed", True
        reason = "Every requested target compiled under the recorded javac invocation; behavior is not verified."
    else:
        outcome, ok = "inconclusive", False
        category = _INCONCLUSIVE_CATEGORIES.get(receipt.outcome, "validation_environment")
        reason = f"Compile evidence is inconclusive ({receipt.outcome}: {receipt.reason})."
    locations = [
        {"kind": "compiler_error", "language": "java", "file": target.path, "line": item.line, "col": item.column,
         "severity": item.severity, "message": item.message}
        for target in failed for item in target.diagnostics
        if item.file == target.path and item.severity == "error"
    ][:_MAX_HANDOFF_LOCATIONS]
    shown = failed or [target for target in receipt.targets if target.attempted]
    return {
        "ran": receipt.attempted,
        # Compatibility: only a genuine pass of every target may be true.
        "ok": ok,
        "outcome": outcome,
        "category": category,
        "command": "\n".join(target.invocation for target in shown if target.invocation),
        "reason": reason,
        "hint": "Measured by PREFLIGHT.REQUEST.1. A compiler result is not behavioral, test or patch evidence.",
        "output": "\n".join(_failure_output(target) for target in failed)[:_MAX_HANDOFF_OUTPUT_CHARS],
        "locations": locations,
        "timed_out": any(target.timed_out for target in receipt.targets),
        "timeout_seconds": max(1, math.ceil(receipt.process_timeout_seconds)),
        "validation_budget_exhausted": category == "validation_budget_exhausted",
        "python_bytecode_cache_isolated": False,
        "evidence_source": PHASE_ID,
        "evidence_kind": receipt.evidence_kind,
        "measured": True,
        "adapter": f"{receipt.adapter_id}/{receipt.adapter_version}",
        "tool_version": receipt.tool_version,
        "receipt_fingerprint": receipt.evidence_fingerprint,
        "control_sha256": receipt.control_sha256,
        # PATCH.BASIS.SCOPE.1 consumes these existing receipt facts to verify
        # source freshness before structurally grouping diagnostics.  This is
        # an additive projection only: it neither changes measurement policy
        # nor gives the handoff any execution or patch authority.
        "repository_id": receipt.repository_id,
        "source_fingerprints": [
            {"path": target.path, "sha256": target.source_sha256}
            for target in receipt.targets
        ],
        "compile_mode": "independent_per_target",
        "targets": [
            {"path": target.path, "outcome": target.outcome, "reason": target.reason,
             "compile_mode": target.compile_mode, "errors": target.error_count, "warnings": target.warning_count}
            for target in receipt.targets
        ],
        "semantics": SEMANTICS,
        "authority": dict(AUTHORITY),
    }


# == one bounded diagnostic cycle ======================================================================

@dataclass(frozen=True)
class PreflightRequestResult:
    """The typed outcome of one request's diagnostic cycle, and the CONTROL that continues (or none)."""

    status: str
    scope: PreflightScope
    control: dict[str, Any] | None
    reason: str = ""
    detail: str = ""
    derivations: tuple[NeedDerivation, ...] = ()
    decisions: tuple[PolicyDecision, ...] = ()
    receipts: tuple[DiagnosticEvidenceReceipt, ...] = ()
    need_receipts: Mapping[str, str] = field(default_factory=dict)
    handoff: Mapping[str, Any] | None = None
    source_freshness: Mapping[str, str] = field(default_factory=dict)
    timing_ms: Mapping[str, float] = field(default_factory=dict)

    def receipt(self) -> dict[str, Any]:
        handoff = {"attached": self.handoff is not None, "field": HANDOFF_FIELD}
        if self.handoff is not None:
            handoff.update(outcome=self.handoff["outcome"], category=self.handoff["category"])
        return {
            "phase_id": PHASE_ID,
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "status": self.status,
            "reason": self.reason,
            "repository": {"canonical_root": self.scope.canonical_root, "repository_id": self.scope.repository_id},
            "control_sha256": self.scope.control_sha256,
            "cycles": 1 if self.receipts else 0,
            "requested_evidence": [item.need.as_dict() for item in self.derivations if item.need is not None],
            "rejected_evidence": [{"provenance": item.provenance, "code": item.code, "field": item.field}
                                  for item in self.derivations if item.need is None],
            "ignored_item_keys": [f"{item.provenance}.{key}" for item in self.derivations
                                  for key in item.ignored_keys],
            "policy": [decision.as_dict() for decision in self.decisions],
            "source_freshness": dict(self.source_freshness),
            "diagnostics": [receipt.as_dict() for receipt in self.receipts],
            "need_receipts": dict(self.need_receipts),
            "handoff": handoff,
            "timing_ms": {key: round(value, 3) for key, value in self.timing_ms.items()},
            "executable_commands_accepted": 0,
            "model_calls": 0,
            "network_operations": 0,
            "repository_traversals": 0,
            "graph_operations": 0,
            "index_operations": 0,
            "embedding_operations": 0,
            "authority": dict(AUTHORITY),
        }

    def attach(self, answer: Any) -> Any:
        """Add this cycle's receipt to the downstream answer; a CONTROL without gaps adds nothing."""
        if isinstance(answer, dict) and self.status != NO_EVIDENCE_NEED:
            answer[RESULT_FIELD] = self.receipt()
        return answer

    def response(self) -> dict[str, Any]:
        """The typed answer for a request whose CONTROL may not continue (a new dict each call)."""
        if self.control is not None:
            raise ValueError("a CONTROL that continues into the pipeline has no stop answer")
        return {
            "error": _MESSAGES[self.status].format(detail=self.detail or "a requested file", reason=self.reason),
            "code": self.status,
            "reason": self.reason,
            "control_context": control_context.FRESH_BOOTSTRAP_REQUIRED,
            RESULT_FIELD: self.receipt(),
        }


def _binding_failure(control: Any, scope: PreflightScope) -> str | None:
    if not isinstance(control, dict) or control_fingerprint(control) != scope.control_sha256:
        return "control_fingerprint"
    if control.get("repo_path") != scope.canonical_root:
        return "repository_root"
    try:
        root = canonicalize_repository_root(scope.canonical_root)
    except NotADirectoryError:
        return "repository_unavailable"
    if root != scope.canonical_root:
        return "repository_root"
    if derive_repository_id_from_canonical_root(root) != scope.repository_id:
        return "repository_id"
    declared = control.get("target_scope")
    if isinstance(declared, dict) and declared.get("evidence_targets") is not None and (
            list(declared["evidence_targets"]) != list(scope.evidence_targets)):
        return "evidence_scope"
    return None


def _content_digest(path: Path, expected: os.stat_result) -> str | None:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        current = os.fstat(descriptor)
        if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
            return None  # the path was swapped between the identity check and the open
        digest, remaining = hashlib.sha256(), MAX_SOURCE_BYTES_PER_FILE + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
            remaining -= len(chunk)
        return None  # larger than any admitted source
    finally:
        os.close(descriptor)


def source_freshness(scope: PreflightScope, source: ScopedSource) -> str:
    """CTX.READ.1's freshness rule for one evidence target, plus its exact content digest."""
    path = Path(scope.canonical_root).joinpath(*PurePosixPath(source.path).parts)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return "deleted"
    except OSError:
        return "unverifiable"
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        return "replaced"
    digest = _content_digest(path, info)
    if digest is None:
        return "unverifiable"
    return verify_direct_read_receipt(
        source.receipt, DirectReadFileIdentity.from_stat_result(info, content_sha256=digest)).status


def _plans(admitted: list[PolicyDecision], scope: PreflightScope) -> tuple[DiagnosticPlan, ...]:
    """One plan per adapter over the union of admitted targets: each target is measured once."""
    grouped: dict[str, tuple[str, list[str], list[str]]] = {}
    for decision in admitted:
        kind, targets, needs = grouped.setdefault(decision.adapter_id, (decision.need.kind, [], []))
        targets.extend(target for target in decision.need.targets if target not in targets)
        if decision.need.identity not in needs:
            needs.append(decision.need.identity)
    sources = {source.path: source for source in scope.sources}
    return tuple(
        DiagnosticPlan(adapter_id, kind, sources[targets[0]].language, tuple(sources[target] for target in targets),
                       tuple(needs), scope.control_sha256, scope.repository_id, scope.canonical_root)
        for adapter_id, (kind, targets, needs) in grouped.items()
    )


def _default_adapters() -> dict[str, Any]:
    return {JAVA_COMPILE_ADAPTER_ID: JavaCompileDiagnosticAdapter()}


def _with_handoff(control: dict[str, Any], handoff: dict[str, Any]) -> dict[str, Any]:
    # The continuing CONTROL is exactly what the continuation parser accepts from this JSON.
    parsed = control_context.normalize_control_values([json.dumps({**control, HANDOFF_FIELD: handoff},
                                                                  ensure_ascii=False)])
    if parsed.state != control_context.PRIOR_CONTROL:
        raise ValueError(f"the measured CONTROL was rejected: {parsed.reason}")
    return parsed.control


def run_preflight_request(
    control: dict[str, Any],
    scope: PreflightScope,
    *,
    adapters: Mapping[str, Any] | None = None,
) -> PreflightRequestResult:
    """At most one bounded diagnostic cycle for CONTROL's typed evidence gaps."""
    began = time.perf_counter()
    timing: dict[str, float] = {}
    result = PreflightRequestResult(status=NO_EVIDENCE_NEED, scope=scope, control=control)

    def done(**changes):
        timing["total"] = (time.perf_counter() - began) * 1000
        process = sum(receipt.timing_ms["process_launch"] + receipt.timing_ms["process_wait"]
                      + receipt.timing_ms["tool_probe"] for receipt in changes.get("receipts", ()))
        timing["harness_overhead"] = max(timing["total"] - process, 0.0)
        return replace(result, timing_ms=dict(timing), **changes)

    mismatch = _binding_failure(control, scope)
    if mismatch is not None:
        return done(status=PREFLIGHT_BINDING_MISMATCH, reason=mismatch, control=None)
    derivations = derive_evidence_needs(control, scope)
    if not derivations:
        return done()
    decisions = tuple(decide_evidence_need(item.need, scope) for item in derivations if item.need is not None)
    timing["policy"] = (time.perf_counter() - began) * 1000
    result = replace(result, status=NO_ADMITTED_NEED, derivations=derivations, decisions=decisions)
    admitted = [decision for decision in decisions if decision.admitted]
    if not admitted:
        return done()

    plans = _plans(admitted, scope)
    checked = time.perf_counter()
    freshness = {source.path: source_freshness(scope, source) for plan in plans for source in plan.sources}
    timing["freshness"] = (time.perf_counter() - checked) * 1000
    stale = next((path for path, status in freshness.items() if status != "fresh"), None)
    if stale is not None:
        # CONTROL's assumptions are stale: nothing is compiled without reacquisition.
        return done(status=PREFLIGHT_SOURCE_CHANGED, reason=freshness[stale], detail=stale, control=None,
                    source_freshness=freshness)

    available = dict(adapters) if adapters is not None else _default_adapters()
    receipts = tuple(available[plan.adapter_id].measure(plan) for plan in plans)
    need_receipts = {identity: receipt.evidence_fingerprint for receipt in receipts
                     for identity in receipt.need_identities}
    if any(receipt.attempted for receipt in receipts):
        # Bind the measurement to the bytes CONTROL was authored from, after the compiler ran.
        freshness = {source.path: source_freshness(scope, source) for plan in plans for source in plan.sources}
        stale = next((path for path, status in freshness.items() if status != "fresh"), None)
        if stale is not None:
            return done(status=PREFLIGHT_SOURCE_CHANGED, reason=freshness[stale], detail=stale, control=None,
                        source_freshness=freshness, receipts=receipts, need_receipts=need_receipts)
    handoff = compile_evidence_handoff(receipts[0])
    return done(status=EVIDENCE_MEASURED, control=_with_handoff(control, handoff), receipts=receipts,
                need_receipts=need_receipts, handoff=handoff, source_freshness=freshness)


def preflight_bootstrapped_control(result: Any, *, adapters: Mapping[str, Any] | None = None) -> PreflightRequestResult:
    """The Generate seam: one bounded diagnostic cycle for a bootstrapped CONTROL's evidence gaps."""
    return run_preflight_request(result.control, scope_from_bootstrap(result), adapters=adapters)
