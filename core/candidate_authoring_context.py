"""Bounded author-facing projection of PATCH.MINIMAL's baseline evidence.

No lexical scan, candidate identity, verdict, or implementation advice lives
here. The binding and immutable-record proofs remain owned by PATCH.MINIMAL.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from core.authoritative_binding_context import AuthoritativeBindingContext
from core.patch_authoring_contract import PatchAuthoringContract

if TYPE_CHECKING:
    from core.candidate_revision import CandidateRevisionEvidence
    from core.authoring_repair_scope import AuthoringRepairScope
    from core.class_semantic_context import ClassSemanticContext


PHASE_ID = "PATCH.AUTHOR.LIVE.3"
SCOPE_VERSION = "candidate_authoring_scope_v1"
MAX_SCOPE_BYTES = 16_384


def load_java_authoring_source(repo_path: str | Path, source_path: str) -> tuple[str, bytes]:
    """Read the one named Java authoring file for both target and OOP context."""
    if not source_path.lower().endswith(".java") or not source_path:
        return "", b""
    try:
        root = Path(repo_path).resolve()
        path = (root / source_path).resolve()
        path.relative_to(root)
        raw = path.read_bytes()
        return raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n"), raw
    except (OSError, ValueError):
        return "", b""


@dataclass(frozen=True, slots=True)
class CandidateAuthoringContext:
    contract: PatchAuthoringContract
    source_path: str
    target_symbol: str
    source_snippet: str
    binding_context: AuthoritativeBindingContext | None = None
    authoritative_source: str = ""
    authoring_repair_scope: AuthoringRepairScope | None = None
    oop_projection: ClassSemanticContext | None = None
    oop_target: tuple[str, str, int, int] | None = None
    oop_source_bytes: bytes = b""

    def source_inputs(self, repo_path: str | Path | None) -> tuple[AuthoritativeBindingContext | None, str, bytes]:
        """Revalidate the same baseline proof; never rebuild it from a candidate."""

        context = self.binding_context
        if (context is None and not self.source_path.lower().endswith(".java")) or not repo_path:
            return None, "", b""
        if self.source_path.lower().endswith(".java"):
            source, raw = load_java_authoring_source(repo_path, self.source_path)
            return None, source, raw
        root = Path(repo_path).resolve()
        try:
            path = (root / self.source_path).resolve()
            path.relative_to(root)
            source = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            return None, "", b""
        if not context.is_current_for(
            authoritative_source=source, source_path=self.source_path,
            target_symbol=self.target_symbol, target_snippet=self.source_snippet,
        ):
            return None, "", b""
        return context, source, b""

    def binding_inputs(self, repo_path: str | Path | None) -> tuple[AuthoritativeBindingContext | None, str]:
        context, source, _ = self.source_inputs(repo_path)
        return context, source

    @property
    def oop_attachment(self):
        from core.oop_reasoning_context import OopReasoningAttachment, build_oop_reasoning_context

        if self.oop_projection is None or self.oop_target is None:
            return OopReasoningAttachment(
                "unavailable" if self.source_path.lower().endswith(".java") else "not_supported")
        kind, name, start, end = self.oop_target
        return build_oop_reasoning_context(
            context=self.oop_projection,
            current_source=self.oop_source_bytes,
            target={"kind": kind, "name": name, "start": start, "end": end},
            repair_scope=self.authoring_repair_scope,
        )

    @property
    def replacement_envelope(self) -> dict | None:
        repair = self.authoring_repair_scope
        if repair is None or len(repair.measured.members) < 2:
            return None
        from core.candidate_replacement_span import canonical_replacement_envelope
        return canonical_replacement_envelope(repair)

    @property
    def scope_text(self) -> str:
        if self.authoring_repair_scope is not None and len(self.authoring_repair_scope.measured.members) > 1:
            return "AUTHORITATIVE AUTHORING SCOPE:\n" + json.dumps({
                "version": "candidate_authoring_scope_v3_replacement_envelope",
                "source_path": self.source_path,
                "target_symbol": self.target_symbol,
                "primary_target": {"file": self.source_path, "symbol": self.target_symbol,
                                   "source_snippet": self.source_snippet},
                "replacement_envelope": self.replacement_envelope,
                "authoring_repair_scope": self.authoring_repair_scope.as_dict(),
            }, ensure_ascii=False, sort_keys=True, indent=2)
        if self.authoring_repair_scope is not None:
            self.authoring_repair_scope.assert_current()
        context = self.binding_context
        bindings = []
        current = context is not None and context.is_current_for(
            authoritative_source=self.authoritative_source,
            source_path=self.source_path, target_symbol=self.target_symbol,
            target_snippet=self.source_snippet,
        )
        if current:
            results = {
                item.bound_name: item
                for item in (context.immutable_result_proof.callable_results
                             if context.immutable_result_proof else ())
            }
            for name in sorted(context.known_binding_names):
                kind = context.binding_kind(name)
                item = {"name": name, "kind": kind}
                if kind == "repository_local_direct_import" and name in results:
                    item["result"] = {
                        "kind": "immutable_repository_local_record",
                        "readable_declared_fields": list(results[name].field_names),
                    }
                bindings.append(item)
        data = {
            "version": SCOPE_VERSION,
            "source_path": self.source_path,
            "target_symbol": self.target_symbol,
            "source_sha256": context.source_sha256 if current else "",
            "target_source_sha256": context.target_source_sha256 if current else "",
            "proof_source_identities": list(context.immutable_result_proof.source_identities)
            if current and context.immutable_result_proof else [],
            "available_baseline_bindings": bindings,
        }
        rendered = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
        if len(("AUTHORITATIVE AUTHORING SCOPE:\n" + rendered).encode("utf-8")) > MAX_SCOPE_BYTES:
            return "AVAILABLE BASELINE BINDINGS: expansion omitted (scope exceeds byte cap)."
        return "AUTHORITATIVE AUTHORING SCOPE:\n" + rendered

    @property
    def scope_fingerprint(self) -> str:
        return hashlib.sha256(self.scope_text.encode("utf-8")).hexdigest()

    def as_telemetry(self) -> dict[str, object]:
        data: dict[str, object] = {
            **self.contract.as_telemetry(),
            "authoring_scope_version": ("candidate_authoring_scope_v3_replacement_envelope"
                if self.authoring_repair_scope is not None and len(self.authoring_repair_scope.measured.members) > 1
                else SCOPE_VERSION),
            "authoring_scope_fingerprint": self.scope_fingerprint,
        }
        if self.source_path.lower().endswith(".java"):
            data["oop_attachment_receipt"] = self.oop_attachment.receipt()
        return data

    def revision_prompt(self, evidence: CandidateRevisionEvidence) -> str:
        from core.candidate_revision import build_revision_prompt

        if (evidence.target_file != self.source_path
                or evidence.target_symbol != self.target_symbol
                or evidence.original_source_digest != hashlib.sha256(
                    self.source_snippet.encode("utf-8")).hexdigest()):
            raise ValueError("revision authoring context does not match the baseline")
        return build_revision_prompt(
            evidence, self.contract, scope_text=self.scope_text,
            oop_context=self.oop_attachment.prompt,
            authoring_source=(self.authoring_repair_scope.replacement_source
                              if self.authoring_repair_scope is not None
                              and len(self.authoring_repair_scope.measured.members) > 1 else None),
        )
