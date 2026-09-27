"""RETRIEVE.LIVE.1 - the localization candidate population boundary.

Two questions, kept apart on purpose:

    which objects are legitimate localization candidates at all?   (here)
    which candidate should rank highest?                           (not here)

Everything in this file is about the first.  Nothing in it changes a weight,
and one test pins that: the ranking coefficients CONTROL uses are asserted
literally, so a population fix cannot quietly become a ranking fix.

The population is also not the graph.  A node may stay in the graph, keep every
edge it had, and still carry ``candidate_eligible=False``.  Connectivity tests
below hold the builder to that.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import LANGUAGE_MAP
from core import control_engine
from core.code_dna import _classify_indent
from core.localization_candidate import (
    DOCUMENT_KINDS,
    ELIGIBLE,
    IMPLEMENTATION_KINDS,
    INVALID_SOURCE_BINDING,
    LOCALIZATION_REJECTION_REASONS,
    MALFORMED_SYMBOL,
    SOURCE_ROLE_MISMATCH,
    STRUCTURAL_KINDS,
    STRUCTURAL_ONLY,
    UNSUPPORTED_CANDIDATE_KIND,
    classify_localization_candidate,
    is_localization_candidate,
    is_wellformed_symbol_name,
    localization_population_metrics,
)
from core.repo_ignore import compute_policy_fingerprint
from core.source_file_policy import (
    SOURCE_ROLE_BY_EXTENSION,
    SOURCE_ROLE_CODE,
    SUPPORTED_EXTENSIONS,
    SYMBOL_EXTRACTION_VERSION,
)
from graph.builder import build_graph_from_repo
from graph.schema import ProgramGraph, build_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _reason(node_id: str, kind: str, **kwargs) -> str:
    return classify_localization_candidate(node_id, kind, **kwargs).reason


def _requires_python_parser(tmp_path: Path) -> None:
    from core.treesitter_parse import parse_code_with_treesitter

    parsed = parse_code_with_treesitter("def probe():\n    return 1\n", "python")
    if "probe" not in [s.get("name") for s in parsed.get("symbols", [])]:
        pytest.skip("tree-sitter python grammar unavailable in this environment")


# ---------------------------------------------------------------------------
# The reproduced malformed nodes are no longer candidates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "node_id",
    [
        "call::e(\n  ",
        "call::n\u26a0\ufe0f O",
        "call::equest_2(\n        \"Y",
        "call::) >",
        "call::_review(content_to_",
    ],
)
def test_reproduced_malformed_call_fragments_are_not_candidates(node_id):
    """The exact garbage the pre-fix parser produced on this repository."""
    verdict = classify_localization_candidate(node_id, "call")

    assert verdict.eligible is False
    assert verdict.reason == STRUCTURAL_ONLY


@pytest.mark.parametrize(
    "symbol",
    [
        "' -> Path:\n   '",
        "n_gemini_request(\n",
        "pt =",
        "ply_fast_env()",
        "() -> set[str]:\n",
        "th_failure_kind_fields(r",
    ],
)
def test_reproduced_malformed_symbol_fragments_are_not_candidates(symbol):
    """Even carrying an implementation kind, extraction residue is refused."""
    verdict = classify_localization_candidate(f"core/thing.py::{symbol}", "function")

    assert verdict.eligible is False
    assert verdict.reason == MALFORMED_SYMBOL


def test_control_characters_and_delimiters_are_refused_regardless_of_language():
    for symbol in ["a\nb", "a\tb", "x;", 'say("hi")', "value = 1", "a b"]:
        assert not is_wellformed_symbol_name(symbol), symbol


# ---------------------------------------------------------------------------
# Language-aware symbol grammar: no ASCII-only rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "symbol,language",
    [
        ("add", "python"),
        ("_classify_indent", "python"),
        ("Calc", "python"),
        ("Calc.add", "python"),          # qualified name
        ("\u00e9l\u00e9vation", "python"),  # Unicode identifier
        ("\u9762\u7a4d", "python"),         # non-Latin identifier
        ("\u043f\u043e\u0438\u0441\u043a", "python"),
        ("loadUser", "typescript"),
        ("$mount", "typescript"),        # $ is an identifier character there
        ("Store#save", "typescript"),
        ("HashMap::new", "rust"),
        ("~Buffer", "cpp"),              # destructor
    ],
)
def test_legitimate_identifiers_are_accepted(symbol, language):
    assert is_wellformed_symbol_name(symbol, language)


def test_dollar_is_language_aware_not_globally_allowed():
    assert is_wellformed_symbol_name("$mount", "typescript")
    assert not is_wellformed_symbol_name("$mount", "python")


def test_truncated_qualified_names_are_refused():
    for symbol in ["mod::", "::name", "Calc..add", "."]:
        assert not is_wellformed_symbol_name(symbol, "python"), symbol


def test_short_names_are_not_refused_for_being_short():
    """``agents/deepseek_client.py::cont`` was corruption, but not because it
    is four characters long.  Length is never the evidence."""
    assert is_wellformed_symbol_name("cont", "python")
    assert is_wellformed_symbol_name("f", "python")
    assert classify_localization_candidate(
        "agents/deepseek_client.py::cont", "function"
    ).eligible is True


# ---------------------------------------------------------------------------
# Node kinds
# ---------------------------------------------------------------------------

def test_structural_kinds_are_never_candidates():
    assert _reason("app.py", "file") == STRUCTURAL_ONLY
    assert _reason("call::helper", "call") == STRUCTURAL_ONLY
    assert _reason("app.py::run::expr::42", "expression") == STRUCTURAL_ONLY


def test_structural_only_node_cannot_become_a_primary_target():
    for node_id, kind in [
        ("app.py", "file"),
        ("call::helper", "call"),
        ("app.py::run::expr::42", "expression"),
    ]:
        verdict = classify_localization_candidate(node_id, kind)
        assert verdict.primary is False


def test_synthetic_top_level_aggregate_is_structural_only():
    verdict = classify_localization_candidate("app.py::<top-level>", "function")

    assert verdict.eligible is False
    assert verdict.reason == STRUCTURAL_ONLY


def test_unknown_kind_is_unsupported_not_silently_admitted():
    assert _reason("app.py::thing", "wormhole") == UNSUPPORTED_CANDIDATE_KIND
    assert _reason("app.py::thing", "") == UNSUPPORTED_CANDIDATE_KIND


def test_implementation_kinds_are_the_primary_localization_kinds():
    for kind in sorted(IMPLEMENTATION_KINDS):
        verdict = classify_localization_candidate("core/app.py::thing", kind)
        assert verdict.eligible is True, kind
        assert verdict.primary is True, kind


def test_kind_sets_do_not_overlap():
    assert not (IMPLEMENTATION_KINDS & STRUCTURAL_KINDS)
    assert not (IMPLEMENTATION_KINDS & DOCUMENT_KINDS)
    assert not (DOCUMENT_KINDS & STRUCTURAL_KINDS)


# ---------------------------------------------------------------------------
# Source binding
# ---------------------------------------------------------------------------

def test_a_candidate_must_carry_a_repo_relative_file_binding():
    assert _reason("justaname", "function") == INVALID_SOURCE_BINDING
    assert _reason("/abs/app.py::run", "function") == INVALID_SOURCE_BINDING
    assert _reason("C:/repo/app.py::run", "function") == INVALID_SOURCE_BINDING
    assert _reason("../outside.py::run", "function") == INVALID_SOURCE_BINDING


def test_unrecognised_source_language_is_an_invalid_binding():
    assert _reason("thing.xyz::run", "function") == INVALID_SOURCE_BINDING
    assert _reason("Makefile::run", "function") == INVALID_SOURCE_BINDING


def test_a_project_map_hotspot_with_an_empty_symbol_half_is_refused():
    """PROJECT_MAP really does emit rows like ``core/thing.py::``.

    They reach ``select_entry_nodes`` as raw hotspots, so the direct-hit
    shortcut has to refuse them on their binding rather than on a prefix.
    """
    assert _reason("core/sandbox_patch_graduation_review.py::", "function") == (
        INVALID_SOURCE_BINDING
    )


def test_span_must_be_internally_consistent():
    ok = classify_localization_candidate(
        "core/app.py::run", "function", metadata={"start": 10, "end": 40}
    )
    assert ok.eligible is True

    for span in [{"start": 40, "end": 10}, {"start": -1, "end": 4},
                 {"start": "10", "end": 40}, {"start": 10, "end": None}]:
        verdict = classify_localization_candidate(
            "core/app.py::run", "function", metadata=span
        )
        assert verdict.eligible is False, span
        assert verdict.reason == INVALID_SOURCE_BINDING


def test_span_must_fit_the_file_it_claims():
    context = {"file_bytes": {"core/app.py": 100}}

    inside = classify_localization_candidate(
        "core/app.py::run", "function",
        metadata={"start": 0, "end": 90}, source_context=context,
    )
    outside = classify_localization_candidate(
        "core/app.py::run", "function",
        metadata={"start": 0, "end": 900}, source_context=context,
    )

    assert inside.eligible is True
    assert outside.eligible is False
    assert outside.reason == INVALID_SOURCE_BINDING


def test_a_node_without_span_metadata_is_still_judged_on_its_binding():
    """Old artifacts predate span metadata; absence is not a rejection."""
    verdict = classify_localization_candidate("core/app.py::run", "function")

    assert verdict.eligible is True


# ---------------------------------------------------------------------------
# Source role: code, documents, and the leak between them
# ---------------------------------------------------------------------------

def test_an_implementation_symbol_parsed_out_of_a_document_is_a_role_leak():
    assert _reason("README.md::parse_config", "function") == SOURCE_ROLE_MISMATCH
    assert _reason("notes.txt::Widget", "class") == SOURCE_ROLE_MISMATCH


def test_document_sections_stay_eligible_for_the_analysis_evidence_path():
    """WAITER.LIVE.1 routes analysis away from defect localization, so a
    document object never competes as a defect target - but it is still a
    legitimate thing to retrieve, and this phase does not remove it."""
    verdict = classify_localization_candidate("README.md::project_overview", "section")

    assert verdict.eligible is True
    assert verdict.primary is False
    assert verdict.source_role != SOURCE_ROLE_CODE


def test_a_prose_object_claimed_from_source_code_is_also_a_role_leak():
    assert _reason("core/app.py::project_overview", "section") == SOURCE_ROLE_MISMATCH


def test_source_role_map_mirrors_the_language_map_it_derives_from():
    """The role view lives outside ``config`` so pure modules can read it.
    Pin it to the map it mirrors so the two cannot drift."""
    assert set(SOURCE_ROLE_BY_EXTENSION) == set(SUPPORTED_EXTENSIONS)

    expected_code = {
        extension
        for extension, language in LANGUAGE_MAP.items()
        if language not in {"document", "text", "json"}
    }
    actual_code = {
        extension
        for extension, role in SOURCE_ROLE_BY_EXTENSION.items()
        if role == SOURCE_ROLE_CODE
    }
    assert actual_code == expected_code & set(SUPPORTED_EXTENSIONS)


# ---------------------------------------------------------------------------
# Tests and benchmarks are not garbage
# ---------------------------------------------------------------------------

def test_test_file_implementation_candidates_survive():
    """T3 and many legitimate tasks need test-file changes, and
    CONTROL.SAFETY.LIVE.1 - not this filter - decides authority."""
    verdict = classify_localization_candidate(
        "tests/test_index_completion.py::write_text", "function"
    )

    assert verdict.eligible is True
    assert verdict.primary is True


def test_benchmark_and_vendor_paths_are_not_excluded_by_this_boundary():
    for node_id in [
        "benchmarks/cases/python/x/buggy_repo/main.py::run",
        "node_modules/pkg/index.js::render",
        "vendor/lib/thing.go::Serve",
    ]:
        assert is_localization_candidate(node_id, "function"), node_id


# ---------------------------------------------------------------------------
# Rejection vocabulary is bounded and deterministic
# ---------------------------------------------------------------------------

def test_every_reason_comes_from_the_bounded_vocabulary():
    samples = [
        ("core/app.py::run", "function"),
        ("core/app.py", "file"),
        ("call::helper", "call"),
        ("core/app.py::<top-level>", "function"),
        ("core/app.py::a\nb", "function"),
        ("core/app.py::run", "wormhole"),
        ("README.md::parse_config", "function"),
        ("README.md::intro", "section"),
        ("naked", "function"),
        ("thing.xyz::run", "function"),
    ]
    for node_id, kind in samples:
        assert _reason(node_id, kind) in LOCALIZATION_REJECTION_REASONS


def test_reasons_are_deterministic_across_repeated_classification():
    samples = [
        ("core/app.py::run", "function"),
        ("call::e(\n", "call"),
        ("core/app.py::pt =", "function"),
        ("README.md::intro", "section"),
    ]
    first = [_reason(node_id, kind) for node_id, kind in samples]
    for _ in range(5):
        assert [_reason(node_id, kind) for node_id, kind in samples] == first


def test_eligible_is_the_only_non_rejection_reason():
    eligible = classify_localization_candidate("core/app.py::run", "function")
    assert eligible.reason == ELIGIBLE
    assert eligible.eligible is True

    rejected = classify_localization_candidate("core/app.py", "file")
    assert rejected.reason != ELIGIBLE


def test_verdict_exposes_bounded_debugging_metadata_only():
    payload = classify_localization_candidate(
        "core/app.py::run", "function", metadata={"start": 0, "end": 12}
    ).as_dict()

    assert set(payload) == {
        "node_id",
        "node_kind",
        "candidate_eligible",
        "eligibility_reason",
        "primary_localization_candidate",
        "source_file",
        "source_role",
    }
    # No source text, no content, no snippet.
    assert not any("content" in key or "text" in key for key in payload)


# ---------------------------------------------------------------------------
# Old persisted artifacts
# ---------------------------------------------------------------------------

def test_old_persisted_malformed_nodes_are_filtered_at_use_time():
    """A graph artifact built before the parser fix stays readable, and its
    malformed nodes are labelled rather than pretended away."""
    legacy = build_graph(
        nodes=[
            {"id": "call::e(\n  ", "type": "call", "label": "e(\n  "},
            {"id": "agents/deepseek_client.py::cont", "type": "function"},
            {"id": "core/code_dna.py::' -> Path:\n   '", "type": "function"},
            {"id": "core/code_dna.py::_classify_indent", "type": "function"},
        ],
        edges=[
            {"source": "core/code_dna.py::_classify_indent",
             "target": "call::e(\n  ", "type": "calls"},
        ],
    )

    metrics = localization_population_metrics(legacy)
    eligible = control_engine.eligible_localization_nodes(legacy)

    assert "core/code_dna.py::_classify_indent" in eligible
    assert "call::e(\n  " not in eligible
    assert "core/code_dna.py::' -> Path:\n   '" not in eligible
    assert metrics["rejected_by_reason"][MALFORMED_SYMBOL] == 1
    assert metrics["rejected_by_reason"][STRUCTURAL_ONLY] == 1

    # Historical evidence is not rewritten: the nodes and their edges remain.
    assert len(legacy.nodes) == 4
    assert len(legacy.edges) == 1


# ---------------------------------------------------------------------------
# Freshness: a parser fix must not be masked by a reused index
# ---------------------------------------------------------------------------

def test_policy_fingerprint_binds_the_symbol_extraction_version(tmp_path, monkeypatch):
    before = compute_policy_fingerprint(str(tmp_path))

    monkeypatch.setattr(
        "core.repo_ignore.SYMBOL_EXTRACTION_VERSION",
        SYMBOL_EXTRACTION_VERSION + "_next",
    )
    after = compute_policy_fingerprint(str(tmp_path))

    assert before != after


def test_fingerprint_is_stable_so_no_run_is_forced_to_rebuild(tmp_path):
    _write(tmp_path, "app.py", "def run():\n    return 1\n")

    assert compute_policy_fingerprint(str(tmp_path)) == compute_policy_fingerprint(
        str(tmp_path)
    )


# ---------------------------------------------------------------------------
# Graph connectivity is not the candidate population
# ---------------------------------------------------------------------------

def test_ineligible_nodes_keep_their_nodes_and_edges(tmp_path):
    _requires_python_parser(tmp_path)
    _write(
        tmp_path,
        "app.py",
        "def helper():\n    return 1\n\n\ndef caller():\n    return helper()\n",
    )

    graph = build_graph_from_repo(str(tmp_path))
    eligible = control_engine.eligible_localization_nodes(graph)

    call_nodes = [n for n in graph.nodes if n.startswith("call::")]
    assert call_nodes, "the fixture should still produce call nodes"
    for node_id in call_nodes:
        assert node_id not in eligible

    # The dependency relation survives even though the node cannot be a
    # primary localization target.
    call_edges = [e for e in graph.edges if e.target in call_nodes]
    assert call_edges
    resolved = [
        e for e in graph.edges
        if e.type == "resolved_call" and e.target == "app.py::helper"
    ]
    assert resolved, "caller -> helper must still be represented"


def test_neighbour_expansion_cannot_promote_a_structural_node_to_a_candidate(
    monkeypatch,
):
    """A bookkeeping aggregate must not become a candidate by adjacency.

    ``app.py::<top-level>`` is a legitimate ``resolved_call`` source, so DFS
    reaches it from a real symbol.  It may still be traversed - the relation
    is real - but it never becomes an evidence row of its own.
    """
    graph = ProgramGraph()
    graph.add_node("app.py::handler", "function")
    graph.add_node("app.py::<top-level>", "function")
    graph.add_node("app.py::helper", "function")
    graph.add_edge("app.py::<top-level>", "app.py::handler", "resolved_call")
    graph.add_edge("app.py::<top-level>", "app.py::helper", "resolved_call")

    monkeypatch.setattr(
        control_engine,
        "explain_symbol",
        lambda graph, symbol: {
            "symbol": symbol,
            "called_by": ["app.py::<top-level>"] if symbol == "app.py::handler" else [],
            "calls": ["app.py::helper"] if symbol == "app.py::<top-level>" else [],
        },
    )
    monkeypatch.setattr(control_engine, "impact_analysis", lambda graph, symbol: [])
    monkeypatch.setattr(
        control_engine,
        "analyze_symbol_risk",
        lambda graph, symbol: {"risk_level": "low", "risk_score": 0},
    )

    evidence = control_engine.control_dfs_v2(graph, ["app.py::handler"])
    symbols = [item["symbol"] for item in evidence]

    assert "app.py::handler" in symbols
    assert "app.py::<top-level>" not in symbols
    # Traversal still passed through it, so its callee is reached.
    assert "app.py::helper" in symbols


def test_file_nodes_remain_in_the_graph_while_being_ineligible(tmp_path):
    _requires_python_parser(tmp_path)
    _write(tmp_path, "app.py", "def run():\n    return 1\n")

    graph = build_graph_from_repo(str(tmp_path))

    assert "app.py" in graph.nodes
    assert not is_localization_candidate("app.py", graph.nodes["app.py"].type)
    assert any(e.source == "app.py" and e.type == "contains" for e in graph.edges)


def test_population_metrics_are_deterministic_counts(tmp_path):
    _requires_python_parser(tmp_path)
    _write(tmp_path, "app.py", "def run():\n    return helper()\n")

    graph = build_graph_from_repo(str(tmp_path))
    metrics = localization_population_metrics(graph)

    assert metrics["total_graph_nodes"] == len(graph.nodes)
    assert (
        metrics["eligible_localization_candidates"] + metrics["rejected_candidates"]
        == metrics["total_graph_nodes"]
    )
    assert sum(metrics["nodes_by_kind"].values()) == metrics["total_graph_nodes"]
    assert sum(metrics["rejected_by_reason"].values()) == metrics["rejected_candidates"]
    assert metrics == localization_population_metrics(graph)
    # Counts only - never a quality score.
    assert not any("score" in key for key in metrics)


# ---------------------------------------------------------------------------
# Small-repo compatibility
# ---------------------------------------------------------------------------

def test_calc_small_repo_localization_still_works(tmp_path):
    _requires_python_parser(tmp_path)
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")

    graph = build_graph_from_repo(str(tmp_path))
    entry_nodes = control_engine.fallback_entry_nodes_from_graph(
        graph, "fix add in calc.py, it returns the wrong value", limit=6
    )

    assert entry_nodes[0] == "calc.py::add"
    assert is_localization_candidate("calc.py::add", "function")


def test_flat_pytest_solution_localization_still_works(tmp_path):
    _requires_python_parser(tmp_path)
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
    entry_nodes = control_engine.fallback_entry_nodes_from_graph(
        graph, "the length_of_longest_substring assertion fails", limit=6
    )

    assert "solution.py::length_of_longest_substring" in entry_nodes
    resolved = control_engine.resolve_symbol_to_graph_nodes(
        graph, "length_of_longest_substring", query="fix the sliding window"
    )
    assert "solution.py::length_of_longest_substring" in resolved


def test_a_test_file_symbol_can_still_be_selected(tmp_path):
    _requires_python_parser(tmp_path)
    _write(tmp_path, "tests/test_thing.py", "def test_thing():\n    assert True\n")

    graph = build_graph_from_repo(str(tmp_path))
    entry_nodes = control_engine.fallback_entry_nodes_from_graph(
        graph, "why does test_thing fail in pytest?", limit=6
    )

    assert "tests/test_thing.py::test_thing" in entry_nodes


# ---------------------------------------------------------------------------
# The live dogfood target
# ---------------------------------------------------------------------------

def test_classify_indent_is_an_eligible_primary_candidate():
    verdict = classify_localization_candidate(
        "core/code_dna.py::_classify_indent", "function"
    )

    assert verdict.eligible is True
    assert verdict.primary is True
    assert verdict.reason == ELIGIBLE


def test_classify_indent_defect_remains_reproducible():
    """RETRIEVE.LIVE.1 must not fix the retrieval target it is measured on.

    Realistically nested two-space code spends most of its indented lines at
    depth two or deeper, so those lines start with four spaces and outvote the
    depth-one lines.  The reported style is therefore ``4space``.
    """
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
    assert _classify_indent(nested_two_space) != "2space"


def test_classify_indent_source_is_untouched_by_this_phase():
    source = inspect.getsource(_classify_indent)

    assert 'counts["4space"] += 1' in source
    assert 'elif line.startswith("  "):' in source
    assert "most_common(1)[0][0]" in source


# ---------------------------------------------------------------------------
# Static boundaries for the phase itself
# ---------------------------------------------------------------------------

def test_ranking_coefficients_are_unchanged():
    """Population hygiene must be measurable separately from ranking."""
    item = {
        "called_by": ["a", "b"],
        "calls": ["c"],
        "impact": ["d"],
        "risk": {"risk_level": "high", "risk_score": 7},
        "query_bonus": 2,
        "graph_weight": 1.5,
        "depth": 2,
    }
    # 2*2 + 1 + 1*2 + 7 + 5 + 2*2 + 1.5 - 2*0.5
    assert control_engine.score_control_node(item) == pytest.approx(23.5)

    empty = {"risk": {"risk_level": "low", "risk_score": 0}}
    assert control_engine.score_control_node(empty) == pytest.approx(1.0)


def test_graph_weight_defaults_are_unchanged():
    from graph.weights import compute_node_weights

    signature = inspect.signature(compute_node_weights)
    assert signature.parameters["alpha"].default == 2.0
    assert signature.parameters["beta"].default == 1.0
    assert signature.parameters["gamma"].default == 0.5


def test_identity_profile_multipliers_are_unchanged():
    from core.context_profiles import score_multiplier_for_path

    assert score_multiplier_for_path("readme.md", "identity") == 4.0
    assert score_multiplier_for_path("docs/x.md", "identity") == 3.0
    assert score_multiplier_for_path("tests/x.py", "identity") == 0.05
    assert score_multiplier_for_path("core/x.py", "default") == 1.0


def test_the_boundary_module_makes_no_model_network_or_repository_call():
    module = PROJECT_ROOT / "core" / "localization_candidate.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden = {
        "requests", "httpx", "urllib", "socket", "http", "aiohttp",
        "openai", "google", "anthropic", "ollama", "agents",
        "sentence_transformers", "torch", "numpy", "faiss", "chromadb",
        "psycopg", "sqlalchemy", "database", "subprocess", "os", "shutil",
        "glob",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)

    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    for traversal in {"walk", "iterdir", "rglob", "glob", "listdir", "scandir"}:
        assert traversal not in called
    assert "open" not in {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_boundary_never_reports_a_confidence_or_score():
    verdict = classify_localization_candidate("core/app.py::run", "function")

    for field in verdict.__dataclass_fields__:
        assert "score" not in field
        assert "confidence" not in field
        assert "weight" not in field


def test_eligibility_grants_no_authority():
    """A candidate is navigation evidence.  It is not defect grounding, not a
    patch basis and not write authority."""
    verdict = classify_localization_candidate("core/app.py::run", "function")
    payload = verdict.as_dict()

    for field in list(verdict.__dataclass_fields__) + list(payload):
        lowered = field.lower()
        assert "authoriz" not in lowered
        assert "grounded" not in lowered
        assert "patch" not in lowered or lowered.startswith("primary")


def test_graph_builder_adds_no_second_repository_traversal():
    """Span metadata comes from the file the builder already had open."""
    source = (PROJECT_ROOT / "graph" / "builder.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    walkers = {"iter_repo_files", "walk", "iterdir", "rglob", "glob", "listdir",
               "scandir", "read_text", "read_bytes"}
    call_sites: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.id if isinstance(node.func, ast.Name)
            else node.func.attr if isinstance(node.func, ast.Attribute)
            else None
        )
        if name in walkers:
            call_sites.append(name)

    # Exactly the traversal and the single per-file read that already existed.
    assert sorted(call_sites) == ["iter_repo_files", "read_text"]
