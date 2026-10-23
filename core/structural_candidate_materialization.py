"""PATCH.CANDIDATE.MATERIALIZE.1: exact immutable virtual bytes, never Apply.

The pure seams require newly acquired named evidence, like the frozen AUTHOR
validator. Supplying repository_root selects the read-only acquisition facade;
it discards caller path witnesses and reacquires all named buffers. Neither seam
writes, invokes an author, executes commands, or repairs generated source.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from core.class_semantic_context import MAX_SOURCE_BYTES
from core.structural_java import get_parser, compact, text, children
from core.structural_patch_author import (
    StructuralAuthorError, validate_structural_patch_candidate,
)
from core.structural_scope_admission import (
    AdmissionError, acquire_structural_admission_evidence,
)

PHASE_ID = "PATCH.CANDIDATE.MATERIALIZE.1"
SCHEMA_VERSION = "patch_candidate_materialize_1_v1"
FIRST_REMAINING_BLOCKER = "STRUCTURAL_CANDIDATE_VALIDATION_NOT_IMPLEMENTED"
MAX_FILES = 64
MAX_FILE_BYTES = MAX_SOURCE_BYTES
MAX_TOTAL_BYTES = 2_000_000
MAX_DIFF_BYTES = 2_000_000
TIMING_FIELDS = ("fresh_candidate_revalidation_seconds", "exact_evidence_acquisition_seconds",
    "event_construction_seconds", "byte_composition_seconds", "java_post_parse_seconds",
    "structural_post_check_seconds", "diff_projection_seconds", "fingerprint_construction_seconds",
    "total_deterministic_seconds")


class MaterializationError(ValueError):
    def __init__(self, code, reason=""):
        self.code, self.reason = code, reason or code
        super().__init__(code + (": " + reason if reason else ""))


def _fail(code, reason=""):
    raise MaterializationError(code, reason)


def _conflict(reason):
    _fail("materialization_structural_conflict", reason)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _immutable(value):
    if value is None or type(value) in {str, int, bool, bytes}:
        return
    if type(value) is tuple:
        for item in value:
            _immutable(item)
    elif is_dataclass(value) and value.__dataclass_params__.frozen:
        for item in fields(value):
            _immutable(getattr(value, item.name))
    else:
        _fail("materialization_invalid", "mutable materialization field")


def _source(raw):
    # Frozen acquired Java contexts use UTF-8 byte offsets. Never transcode or
    # guess another encoding; a UTF-8 BOM, if admitted, is an untouched byte.
    if type(raw) is not bytes:
        _fail("materialization_unsupported_source_encoding", "exact UTF-8 bytes required")
    try:
        result = raw.decode("utf-8", errors="strict")
        if b"\x00" in raw or result.encode("utf-8") != raw:
            raise UnicodeError()
        return result
    except UnicodeError:
        _fail("materialization_unsupported_source_encoding", "strict acquired UTF-8 only")


def _newline(raw):
    crlf = raw.count(b"\r\n")
    remainder = raw.replace(b"\r\n", b"")
    if b"\r" in remainder or (crlf and b"\n" in remainder):
        _fail("materialization_unsupported_line_endings", "mixed or bare CR target")
    # A file without newlines has no conflicting convention: deterministic LF.
    return "\r\n" if crlf else "\n"


@dataclass(frozen=True, slots=True)
class ByteEditEvent:
    operation_id: str
    kind: str
    start: int
    end: int
    payload: bytes
    order: int

    def __post_init__(self):
        _immutable(self)
        if (type(self.start) is not int or type(self.end) is not int or type(self.order) is not int
                or self.start < 0 or self.end < self.start or not self.operation_id
                or type(self.payload) is not bytes or self.kind not in {"remove", "insert"}
                or (self.kind == "remove" and (self.start == self.end or self.payload))
                or (self.kind == "insert" and (self.start != self.end or not self.payload))):
            _conflict("invalid original-coordinate event")


@dataclass(frozen=True, slots=True)
class BytePreservationSegment:
    before_start: int
    before_end: int
    after_start: int
    after_end: int
    sha256: str


def _compose(before, events):
    if type(before) is not bytes or type(events) is not tuple or any(type(e) is not ByteEditEvent for e in events):
        _conflict("immutable source/events required")
    if len(events) > 64 or len(before) > MAX_FILE_BYTES:
        _fail("materialization_bounds_exceeded", "source/event bound")
    if len({e.operation_id for e in events}) != len(events):
        _conflict("duplicate event ID")
    removals = sorted((e for e in events if e.kind == "remove"), key=lambda e: e.start)
    for left, right in zip(removals, removals[1:]):
        if left.end > right.start:
            _conflict("overlapping removals")
    seen = set()
    for event in events:
        if event.end > len(before):
            _conflict("event outside exact source")
        if event.kind == "insert":
            if any(r.start <= event.start < r.end for r in removals):
                _conflict("insertion at/inside removed bytes")
            key = (event.start, event.order)
            if key in seen:
                _conflict("ambiguous insertion order")
            seen.add(key)
    projected_size = len(before) - sum(e.end - e.start for e in removals) + sum(len(e.payload) for e in events)
    if projected_size > MAX_FILE_BYTES:
        _fail("materialization_bounds_exceeded", "virtual file byte bound")
    ordered = sorted(events, key=lambda e: (e.start, e.order))
    chunks, proofs, positions = [], [], {}
    cursor, output_size = 0, 0
    for event in ordered:
        if event.start > cursor:
            unchanged = before[cursor:event.start]
            proofs.append(BytePreservationSegment(cursor, event.start, output_size,
                output_size + len(unchanged), sha256(unchanged).hexdigest()))
            chunks.append(unchanged)
            output_size += len(unchanged)
            cursor = event.start
        positions[event.operation_id] = (output_size, output_size + len(event.payload))
        if event.kind == "remove":
            cursor = event.end
        else:
            chunks.append(event.payload)
            output_size += len(event.payload)
    if cursor < len(before):
        unchanged = before[cursor:]
        proofs.append(BytePreservationSegment(cursor, len(before), output_size,
            output_size + len(unchanged), sha256(unchanged).hexdigest()))
        chunks.append(unchanged)
    after = b"".join(chunks)
    for proof in proofs:
        if (before[proof.before_start:proof.before_end] != after[proof.after_start:proof.after_end]
                or sha256(after[proof.after_start:proof.after_end]).hexdigest() != proof.sha256):
            _conflict("byte preservation proof failed")
    if sum(p.before_end - p.before_start for p in proofs) != len(before) - sum(e.end - e.start for e in removals):
        _conflict("incomplete byte preservation coverage")
    return after, tuple(proofs), positions


def compose_byte_events(before, events):
    """Pure one-pass composition, with complete untouched-byte proof."""
    after, proofs, _ = _compose(before, events)
    return after, proofs


@dataclass(frozen=True, slots=True)
class AppliedStructuralOperation:
    operation_id: str
    operation: str
    path: str
    owner: str
    definition_ids: tuple[str, ...]
    order: int
    before_start: int | None
    before_end: int | None
    after_start: int
    after_end: int
    rendered_source: str
    rendered_sha256: str
    canonical_source_sha256: str | None

    @property
    def payload_bytes(self):
        return self.rendered_source.encode("utf-8")

    @property
    def anchor_offset(self):
        return self.before_start if self.operation in {"insert_member", "insert_nested_class"} else None


@dataclass(frozen=True, slots=True)
class VirtualStructuralFile:
    path: str
    before_state: str
    before_sha256: str | None
    after_sha256: str
    before_size: int | None
    after_size: int
    operation_ids: tuple[str, ...]
    after_source: str
    source_bindings: tuple[tuple[str, str, str, str], ...]
    preservation_proof: tuple[BytePreservationSegment, ...]
    encoding: str = field(default="utf-8", init=False)
    physical_write_authority: bool = field(default=False, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)

    @property
    def after_bytes(self):
        return self.after_source.encode("utf-8")


@dataclass(frozen=True, slots=True)
class UnchangedSupportingFile:
    path: str
    source_sha256: str
    source_size: int
    source_bindings: tuple[tuple[str, str, str, str], ...]


@dataclass(frozen=True, slots=True)
class SupportingDeclarationProof:
    path: str
    owner: str
    name: str
    kind: str
    before_span: tuple[int, int]
    preserved_segments: tuple[BytePreservationSegment, ...]
    preserved_sha256: str
    mode: str


@dataclass(frozen=True, slots=True)
class MaterializedStructuralCandidate:
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
    source_bindings: tuple[tuple[str, str, str, str], ...]
    virtual_files: tuple[VirtualStructuralFile, ...]
    applied_operations: tuple[AppliedStructuralOperation, ...]
    supporting_files: tuple[UnchangedSupportingFile, ...]
    supporting_declarations: tuple[SupportingDeclarationProof, ...]
    diff_preview: str
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    status: str = field(default="materialized_structural_candidate", init=False)
    authority: str = field(default="virtual_post_state_only", init=False)
    diff_authority: str = field(default="display_only", init=False)
    encoding_policy: str = field(default="strict_acquired_utf8", init=False)
    line_ending_policy: str = field(default="existing_uniform_LF_or_CRLF; newline_free_LF; new_file_candidate_LF", init=False)
    insertion_policy: str = field(default="before_exact_admitted_class_closing_brace; newline_separators; plan_definition_order", init=False)
    write_authority: bool = field(default=False, init=False)
    filesystem_write_authority: bool = field(default=False, init=False)
    filesystem_file_creation_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    source_mutation: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    first_remaining_blocker: str = field(default=FIRST_REMAINING_BLOCKER, init=False)

    def __post_init__(self):
        _immutable(self)

    @property
    def fingerprint(self):
        return _hash(asdict(self))

    @property
    def materialization_fingerprint(self):
        return self.fingerprint

    def as_dict(self):
        return {**json.loads(_json(asdict(self))), "materialization_fingerprint": self.fingerprint}

    def to_json(self):
        return _json(self.as_dict())


def _pairs(inputs):
    return ((inputs["current_context"], inputs["current_source"]), *inputs.get("related_contexts", ()))


def _sources(inputs):
    result = {}
    for context, raw in _pairs(inputs):
        _source(raw)
        if len(raw) > MAX_FILE_BYTES:
            _fail("materialization_bounds_exceeded", "source byte bound")
        if context.file in result and result[context.file] != raw:
            _fail("reacquisition_required", "conflicting exact source versions")
        if sha256(raw).hexdigest() != context.source_fingerprint:
            _fail("reacquisition_required", "source/context binding differs")
        result[context.file] = raw
    if len(result) > MAX_FILES or sum(map(len, result.values())) > MAX_TOTAL_BYTES:
        _fail("materialization_bounds_exceeded", "named evidence bound")
    return result


def _fresh_inputs(inputs, repository_root, measured):
    tick = perf_counter()
    try:
        result = dict(inputs)
        _sources(result)
        if repository_root is None:
            return result
        result.pop("repository_evidence", None)
        evidence = acquire_structural_admission_evidence(result["plan"], repository_root=repository_root,
            **{k: v for k, v in result.items() if k != "plan"})
        root = Path(evidence.canonical_root)
        witnesses = {w.path: w for w in evidence.paths}
        acquired = {}
        for context, old_raw in _pairs(result):
            witness = witnesses[context.file]
            if witness.state != "file":
                _fail("reacquisition_required", "named source disappeared")
            if context.file not in acquired:
                with (root / witness.path).open("rb") as stream:
                    raw = stream.read(MAX_FILE_BYTES + 1)
                _source(raw)
                if len(raw) > MAX_FILE_BYTES:
                    _fail("materialization_bounds_exceeded", "source acquisition bound")
                acquired[context.file] = raw
            raw = acquired[context.file]
            if raw != old_raw or sha256(raw).hexdigest() != witness.source_fingerprint:
                _fail("reacquisition_required", "named source changed during acquisition")
        result["current_source"] = acquired[result["current_context"].file]
        result["related_contexts"] = tuple((c, acquired[c.file]) for c, _ in result.get("related_contexts", ()))
        result["repository_evidence"] = evidence
        return result
    finally:
        measured["exact_evidence_acquisition_seconds"] += perf_counter() - tick


def _absence(scope, evidence):
    witnesses = {w.path: w for w in evidence.paths}
    for target in scope.new_file_creation_targets:
        if target.physical_target not in witnesses or witnesses[target.physical_target].state != "absent":
            _fail("materialization_conflict_existing_path", target.physical_target)


def _operation_key(operation):
    return operation.operation, operation.physical_target, operation.owner, operation.definition_ids


def _events(candidate, scope, inputs, sources):
    # PLAN's canonical definition ordering, never candidate JSON transport order.
    plan = inputs["plan"].planner_proposal
    ids = [d.identity for m in (*plan.logical_creations, *plan.existing_modifications) for d in m.definitions]
    index = {identity: position for position, identity in enumerate(ids)}
    admitted = {_operation_key(o): o for o in scope.permitted_structural_operations}
    ordered = sorted(candidate.operations, key=lambda o: (min((index[i] for i in o.definition_ids), default=len(ids)),
        tuple(index[i] for i in o.definition_ids), _operation_key(o)))
    events, drafts, rows = {}, {}, []
    for order, operation in enumerate(ordered):
        target = admitted[_operation_key(operation)]
        path = operation.physical_target
        operation_id = _hash({"admission": scope.fingerprint, "operation": asdict(target)})
        raw_source = None if operation.source_text is None else operation.source_text.encode("utf-8")
        if raw_source is not None and b"\r" in raw_source:
            _conflict("candidate source must retain frozen canonical LF")
        if operation.operation == "draft_new_file":
            if path in drafts or path in events or path in sources:
                _conflict("duplicate/conflicting new-file target")
            drafts[path] = raw_source
            rows.append((operation_id, operation, order, None, raw_source))
            continue
        if path not in sources or path in drafts:
            _conflict("missing/conflicting existing target")
        before = sources[path]
        if operation.operation == "remove_declaration":
            if target.existing_declaration != operation.existing_declaration or target.declaration_byte_span is None:
                _conflict("missing admission-owned removal span")
            start, end = target.declaration_byte_span
            event = ByteEditEvent(operation_id, "remove", start, end, b"", order)
        else:
            body = target.class_body
            if body is None:
                _conflict("missing admission-owned class container")
            start, end = body.body_span
            if (not 0 <= start < end <= len(before) or before[start:start + 1] != b"{"
                    or before[end - 1:end] != b"}" or sha256(before[start:end]).hexdigest() != body.body_fingerprint):
                _fail("reacquisition_required", "exact class container differs")
            newline = _newline(before)
            rendered = (newline + operation.source_text.replace("\n", newline) + newline).encode("utf-8")
            event = ByteEditEvent(operation_id, "insert", end - 1, end - 1, rendered, order)
        events.setdefault(path, []).append(event)
        rows.append((operation_id, operation, order, event, raw_source))
    return {p: tuple(e) for p, e in events.items()}, drafts, tuple(rows)


def _parse(raw):
    tree = get_parser("java").parse(raw)
    if tree.root_node.has_error:
        _conflict("composed Java syntax incomplete")
    return tree


def _inventory(root, raw, owner=""):
    """Definition identities and exact declaration bytes, including neighbors.

    Java callable identity ignores parameter names and return type; both are
    still preserved through exact declaration bytes and frozen AUTHOR checks.
    """
    result = []
    classes = {"class_declaration", "interface_declaration", "enum_declaration",
               "record_declaration", "annotation_type_declaration"}
    def visit(node, parent, local_path=()):
        kind = node.type
        if kind in classes:
            name = text(node.child_by_field_name("name"), raw)
            if local_path:
                parent += "::@scope:" + ".".join(map(str, local_path))
            result.append(((parent, kind, name, ()), node.start_byte, node.end_byte))
            for child in node.named_children:
                visit(child, parent + "::" + name if parent else name)
            return
        if kind in {"method_declaration", "constructor_declaration", "compact_constructor_declaration"}:
            params = node.child_by_field_name("parameters")
            def parameter_type(parameter):
                dtype = parameter.child_by_field_name("type")
                if dtype is None and parameter.type == "spread_parameter":
                    dtype = next((n for n in parameter.named_children if n.type != "variable_declarator"), None)
                dimensions = compact(parameter.child_by_field_name("dimensions"), raw)
                declarator = next((n for n in parameter.named_children if n.type == "variable_declarator"), None)
                if declarator is not None:
                    dimensions += compact(declarator.child_by_field_name("dimensions"), raw)
                # Varargs and an array of the same element type collide in Java.
                return compact(dtype, raw) + dimensions + ("[]" if parameter.type == "spread_parameter" else "")
            types = tuple(parameter_type(p) for p in children(params)) if params else ()
            name = text(node.child_by_field_name("name"), raw)
            result.append(((parent, kind, name, types), node.start_byte, node.end_byte))
            # Local classes in different executable/block scopes may legally
            # share a name. Their unchanged syntax paths are stable even when
            # another class member is removed or appended.
            local_parent = parent + "::@" + kind + ":" + name + "(" + ",".join(types) + ")"
            for index, child in enumerate(node.named_children):
                visit(child, local_parent, (index,))
            return
        elif kind in {"field_declaration", "constant_declaration"}:
            for declarator in children(node):
                if declarator.type == "variable_declarator":
                    result.append(((parent, kind, text(declarator.child_by_field_name("name"), raw), ()),
                        node.start_byte, node.end_byte))
        elif kind in {"enum_constant", "annotation_type_element_declaration"}:
            result.append(((parent, kind, text(node.child_by_field_name("name"), raw), ()), node.start_byte, node.end_byte))
        for index, child in enumerate(node.named_children):
            visit(child, parent, (*local_path, index) if local_path else ())
    visit(root, owner)
    return tuple(result)


def _inserted_inventory(operation, rendered_source=None, owner=None):
    if operation.operation == "remove_declaration":
        return ()
    raw = (operation.source_text if rendered_source is None else rendered_source).encode("utf-8")
    if operation.operation == "insert_member":
        raw = ("class " + operation.owner + " {\n").encode() + raw + b"\n}"
        tree = _parse(raw)
        cls = next(n for n in children(tree.root_node) if n.type == "class_declaration")
        inventory = _inventory(cls.child_by_field_name("body"), raw, operation.owner if owner is None else owner)
        return tuple((identity, raw[start:end]) for identity, start, end in inventory)
    inventory = _inventory(_parse(raw).root_node, raw,
        (operation.owner if owner is None else owner) if operation.operation == "insert_nested_class" else "")
    return tuple((identity, raw[start:end]) for identity, start, end in inventory)


def _post_check(before_sources, after_sources, before_trees, after_trees, events, rows, records):
    expected = {p: Counter(item[0] for item in _inventory(tree.root_node, before_sources[p]))
                for p, tree in before_trees.items()}
    for path in after_sources:
        expected.setdefault(path, Counter())
    for path, file_events in events.items():
        inventory = _inventory(before_trees[path].root_node, before_sources[path])
        for event in file_events:
            if event.kind == "remove":
                exact = [record for record in inventory if record[1:3] == (event.start, event.end)]
                if not exact:
                    _conflict("removal does not own an exact parsed declaration")
                for identity, start, end in inventory:
                    if event.start <= start and end <= event.end:
                        expected[path][identity] -= 1
    receipts = {r.operation_id: r for r in records}
    for operation_id, operation, _, event, _ in rows:
        path = operation.physical_target
        owner = None
        if event is not None and event.kind == "insert":
            inventory = _inventory(before_trees[path].root_node, before_sources[path])
            containers = [record for record in inventory if record[0][1] == "class_declaration"
                          and record[1] <= event.start == record[2] - 1]
            if len(containers) != 1:
                _conflict("exact parsed insertion container missing")
            parent, _, name, _ = containers[0][0]
            owner = parent + "::" + name if parent else name
        receipt = receipts[operation_id]
        inserted = _inserted_inventory(operation, receipt.rendered_source, owner)
        expected[path].update(r[0] for r in inserted)
        if operation.operation != "remove_declaration":
            # Prove generated declarations exist exactly as rendered at their
            # composed ranges, beyond checking the aggregate definition census.
            actual = tuple((identity, after_sources[path][start:end]) for identity, start, end in
                _inventory(after_trees[path].root_node, after_sources[path])
                if receipt.after_start <= start and end <= receipt.after_end)
            if Counter(inserted) != Counter(actual):
                _conflict("generated declaration bytes or placement differ")
    for path, tree in after_trees.items():
        actual = Counter(r[0] for r in _inventory(tree.root_node, after_sources[path]))
        if any(count != 1 for count in actual.values()):
            _conflict("duplicate resulting Java definition identity")
        if actual != +expected[path]:
            _conflict("removed/inserted/unplanned definition mismatch")


def _support_proofs(scope, inputs, before_sources, after_sources, files):
    contexts = {(c.file, c.class_identity.name): c for c, _ in _pairs(inputs)}
    proofs = []
    for target in scope.read_only_supporting_targets:
        declaration = target.declaration
        context = contexts[(declaration.file, declaration.owner)]
        members = ((context.class_identity,) if declaration.kind == "class" else context.fields
            if declaration.kind == "field" else context.methods if declaration.kind == "method" else context.explicit_constructors)
        exact = [m for m in members if m.name == declaration.name and
                 (m.span.start_line, m.span.end_line) == declaration.member_span]
        if len(exact) != 1:
            _conflict("support declaration span missing")
        start, end = exact[0].span.start, exact[0].span.end
        path = declaration.file
        before = before_sources[path]
        after = after_sources.get(path, before)
        all_segments = files[path].preservation_proof if path in files else (
            BytePreservationSegment(0, len(before), 0, len(before), sha256(before).hexdigest()),)
        segments = []
        for segment in all_segments:
            left, right = max(start, segment.before_start), min(end, segment.before_end)
            if left < right:
                offset = segment.after_start - segment.before_start
                if before[left:right] != after[left + offset:right + offset]:
                    _conflict("support byte preservation failed")
                segments.append(BytePreservationSegment(left, right, left + offset, right + offset,
                    sha256(before[left:right]).hexdigest()))
        full = sum(s.before_end - s.before_start for s in segments) == end - start
        contiguous = full and all(a.after_end == b.after_start for a, b in zip(segments, segments[1:]))
        if declaration.kind != "class" and not contiguous:
            _conflict("read-only neighboring declaration changed")
        # An edited class is an insertion container: its surviving original
        # bytes, including braces, remain exact. Do not claim its whole span is
        # unchanged when admitted operations occur inside it.
        mode = "exact_declaration" if contiguous else "container_surviving_bytes"
        digest = sha256(b"".join(before[s.before_start:s.before_end] for s in segments)).hexdigest()
        proofs.append(SupportingDeclarationProof(path, declaration.owner, declaration.name,
            declaration.kind, (start, end), tuple(segments), digest, mode))
    return tuple(proofs)


def _diff(files, sources):
    chunks, size = [], 0
    for file in files:
        # /dev/null identifies ABSENT; an empty sequence here is display-only.
        before = _source(sources[file.path]) if file.before_state == "file" else ""
        for line in unified_diff(before.splitlines(keepends=True), file.after_source.splitlines(keepends=True),
                fromfile="a/" + file.path if file.before_state == "file" else "/dev/null",
                tofile="b/" + file.path, lineterm="\n"):
            rendered = line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            size += len(rendered.encode("utf-8"))
            if size > MAX_DIFF_BYTES:
                _fail("materialization_bounds_exceeded", "diff byte bound; no truncation")
            chunks.append(rendered)
    return "".join(chunks)


def _materialize(candidate, scope, inputs, measured):
    sources = _sources(inputs)
    tick = perf_counter()
    events, drafts, rows = _events(candidate, scope, inputs, sources)
    measured["event_construction_seconds"] += perf_counter() - tick
    if len(set(events) | set(drafts)) > MAX_FILES:
        _fail("materialization_bounds_exceeded", "changed file bound")
    tick = perf_counter()
    after, proofs, positions = dict(drafts), {}, {}
    for path, file_events in events.items():
        after[path], proofs[path], locations = _compose(sources[path], file_events)
        positions.update(locations)
    if any(len(raw) > MAX_FILE_BYTES for raw in after.values()) or sum(map(len, after.values())) > MAX_TOTAL_BYTES:
        _fail("materialization_bounds_exceeded", "virtual file-set bound")
    files, records = [], []
    for operation_id, operation, order, event, canonical in rows:
        payload = canonical if event is None else event.payload
        left, right = (0, len(payload)) if event is None else positions[operation_id]
        records.append(AppliedStructuralOperation(operation_id, operation.operation, operation.physical_target,
            operation.owner, operation.definition_ids, order, None if event is None else event.start,
            None if event is None else event.end, left, right, _source(payload), sha256(payload).hexdigest(),
            None if canonical is None else sha256(canonical).hexdigest()))
    for path, raw in sorted(after.items()):
        before = sources.get(path)
        files.append(VirtualStructuralFile(path, "absent" if before is None else "file",
            None if before is None else sha256(before).hexdigest(), sha256(raw).hexdigest(),
            None if before is None else len(before), len(raw), tuple(r.operation_id for r in records if r.path == path),
            _source(raw), tuple(b for b in candidate.source_bindings if b[0] == path), proofs.get(path, ())))
    measured["byte_composition_seconds"] += perf_counter() - tick
    tick = perf_counter()
    before_trees = {p: _parse(sources[p]) for p in events}
    after_trees = {p: _parse(raw) for p, raw in after.items()}
    measured["java_post_parse_seconds"] += perf_counter() - tick
    tick = perf_counter()
    _post_check(sources, after, before_trees, after_trees, events, rows, records)
    support = _support_proofs(scope, inputs, sources, after, {f.path: f for f in files})
    supporting_files = tuple(UnchangedSupportingFile(p, sha256(raw).hexdigest(), len(raw),
        tuple(b for b in candidate.source_bindings if b[0] == p)) for p, raw in sorted(sources.items()) if p not in after)
    measured["structural_post_check_seconds"] += perf_counter() - tick
    tick = perf_counter()
    preview = _diff(files, sources)
    measured["diff_projection_seconds"] += perf_counter() - tick
    tick = perf_counter()
    materialized = MaterializedStructuralCandidate(candidate.fingerprint, candidate.admission_fingerprint,
        candidate.implementation_plan_fingerprint, candidate.task_fingerprint, candidate.effective_design_fingerprint,
        candidate.p1_fingerprint, candidate.approval_receipt_fingerprint, candidate.approved_ceiling_fingerprint,
        candidate.repository_id, candidate.repository_evidence_fingerprint, candidate.source_bindings,
        tuple(files), tuple(records), supporting_files, support, preview)
    materialized.fingerprint
    measured["fingerprint_construction_seconds"] += perf_counter() - tick
    return materialized


def materialize_structural_candidate(candidate, *, admitted_scope, repository_root=None, timings=None, **fresh_inputs):
    """All-or-nothing virtual composition; errors never return partial files.

    With no root this is pure; the caller must acquire evidence immediately
    before invocation. With a root it remeasures named paths/buffers itself,
    including a second path/source check after frozen candidate revalidation.
    """
    measured = {} if timings is None else timings
    measured.update({key: 0.0 for key in TIMING_FIELDS})
    start = perf_counter()
    try:
        inputs = _fresh_inputs(fresh_inputs, repository_root, measured)
        _absence(admitted_scope, inputs["repository_evidence"])
        tick = perf_counter()
        try:
            checked = validate_structural_patch_candidate(candidate, admitted_scope=admitted_scope, **inputs)
        finally:
            measured["fresh_candidate_revalidation_seconds"] += perf_counter() - tick
        if repository_root is not None:
            newer = _fresh_inputs(inputs, repository_root, measured)
            _absence(admitted_scope, newer["repository_evidence"])
            if newer["repository_evidence"] != inputs["repository_evidence"]:
                _fail("reacquisition_required", "path/policy evidence changed during validation")
            inputs = newer
        return _materialize(checked, admitted_scope, inputs, measured)
    except (StructuralAuthorError, AdmissionError) as exc:
        code = "materialization_conflict_existing_path" if exc.code == "admission_conflict_existing_path" else exc.code
        _fail(code, exc.reason)
    except MaterializationError:
        raise
    except OSError as exc:
        _fail("reacquisition_required", type(exc).__name__)
    except (ValueError, TypeError, AttributeError, KeyError, StopIteration, RecursionError) as exc:
        _fail("materialization_invalid", type(exc).__name__)
    finally:
        measured["total_deterministic_seconds"] = perf_counter() - start


def validate_materialized_structural_candidate(materialized, *, candidate, admitted_scope,
        repository_root=None, timings=None, **fresh_inputs):
    """Independently reconstruct exact content, proofs, lineage and authority.

    This pure consumer gate needs fresh caller evidence; repository_root selects
    the same exact read-only acquisition facade as materialization. Historical
    virtual bytes remain immutable even when this gate rejects stale evidence.
    """
    payload = materialized.as_dict() if type(materialized) is MaterializedStructuralCandidate else materialized
    if type(payload) is not dict:
        _fail("materialization_invalid", "closed materialization required")
    def authorities(value):
        if type(value) is dict:
            for key, item in value.items():
                if key in {"write_authority", "filesystem_write_authority", "filesystem_file_creation_authority",
                           "execution_authorized", "apply_authority", "auto_apply", "physical_write_authority"} and item is not False:
                    _fail("materialization_authority_escalation", key)
                authorities(item)
        elif type(value) in {tuple, list}:
            for item in value:
                authorities(item)
    try:
        authorities(payload)
        # Bound hostile serialized claims before constructing canonical JSON.
        if len(_json(payload).encode("utf-8")) > 16_000_000:
            _fail("materialization_bounds_exceeded", "canonical materialization bound")
        rebuilt = materialize_structural_candidate(candidate, admitted_scope=admitted_scope,
            repository_root=repository_root, timings=timings, **fresh_inputs)
        if _json(payload) != _json(rebuilt.as_dict()):
            _fail("materialization_stale", "canonical content, lineage, fingerprint or authority differs")
        return rebuilt
    except MaterializationError:
        raise
    except (ValueError, TypeError, RecursionError):
        _fail("materialization_invalid", "invalid canonical materialization")
