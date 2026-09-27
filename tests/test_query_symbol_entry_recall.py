"""RETRIEVE.LIVE.2 query-to-symbol entry recall regressions."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from core import control_engine
from core.code_dna import _classify_indent
from core.identifier_recall import (
    BOUNDED_MORPHOLOGY,
    ENTRY_MATCH_KINDS,
    EXACT_SYMBOL,
    EXACT_TAIL,
    IDENTIFIER_TOKEN,
    MULTI_TOKEN_IDENTIFIER,
    IdentifierEntryMatch,
    decompose_identifier,
    extract_query_symbol_candidates,
)
from graph.schema import ProgramGraph
from graph.builder import build_graph_from_repo
from reasoning.deep_project_understand import extract_symbol_candidates


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _graph(*nodes: tuple[str, str]) -> ProgramGraph:
    graph = ProgramGraph()
    for node_id, node_kind in nodes:
        graph.add_node(node_id, node_kind)
    return graph


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _require_python_parser() -> None:
    from core.treesitter_parse import parse_code_with_treesitter

    parsed = parse_code_with_treesitter("def probe():\n    return 1\n", "python")
    if "probe" not in [symbol.get("name") for symbol in parsed.get("symbols", [])]:
        pytest.skip("tree-sitter python grammar unavailable in this environment")


def _resolve(
    graph: ProgramGraph,
    query: str,
    *,
    limit: int = 6,
) -> list[IdentifierEntryMatch]:
    return control_engine.resolve_query_to_graph_nodes(
        graph,
        extract_symbol_candidates(query),
        limit=limit,
    )


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("length_of_longest_substring", ("length", "of", "longest", "substring")),
        ("_classify_indent", ("classify", "indent")),
        ("__init__", ("init",)),
        ("detectDefaultPreflightCommand", ("detect", "default", "preflight", "command")),
        ("HTTPResponseParser", ("http", "response", "parser")),
        ("ClassName.method_name", ("class", "name", "method")),
        ("module::面積", ("module", "面積")),
    ],
)
def test_identifier_decomposition(identifier, expected):
    assert decompose_identifier(identifier) == expected


def test_query_extraction_preserves_exact_identity_and_unicode():
    query = "inspect core/code_dna.py::_classify_indent and 面積"
    candidates = extract_query_symbol_candidates(query)

    assert candidates[0] == "core/code_dna.py::_classify_indent"
    assert "_classify_indent" in candidates
    assert "面積" in candidates
    # Production's established extractor delegates to the same bounded rules.
    assert extract_symbol_candidates(query) == candidates


def test_exact_full_symbol_has_strongest_entry_evidence():
    target = "core/code_dna.py::_classify_indent"
    matches = _resolve(_graph((target, "function")), target)

    assert [item.node_id for item in matches] == [target]
    assert matches[0].entry_match_kind == EXACT_SYMBOL
    assert matches[0].exact_query == target


def test_exact_tail_is_preserved_for_private_and_dunder_symbols():
    graph = _graph(
        ("core/code_dna.py::_classify_indent", "function"),
        ("core/thing.py::__init__", "constructor"),
    )

    private = _resolve(graph, "_classify_indent")
    dunder = _resolve(graph, "__init__")

    assert private[0].entry_match_kind == EXACT_TAIL
    assert private[0].node_id == "core/code_dna.py::_classify_indent"
    assert dunder[0].entry_match_kind == EXACT_TAIL
    assert dunder[0].node_id == "core/thing.py::__init__"


def test_indent_token_recalls_the_live_target():
    target = "core/code_dna.py::_classify_indent"
    matches = _resolve(_graph((target, "function")), "indent")

    assert [item.node_id for item in matches] == [target]
    assert matches[0].entry_match_kind == IDENTIFIER_TOKEN
    assert matches[0].identifier_tokens == ("classify", "indent")
    assert matches[0].matched_query_tokens == ("indent",)


def test_real_dogfood_wording_uses_only_bounded_observed_morphology():
    target = "core/code_dna.py::_classify_indent"
    matches = _resolve(
        _graph((target, "function")),
        "2-space indentation is classified as 4-space",
    )

    assert matches[0].node_id == target
    assert matches[0].entry_match_kind == MULTI_TOKEN_IDENTIFIER
    assert matches[0].morphology_relations == (
        "indentation->indent",
        "classified->classify",
    )


def test_single_classification_form_uses_bounded_morphology():
    target = "core/code_dna.py::_classify_indent"
    matches = _resolve(_graph((target, "function")), "classification is wrong")

    assert matches[0].entry_match_kind == BOUNDED_MORPHOLOGY
    assert matches[0].morphology_relations == ("classification->classify",)


def test_arbitrary_ation_stemming_is_not_used():
    graph = _graph(("core/op.py::oper", "function"))

    assert _resolve(graph, "operation") == []


def test_multi_token_identifier_evidence_and_common_naming_styles():
    graph = _graph(
        ("solution.py::length_of_longest_substring", "function"),
        ("commands.ts::detectValidationCommand", "function"),
    )

    longest = _resolve(graph, "longest substring")
    command = _resolve(graph, "validation command")

    assert longest[0].entry_match_kind == MULTI_TOKEN_IDENTIFIER
    assert longest[0].node_id == "solution.py::length_of_longest_substring"
    assert command[0].entry_match_kind == MULTI_TOKEN_IDENTIFIER
    assert command[0].node_id == "commands.ts::detectValidationCommand"


def test_exact_unicode_identifier_query_still_resolves():
    graph = _graph(("core/geometry.py::面積", "function"))

    matches = _resolve(graph, "面積")

    assert matches[0].node_id == "core/geometry.py::面積"
    assert matches[0].entry_match_kind == EXACT_TAIL


def test_ambiguous_meaningful_token_returns_a_bounded_deterministic_set():
    graph = ProgramGraph()
    for index in range(20):
        graph.add_node(f"parser_{index}.py::parse_record_{index}", "function")

    matches = _resolve(graph, "parse", limit=5)

    assert len(matches) == 5
    assert [item.node_id for item in matches] == sorted(
        item.node_id for item in matches
    )
    assert all(item.entry_match_kind == IDENTIFIER_TOKEN for item in matches)


def test_lone_low_information_token_does_not_explode_the_population():
    graph = ProgramGraph()
    graph.add_node("app.py::run", "function")
    for index in range(40):
        graph.add_node(f"worker_{index}.py::run_task_{index}", "function")

    matches = _resolve(graph, "run", limit=6)

    # Exact lookup remains valid, while generic token membership is suppressed.
    assert [(item.node_id, item.entry_match_kind) for item in matches] == [
        ("app.py::run", EXACT_TAIL)
    ]


def test_low_information_token_can_support_a_meaningful_multi_token_match():
    graph = _graph(("core/users.py::get_user", "function"))

    matches = _resolve(graph, "get user")

    assert matches[0].entry_match_kind == MULTI_TOKEN_IDENTIFIER
    assert matches[0].matched_query_tokens == ("get", "user")


def test_substring_character_containment_is_not_entry_evidence():
    graph = _graph(
        ("text.py::concatenate", "function"),
        ("runtime.py::runner", "function"),
    )

    assert _resolve(graph, "cat") == []
    assert _resolve(graph, "run") == []


def test_structural_call_and_malformed_historical_nodes_cannot_resurrect():
    graph = _graph(
        ("call::indent", "call"),
        ("core/broken.py::indent(\n", "function"),
        ("core/good.py::classify_indent", "function"),
    )

    matches = _resolve(graph, "indent")

    assert [item.node_id for item in matches] == [
        "core/good.py::classify_indent"
    ]


def test_calc_flat_pytest_and_test_symbol_compatibility():
    graph = _graph(
        ("calc.py::add", "function"),
        ("solution.py::length_of_longest_substring", "function"),
        ("tests/test_solution.py::test_longest_substring", "function"),
    )

    assert _resolve(graph, "add bug")[0].node_id == "calc.py::add"
    longest = _resolve(graph, "longest substring")
    assert {item.node_id for item in longest} == {
        "solution.py::length_of_longest_substring",
        "tests/test_solution.py::test_longest_substring",
    }


def test_calc_product_smoke_uses_query_derived_add_entry(monkeypatch, tmp_path):
    _require_python_parser()
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    graph = build_graph_from_repo(str(tmp_path))
    monkeypatch.setattr(control_engine, "load_project_map", lambda repo_path: "")
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda *args, **kwargs: {"findings": []},
    )

    selection = control_engine.select_entry_nodes(
        "fix the add bug in calc.py",
        str(tmp_path),
        graph=graph,
        return_details=True,
    )

    assert selection["query_derived_entry_nodes"][0] == "calc.py::add"
    assert selection["hotspot_only"] is False


def test_flat_pytest_product_smoke_uses_longest_substring_entry(
    monkeypatch,
    tmp_path,
):
    _require_python_parser()
    _write(
        tmp_path,
        "solution.py",
        "def length_of_longest_substring(value):\n    return len(value)\n",
    )
    _write(
        tmp_path,
        "test_solution.py",
        "from solution import length_of_longest_substring\n\n"
        "def test_abba():\n"
        "    assert length_of_longest_substring('abba') == 2\n",
    )
    graph = build_graph_from_repo(str(tmp_path))
    monkeypatch.setattr(control_engine, "load_project_map", lambda repo_path: "")
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda *args, **kwargs: {"findings": []},
    )

    selection = control_engine.select_entry_nodes(
        "longest substring assertion fails",
        str(tmp_path),
        graph=graph,
        return_details=True,
    )

    assert "solution.py::length_of_longest_substring" in selection[
        "query_derived_entry_nodes"
    ]
    assert selection["hotspot_only"] is False


def test_unresolved_query_still_uses_project_map_fallback(monkeypatch):
    hotspot = "tests/test_index_completion.py::write_text"
    graph = _graph((hotspot, "function"))
    monkeypatch.setattr(
        control_engine,
        "load_project_map",
        lambda repo_path: f"## Critical Symbols\n- {hotspot} (score=99)\n",
    )
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda *args, **kwargs: {"findings": []},
    )

    selection = control_engine.select_entry_nodes(
        "unrelated mystery",
        str(PROJECT_ROOT),
        graph=graph,
        return_details=True,
    )

    assert selection["entry_nodes"] == [hotspot]
    assert selection["query_derived_entry_nodes"] == []
    assert selection["project_map_fallback_used"] is True
    assert selection["hotspot_only"] is True


def test_successful_query_resolution_cannot_become_hotspot_only(
    monkeypatch,
):
    target = "core/code_dna.py::_classify_indent"
    hotspot = "tests/test_index_completion.py::write_text"
    graph = _graph((target, "function"), (hotspot, "function"))
    monkeypatch.setattr(
        control_engine,
        "load_project_map",
        lambda repo_path: f"## Critical Symbols\n- {hotspot} (score=99)\n",
    )
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda *args, **kwargs: {"findings": []},
    )

    selection = control_engine.select_entry_nodes(
        "indent classification",
        str(PROJECT_ROOT),
        graph=graph,
        return_details=True,
    )

    assert selection["entry_nodes"][0] == target
    assert selection["query_derived_entry_nodes"] == [target]
    assert selection["project_map_fallback_used"] is False
    assert selection["hotspot_only"] is False


def test_ranking_formula_and_natural_relevance_input_are_unchanged():
    item = {
        "called_by": ["a", "b"],
        "calls": ["c"],
        "impact": ["d"],
        "risk": {"risk_level": "high", "risk_score": 7},
        "query_bonus": 2,
        "graph_weight": 1.5,
        "depth": 2,
    }
    assert control_engine.score_control_node(item) == pytest.approx(23.5)
    # This phase does not rewrite the downstream relevance function.  Entry-set
    # membership changes; its existing score input is reported independently.
    assert control_engine.relevance_bonus(
        "core/code_dna.py::_classify_indent",
        control_engine.query_words("2-space indentation is classified as 4-space"),
    ) == 0


def test_entry_metadata_contains_no_confidence_rank_or_authority():
    assert set(ENTRY_MATCH_KINDS) == {
        EXACT_SYMBOL,
        EXACT_TAIL,
        IDENTIFIER_TOKEN,
        MULTI_TOKEN_IDENTIFIER,
        BOUNDED_MORPHOLOGY,
        "unresolved",
    }
    for field in IdentifierEntryMatch.__dataclass_fields__:
        lowered = field.lower()
        assert "score" not in lowered
        assert "weight" not in lowered
        assert "confidence" not in lowered
        assert "author" not in lowered
        assert "patch" not in lowered
        assert "ground" not in lowered


def test_identifier_bridge_has_no_model_network_embedding_or_repo_traversal():
    module = PROJECT_ROOT / "core" / "identifier_recall.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden_imports = {
        "agents",
        "aiohttp",
        "anthropic",
        "chromadb",
        "database",
        "faiss",
        "google",
        "http",
        "httpx",
        "numpy",
        "ollama",
        "openai",
        "os",
        "pathlib",
        "requests",
        "sentence_transformers",
        "shutil",
        "socket",
        "subprocess",
        "torch",
        "urllib",
    }
    assert not (imported & forbidden_imports)

    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls.intersection(
        {"glob", "iterdir", "listdir", "rglob", "scandir", "walk"}
    )


def test_classify_indent_remains_intentionally_broken_and_untouched():
    nested_two_space = (
        "def outer():\n"
        "  if condition:\n"
        "    for item in items:\n"
        "      handle(item)\n"
        "      record(item)\n"
        "    finish()\n"
        "  return 1\n"
    )

    assert _classify_indent(nested_two_space) == "4space"
    source = inspect.getsource(_classify_indent)
    assert 'counts["4space"] += 1' in source
    assert 'elif line.startswith("  "):' in source
