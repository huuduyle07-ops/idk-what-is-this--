"""CTX.OOP.1A: immutable, read-only class structure from one exact source buffer.

The dispatcher owns no file access, repository discovery, model calls, or edit
authority. Language adapters receive the already-grounded target and bytes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping


MAX_FIELDS = 64
MAX_METHODS = 96
MAX_CONSTRUCTORS = 32
MAX_RELATIONS = 128
MAX_SERIALIZED_BYTES = 48_000
MAX_SOURCE_BYTES = 512_000


@dataclass(frozen=True, slots=True)
class SourceSpan:
    start: int
    end: int
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class ClassIdentity:
    name: str
    qualified_name: str
    kind: str
    span: SourceSpan
    declaration_fingerprint: str
    visibility: str
    is_static: bool
    is_final: bool
    is_abstract: bool
    extends: str | None
    implements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetIdentity:
    name: str
    kind: str
    span: SourceSpan
    owner: str


@dataclass(frozen=True, slots=True)
class FieldSemantic:
    name: str
    declared_type: str
    ownership: str
    visibility: str
    is_final: bool
    span: SourceSpan
    declaration_fingerprint: str


@dataclass(frozen=True, slots=True)
class ParameterSemantic:
    name: str
    declared_type: str


@dataclass(frozen=True, slots=True)
class CallableSemantic:
    name: str
    parameters: tuple[ParameterSemantic, ...]
    return_type: str | None
    visibility: str
    ownership: str
    is_final: bool
    is_abstract: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ClassRelation:
    kind: str
    method_name: str
    method_span: SourceSpan
    field_name: str
    field_span: SourceSpan
    access: str


@dataclass(frozen=True, slots=True)
class ClassSemanticContext:
    language: str
    file: str
    repository_id: str | None
    source_fingerprint: str
    status: str
    read_only: bool = True
    class_identity: ClassIdentity | None = None
    target: TargetIdentity | None = None
    fields: tuple[FieldSemantic, ...] = ()
    methods: tuple[CallableSemantic, ...] = ()
    explicit_constructors: tuple[CallableSemantic, ...] = ()
    relations: tuple[ClassRelation, ...] = ()
    overflow: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def project_class_semantic_context(
    *, raw: bytes, language: str, file: str, target: Mapping[str, Any],
    expected_source_fingerprint: str, repository_id: str | None = None,
) -> ClassSemanticContext:
    """Project one exact, structurally grounded target; never read the filesystem.

    ``target`` uses the ``kind/name/start/end`` fields from
    :func:`core.treesitter_parse.structural_definitions`. The caller must bind
    those offsets to ``raw`` with its SHA-256 fingerprint. A later caller must
    compare that fingerprint to the current source before treating the result
    as current.
    """
    if not isinstance(raw, bytes):
        raise TypeError("raw must be exact source bytes")
    fingerprint = hashlib.sha256(raw).hexdigest()
    language_name = (language or "").lower()
    file_name = str(file or "")
    invalid_identity = (len(language_name) > 64 or len(file_name) > 512
                        or (repository_id is not None and len(repository_id) > 512))
    base = dict(language=language_name[:64], file=file_name[:512],
                repository_id=(repository_id if repository_id is None or len(repository_id) <= 512 else None),
                source_fingerprint=fingerprint)
    if base["language"] != "java":
        return ClassSemanticContext(**base, status="not_supported")
    if (invalid_identity or not file_name or not expected_source_fingerprint
            or expected_source_fingerprint != fingerprint):
        return ClassSemanticContext(**base, status="unavailable")
    if len(raw) > MAX_SOURCE_BYTES:
        return ClassSemanticContext(**base, status="bounded", overflow=("source_bytes",))

    from core.java_class_semantic_context import project_java_class_semantic_context

    try:
        result = project_java_class_semantic_context(raw=raw, target=target, **base)
    except (RecursionError, UnicodeError):
        return ClassSemanticContext(**base, status="unavailable")
    if len(result.to_json().encode("utf-8")) > MAX_SERIALIZED_BYTES:
        bounded = ClassSemanticContext(**base, status="bounded", class_identity=result.class_identity,
                                       target=result.target, overflow=result.overflow + ("serialized_bytes",))
        if len(bounded.to_json().encode("utf-8")) > MAX_SERIALIZED_BYTES:
            return ClassSemanticContext(**base, status="bounded", overflow=("serialized_bytes",))
        return bounded
    return result
