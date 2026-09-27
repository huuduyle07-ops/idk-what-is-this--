"""CONTROL.LOCALIZE.LIVE.2: relevance, authority separation and target handoff."""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import control_engine as control
from core import localization_handoff as handoff
from core import localization_relevance as relevance
from core.live_task_routing import route_live_task
from core.patch_basis import FailureLocation, FailureRelevanceBinding
from graph.schema import ProgramGraph


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/control_localize_live2_t6.json"


def _row(symbol, callers=0, **extra):
    row = {"symbol": symbol, "called_by": [f"caller{i}.py::invoke" for i in range(callers)],
           "calls": [], "impact": [], "risk": {"risk_level": "low", "risk_score": 1},
           "query_bonus": 0, "graph_weight": 0, "depth": 0, **extra}
    row["score"] = control.score_control_node(row)
    return row


def _entries(*symbols):
    return {"query_derived_entry_nodes": list(symbols), "entry_ordering": [
        {"node_id": symbol, "rank": rank, "matched_query_tokens": ["parse"],
         "lexical_specificity_score": 2, "entry_match_kind": "identifier_token"}
        for rank, symbol in enumerate(symbols, 1)
    ]}


def _rank(rows, entries, query="find the fault", **kwargs):
    return control.infer_hypotheses(query, rows, "", entry_resolution=entries, **kwargs)


@pytest.mark.parametrize("callers,weight", [(100, 0), (10000, 1e100)])
def test_unanchored_hub_cannot_cross_direct_entry_class(callers, weight):
    direct = "parser.py::parse_indent"
    hub = "executor.py::run"
    rows = [_row(hub, callers, graph_weight=weight), _row(direct)]
    ranked = _rank(rows, _entries(direct))
    assert ranked[0]["symbol"] == direct
    assert ranked[1]["anchor_relation"] == "unanchored_expansion"
    assert "has upstream callers" in ranked[1]["reasons"]
    assert ranked[1]["localization_score"] > ranked[0]["localization_score"]


def test_anchored_path_retains_entry_and_direction_but_centrality_cannot_cross_class():
    entry, expanded = "app.py::wrapper", "parser.py::parse"
    row = _row(expanded, 100, originating_entry=entry, entry_path=[{
        "from": entry, "to": expanded, "edge_kind": "resolved_call", "direction": "downstream",
    }])
    ranked = _rank([row, _row(entry)], _entries(entry))
    assert ranked[0]["symbol"] == entry
    assert ranked[1]["anchor_relation"] == "anchored_expansion"
    assert ranked[1]["originating_entry"] == entry
    assert ranked[1]["graph_support"]["hop_count"] == 1


def test_substring_navigation_is_not_an_exact_anchor_edge():
    graph = ProgramGraph()
    graph.add_edge("app.py::run", "parser.py::parse_extra", "resolved_call")
    rows = [_row("app.py::run", originating_entry="parser.py::parse", entry_path=[{
        "from": "parser.py::parse", "to": "app.py::run", "edge_kind": "resolved_call", "direction": "upstream",
    }])]
    relevance.verify_entry_paths(graph, rows)
    assert rows[0]["entry_path"] == []
    assert _rank(rows, _entries("parser.py::parse"))[0]["anchor_relation"] == "unanchored_expansion"


def test_typed_executed_frame_can_override_entry_without_granting_authority():
    entry, downstream = "app.py::wrapper", "parser.py::parse"
    binding = FailureRelevanceBinding(
        kind="direct_location", candidate_file="parser.py", candidate_symbol="parse",
        location=FailureLocation(file="parser.py", line=9, kind="stack_frame"),
    )
    ranked = _rank([_row(entry, 100), _row(downstream)], _entries(entry), failure_binding=binding)
    assert ranked[0]["symbol"] == downstream
    assert ranked[0]["final_localization_class"] == "executed_failure_reference"
    assert ranked[0]["defect_established"] is False
    assert ranked[0]["defect_grounding"] == []
    assert ranked[0]["recommended_action"] == "inspect_candidate"


def test_explicit_file_reference_can_override_graph_entry():
    rows = [_row("app.py::wrapper", 100), _row("parser.py::parse")]
    assert _rank(rows, _entries("app.py::wrapper"), "failure in parser.py")[0]["symbol"] == "parser.py::parse"


def test_free_text_trace_is_not_executed_evidence():
    ranked = control.infer_hypotheses(
        "find the fault", [_row("app.py::wrapper"), _row("parser.py::parse", 100)],
        "parse appears in execution trace; return value differs across execution paths",
        entry_resolution=_entries("app.py::wrapper"),
    )
    assert ranked[0]["symbol"] == "app.py::wrapper"
    assert all(row["execution_support"] is None for row in ranked)


def test_canonical_tie_and_legitimate_test_entry():
    nodes = ["tests/test_parser.py::test_parser", "tests/test_parser.py::check_parser"]
    rows = [_row(node) for node in nodes]
    first = _rank(rows, _entries(*nodes))
    second = _rank(list(reversed(rows)), _entries(*reversed(nodes)))
    assert [h["symbol"] for h in first] == [h["symbol"] for h in second] == sorted(nodes)
    assert first[0]["anchor_relation"] == "direct_query_entry"


def test_all_bounded_candidates_are_gated_before_top_hypothesis_cap():
    entry = "parser.py::parse"
    rows = [_row(f"m{i}.py::hub", 100) for i in range(19)] + [_row(entry)]
    ranked = _rank(rows, _entries(entry))
    assert ranked[0]["symbol"] == entry
    assert len(ranked) == 5
    assert all("localization" in row for row in rows)


def test_exact_long_t6_replays_real_prechange_features():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    entries = fixture["entry_resolution"]
    rows = fixture["evidence"]
    target = "core/code_dna.py::_classify_indent"
    assert entries["entry_nodes"].index(target) + 1 == 2
    assert len(entries["entry_nodes"]) == 6
    assert entries["fallback_used"] is False
    old = max(rows, key=lambda row: row["score"])
    assert old["symbol"] == "core/executor.py::run"
    assert len(old["called_by"]) == 111
    assert old["score"] == pytest.approx(223.2558)
    ranked = _rank(rows, entries, fixture["query"])
    assert ranked[0]["symbol"] == target
    executor = next(row["localization"] for row in rows if row["symbol"] == old["symbol"])
    assert executor["anchor_relation"] == "anchored_expansion"
    assert executor["graph_support"]["hop_count"] == 2
    assert executor["selection_result"] == "rejected"
    assert ranked[0]["source_support"]["status"] == "unavailable"


def _control_target(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    return control.build_control_result(
        "fix the arithmetic bug", str(tmp_path), ["calc.py::add"],
        [_row("calc.py::add")], "", _entries("calc.py::add"),
    )


def test_mismatching_payload_cannot_launder_entity_grounding_as_target(tmp_path):
    result = _control_target(tmp_path)
    block = {"patch_candidate": {"file": "patching/patch_engine.py", "target_node_name": "apply_patch_from_json"},
             "answer_entity_grounding": {"action": "unchanged"},
             "localization_handoff": {"localized_target": "patching/patch_engine.py::apply_patch_from_json"}}
    handoff.enforce_payload_target(result, block)
    assert block["patch_candidate"] is None
    assert block["localization_target_rejected"] is True
    assert block["localization_handoff"]["localized_target"] == "calc.py::add"
    assert result["patch_candidate_state"]["write_authority"] is False


def test_same_file_different_symbol_and_unnamed_other_body_are_rejected(tmp_path):
    result = _control_target(tmp_path)
    for candidate in ({"file": "calc.py", "target_node_name": "subtract"},
                      {"file": "calc.py", "target_snippet": "return something_else"}):
        block = {"patch_candidate": candidate}
        handoff.enforce_payload_target(result, block)
        assert block["patch_candidate"] is None


def test_matching_target_still_has_no_patch_basis_or_authority(tmp_path):
    result = _control_target(tmp_path)
    candidate = {"file": "calc.py", "target_node_name": "add", "target_snippet": "return a - b"}
    block = {"patch_candidate": candidate}
    handoff.enforce_payload_target(result, block)
    assert block["patch_candidate"] == candidate
    control.enforce_control_grounding_on_payload(result, block)
    assert block["patch_candidate"] is None


def test_existing_failure_binding_replaces_target_with_current_typed_receipt(tmp_path):
    (tmp_path / "app.py").write_text("def wrapper():\n    return 0\n")
    (tmp_path / "parser.py").write_text("def parse():\n    return 0\n")
    result = control.build_control_result(
        "fix the fault", str(tmp_path), ["app.py::wrapper"],
        [_row("app.py::wrapper", 100), _row("parser.py::parse")], "", _entries("app.py::wrapper"),
    )
    preflight = {"ran": True, "ok": False, "category": "assertion_failure", "outcome": "failed",
                 "command": "python parser.py", "locations": [
                     {"file": "parser.py", "line": 2, "kind": "stack_frame"}],
                 "output": "parser.py:2: AssertionError"}
    control.attach_preflight_validation(result, preflight)
    receipt = handoff.current_target_receipt(result)
    assert receipt["localized_target"] == "parser.py::parse"
    replacement = receipt["replacement_receipt"]
    assert replacement["previous_target"] == "app.py::wrapper"
    assert replacement["replacement_basis"] == "direct_location"
    assert replacement["evidence_source"] == "executed_validation_failure"
    assert replacement["freshness"] == "current_control_receipt"
    assert len(replacement["evidence_fingerprint"]) == 64
    assert result["patch_candidate_state"]["write_authority"] is False
    result["preflight_validation"] = {"ran": True, "ok": False, "category": "validation_budget_exhausted"}
    assert handoff.current_target_receipt(result)["replacement_receipt"] is None


def test_entry_slots_survive_early_expansion_budget(monkeypatch):
    entries = [f"entry{i}.py::parse" for i in range(6)]
    graph = ProgramGraph()
    for node in entries + [f"neighbor{i}.py::run" for i in range(6)]:
        graph.add_node(node, "function")
    monkeypatch.setattr(control, "explain_symbol", lambda g, node: {
        "called_by": [], "calls": [f"neighbor{i}.py::run" for i in range(6)],
    })
    monkeypatch.setattr(control, "impact_analysis", lambda *args: [])
    monkeypatch.setattr(control, "analyze_symbol_risk", lambda *args: {"risk_level": "low", "risk_score": 1})
    rows = control.control_dfs_v2(graph, entries, max_nodes=7, node_metrics={})
    assert len(rows) <= 7
    assert set(entries).issubset({row["symbol"] for row in rows})


def test_display_explicitly_preserves_target_even_when_other_entity_exists(tmp_path):
    result = _control_target(tmp_path)
    state = SimpleNamespace(control_result=result, user_input=result["query"], repo_path=str(tmp_path))
    answer = "The root cause is `patching/patch_engine.py::apply_patch_from_json`."
    final, _, _, _ = handoff.ground_answer_for_display(state, answer)
    assert "not the localized target" in final
    assert "CONTROL localization target: `calc.py::add`" in final
    assert "root cause is" in final  # qualifiers insert; prose is not deleted


@pytest.mark.parametrize("query,expected", [
    ("Add a new priority field to tasks", "explicit_change"),
    ("Compare the repository architecture", "analysis_only"),
])
def test_explicit_change_and_analysis_handoffs_are_unchanged(tmp_path, query, expected):
    result = _control_target(tmp_path)
    route = route_live_task(query, repository_available=True).as_dict()
    assert route["task_shape"] == expected
    result["live_route"] = route
    block = {"patch_candidate": {"file": "other.py", "target_node_name": "change"}}
    original = copy.deepcopy(block)
    handoff.enforce_payload_target(result, block)
    assert block == original
    assert handoff.current_target_receipt(result) is None


def test_new_selection_module_has_no_io_provider_or_target_literals():
    source = inspect.getsource(relevance)
    for forbidden in ("_classify_indent", "indentation", "2space", "4space", "code_dna.py"):
        assert forbidden not in source
    tree = ast.parse(source)
    forbidden_calls = {"open", "read_text", "read_bytes", "rglob", "glob", "walk", "scandir",
                       "build_graph_from_repo", "resolve_identifier_recall", "build_lexical_specificity_index"}
    assert not any(isinstance(node, ast.Call) and
                   (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) in forbidden_calls
                   for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Import) and any(alias.name in {"socket", "requests", "os"} for alias in node.names)
                   for node in ast.walk(tree))


def test_frozen_retrieval_graph_probe_validation_authority_and_safety_boundaries():
    from _harness_maintenance import before_harness_remediation

    pins = json.loads((ROOT / "tests/fixtures/control_localize_live2_boundaries.json").read_text())
    # The explicitly requested harness remediation (2026-09-11) edited some of
    # these files after this phase froze them; its receipt undoes exactly those
    # edits, so the pin is checked against history and is never re-pinned.
    for file, digest in pins["files"].items():
        assert hashlib.sha256(before_harness_remediation(file)).hexdigest() == digest, file
    for name, digest in pins["control_functions"].items():
        node = ast.parse(inspect.getsource(getattr(control, name))).body[0]
        assert hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest() == digest, name


def test_exact_long_t6_reaches_frozen_probe_adapter_boundary_without_manufacturing_candidate():
    from tests.test_defect_probe_live import _inconclusive_preflight

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source_before = (ROOT / "core/code_dna.py").read_bytes()
    result = control.build_control_result(
        fixture["query"], str(ROOT), fixture["entry_resolution"]["entry_nodes"],
        fixture["evidence"], "", fixture["entry_resolution"],
    )
    result["live_route"] = route_live_task(fixture["query"], repository_available=True).as_dict()
    assert result["live_route"]["task_shape"] == "defect_repair"
    assert result["top_hypothesis"]["symbol"] == "core/code_dna.py::_classify_indent"
    control.attach_preflight_validation(result, _inconclusive_preflight())
    assert result["defect_probe"]["target_binding"]["symbol"] == "_classify_indent"
    # The adapter limitation this phase recorded — "no deterministic typed
    # adapter exists for the preserved task facts" — was DEFECT.FACT.LIVE.1's
    # brief, and it is gone: the exact prompt now carries a typed behavioral
    # expectation, so the same target reaches the same bounded probe and it
    # runs. The prompt itself is still never shortened to make one pass.
    assert result["defect_probe"]["probe_result"] == "reproduced"
    assert result["defect_probe"]["probe_observed"] == "4space"
    assert result["defect_probe"]["probe_expected"] == "2space"
    # PATCH.BASIS is untouched: the basis is whatever the existing gate makes of
    # an executed bounded reproduction, and no candidate was manufactured here.
    assert result["patch_candidate_state"]["write_authority"] is False
    assert result["patch_candidate_state"]["auto_patch_candidate_allowed"] is False
    assert source_before == (ROOT / "core/code_dna.py").read_bytes()
