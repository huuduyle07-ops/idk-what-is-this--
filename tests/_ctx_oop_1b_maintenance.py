"""Remove CTX.OOP.1B additive seams before older frozen receipts."""
from __future__ import annotations


def _once(data: bytes, after: bytes, before: bytes = b"") -> bytes:
    assert data.count(after) == 1, "non-unique CTX.OOP.1B reversal"
    return data.replace(after, before, 1)


def _section(data: bytes, start: bytes, end: bytes, before: bytes = b"") -> bytes:
    assert data.count(start) == data.count(end) == 1, "non-unique CTX.OOP.1B section"
    left = data.index(start)
    right = data.index(end, left)
    return data[:left] + before + data[right:]


def before_ctx_oop_1b(relative: str, content: bytes) -> bytes:
    if relative == "core/control_engine.py":
        data = _section(content, b'    context, source, source_raw = (None, "", b"")\n',
                        b'    repair = None\n',
                        b'    context, source = (None, "")\n'
                        b'    if repo_path and path and symbol:\n'
                        b'        context, source = load_authoritative_binding_context(\n'
                        b'            repo_root=repo_path, source_path=path, target_symbol=symbol,\n'
                        b'        )\n')
        data = _section(data, b'    oop_projection = oop_target = None\n',
                        b'    return CandidateAuthoringContext(\n')
        data = _once(data,
                     b'        oop_projection=oop_projection, oop_target=oop_target,\n'
                     b'        oop_source_bytes=source_raw,\n')
        data = _once(data,
                     b'    current_binding, current_source, current_raw = authoring_context.source_inputs(repo_path)\n',
                     b'    current_binding, current_source = authoring_context.binding_inputs(repo_path)\n')
        data = _once(data, b'        current_binding, current_source, current_raw = None, "", b""\n',
                     b'        current_binding, current_source = None, ""\n')
        data = _once(data,
                     b'    oop_attachment = replace(authoring_context, authoritative_source=current_source,\n'
                     b'                             oop_source_bytes=current_raw).oop_attachment\n')
        return _once(data, b'{repair_scope_prompt}\n\n{oop_attachment.prompt}\n\n[RELATED CONTEXT',
                     b'{repair_scope_prompt}\n\n[RELATED CONTEXT')
    if relative == "core/candidate_authoring_context.py":
        data = _once(content, b'    from core.class_semantic_context import ClassSemanticContext\n')
        data = _section(data, b'def load_java_authoring_source(', b'@dataclass(frozen=True, slots=True)\n')
        data = _once(data,
                     b'    oop_projection: ClassSemanticContext | None = None\n'
                     b'    oop_target: tuple[str, str, int, int] | None = None\n'
                     b'    oop_source_bytes: bytes = b""\n')
        original_binding = (
            b'    def binding_inputs(self, repo_path: str | Path | None) -> tuple[AuthoritativeBindingContext | None, str]:\n'
            b'        """Revalidate the same baseline proof; never rebuild it from a candidate."""\n'
            b'\n'
            b'        context = self.binding_context\n'
            b'        if context is None or not repo_path:\n'
            b'            return None, ""\n'
            b'        root = Path(repo_path).resolve()\n'
            b'        try:\n'
            b'            path = (root / self.source_path).resolve()\n'
            b'            path.relative_to(root)\n'
            b'            source = path.read_text(encoding="utf-8", errors="replace")\n'
            b'        except (OSError, ValueError):\n'
            b'            return None, ""\n'
            b'        if not context.is_current_for(\n'
            b'            authoritative_source=source, source_path=self.source_path,\n'
            b'            target_symbol=self.target_symbol, target_snippet=self.source_snippet,\n'
            b'        ):\n'
            b'            return None, ""\n'
            b'        return context, source\n'
            b'\n')
        data = _section(data, b'    def source_inputs(',
                        b'    @property\n    def replacement_envelope', original_binding)
        data = _once(data, b'    def as_telemetry(self) -> dict[str, object]:\n'
                          b'        data: dict[str, object] = {\n',
                     b'    def as_telemetry(self) -> dict[str, str]:\n'
                     b'        return {\n')
        data = _once(data,
                     b'        if self.source_path.lower().endswith(".java"):\n'
                     b'            data["oop_attachment_receipt"] = self.oop_attachment.receipt()\n'
                     b'        return data\n')
        data = _once(data, b'            oop_context=self.oop_attachment.prompt,\n')
        return _once(data,
                     b'        return build_revision_prompt(\n'
                     b'            evidence, self.contract, scope_text=self.scope_text,\n',
                     b'        return build_revision_prompt(\r\n'
                     b'            evidence, self.contract, scope_text=self.scope_text,\r\n')
    if relative == "core/candidate_revision.py":
        data = _once(content, b'    authoring_source: str | None = None, oop_context: str = "",\n',
                     b'    authoring_source: str | None = None,\r\n')
        return _once(data, b'        *(["", oop_context] if oop_context else []),\n')
    if relative == "core/pipeline.py":
        return _once(content,
                     b'    current_binding, current_source, current_raw = authoring.source_inputs(state.repo_path)\n'
                     b'    authoring = replace(authoring, binding_context=current_binding,\n'
                     b'                        authoritative_source=current_source, oop_source_bytes=current_raw)\n',
                     b'    current_binding, current_source = authoring.binding_inputs(state.repo_path)\n'
                     b'    authoring = replace(authoring, binding_context=current_binding,\n'
                     b'                        authoritative_source=current_source)\n')
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "CTX.OOP.1B",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        return content[:content.index(marker)] + b'    }' + content[content.index(tail):]
    if relative == "tests/test_phase_registry.py":
        assert content.count(b'len(data["phases"]) == 203') == 1
        assert content.count(b'"CONTROL": 22') == 1
        return content.replace(b'len(data["phases"]) == 203', b'len(data["phases"]) == 202', 1).replace(
            b'"CONTROL": 22', b'"CONTROL": 21', 1)
    if relative == "tests/test_phase_picker.py":
        assert content.count(b'"complete_or_history": 199') == 1
        assert content.count(b'["complete_or_history"] == 199') == 28
        return content.replace(b'"complete_or_history": 199', b'"complete_or_history": 198').replace(
            b'["complete_or_history"] == 199', b'["complete_or_history"] == 198')
    return content
