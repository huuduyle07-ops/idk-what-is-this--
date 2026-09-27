"""RETRIEVE.LIVE.3 production query-recall path unification regressions."""

from __future__ import annotations

from pathlib import Path

from core import control_engine, identifier_recall
from core.identifier_recall import (
    EXACT_TAIL,
    MULTI_TOKEN_IDENTIFIER,
    resolve_identifier_recall,
)
from graph.schema import ProgramGraph


PROJECT_ROOT = Path(__file__).resolve().parents[1]
T6_QUERY = "2-space indentation is classified as 4-space"
TARGET = "core/code_dna.py::_classify_indent"


def _graph(*nodes: tuple[str, str]) -> ProgramGraph:
    graph = ProgramGraph()
    for node_id, node_kind in nodes:
        graph.add_node(node_id, node_kind)
    return graph


def _production_control(
    monkeypatch,
    graph: ProgramGraph,
    query: str,
    *,
    project_map: str = "",
) -> dict:
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda *args, **kwargs: {"findings": []},
    )
    monkeypatch.setattr(
        control_engine,
        "load_project_map",
        lambda repo_path: project_map,
    )
    monkeypatch.setattr(
        control_engine,
        "trace_execution_flow",
        lambda **kwargs: "",
    )
    monkeypatch.setattr(
        control_engine,
        "load_phantom_limb_report",
        lambda repo_path: {"findings": []},
    )
    return control_engine.run_control_structured(
        query,
        str(PROJECT_ROOT),
        graph=graph,
    )


def test_focused_resolver_and_real_control_prefix_have_candidate_parity(
    monkeypatch,
):
    hotspot = "tests/test_index_completion.py::write_text"
    graph = _graph((TARGET, "function"), (hotspot, "function"))
    eligible = control_engine.eligible_localization_nodes(graph)
    focused = resolve_identifier_recall(T6_QUERY, eligible, entry_limit=6)

    calls: list[tuple[str, tuple[str, ...], int]] = []
    canonical = identifier_recall.resolve_identifier_recall

    def observed(query, eligible_node_ids, *, query_term_limit=12, entry_limit=6):
        node_ids = tuple(eligible_node_ids)
        calls.append((query, node_ids, entry_limit))
        return canonical(
            query,
            node_ids,
            query_term_limit=query_term_limit,
            entry_limit=entry_limit,
        )

    monkeypatch.setattr(control_engine, "resolve_identifier_recall", observed)
    production = _production_control(monkeypatch, graph, T6_QUERY)
    receipt = production["entry_resolution"]

    assert calls == [(T6_QUERY, tuple(eligible), 6)]
    assert receipt["resolved_entry_nodes"] == list(focused.resolved_entry_nodes)
    assert production["entry_nodes"] == list(focused.resolved_entry_nodes)
    assert TARGET in receipt["resolved_entry_nodes"]


def test_t6_live_receipt_exposes_normalization_morphology_and_membership(
    monkeypatch,
):
    graph = _graph((TARGET, "function"))

    result = _production_control(monkeypatch, graph, T6_QUERY)
    receipt = result["entry_resolution"]

    assert TARGET in control_engine.eligible_localization_nodes(graph)
    assert receipt["raw_query_terms"] == [
        "space",
        "indentation",
        "classified",
    ]
    assert "indent" in receipt["normalized_query_terms"]
    assert "classify" in receipt["normalized_query_terms"]
    assert receipt["morphology_relations"] == [
        "indentation->indent",
        "classified->classify",
    ]
    assert receipt["resolved_entry_nodes"] == [TARGET]
    assert receipt["entry_match_kind"][TARGET] == MULTI_TOKEN_IDENTIFIER
    assert receipt["fallback_used"] is False
    assert receipt["project_map_fallback_used"] is False
    assert receipt["graph_fallback_used"] is False
    assert receipt["hotspot_only"] is False
    assert receipt["query_resolution_seconds"] >= 0.0


def test_successful_canonical_recall_is_not_overwritten_by_project_map(
    monkeypatch,
):
    hotspot = "tests/test_index_completion.py::write_text"
    graph = _graph((TARGET, "function"), (hotspot, "function"))
    project_map = f"## Critical Symbols\n- {hotspot} (score=99)\n"

    result = _production_control(
        monkeypatch,
        graph,
        T6_QUERY,
        project_map=project_map,
    )
    receipt = result["entry_resolution"]

    assert result["entry_nodes"][0] == TARGET
    assert receipt["resolved_entry_nodes"] == [TARGET]
    assert receipt["project_map_entry_nodes"] == [hotspot]
    assert receipt["project_map_supplemented"] is True
    assert receipt["project_map_fallback_used"] is False
    assert receipt["fallback_used"] is False
    assert receipt["hotspot_only"] is False


def test_truly_unresolved_production_query_keeps_project_map_fallback(
    monkeypatch,
):
    hotspot = "tests/test_index_completion.py::write_text"
    graph = _graph((hotspot, "function"))
    project_map = f"## Critical Symbols\n- {hotspot} (score=99)\n"

    result = _production_control(
        monkeypatch,
        graph,
        "unrelated mystery",
        project_map=project_map,
    )
    receipt = result["entry_resolution"]

    assert receipt["resolved_entry_nodes"] == []
    assert result["entry_nodes"] == [hotspot]
    assert receipt["project_map_fallback_used"] is True
    assert receipt["fallback_used"] is True
    assert receipt["hotspot_only"] is True


def test_compatibility_resolvers_delegate_without_new_matching_power():
    graph = _graph(
        ("calc.py::add", "function"),
        ("solution.py::length_of_longest_substring", "function"),
        ("text.py::concatenate", "function"),
        (TARGET, "function"),
    )

    exact = control_engine.resolve_symbol_to_graph_nodes(graph, "_classify_indent")
    calc = control_engine.resolve_query_to_graph_nodes(graph, ["add"])
    longest = control_engine.resolve_query_to_graph_nodes(
        graph, ["longest", "substring"]
    )

    assert exact == [TARGET]
    assert resolve_identifier_recall(
        "_classify_indent",
        control_engine.eligible_localization_nodes(graph),
    ).matches[0].entry_match_kind == EXACT_TAIL
    assert [match.node_id for match in calc] == ["calc.py::add"]
    assert [match.node_id for match in longest] == [
        "solution.py::length_of_longest_substring"
    ]
    assert control_engine.resolve_query_to_graph_nodes(graph, ["cat"]) == []


def test_canonical_recall_scans_the_supplied_population_once():
    class OneShotPopulation:
        def __init__(self):
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("eligible population scanned more than once")
            yield TARGET
            yield "tests/test_index_completion.py::write_text"

    population = OneShotPopulation()
    recall = resolve_identifier_recall(T6_QUERY, population, entry_limit=6)

    assert population.iterations == 1
    assert recall.candidate_population_count == 2
    assert recall.resolved_entry_nodes == (TARGET,)


def test_query_recall_receipt_carries_navigation_facts_only(monkeypatch):
    result = _production_control(
        monkeypatch,
        _graph((TARGET, "function")),
        T6_QUERY,
    )
    receipt = result["entry_resolution"]

    forbidden = {
        "authority",
        "confidence",
        "defect",
        "grounding",
        "patch_basis",
        "write_authority",
    }
    assert not forbidden.intersection(receipt)
    assert result["patch_candidate_state"]["write_authority"] is False
    assert result["patch_candidate_state"]["patch_application_authority"] is False
