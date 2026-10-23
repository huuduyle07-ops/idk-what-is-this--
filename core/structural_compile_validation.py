"""PATCH.CANDIDATE.VALIDATE.1A: compile exact virtual bytes, diagnostic authority only.

The execution facade reacquires named evidence before creating its ephemeral
workspace. The pure normalization/consumer seams require freshly acquired caller
evidence. Neither seam authors, repairs, discovers dependencies or runs Java.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from time import perf_counter

from core import structural_candidate_materialization as materializer
from core.repository_path_policy import is_safe_repository_relative_path
from web import preflight_request as preflight

PHASE_ID = "PATCH.CANDIDATE.VALIDATE.1A"
SCHEMA_VERSION = "patch_candidate_validate_1a_v1"
FIRST_REMAINING_BLOCKER = "STRUCTURAL_CANDIDATE_BEHAVIORAL_VALIDATION_NOT_IMPLEMENTED"
LIMITS = preflight.DiagnosticLimits()
MAX_OUTPUT_BYTES = LIMITS.max_output_bytes
MAX_DIAGNOSTICS = LIMITS.max_diagnostics
TIMING_FIELDS = (
    "fresh_materialization_validation_seconds", "exact_evidence_acquisition_seconds",
    "temporary_workspace_construction_seconds", "virtual_byte_integrity_verification_seconds",
    "javac_provider_seconds", "compiler_identity_seconds", "diagnostic_normalization_seconds",
    "owner_mapping_seconds", "receipt_fingerprinting_seconds", "total_harness_overhead_seconds",
    "total_seconds",
)
_AUTHORITIES = {"write_authority", "filesystem_write_authority", "filesystem_file_creation_authority",
    "execution_authorized", "apply_authority", "auto_apply", "test_write_authority"}
_LINEAGE = ("candidate_fingerprint", "admission_fingerprint", "implementation_plan_fingerprint",
    "task_fingerprint", "effective_design_fingerprint", "p1_fingerprint", "approval_receipt_fingerprint",
    "approved_ceiling_fingerprint", "repository_id", "repository_evidence_fingerprint")


class CompileValidationError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise CompileValidationError(code, reason)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is tuple:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for descriptor in fields(value):
            _immutable(getattr(value, descriptor.name))
    else:
        _fail("compile_receipt_invalid", "mutable evidence field")


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True, slots=True)
class JavacIdentity:
    executable: str
    executable_sha256: str
    version: str

    def __post_init__(self):
        _immutable(self)
        path = Path(self.executable)
        if (not path.is_absolute() or path.name.lower() not in {"javac", "javac.exe", "javac.com"}
                or not _digest(self.executable_sha256) or re.fullmatch(r"javac \S+", self.version) is None
                or len(self.version.encode("utf-8")) > MAX_OUTPUT_BYTES):
            _fail("compile_receipt_invalid", "closed javac identity required")


@dataclass(frozen=True, slots=True)
class CompilerResult:
    """Replayable, path-normalized compiler evidence; no runtime durations."""
    compiler: JavacIdentity | None
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    output_overflow: bool = False
    unavailable_reason: str = ""
    javac_invocation_count: int = 1
    version_probe_count: int = 1

    def __post_init__(self):
        _immutable(self)
        if (self.compiler is not None and type(self.compiler) is not JavacIdentity
                or self.exit_code is not None and type(self.exit_code) is not int
                or type(self.stdout) is not str or type(self.stderr) is not str
                or type(self.timed_out) is not bool or type(self.output_overflow) is not bool
                or type(self.unavailable_reason) is not str or len(self.unavailable_reason) > 200
                or type(self.javac_invocation_count) is not int or self.javac_invocation_count not in {0, 1}
                or type(self.version_probe_count) is not int or self.version_probe_count not in {0, 1}
                or any(len(s.encode("utf-8")) > MAX_OUTPUT_BYTES for s in (self.stdout, self.stderr))):
            _fail("compile_receipt_invalid", "invalid bounded compiler result")
        if self.exit_code is not None and (self.compiler is None or self.javac_invocation_count != 1
                or self.version_probe_count != 1 or self.timed_out or self.unavailable_reason):
            _fail("compile_receipt_invalid", "exit code requires a completed identified compile")
        if (self.javac_invocation_count == 1 and (self.compiler is None or self.version_probe_count != 1)
                or self.compiler is None and not (self.unavailable_reason or self.timed_out or self.output_overflow)
                or self.exit_code is None and not (self.unavailable_reason or self.timed_out or self.output_overflow)):
            _fail("compile_receipt_invalid", "incomplete compiler accounting")


@dataclass(frozen=True, slots=True)
class CompileInput:
    path: str
    sha256: str
    size: int
    provenance: str


@dataclass(frozen=True, slots=True)
class DiagnosticSourceReference:
    file: str
    source_sha256: str
    owner: str


@dataclass(frozen=True, slots=True)
class StructuralCompileDiagnostic:
    file: str | None
    line: int | None
    column: int | None
    kind: str
    message: str
    text: str
    symbol: str | None
    owner: str | None
    member: str | None
    definition_ids: tuple[str, ...]
    source_sha256: str | None
    related_sources: tuple[DiagnosticSourceReference, ...]
    compiler_receipt_fingerprint: str
    materialization_fingerprint: str


@dataclass(frozen=True, slots=True)
class JavacEvidenceSatisfaction:
    need_fingerprint: str
    implementation_plan_fingerprint: str
    kind: str
    satisfied: bool
    compiler_receipt_fingerprint: str


@dataclass(frozen=True, slots=True)
class StructuralCompileValidationReceipt:
    materialization_fingerprint: str
    candidate_fingerprint: str
    admission_fingerprint: str
    implementation_plan_fingerprint: str
    task_fingerprint: str
    effective_design_fingerprint: str
    p1_fingerprint: str
    approval_receipt_fingerprint: str
    approved_ceiling_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str
    input_manifest: tuple[CompileInput, ...]
    invocation_contract: tuple[str, ...]
    compiler_result: CompilerResult
    compiler_receipt_fingerprint: str
    status: str
    compile_success: bool
    diagnostics: tuple[StructuralCompileDiagnostic, ...]
    warnings: tuple[StructuralCompileDiagnostic, ...]
    javac_evidence_satisfaction: tuple[JavacEvidenceSatisfaction, ...]
    behavioral_validation_pending: bool
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    authority: str = field(default="diagnostic_evidence_only", init=False)
    shell: bool = field(default=False, init=False)
    compile_timeout_seconds: int = field(default=int(LIMITS.process_timeout_seconds), init=False)
    version_probe_timeout_seconds: int = field(default=int(LIMITS.version_probe_timeout_seconds), init=False)
    max_output_bytes_per_stream: int = field(default=MAX_OUTPUT_BYTES, init=False)
    max_diagnostics: int = field(default=MAX_DIAGNOSTICS, init=False)
    output_capture_policy: str = field(default="bounded_raw_text_with_logical_path_normalization; overflow_fail_closed", init=False)
    write_authority: bool = field(default=False, init=False)
    filesystem_write_authority: bool = field(default=False, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    test_write_authority: bool = field(default=False, init=False)
    behavior_validated: bool = field(default=False, init=False)
    correctness_proven: bool = field(default=False, init=False)
    arbitrary_command_execution_count: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    test_generation_count: int = field(default=0, init=False)
    java_execution_count: int = field(default=0, init=False)
    first_remaining_blocker: str = field(default=FIRST_REMAINING_BLOCKER, init=False)

    def __post_init__(self):
        _immutable(self)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def validation_fingerprint(self):
        return self.fingerprint

    @property
    def javac_invocation_count(self):
        return self.compiler_result.javac_invocation_count

    @property
    def version_probe_count(self):
        return self.compiler_result.version_probe_count

    @property
    def javac_total_invocation_count(self):
        return self.javac_invocation_count + self.version_probe_count

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "validation_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _gate(materialized, candidate, admitted_scope, fresh_inputs, repository_root, measured):
    inputs = dict(fresh_inputs)
    acquisition = {"exact_evidence_acquisition_seconds": 0.0}
    try:
        # This frozen acquisition seam reads only named source/path/policy evidence.
        inputs = materializer._fresh_inputs(inputs, repository_root, acquisition)
        tick = perf_counter()
        try:
            checked = materializer.validate_materialized_structural_candidate(materialized,
                candidate=candidate, admitted_scope=admitted_scope, **inputs)
        finally:
            measured["fresh_materialization_validation_seconds"] += perf_counter() - tick
        if repository_root is not None:
            newer = materializer._fresh_inputs(inputs, repository_root, acquisition)
            materializer._absence(admitted_scope, newer["repository_evidence"])
            if newer["repository_evidence"] != inputs["repository_evidence"]:
                _fail("reacquisition_required", "named evidence changed during validation")
            inputs = newer
        return checked, inputs
    except CompileValidationError:
        raise
    except (materializer.MaterializationError, materializer.AdmissionError) as exc:
        _fail(exc.code, exc.reason)
    except OSError as exc:
        _fail("reacquisition_required", type(exc).__name__)
    except (ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        _fail("compile_receipt_invalid", type(exc).__name__)
    finally:
        measured["exact_evidence_acquisition_seconds"] += acquisition["exact_evidence_acquisition_seconds"]


def _input_bytes(materialized, inputs, admitted_scope):
    sources = materializer._sources(inputs)
    rows = {f.path: (f.after_bytes, f.after_sha256, "materialized_virtual_file") for f in materialized.virtual_files}
    for dependency in materialized.supporting_files:
        raw = sources.get(dependency.path)
        if raw is None or sha256(raw).hexdigest() != dependency.source_sha256 or len(raw) != dependency.source_size:
            _fail("compile_evidence_incomplete", "exact bound dependency unavailable")
        rows[dependency.path] = (raw, dependency.source_sha256, "read_only_compile_dependency")
    test_paths = {n.proposed_test_file for n in admitted_scope.validation_evidence_needs if n.proposed_test_file}
    if not rows or len(rows) > materializer.MAX_FILES or sum(len(v[0]) for v in rows.values()) > materializer.MAX_TOTAL_BYTES:
        _fail("compile_evidence_incomplete", "bounded Java input set required")
    for path, (raw, digest, _) in rows.items():
        if (not is_safe_repository_relative_path(path) or PurePosixPath(path).suffix != ".java"
                or preflight._unsupported_target_reason(path) or path in test_paths
                or len(raw) > materializer.MAX_FILE_BYTES or sha256(raw).hexdigest() != digest):
            _fail("compile_evidence_incomplete", "unbound, unsafe or proposed-test input")
    return dict(sorted(rows.items()))


def _contract(paths):
    return tuple(preflight._javac_argv("javac", Path("<isolated-empty>"), Path("<isolated-output>"), tuple(paths)))


_HEADER = re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<kind>error|warning): (?P<message>.*)$")
_GLOBAL = re.compile(r"^(?P<kind>error|warning|Note): (?P<message>.*)$")
_COUNT = re.compile(r"^\d+ (?:error|warning)s?$|^printing javac parameters to:")
_SYMBOL = re.compile(r"^\s*symbol:\s+(?:class|variable|method|constructor)\s+(.+?)\s*$", re.MULTILINE)
_CLASS_REFERENCE = re.compile(r"\b(?:class|constructor) ([\w$]+(?:\.[\w$]+)*)")


def _blocks(output):
    blocks, current = [], None
    for line in output.splitlines():
        header = _HEADER.match(line)
        global_header = _GLOBAL.match(line)
        if header or global_header:
            match = header or global_header
            current = [match.groupdict(), [line]]
            blocks.append(current)
        elif _COUNT.match(line):
            current = None
        elif current is not None:
            current[1].append(line)
    return blocks


def _offset(raw, line, column):
    lines = raw.splitlines(keepends=True)
    if not 1 <= line <= len(lines):
        return None
    start = sum(map(len, lines[:line - 1]))
    if column is None:
        return start, start + len(lines[line - 1])
    decoded, visual = lines[line - 1].decode("utf-8"), 1
    for index, character in enumerate(decoded):
        if visual == column:
            byte = start + len(decoded[:index].encode("utf-8"))
            return byte, byte + len(character.encode("utf-8"))
        visual += 8 - ((visual - 1) % 8) if character == "\t" else 1
    return None


def _ownership(path, raw, inventory, line, column, materialized, admitted_scope):
    position = _offset(raw, line, column)
    if position is None:
        return None, None, ()
    left, right = position
    matches = [item for item in inventory if item[1] <= left < item[2]] if column else [
        item for item in inventory if item[1] < right and left < item[2]]
    if not matches:
        return None, None, ()
    minimum = min(item[2] - item[1] for item in matches)
    smallest = [item for item in matches if item[2] - item[1] == minimum]
    if len(smallest) != 1:
        return None, None, ()
    identity, start, end = smallest[0]
    parent, node_kind, name, parameter_types = identity
    is_class = node_kind.endswith("class_declaration") or node_kind in {"interface_declaration", "enum_declaration", "record_declaration"}
    owner = ((parent + "::") if parent else "") + name if is_class else parent
    kind = {"class_declaration": "class", "method_declaration": "method", "constructor_declaration": "constructor",
        "field_declaration": "field"}.get(node_kind)
    allowed = {d.definition.identity: d.definition for d in admitted_scope.definition_allowances}
    definitions = []
    for operation in materialized.applied_operations:
        if operation.path == path and operation.operation != "remove_declaration" and operation.after_start <= start <= end <= operation.after_end:
            for definition_id in operation.definition_ids:
                definition = allowed[definition_id]
                expected_owner = name if is_class else parent.split("::")[-1]
                if (definition.name == name and definition.kind == kind and definition.owner == expected_owner
                        and (kind not in {"method", "constructor"} or
                             tuple(re.sub(r"\s+", "", t) for t, _ in definition.parameters) == parameter_types)):
                    definitions.append(definition_id)
    return owner or None, None if is_class else name, tuple(sorted(definitions))


def _diagnostics(result, rows, materialized, scope, compiler_fingerprint, measured):
    tick = perf_counter()
    blocks = _blocks(result.stderr) + _blocks(result.stdout)
    measured["diagnostic_normalization_seconds"] += perf_counter() - tick
    if len(blocks) > MAX_DIAGNOSTICS:
        return (), True, False
    tick = perf_counter()
    inventories, classes = {}, {}
    for path, (raw, digest, _) in rows.items():
        tree = materializer.get_parser("java").parse(raw)
        inventory = materializer._inventory(tree.root_node, raw)
        inventories[path] = inventory
        packages = [n for n in tree.root_node.named_children if n.type == "package_declaration"]
        package = materializer.compact(materializer.children(packages[0])[0], raw) if packages else ""
        for (parent, kind, name, _), _, _ in inventory:
            if kind == "class_declaration":
                qualified = (parent + "::" if parent else "") + name
                # Keep ambiguous simple names unresolvable, rather than guessing.
                reference = DiagnosticSourceReference(path, digest, qualified)
                classes.setdefault(name, []).append(reference)
                exact_java_name = ((package + ".") if package else "") + qualified.replace("::", ".")
                if exact_java_name != name:
                    classes.setdefault(exact_java_name, []).append(reference)
    diagnostics, incomplete = [], False
    lookup = {preflight._path_key(p): p for p in rows}
    for header, lines in blocks:
        file = lookup.get(preflight._path_key(header.get("file", "")))
        line = int(header["line"]) if "line" in header else None
        column = next((len(s.rstrip()) for s in lines[1:] if s.rstrip().endswith("^") and not s.rstrip()[:-1].strip()), None)
        block = "\n".join(lines).rstrip()
        symbol_match = _SYMBOL.search(block)
        symbol = symbol_match[1] if symbol_match else None
        owner, member, definitions = (None, None, ())
        if file is not None:
            owner, member, definitions = _ownership(file, rows[file][0], inventories[file], line, column, materialized, scope)
        related = []
        for name in _CLASS_REFERENCE.findall(block):
            exact = classes.get(name, ())
            if len(exact) == 1 and exact[0] not in related:
                related.append(exact[0])
        message, kind = header["message"], header["kind"].lower()
        # Only missing external type/package evidence is incomplete. Missing
        # members in known classes remain measured language failures.
        if kind == "error" and (re.match(r"package \S+ does not exist$|cannot access \S", message)
                or message == "cannot find symbol" and re.search(r"^\s*symbol:\s+class\s+", block, re.MULTILINE)):
            incomplete = True
        diagnostics.append(StructuralCompileDiagnostic(file, line, column, kind, message, block, symbol,
            owner, member, definitions, rows[file][1] if file else None, tuple(related), compiler_fingerprint, materialized.fingerprint))
    measured["owner_mapping_seconds"] += perf_counter() - tick
    return tuple(diagnostics), False, incomplete


def _normalize(materialized, result, inputs, scope, measured):
    if type(result) is not CompilerResult:
        _fail("compile_receipt_invalid", "closed compiler result required")
    if result.compiler is not None:
        compiler_path = os.path.normcase(os.path.abspath(result.compiler.executable))
        root = os.path.normcase(inputs["repository_evidence"].canonical_root).rstrip("\\/")
        if compiler_path == root or compiler_path.startswith(root + os.sep):
            _fail("compile_receipt_invalid", "repository cannot supply the compiler")
    rows = _input_bytes(materialized, inputs, scope)
    manifest = tuple(CompileInput(path, digest, len(raw), provenance) for path, (raw, digest, provenance) in rows.items())
    contract = _contract(rows)
    tick = perf_counter()
    compiler_fingerprint = _hash({"materialization": materialized.fingerprint, "inputs": [asdict(i) for i in manifest],
        "invocation": contract, "result": asdict(result)})
    measured["receipt_fingerprinting_seconds"] += perf_counter() - tick
    diagnostics, diagnostics_overflow, incomplete = _diagnostics(result, rows, materialized, scope, compiler_fingerprint, measured)
    if result.output_overflow or diagnostics_overflow:
        status = "compile_output_bounded"
    elif result.timed_out:
        status = "compile_timeout"
    elif result.unavailable_reason:
        status = "validator_unavailable"
    elif result.exit_code == 0:
        status = "compile_evidence_incomplete" if any(d.kind == "error" for d in diagnostics) else "compile_validated"
    else:
        status = "compile_evidence_incomplete" if incomplete else "compile_failed"
    success = status == "compile_validated"
    needs = scope.validation_evidence_needs
    satisfaction = tuple(JavacEvidenceSatisfaction(_hash(asdict(n)), materialized.implementation_plan_fingerprint,
        n.kind, success, compiler_fingerprint) for n in needs if n.kind == "javac" and success)
    tick = perf_counter()
    receipt = StructuralCompileValidationReceipt(materialized.fingerprint,
        *(getattr(materialized, name) for name in _LINEAGE), manifest, contract, result, compiler_fingerprint,
        status, success, diagnostics, tuple(d for d in diagnostics if d.kind in {"warning", "note"}), satisfaction,
        any(n.kind in {"focused_behavioral_test", "validation_evidence_need"} for n in needs))
    receipt.fingerprint
    measured["receipt_fingerprinting_seconds"] += perf_counter() - tick
    return receipt


def _timings(timings):
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    return measured


def _finish_timing(measured, began):
    measured["total_seconds"] = perf_counter() - began
    measured["total_harness_overhead_seconds"] = max(0.0, measured["total_seconds"] - measured["javac_provider_seconds"])


def normalize_structural_compile_result(materialized, *, compiler_result, candidate, admitted_scope,
        timings=None, **fresh_inputs):
    """Pure normalization for exact acquired evidence and synthetic provider replay."""
    measured, began = _timings(timings), perf_counter()
    try:
        checked, inputs = _gate(materialized, candidate, admitted_scope, fresh_inputs, None, measured)
        return _normalize(checked, compiler_result, inputs, admitted_scope, measured)
    finally:
        _finish_timing(measured, began)


def _run_javac(argv, *, cwd, env, workspace, label, timeout):
    """Frozen launch/capture policy, with direct child cleanup: no second executable.

    javac is the sole child process, with annotation processing and implicit
    compilation disabled. Output files and all class files die with the workspace.
    """
    out_path, err_path = workspace / (label + ".stdout"), workspace / (label + ".stderr")
    with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
        began = perf_counter()
        try:
            process = preflight._start(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr)
        except OSError as exc:
            return preflight._ProcessRun(None, False, b"", b"", 0, 0, 0.0, 0.0, type(exc).__name__)
        launched = perf_counter()
        try:
            code, timed_out = process.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass
            code, timed_out = None, True
        finished = perf_counter()
    def capture(path):
        # A failed capture is not an empty successful compiler stream.
        try:
            total = path.stat().st_size
            with path.open("rb") as stream:
                return stream.read(MAX_OUTPUT_BYTES), total
        except OSError as exc:
            _fail("compile_evidence_incomplete", "compiler capture unavailable: " + type(exc).__name__)
    out, out_total = capture(out_path)
    err, err_total = capture(err_path)
    return preflight._ProcessRun(code, timed_out, out, err, out_total, err_total,
        (launched - began) * 1000, (finished - launched) * 1000)


def _normalize_paths(text, source_root, workspace):
    # Longest prefix first; javac may report either separator spelling.
    flags = re.IGNORECASE if os.name == "nt" else 0
    for base, replacement in ((source_root, ""), (workspace, "<isolated>/")):
        for spelling in dict.fromkeys((str(base), str(base).replace("\\", "/"))):
            text = re.sub(re.escape(spelling) + r"[\\/]", lambda _: replacement, text, flags=flags)
            text = re.sub(re.escape(spelling) + r"(?![\w.\-])", lambda _: replacement.rstrip("/") or ".", text, flags=flags)
    return text.replace("\r\n", "\n")


def _captured(run, source_root, workspace):
    overflow = (run.stdout_total > MAX_OUTPUT_BYTES or run.stderr_total > MAX_OUTPUT_BYTES
        or run.stdout_total != len(run.stdout) or run.stderr_total != len(run.stderr))
    streams = tuple(_normalize_paths(raw.decode("utf-8", "replace"), source_root, workspace) for raw in (run.stdout, run.stderr))
    # UTF-8 replacement can expand invalid bytes. Keep the bounded captured
    # prefix explicitly marked incomplete; never silently claim a canonical pass.
    if any(len(s.encode("utf-8")) > MAX_OUTPUT_BYTES for s in streams):
        overflow = True
        streams = tuple(s.encode("utf-8")[:MAX_OUTPUT_BYTES].decode("utf-8", "ignore") for s in streams)
    return *streams, overflow


def _project_workspace(rows, source_root):
    for path, (raw, _, _) in rows.items():
        target = source_root.joinpath(*PurePosixPath(path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def _verify_workspace(rows, source_root):
    for path, (raw, digest, _) in rows.items():
        target = source_root.joinpath(*PurePosixPath(path).parts)
        with target.open("rb") as stream:
            written = stream.read(materializer.MAX_FILE_BYTES + 1)
        if written != raw or sha256(written).hexdigest() != digest:
            _fail("validation_workspace_integrity_failure", path)


def _tool_digest(tool):
    digest = sha256()
    with Path(tool).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compile_materialized_structural_candidate(materialized, *, candidate, admitted_scope,
        repository_root, timings=None, **fresh_inputs):
    """One exact grouped javac diagnostic action after named-source freshness.

    Repository root is required for execution. No caller-supplied tool, flags,
    provider, classpath, temporary directory or dependency discovery is accepted.
    """
    measured, began = _timings(timings), perf_counter()
    try:
        if repository_root is None:
            _fail("reacquisition_required", "execution requires exact repository acquisition")
        checked, inputs = _gate(materialized, candidate, admitted_scope, fresh_inputs, repository_root, measured)
        rows = _input_bytes(checked, inputs, admitted_scope)
        root = Path(inputs["repository_evidence"].canonical_root)
        # Check the system temp parent before creating anything. An inherited
        # TEMP/TMP pointing into the repository cannot create even a directory.
        for location in (tempfile.tempdir, *(os.environ.get(n) for n in ("TMPDIR", "TEMP", "TMP"))):
            if location and Path(os.fsdecode(location)).resolve().is_relative_to(root):
                _fail("validation_workspace_integrity_failure", "configured temporary parent is inside repository")
        temp_parent = Path(tempfile.gettempdir()).resolve()
        if temp_parent.is_relative_to(root):
            _fail("validation_workspace_integrity_failure", "temporary parent is inside repository")
        tick = perf_counter()
        tool = preflight.resolve_javac(excluded_root=Path(inputs["repository_evidence"].canonical_root))
        if tool is None:
            measured["compiler_identity_seconds"] += perf_counter() - tick
            return _normalize(checked, CompilerResult(None, None, unavailable_reason="javac_not_found",
                javac_invocation_count=0, version_probe_count=0), inputs, admitted_scope, measured)
        try:
            tool_digest = _tool_digest(tool)
        except OSError:
            measured["compiler_identity_seconds"] += perf_counter() - tick
            return _normalize(checked, CompilerResult(None, None, unavailable_reason="javac_identity_unavailable",
                javac_invocation_count=0, version_probe_count=0), inputs, admitted_scope, measured)
        measured["compiler_identity_seconds"] += perf_counter() - tick
        tick = perf_counter()
        # Always the system temporary-directory lifetime, never repo-relative.
        with tempfile.TemporaryDirectory(prefix="patch-candidate-validate1a-", dir=temp_parent) as directory:
            workspace = Path(directory)
            if workspace.resolve().is_relative_to(root):
                _fail("validation_workspace_integrity_failure", "temporary directory is inside repository")
            source_root, output, empty = workspace / "sources", workspace / "classes", workspace / "empty"
            for path in (source_root, output, empty):
                path.mkdir()
            _project_workspace(rows, source_root)
            measured["temporary_workspace_construction_seconds"] += perf_counter() - tick
            tick = perf_counter()
            _verify_workspace(rows, source_root)
            measured["virtual_byte_integrity_verification_seconds"] += perf_counter() - tick
            env = preflight._child_environment(workspace)
            tick = perf_counter()
            probe = _run_javac(preflight._version_argv(tool), cwd=str(workspace), env=env,
                workspace=workspace, label="version", timeout=LIMITS.version_probe_timeout_seconds)
            measured["javac_provider_seconds"] += perf_counter() - tick
            tick = perf_counter()
            stdout, stderr, overflow = _captured(probe, source_root, workspace)
            measured["diagnostic_normalization_seconds"] += perf_counter() - tick
            version = (stdout + "\n" + stderr).strip()
            if overflow or probe.timed_out or probe.launch_error or probe.exit_status != 0 or not re.fullmatch(r"javac \S+", version):
                result = CompilerResult(None, None, stdout, stderr, probe.timed_out, overflow,
                    "" if probe.timed_out or overflow else (probe.launch_error or "version_probe_failed"), 0, 1)
                return _normalize(checked, result, inputs, admitted_scope, measured)
            tick = perf_counter()
            try:
                identity_unchanged = _tool_digest(tool) == tool_digest
            except OSError:
                identity_unchanged = False
            if not identity_unchanged:
                measured["compiler_identity_seconds"] += perf_counter() - tick
                return _normalize(checked, CompilerResult(None, None, stdout, stderr,
                    unavailable_reason="compiler_identity_changed", javac_invocation_count=0,
                    version_probe_count=1), inputs, admitted_scope, measured)
            compiler = JavacIdentity(str(Path(tool).resolve()), tool_digest, version)
            measured["compiler_identity_seconds"] += perf_counter() - tick
            # Verify again immediately before the only compile invocation.
            tick = perf_counter()
            _verify_workspace(rows, source_root)
            measured["virtual_byte_integrity_verification_seconds"] += perf_counter() - tick
            tick = perf_counter()
            run = _run_javac(preflight._javac_argv(tool, empty, output, tuple(rows)),
                cwd=str(source_root), env=env, workspace=workspace, label="compile", timeout=LIMITS.process_timeout_seconds)
            measured["javac_provider_seconds"] += perf_counter() - tick
            tick = perf_counter()
            stdout, stderr, overflow = _captured(run, source_root, workspace)
            measured["diagnostic_normalization_seconds"] += perf_counter() - tick
            tick = perf_counter()
            try:
                identity_unchanged = _tool_digest(tool) == tool_digest
            except OSError:
                identity_unchanged = False
            measured["compiler_identity_seconds"] += perf_counter() - tick
            tick = perf_counter()
            _verify_workspace(rows, source_root)
            measured["virtual_byte_integrity_verification_seconds"] += perf_counter() - tick
            result = CompilerResult(compiler, run.exit_status, stdout, stderr, run.timed_out, overflow,
                run.launch_error or "", 1, 1)
            if not identity_unchanged:
                result = CompilerResult(compiler, None, stdout, stderr, run.timed_out, overflow,
                    "compiler_identity_changed", 1, 1)
            # Returning from this block still closes/removes the workspace.
            return _normalize(checked, result, inputs, admitted_scope, measured)
    except CompileValidationError:
        raise
    except OSError as exc:
        _fail("compile_evidence_incomplete", "diagnostic workspace unavailable: " + type(exc).__name__)
    finally:
        _finish_timing(measured, began)


def _authority_gate(value):
    if type(value) is dict:
        for key, item in value.items():
            if key in _AUTHORITIES and item is not False:
                _fail("compile_receipt_authority_escalation", key)
            _authority_gate(item)
    elif type(value) in {list, tuple}:
        for item in value:
            _authority_gate(item)


def validate_structural_compile_receipt(receipt, *, materialized, candidate, admitted_scope,
        repository_root=None, timings=None, **fresh_inputs):
    """Pure canonical reconstruction detects altered inputs, lineage and authority.

    Supplying a root selects fresh exact read-only acquisition, never execution.
    A provider result is evidence rather than a signed attestation: this gate
    verifies its closed identity and canonical bindings without rerunning javac.
    """
    measured, began = _timings(timings), perf_counter()
    try:
        payload = receipt.as_dict() if type(receipt) is StructuralCompileValidationReceipt else receipt
        if type(payload) is not dict:
            _fail("compile_receipt_invalid", "closed receipt required")
        _authority_gate(payload)
        if len(_json(payload).encode("utf-8")) > 2_000_000:
            _fail("compile_receipt_invalid", "canonical receipt bound")
        checked, inputs = _gate(materialized, candidate, admitted_scope, fresh_inputs, repository_root, measured)
        record = dict(payload["compiler_result"])
        if record["compiler"] is not None:
            record["compiler"] = JavacIdentity(**record["compiler"])
        result = CompilerResult(**record)
        rebuilt = _normalize(checked, result, inputs, admitted_scope, measured)
        if _json(payload) != _json(rebuilt.as_dict()):
            _fail("compile_receipt_stale", "canonical content, lineage, fingerprint or authority differs")
        return rebuilt
    except CompileValidationError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        _fail("compile_receipt_invalid", "invalid canonical receipt")
    finally:
        _finish_timing(measured, began)
