"""LIVE.3B: generic field proofs, occurrence negatives, and the real T6 lifecycle."""

from __future__ import annotations

import ast
import hashlib
import json
import statistics
import time
from dataclasses import replace
from pathlib import Path

import pytest

import core.pipeline as pipeline
from core.authoritative_binding_context import build_authoritative_binding_context
from core.immutable_result_fields import PROVEN_IMMUTABLE_RESULT_FIELD_READ as FIELD_READ
from test_patch_minimal_binding_context_live3 import (
    ROOT, TARGET_FILE, TARGET_SYMBOL, TARGET_FUNCTION, TARGET_BODY, CORRECT_BODY,
    _gate, _accepted, live_context,
)


RECORD = '''from dataclasses import dataclass

@dataclass(frozen=True)
class Result:
    value: str
    payload: str
    callback: str

    def render(self):
        return "render"

    @property
    def dangerous(self):
        raise AssertionError("property must never be accessed")

def existing_helper() -> Result:
    return Result("ok", "ok", "ok")

raise AssertionError("policy must never execute this module")
'''
SOURCE = "from helper import existing_helper\n\ndef target(text):\n    return text\n"


def fixture_gate(tmp_path, patched, *, helper=RECORD, source=SOURCE, target="    return text", files=None):
    (tmp_path / "helper.py").write_text(helper, encoding="utf-8")
    (tmp_path / "target.py").write_text(source, encoding="utf-8")
    for name, text in (files or {}).items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    context = build_authoritative_binding_context(
        repo_root=tmp_path, source_path="target.py", target_symbol="target",
        authoritative_source=source,
    )
    assert context is not None
    block = _gate(target=target, patched=patched, source_path="target.py",
                  target_symbol="target", context=context, authoritative_source=source)
    return block, context


@pytest.mark.parametrize("field", ["value", "payload", "callback"])
@pytest.mark.parametrize("local", [False, True])
def test_generic_record_field_is_admitted_by_proof(tmp_path, field, local):
    patched = ("    result = existing_helper()\n    return result." + field
               if local else "    return existing_helper()." + field)
    block, context = fixture_gate(tmp_path, patched)
    assert _accepted(block)
    assert block["candidate_novelty_reason"] == FIELD_READ
    assert block["candidate_novelty_classification"][FIELD_READ]["names"] == [field]
    assert block["candidate_novelty_local_binding_names"] == (["result"] if local else [])
    assert block["candidate_novelty_unexplained_identifiers"] == []
    assert context.immutable_result_proof.callable_results[0].type_name == "Result"


@pytest.mark.parametrize("patched", [
    "    return existing_helper().missing",
    "    return existing_helper().__dict__",
    "    return existing_helper().render()",
    "    return existing_helper().render",
    "    return existing_helper().dangerous",
    "    return existing_helper().value()",
    "    return existing_helper().callback()",
    "    return existing_helper().value.other",
    "    return existing_helper().value.value",
    "    return existing_helper().value.render()",
    "    return existing_helper().value[0].value",
    "    return existing_helper().value + text.value",
    "    return existing_helper().value + value",
    "    return existing_helper().payload + text.payload()",
    "    result = existing_helper()\n    result.value = 'x'\n    return text",
    "    result = existing_helper()\n    del result.value\n    return text",
    "    result = existing_helper()\n    result.value += 'x'\n    return text",
    "    result = existing_helper()\n    result = text\n    return result.value",
    "    result = existing_helper()\n    result, text = text\n    return result.value",
    "    if text:\n        result = existing_helper()\n    return result.value",
    "    result = existing_helper()\n    holder = [result]\n    return result.value",
    "    result = existing_helper()\n    other = result\n    return other.value",
    "    result = existing_helper()\n    return [result][0].value",
    "    result = existing_helper()\n    return result.value()",
    "    fn = existing_helper().callback\n    return fn()",
    "    return existing_helper().value\n    existing_helper = text",
    "    existing_helper = text\n    return existing_helper().value",
    "    result: Result = text\n    return result.value",
    "    return new_helper().value",
    "    return text.lstrip()",
    "    stripped = text\n    return stripped.lstrip(' ')",
    "    return text.strip()",
    "    return text.startswith(' ')",
    "    return text.lower()",
    "    return subprocess.run(text)",
    "    return os.remove(text)",
    "    return text.unlink()",
    "    return helper.value",
    "    import helper\n    return helper.existing_helper().value",
])
def test_member_and_provenance_negatives(tmp_path, patched):
    block, _ = fixture_gate(tmp_path, patched)
    assert not _accepted(block), patched
    assert block["candidate_novelty_reason"]
    if "lstrip" in patched:
        assert block["candidate_novelty_reason"] == "novel_external_reference"


@pytest.mark.parametrize("helper", [
    RECORD.replace("@dataclass(frozen=True)\n", ""),
    RECORD.replace("frozen=True", "frozen=False"),
    RECORD.replace("@dataclass(frozen=True)", "@dataclass"),
    RECORD.replace("class Result:", "class Result(Base):"),
    RECORD.replace("class Result:", "class Result(metaclass=Meta):"),
    RECORD.replace("@dataclass(frozen=True)", "@unknown\n@dataclass(frozen=True)"),
    RECORD.replace("    value: str", "    value: str = Descriptor()"),
    RECORD.replace("    value: str", "    value: str\n    @property\n    def value(self):\n        return 'bad'"),
    RECORD.replace("    value: str", "    value: str\n    def __getattribute__(self, name):\n        return 'bad'"),
    RECORD.replace("    value: str", "    value: str\n    def __getattr__(self, name):\n        return 'bad'"),
    RECORD.replace("    value: str", "    value: ClassVar[str]"),
    RECORD.replace("    value: str", "    value: InitVar[str]"),
    RECORD.replace("    value: str", '    value: "ClassVar[str]"'),
    RECORD.replace("from dataclasses import dataclass", "from dataclasses import dataclass, InitVar as IV").replace("    value: str", "    value: IV"),
    RECORD.replace("def existing_helper()", "async def existing_helper()"),
    RECORD.replace("def existing_helper()", "@unknown\ndef existing_helper()"),
    RECORD.replace("return Result(\"ok\", \"ok\", \"ok\")", "yield Result('ok', 'ok', 'ok')"),
    RECORD.replace("-> Result", "-> Result | None"),
    RECORD.replace("-> Result", "-> Optional[Result]"),
    RECORD.replace("-> Result", "-> Result[str]"),
    RECORD.replace("-> Result", '-> "Result | None"'),
    RECORD.replace("-> Result", "-> Unknown"),
    RECORD.replace("-> Result", ""),
    RECORD + "\nResult = unknown\n",
    RECORD + "\nexisting_helper = unknown\n",
    RECORD + "\ndataclass = unknown\n",
    RECORD + "\nResult.value = property(unknown)\n",
    RECORD + "\nsetattr(Result, 'value', property(unknown))\n",
    RECORD + "\nfrom unknown import *\n",
    RECORD.replace("    def render(self):", "    @unknown\n    def render(self):"),
    RECORD.replace("    value: str", "    value: CV") + "\nCV = ClassVar\n",
])
def test_non_record_or_unresolved_return_proofs_fail_closed(tmp_path, helper):
    block, _ = fixture_gate(tmp_path, "    return existing_helper().value", helper=helper)
    assert not _accepted(block)
    assert block["candidate_novelty_reason"] == "novel_external_reference"


@pytest.mark.parametrize("helper", [
    RECORD.replace("-> Result", '-> "Result"'),
    "from __future__ import annotations\n" + RECORD,
    RECORD.replace("from dataclasses import dataclass", "from dataclasses import dataclass as record").replace("@dataclass", "@record"),
    RECORD.replace("from dataclasses import dataclass", "import dataclasses as dc").replace("@dataclass", "@dc.dataclass"),
    RECORD.replace("frozen=True", "frozen=True, slots=True"),
    RECORD.replace("    value: str", "    value: str = 'literal'"),
])
def test_small_authoritative_annotation_and_decorator_forms(tmp_path, helper):
    block, _ = fixture_gate(tmp_path, "    return existing_helper().value", helper=helper)
    assert _accepted(block)


def test_direct_import_alias_and_one_type_import_hop(tmp_path):
    source = SOURCE.replace("import existing_helper", "import existing_helper as trusted")
    helper = "from records import Result as Answer\ndef existing_helper() -> 'Answer':\n    ...\n"
    block, context = fixture_gate(tmp_path, "    return trusted().payload", source=source,
                                  helper=helper, files={"records.py": RECORD})
    assert _accepted(block)
    assert context.immutable_result_proof.callable_results[0].type_source_path == "records.py"
    assert len(context.immutable_result_proof.source_identities) == 2


@pytest.mark.parametrize("import_line, annotation", [
    ("from pathlib import Path", "Path"),
    ("from requests import Response", "Response"),
    ("import unknown", "unknown.Result"),
])
def test_repository_helper_cannot_launder_nonlocal_result_type(tmp_path, import_line, annotation):
    helper = f"{import_line}\ndef existing_helper() -> {annotation}:\n    ...\n"
    block, _ = fixture_gate(tmp_path, "    return existing_helper().value", helper=helper)
    assert not _accepted(block)


@pytest.mark.parametrize("import_line, expression", [
    ("from pathlib import Path", "Path(text).name"),
    ("from requests import get", "get(text).content"),
    ("import helper", "helper.existing_helper().value"),
    ("import subprocess", "subprocess.run(text)"),
    ("import os", "os.remove(text)"),
])
def test_existing_nonlocal_imports_and_module_namespaces(tmp_path, import_line, expression):
    source = import_line + "\n\ndef target(text):\n    return text\n"
    block, _ = fixture_gate(tmp_path, "    return " + expression, source=source)
    assert not _accepted(block)


def test_candidate_cannot_create_own_class_or_return_proof(tmp_path):
    patched = "    class Fake:\n        value: str\n    return Fake().value"
    block, _ = fixture_gate(tmp_path, patched)
    assert not _accepted(block)
    # A candidate-only return annotation is also structural novelty.
    patched = SOURCE[SOURCE.index("def target"):].replace("target(text)", "target(text) -> Result").replace("return text", "return existing_helper().value")
    block, _ = fixture_gate(tmp_path, patched, target="def target(text):\n    return text\n")
    assert not _accepted(block)
    assert "signature_change" in block["candidate_novelty_blocking_reasons"]


@pytest.mark.parametrize("mutation", ["helper", "type", "target"])
def test_every_authoritative_proof_source_must_still_match(tmp_path, mutation):
    helper = "from records import Result\ndef existing_helper() -> Result:\n    ...\n"
    block, context = fixture_gate(tmp_path, "    return existing_helper().value", helper=helper,
                                  files={"records.py": RECORD})
    assert _accepted(block)
    path = tmp_path / {"helper": "helper.py", "type": "records.py", "target": "target.py"}[mutation]
    path.write_text(path.read_text() + "\n# changed baseline\n")
    block = _gate(target="    return text", patched="    return existing_helper().value",
                  source_path="target.py", target_symbol="target", context=context,
                  authoritative_source=(tmp_path / "target.py").read_text())
    assert not _accepted(block)
    assert block["authoritative_binding_context_current"] is False


def test_baseline_local_is_supported_when_assignment_is_in_selected_body(tmp_path):
    body = "    result = existing_helper()\n    return text"
    source = SOURCE.replace("    return text", body)
    block, _ = fixture_gate(tmp_path, body.replace("return text", "return result.value"), source=source, target=body)
    assert _accepted(block)
    block, _ = fixture_gate(tmp_path, "    return result.value", source=source)
    assert not _accepted(block)  # no inference from outside the selected fragment


def test_baseline_parameter_and_local_shadowing_are_not_callable_provenance(tmp_path):
    for source in (SOURCE.replace("target(text)", "target(text, existing_helper)"),
                   SOURCE.replace("    return text", "    existing_helper = text\n    return text"),
                   SOURCE + "\nexisting_helper = unknown\n"):
        block, _ = fixture_gate(tmp_path, "    return existing_helper().value", source=source)
        assert not _accepted(block)


def test_exact_t6_body_and_full_function_pre_post_parity(live_context):
    context, source = live_context
    for target, patched in ((TARGET_BODY.rstrip("\n"), CORRECT_BODY.rstrip("\n")),
                            (TARGET_FUNCTION.rstrip("\n"), TARGET_FUNCTION.replace(TARGET_BODY, CORRECT_BODY).rstrip("\n"))):
        inputs = dict(target=target, patched=patched, source_path=TARGET_FILE,
                      target_symbol=TARGET_SYMBOL, authoritative_source=source)
        pre = _gate(**inputs, context=replace(context, immutable_result_proof=None))
        assert not _accepted(pre)
        assert pre["candidate_novelty_unexplained_identifiers"] == ["value"]
        assert pre["candidate_novelty_blocking_reasons"] == ["novel_external_reference"]
        post = _gate(**inputs, context=context)
        assert _accepted(post)
        assert post["candidate_novelty_reason"] == FIELD_READ
        assert post["candidate_novelty_unexplained_identifiers"] == []


def test_exact_candidate_bytes_match_request_and_runtime1_semantics():
    from test_indent_runtime1 import RUNTIME1_TEST_ONLY_CORRECT_BODY
    import textwrap
    # The request spells out six physical lines; the older fixture puts the
    # inner call on one line. Keep both byte forms intact and prove AST parity.
    assert CORRECT_BODY == (
        "    return assess_indentation_observation(\n"
        "        observe_source_indentation(\n"
        "            text,\n"
        "            language=language,\n"
        "        )\n"
        "    ).value\n"
    )
    assert ast.dump(ast.parse(textwrap.dedent(CORRECT_BODY))) == ast.dump(
        ast.parse(textwrap.dedent(RUNTIME1_TEST_ONLY_CORRECT_BODY))
    )


def test_exact_t6_real_frozen_lifecycle(monkeypatch):
    from test_patch_minimal_novelty_live import _t6_contract, _t6_lifecycle_state
    from core.defect_probe import execute_defect_probe
    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == "reproduced"
    before = (ROOT / TARGET_FILE).read_bytes()
    state = _t6_lifecycle_state(TARGET_FUNCTION, (contract, pre))
    payload = {
        "summary": "test-only exact repair", "issues": [], "confidence": 0.4,
        "needs_escalation": False, "patch_basis": "grounded_defect",
        "target_source_grounded": True,
        "patch_candidate": {
            "file": TARGET_FILE, "relative_path": TARGET_FILE,
            "target_node_name": TARGET_SYMBOL, "target_node_kind": "function",
            "target_snippet": TARGET_BODY.rstrip("\n"),
            "patched_snippet": CORRECT_BODY.rstrip("\n"),
        },
    }
    pipeline.finalize_answer(state, json.dumps(payload))
    assert _accepted(state.json_block)
    assert state.json_block["candidate_novelty_reason"] == FIELD_READ
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    pipeline.maybe_run_auto_patch(state, interactive=False)
    block = state.json_block
    assert block["candidate_effect_status"] == "mutating"
    assert block["candidate_probe_apply_status"] == "applied"
    assert block["behavioral_matrix_status"] == "fixed_and_preserved"
    assert block["behavioral_matrix_case_count"] == 8
    assert block["candidate_verification_status"] == "verified"
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False
    assert (ROOT / TARGET_FILE).read_bytes() == before
    # Durable test-run evidence, outside the product and never used by policy.
    report = {key: value for key, value in block.items() if key.startswith((
        "candidate_", "behavioral_matrix_", "sandbox_", "execution_", "final_repository_",
    ))}
    report["target_sha256"] = hashlib.sha256(before).hexdigest()
    out = ROOT / ".agent/live3b/lifecycle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def test_static_policy_has_no_execution_or_traversal_surface():
    path = ROOT / "core/immutable_result_fields.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    names = {n.func.id for n in calls if isinstance(n.func, ast.Name)}
    attrs = {n.func.attr for n in calls if isinstance(n.func, ast.Attribute)}
    assert not names & {"eval", "exec", "__import__", "getattr"}
    assert not attrs & {"rglob", "glob", "get_type_hints", "getmembers", "import_module", "run", "Popen"}
    assert all(isinstance(n.func.value, ast.Name) and n.func.value.id == "ast"
               for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "walk")


def test_proof_and_gate_costs_are_bounded(live_context, capsys):
    context, source = live_context
    inputs = dict(target=TARGET_BODY.rstrip("\n"), patched=CORRECT_BODY.rstrip("\n"),
                  source_path=TARGET_FILE, target_symbol=TARGET_SYMBOL, authoritative_source=source)
    proof_times, lookup_times, pre_times, post_times = [], [], [], []
    for _ in range(31):
        context = build_authoritative_binding_context(repo_root=ROOT, source_path=TARGET_FILE,
                      target_symbol=TARGET_SYMBOL, authoritative_source=source)
        proof_times.append(context.immutable_result_proof.construction_seconds)
        for active, samples in ((replace(context, immutable_result_proof=None), pre_times), (context, post_times)):
            started = time.perf_counter()
            block = _gate(**inputs, context=active)
            samples.append(time.perf_counter() - started)
        lookup_times.append(block["immutable_result_field_lookup_seconds"])
    result = {"return_type_proof_median_ms": statistics.median(proof_times) * 1000,
              "field_lookup_median_ms": statistics.median(lookup_times) * 1000,
              "safe_minimal_pre_median_ms": statistics.median(pre_times) * 1000,
              "safe_minimal_post_median_ms": statistics.median(post_times) * 1000}
    result["safe_minimal_gate_delta_ms"] = result["safe_minimal_post_median_ms"] - result["safe_minimal_pre_median_ms"]
    assert max(proof_times + post_times) < 0.5
    out = ROOT / ".agent/live3b/performance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")


def test_local_t6_result_has_equivalent_member_classification(live_context):
    context, source = live_context
    local = CORRECT_BODY.replace("    return assess_", "    assessment = assess_").replace(
        "    ).value\n", "    )\n    return assessment.value\n"
    )
    block = _gate(target=TARGET_BODY.rstrip("\n"), patched=local.rstrip("\n"),
                  source_path=TARGET_FILE, target_symbol=TARGET_SYMBOL,
                  context=context, authoritative_source=source)
    assert _accepted(block)
    assert block["candidate_novelty_reason"] == FIELD_READ
    assert block["candidate_novelty_local_binding_names"] == ["assessment"]


def test_repository_dataclass_lookalike_does_not_prove_immutability(tmp_path):
    block, _ = fixture_gate(tmp_path, "    return existing_helper().value",
                            files={"dataclasses.py": "def dataclass(**kwargs): ...\n"})
    assert not _accepted(block)


def test_oversize_source_is_not_parsed_for_proof(tmp_path):
    from core.immutable_result_fields import MAX_SOURCE_BYTES
    block, _ = fixture_gate(tmp_path, "    return existing_helper().value",
                            helper=RECORD + "#" + "x" * MAX_SOURCE_BYTES)
    assert not _accepted(block)


def test_combined_phase_frozen_bytes_and_reversal_receipt():
    from _harness_maintenance import before_later_receipts
    receipt = ROOT / "tests/fixtures/patch_minimal_live3_reversal.json"
    for item in json.loads(receipt.read_text())["reversals"]:
        restored = before_later_receipts(item["path"], (ROOT / item["path"]).read_bytes(),
                                         newer_than=ROOT / "tests/fixtures/indent_runtime1_reversal.json")
        assert hashlib.sha256(restored).hexdigest() == item["pre_sha256"]
    frozen = json.loads((ROOT / "tests/fixtures/patch_minimal_live3_frozen_boundaries.json").read_text())
    for relative, digest in frozen["files"].items():
        if relative == "web/sessions.json":
            # Runtime session data is intentionally mutable and earlier tests in
            # the same process write it; it is not a frozen production source.
            continue
        assert hashlib.sha256(before_later_receipts(relative, (ROOT / relative).read_bytes(), newer_than=receipt)).hexdigest() == digest, relative


def test_one_combined_phase_is_complete_without_future_authoring_phase():
    from core.phase_registry import load_phase_registry
    from core.phase_picker import pick_phase_candidates
    data = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    phases = {p["phase_id"]: p for p in data["phases"]}
    phase = phases["PATCH.MINIMAL.LIVE.3"]
    assert phase["status"] == "complete"
    assert not {"PATCH.MINIMAL.LIVE.3A", "PATCH.MINIMAL.LIVE.3B", "PATCH.AUTHOR.LIVE.4"} & phases.keys()
    assert phase["network_allowed"] is phase["model_calls_allowed"] is False
    report = pick_phase_candidates(data)
    assert "PATCH.MINIMAL.LIVE.3" in {p["phase_id"] for p in report["buckets"]["complete_or_history"]}


def test_imported_pseudo_field_alias_is_not_assumed_to_be_data(tmp_path):
    helper = "from aliases import Pseudo\n" + RECORD.replace("    value: str", "    value: Pseudo")
    block, _ = fixture_gate(tmp_path, "    return existing_helper().value", helper=helper,
                            files={"aliases.py": "from typing import ClassVar as Pseudo\n"})
    assert not _accepted(block)
