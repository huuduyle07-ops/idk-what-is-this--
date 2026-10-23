"""Explicit pytest plugin for authenticated pre-Java historical registry checks.

Invoke with ``-p tests._runtime_java1_frozen_regressions`` only for frozen
regressions. It projects exactly the pre-Java registry bytes for an explicit
list of historical modules, never modifies a file or historical hash, and
leaves current Java tests reading the current registry. Current registry and
picker coverage lives in ``tests/test_runtime_java1_governance.py``.
"""
from pathlib import Path

import pytest

from tests._runtime_java1_maintenance import before_runtime_java1


_REGISTRY = Path(__file__).resolve().parents[1] / "docs/roadmap/phase_registry.json"
_HISTORICAL_MODULES = frozenset({
    "test_phase_registry", "test_phase_picker", "test_runtime_sandbox1",
    "test_patch_candidate_behavior_executor1", "test_preflight_runtime1",
    "test_patch_candidate_behavior_exec_admit1",
    "test_patch_candidate_behavior_reflect1",
    "test_patch_candidate_behavior_exec_plan1",
    "test_patch_candidate_behavior_spec1", "test_patch_candidate_validate1a",
    "test_patch_candidate_materialize1", "test_patch_author_structural1",
    "test_patch_scope_admit1", "test_patch_scope_plan1",
    "test_patch_scope_approve1", "test_patch_scope_refresh1",
    "test_patch_scope_recheck1", "test_patch_scope_expand1",
    "test_oop_intent_continue1", "test_oop_intent_design1", "test_oop_intent_detect2",
})


@pytest.fixture(autouse=True)
def runtime_java1_authenticated_frozen_registry_snapshot(request, monkeypatch):
    module = getattr(request, "module", None)
    if module is None or module.__name__.rsplit(".", 1)[-1] not in _HISTORICAL_MODULES:
        return
    raw_read_bytes = Path.read_bytes
    raw_read_text = Path.read_text

    def frozen_read_bytes(path):
        content = raw_read_bytes(path)
        if path.resolve() == _REGISTRY:
            return before_runtime_java1("docs/roadmap/phase_registry.json", content)
        return content

    def frozen_read_text(path, *args, **kwargs):
        if path.resolve() == _REGISTRY:
            encoding = kwargs.get("encoding") or (args[0] if args else None) or "utf-8"
            errors = kwargs.get("errors") or (args[1] if len(args) > 1 else None) or "strict"
            return frozen_read_bytes(path).decode(encoding, errors).replace("\r\n", "\n")
        return raw_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", frozen_read_bytes)
    monkeypatch.setattr(Path, "read_text", frozen_read_text)
