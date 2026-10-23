"""PATCH.SCOPE.ADMIT.1: deterministic narrowing, never author or write authority.

Acquisition measures only named paths. The admission and future-author validators
are pure: callers must supply newly acquired repository evidence and fresh typed
PLAN/APPROVE inputs. Historical evidence alone is never a freshness guarantee.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import stat
from time import perf_counter

from pathspec import PathSpec
from core.repo_ignore import RepoIgnorePolicy, REPO_IGNORE_POLICY_VERSION
from core.repository_identity import (
    canonicalize_repository_root, derive_repository_id_from_canonical_root,
)
from core.repository_path_policy import is_safe_repository_relative_path
from core.source_file_policy import SUPPORTED_EXTENSIONS
from core.structural_implementation_plan import (
    CapabilityCoverage, DeclarationBinding, ImplementationDecision, PlannedDefinition,
    PlanTargetIdentity, StructuralImplementationPlan, ValidationEvidenceNeed, PlanError, declaration_bindings,
    validate_structural_implementation_plan,
)
from core.structural_scope_expansion import scope_fingerprint

PHASE_ID = "PATCH.SCOPE.ADMIT.1"
SCHEMA_VERSION = "patch_scope_admit_1_v1"
TIMING_FIELDS = ("plan_revalidation_seconds", "path_policy_validation_seconds",
    "source_declaration_freshness_seconds", "logical_physical_admission_seconds",
    "structural_minimality_seconds", "admission_fingerprint_seconds", "total_seconds")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode()).hexdigest()


class AdmissionError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise AdmissionError(code, reason)


def _immutable(value):
    if value is None or type(value) in {str, int, bool, float}:
        return
    if type(value) is tuple:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for descriptor in fields(value):
            _immutable(getattr(value, descriptor.name))
    else:
        _fail("admission_outside_validated_plan", "mutable authority/evidence field")


def _path(path):
    if (type(path) is not str or not is_safe_repository_relative_path(path)
            or PurePosixPath(path).suffix not in SUPPORTED_EXTENSIONS
            or PurePosixPath(path).suffix != ".java"):
        _fail("admission_outside_repository_policy", "unsafe or unsupported exact target")


def _pairs(inputs):
    return ((inputs["current_context"], inputs["current_source"]), *inputs.get("related_contexts", ()))


def _paths(plan, inputs):
    return tuple(sorted({c.file for c, _ in _pairs(inputs)} | {
        m.proposed_physical_target for m in (*plan.planner_proposal.logical_creations,
                                           *plan.planner_proposal.existing_modifications)}))


@dataclass(frozen=True, slots=True)
class PathWitness:
    path: str
    resolved_relative_path: str
    state: str
    source_fingerprint: str | None
    ancestors: tuple[tuple[str, str, str], ...]

    def __post_init__(self):
        _immutable(self)

    @property
    def fingerprint(self):
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class RepositoryAdmissionEvidence:
    canonical_root: str
    repository_id: str
    policy_sources: tuple[tuple[str, str | None], ...]
    paths: tuple[PathWitness, ...]
    policy_version: str = field(default=REPO_IGNORE_POLICY_VERSION, init=False)

    def __post_init__(self):
        _immutable(self)

    @property
    def fingerprint(self):
        return _hash(asdict(self))


def acquire_structural_admission_evidence(plan, *, repository_root, **inputs):
    """Read/stat exact known targets and two policy files; no inventory or walk.

    This is the only I/O seam. It never writes. The pure consumers check every
    measured fact against PLAN and source buffers; acquisition is not approval.
    """
    if type(plan) is not StructuralImplementationPlan:
        _fail("admission_stale", "typed validated plan required for acquisition")
    try:
        root = Path(canonicalize_repository_root(repository_root))
        policies = []
        for name in (".gitignore", ".cattusignore"):
            policy_path = root / name
            resolved = policy_path.resolve()
            if not resolved.is_relative_to(root):
                _fail("admission_outside_repository_policy", "policy symlink escape")
            try:
                policy_path.lstat()
            except FileNotFoundError:
                policies.append((name, None))
            else:
                policies.append((name, policy_path.read_bytes().decode("utf-8")))
        witnesses = []
        for path in _paths(plan, inputs):
            _path(path)
            ancestors = []
            components = PurePosixPath(path).parts
            for index in range(1, len(components) + 1):
                relative = "/".join(components[:index])
                candidate = root / relative
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root):
                    _fail("admission_outside_repository_policy", "symlink escape")
                try:
                    mode = candidate.lstat().st_mode
                except FileNotFoundError:
                    state = "absent"
                else:
                    # A dangling symlink occupies a path even when exists() is false.
                    if stat.S_ISLNK(mode) and not candidate.exists():
                        state = "occupied"
                    elif candidate.is_dir():
                        state = "directory"
                    elif candidate.is_file():
                        state = "file"
                    else:
                        state = "occupied"
                actual = resolved.relative_to(root).as_posix()
                if index < len(components):
                    if state not in {"absent", "directory"}:
                        _fail("admission_outside_repository_policy", "non-directory ancestor")
                    ancestors.append((relative, actual, state))
                else:
                    digest = sha256(candidate.read_bytes()).hexdigest() if state == "file" else None
                    witnesses.append(PathWitness(path, actual, state, digest, tuple(ancestors)))
        return RepositoryAdmissionEvidence(str(root), derive_repository_id_from_canonical_root(str(root)),
                                           tuple(policies), tuple(witnesses))
    except AdmissionError:
        raise
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        _fail("scope_evidence_incomplete", type(exc).__name__)


def _policy(evidence, paths):
    if (type(evidence) is not RepositoryAdmissionEvidence
            or type(evidence.paths) is not tuple or len(evidence.paths) != len(paths)
            or any(type(p) is not PathWitness for p in evidence.paths)
            or tuple(p.path for p in evidence.paths) != paths
            or evidence.policy_version != REPO_IGNORE_POLICY_VERSION
            or type(evidence.policy_sources) is not tuple
            or len(evidence.policy_sources) != 2):
        _fail("scope_evidence_incomplete", "closed typed exact-path evidence required")
    root = Path(evidence.canonical_root)
    if (not root.is_absolute() or str(root) != evidence.canonical_root
            or evidence.repository_id != derive_repository_id_from_canonical_root(str(root))):
        _fail("admission_stale", "repository identity mismatch")
    specs = []
    for row, expected in zip(evidence.policy_sources, (".gitignore", ".cattusignore")):
        if (type(row) is not tuple or len(row) != 2 or row[0] != expected
                or (row[1] is not None and type(row[1]) is not str)):
            _fail("scope_evidence_incomplete", "exact policy buffers required")
        specs.append(PathSpec.from_lines("gitwildmatch", (row[1] or "").splitlines()))
    policy = RepoIgnorePolicy(root, *specs)
    for witness in evidence.paths:
        _path(witness.path)
        _path(witness.resolved_relative_path)
        prefixes = tuple("/".join(PurePosixPath(witness.path).parts[:i])
                         for i in range(1, len(PurePosixPath(witness.path).parts)))
        if (type(witness.ancestors) is not tuple or len(witness.ancestors) != len(prefixes)
                or witness.state not in {"absent", "file", "directory", "occupied"}
                or ((witness.state == "file") != (type(witness.source_fingerprint) is str))):
            _fail("scope_evidence_incomplete", "exact path state required")
        candidates = [(witness.path, False), (witness.resolved_relative_path, False)]
        for row, prefix in zip(witness.ancestors, prefixes):
            if (type(row) is not tuple or len(row) != 3 or row[0] != prefix
                    or row[2] not in {"absent", "directory"}
                    or not is_safe_repository_relative_path(row[1])):
                _fail("scope_evidence_incomplete", "exact ancestor witness required")
            candidates.extend(((row[0], True), (row[1], True)))
        for relative, is_dir in candidates:
            decision = policy.classify(Path(relative), is_dir=is_dir)
            if decision.ignored:
                _fail("admission_outside_repository_policy", decision.source or "ignored target")
    return {p.path: p for p in evidence.paths}


@dataclass(frozen=True, slots=True)
class ClassBodyBoundary:
    declaration: DeclarationBinding
    body_span: tuple[int, int]
    body_fingerprint: str


@dataclass(frozen=True, slots=True)
class DefinitionAllowance:
    approved_target: PlanTargetIdentity
    physical_target: str
    physical_layout: str
    definition: PlannedDefinition


@dataclass(frozen=True, slots=True)
class StructuralOperation:
    operation: str
    physical_target: str
    owner: str
    approved_targets: tuple[PlanTargetIdentity, ...]
    definition_ids: tuple[str, ...]
    class_body: ClassBodyBoundary | None
    existing_declaration: DeclarationBinding | None
    declaration_byte_span: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class NewFileAuthoringTarget:
    physical_target: str
    owner: str
    package_name: str
    definition_ids: tuple[str, ...]
    absence_witness: PathWitness
    candidate_may_propose_new_file: bool = field(default=True, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class ReadOnlySupportingTarget:
    declaration: DeclarationBinding
    authority: str = field(default="read_only_support", init=False)


@dataclass(frozen=True, slots=True)
class AdmittedStructuralAuthoringScope:
    task_fingerprint: str
    effective_design_fingerprint: str
    p1_fingerprint: str
    approval_receipt_fingerprint: str
    approved_ceiling_fingerprint: str
    implementation_plan_fingerprint: str
    repository_id: str
    repository_evidence_fingerprint: str
    source_bindings: tuple[tuple[str, str, str, str], ...]
    current_scope_fingerprint: str
    current_repair_scope_fingerprint: str
    existing_file_authoring_targets: tuple[StructuralOperation, ...]
    new_file_creation_targets: tuple[NewFileAuthoringTarget, ...]
    definition_allowances: tuple[DefinitionAllowance, ...]
    permitted_structural_operations: tuple[StructuralOperation, ...]
    read_only_supporting_targets: tuple[ReadOnlySupportingTarget, ...]
    validation_evidence_needs: tuple[ValidationEvidenceNeed, ...]
    semantic_commitments: tuple[tuple[str, str], ...]
    capability_coverage: tuple[CapabilityCoverage, ...]
    implementation_decisions: tuple[ImplementationDecision, ...]
    savings_credit_guard: str
    inherited_balance_access: str
    base_saving_action: str
    common_savings_contract: bool
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    status: str = field(default="admitted_candidate_authoring_scope", init=False)
    scope_authority: str = field(default="candidate_authoring_only", init=False)
    candidate_authoring_allowed: bool = field(default=True, init=False)
    write_authority: bool = field(default=False, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_delta: int = field(default=0, init=False)
    authoring_scope_delta: int = field(default=0, init=False)
    candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)

    def __post_init__(self):
        _immutable(self)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "admission_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _source_structure(inputs):
    """Parse supplied Java buffers, never generate source or choose definitions."""
    from tree_sitter_language_pack import get_parser
    inventory = declaration_bindings(inputs)
    structures = {}
    for context, raw in _pairs(inputs):
        tree = get_parser("java").parse(raw)
        if tree.root_node.has_error:
            _fail("scope_evidence_incomplete", "source parse is incomplete")
        packages = [n for n in tree.root_node.named_children if n.type == "package_declaration"]
        if len(packages) > 1:
            _fail("scope_evidence_incomplete", "ambiguous package evidence")
        package = ""
        if packages:
            names = [n for n in packages[0].named_children if n.type in {"identifier", "scoped_identifier"}]
            if len(names) != 1:
                _fail("scope_evidence_incomplete", "package evidence missing")
            package = raw[names[0].start_byte:names[0].end_byte].decode()
        identity = context.class_identity
        nodes = [tree.root_node]
        matches = []
        while nodes:
            node = nodes.pop()
            if (node.type == "class_declaration" and node.start_byte == identity.span.start
                    and node.end_byte == identity.span.end):
                matches.append(node)
            # This is a bounded in-memory syntax tree, not a repository traversal.
            nodes.extend(node.named_children)
        if len(matches) != 1:
            _fail("scope_evidence_incomplete", "exact class body missing")
        body = matches[0].child_by_field_name("body")
        if body is None:
            _fail("scope_evidence_incomplete", "class body missing")
        binding = next(b for b in inventory if (b.file, b.owner, b.kind) ==
                       (context.file, identity.name, "class"))
        structures[(context.file, identity.name)] = (context, raw, package,
            ClassBodyBoundary(binding, (body.start_byte, body.end_byte),
                              sha256(raw[body.start_byte:body.end_byte]).hexdigest()))
    return structures


def _package_for_new(mapping, structures):
    parents = [row for (file, owner), row in structures.items() if owner == mapping.approved_target.parent]
    if len(parents) != 1:
        _fail("scope_evidence_incomplete", "exact parent/package evidence required")
    context, _, package, _ = parents[0]
    source_dir = PurePosixPath(context.file).parent
    # The acquired parent's package directory establishes this source root.
    package_parts = tuple(package.split(".")) if package else ()
    if package_parts and tuple(source_dir.parts[-len(package_parts):]) != package_parts:
        _fail("scope_evidence_incomplete", "source package/directory correspondence unknown")
    if PurePosixPath(mapping.proposed_physical_target).parent != source_dir:
        _fail("scope_evidence_incomplete", "proposed directory has no exact package evidence")
    return package


def _project(plan, witnesses, structures):
    proposal = plan.planner_proposal
    mappings = (*proposal.logical_creations, *proposal.existing_modifications)
    allowances, operations, new_files = [], [], []
    groups = {}
    for mapping in mappings:
        target, path = mapping.approved_target, mapping.proposed_physical_target
        for definition in mapping.definitions:
            allowances.append(DefinitionAllowance(target, path, mapping.physical_layout, definition))
            if (definition.kind == "class" and definition.visibility == "public"
                    and mapping.physical_layout == "top_level"
                    and PurePosixPath(path).name != definition.name + ".java"):
                _fail("scope_evidence_incomplete", "public Java class filename mismatch")
        if mapping in proposal.logical_creations:
            key = (path, target.owner, mapping.proposed_new_file, mapping.physical_layout)
            groups.setdefault(key, []).append(mapping)
            continue
        key = (path, target.owner)
        if key not in structures:
            _fail("scope_evidence_incomplete", "exact existing owner required")
        context, _, _, body = structures[key]
        ids = tuple(sorted(d.identity for d in mapping.definitions))
        if mapping.action == "add_internal_capability":
            operations.append(StructuralOperation("insert_member", path, target.owner, (target,), ids,
                                                  body, None, None))
        else:
            for declaration in mapping.existing_declarations:
                members = (context.methods if declaration.kind == "method" else context.fields
                           if declaration.kind == "field" else context.explicit_constructors
                           if declaration.kind == "constructor" else ())
                exact = [m for m in members if m.name == declaration.name and
                         (m.span.start_line, m.span.end_line) == declaration.member_span]
                if len(exact) != 1:
                    _fail("scope_evidence_incomplete", "exact declaration boundary required")
                definition_ids = tuple(sorted(d.identity for d in mapping.definitions
                                             if (d.kind, d.name) == (declaration.kind, declaration.name)))
                operations.append(StructuralOperation("remove_declaration" if mapping.action == "remove"
                    else "modify_declaration", path, target.owner, (target,), definition_ids, None,
                    declaration, (exact[0].span.start, exact[0].span.end)))
    for (path, owner, new, layout), group in sorted(groups.items()):
        ids = tuple(sorted(d.identity for m in group for d in m.definitions))
        targets = tuple(sorted((m.approved_target for m in group), key=lambda t: t.target))
        class_mapping = next((m for m in group if m.approved_target.kind == "new_class"), None)
        if class_mapping is None:
            _fail("admission_outside_validated_plan", "logical definitions lack a planned class")
        if new:
            witness = witnesses[path]
            if witness.state != "absent":
                _fail("admission_conflict_existing_path", path)
            package = _package_for_new(class_mapping, structures)
            new_files.append(NewFileAuthoringTarget(path, owner, package, ids, witness))
            operations.append(StructuralOperation("draft_new_file", path, owner, targets, ids, None, None, None))
        else:
            parent = class_mapping.approved_target.parent
            if layout != "nested_in_parent" or (path, parent) not in structures:
                _fail("scope_evidence_incomplete", "exact nested parent required")
            operations.append(StructuralOperation("insert_nested_class", path, parent, targets, ids,
                                                  structures[(path, parent)][3], None, None))
    return (tuple(sorted(allowances, key=lambda a: a.definition.identity)),
            tuple(sorted(operations, key=lambda o: _json(asdict(o)))), tuple(new_files))


def admit_structural_authoring_scope(plan, *, approval_receipt, stored_human_action,
        repository_evidence, timings=None, **inputs):
    """Pure narrowing of one fully reconstructed plan against fresh evidence."""
    measured = {} if timings is None else timings
    measured.update({k: 0.0 for k in TIMING_FIELDS})
    started = perf_counter()
    try:
        tick = perf_counter()
        try:
            checked = validate_structural_implementation_plan(plan, approval_receipt=approval_receipt,
                stored_human_action=stored_human_action, **inputs)
        except PlanError as exc:
            code = ("reacquisition_required" if exc.code == "reacquisition_required" else
                    "admission_unavailable" if exc.code == "planning_unavailable" else "admission_stale")
            _fail(code, exc.code)
        finally:
            measured["plan_revalidation_seconds"] = perf_counter() - tick
        if checked.current_scope_fingerprint != scope_fingerprint(inputs.get("current_scope")):
            _fail("admission_stale", "current actual scope changed")
        tick = perf_counter()
        witnesses = _policy(repository_evidence, _paths(checked, inputs))
        if repository_evidence.repository_id != checked.repository_id:
            _fail("admission_stale", "repository mismatch")
        measured["path_policy_validation_seconds"] = perf_counter() - tick
        tick = perf_counter()
        for context, raw in _pairs(inputs):
            witness = witnesses[context.file]
            if witness.state != "file" or witness.source_fingerprint != sha256(raw).hexdigest():
                _fail("reacquisition_required", "measured source changed")
        structures = _source_structure(inputs)
        measured["source_declaration_freshness_seconds"] = perf_counter() - tick
        tick = perf_counter()
        allowances, operations, new_files = _project(checked, witnesses, structures)
        # Relevant acquired declarations and source-proven capability mechanisms
        # remain read-only. A declaration selected for removal/modification is
        # kept only in its exact edit operation, never in the support collection.
        edited = {o.existing_declaration for o in operations if o.existing_declaration}
        required_owners = {a.definition.owner for a in allowances} | {
            m.approved_target.parent for m in checked.planner_proposal.logical_creations}
        support = tuple(ReadOnlySupportingTarget(d) for d in declaration_bindings(inputs)
                        if d.owner in required_owners and d not in edited)
        measured["logical_physical_admission_seconds"] = perf_counter() - tick
        tick = perf_counter()
        expected_definitions = {d.identity for m in (*checked.planner_proposal.logical_creations,
            *checked.planner_proposal.existing_modifications) for d in m.definitions}
        if ({a.definition.identity for a in allowances} != expected_definitions
                or {ref for o in operations for ref in o.definition_ids} != expected_definitions
                or {t for o in operations for t in o.approved_targets} !=
                    set(checked.planner_proposal.selected_targets)):
            _fail("admission_scope_nonminimal", "exact plan realization required")
        measured["structural_minimality_seconds"] = perf_counter() - tick
        tick = perf_counter()
        result = AdmittedStructuralAuthoringScope(checked.task_fingerprint, checked.effective_design_fingerprint,
            checked.p1_fingerprint, checked.approval_receipt_fingerprint, checked.approved_ceiling_fingerprint,
            checked.fingerprint, checked.repository_id, repository_evidence.fingerprint, checked.source_bindings,
            checked.current_scope_fingerprint, checked.current_repair_scope_fingerprint,
            tuple(o for o in operations if o.operation != "draft_new_file"), new_files, allowances, operations,
            support, checked.planner_proposal.required_validation, checked.planner_proposal.semantic_commitments,
            checked.planner_proposal.capability_coverage, checked.planner_proposal.implementation_decisions,
            checked.planner_proposal.savings_credit_guard, checked.planner_proposal.inherited_balance_access,
            checked.planner_proposal.base_saving_action, checked.planner_proposal.common_savings_contract)
        result.fingerprint
        measured["admission_fingerprint_seconds"] = perf_counter() - tick
        return result
    except AdmissionError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration) as exc:
        _fail("scope_evidence_incomplete", type(exc).__name__)
    finally:
        measured["total_seconds"] = perf_counter() - started


def validate_admitted_structural_authoring_scope(scope, *, plan, approval_receipt,
        stored_human_action, repository_evidence, **inputs):
    """Pure future-author gate. Use newly measured evidence, never UI labels.

    Reconstruction checks definition subset, exact edit operations, absence,
    source freshness, full canonical scope identity and approval lineage.
    """
    payload = scope.as_dict() if type(scope) is AdmittedStructuralAuthoringScope else scope
    if type(payload) is not dict:
        _fail("admission_outside_validated_plan", "closed scope required")
    def authorities(value):
        if type(value) is dict:
            for key, item in value.items():
                if key in {"write_authority", "execution_authorized", "apply_authority", "auto_apply",
                           "filesystem_file_creation_authority", "test_write_authority"} and item is not False:
                    _fail("admission_authority_escalation", key)
                authorities(item)
        elif type(value) is list:
            for item in value:
                authorities(item)
    authorities(payload)
    expected = admit_structural_authoring_scope(plan, approval_receipt=approval_receipt,
        stored_human_action=stored_human_action, repository_evidence=repository_evidence, **inputs)
    exact = expected.as_dict()
    if any(payload.get(k) != exact[k] for k in ("implementation_plan_fingerprint", "task_fingerprint",
        "effective_design_fingerprint", "p1_fingerprint", "approval_receipt_fingerprint",
        "approved_ceiling_fingerprint", "repository_id", "repository_evidence_fingerprint",
        "source_bindings", "current_scope_fingerprint", "current_repair_scope_fingerprint")):
        _fail("admission_stale", "admission lineage/freshness changed")
    if payload.get("definition_allowances") != exact["definition_allowances"]:
        _fail("admission_outside_validated_plan", "unplanned definition or physical identity")
    if any(payload.get(k) != exact[k] for k in ("existing_file_authoring_targets",
            "permitted_structural_operations", "new_file_creation_targets")):
        _fail("admission_scope_nonminimal", "exact structural operations required")
    if _json(payload) != _json(exact):
        _fail("admission_outside_validated_plan", "canonical scope/fingerprint mismatch")
    return expected
