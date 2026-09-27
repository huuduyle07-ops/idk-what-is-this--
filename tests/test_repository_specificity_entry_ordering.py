"""RETRIEVE.LIVE.4 repository-specificity weighted entry ordering regressions.

The phase owns ordering among already-resolved eligible entry candidates.  It
owns neither candidate existence (RETRIEVE.LIVE.1), query-to-symbol recall
(RETRIEVE.LIVE.2/.3), nor downstream CONTROL ranking, so every test here either
pins a specificity fact or proves that a frozen neighbour did not move.
"""

from __future__ import annotations

import ast
import inspect
import math
from pathlib import Path

import pytest

from core import control_engine
from core.identifier_recall import (
    BOUNDED_MORPHOLOGY,
    EXACT_SYMBOL,
    EXACT_TAIL,
    IDENTIFIER_TOKEN,
    MULTI_TOKEN_IDENTIFIER,
    LexicalSpecificityIndex,
    build_lexical_specificity_index,
    decompose_identifier,
    entry_match_order_key,
    extract_query_symbol_candidates,
    match_identifier_entry,
    prepare_identifier_query,
    resolve_identifier_candidates,
    resolve_identifier_recall,
)
from graph.schema import ProgramGraph


PROJECT_ROOT = Path(__file__).resolve().parents[1]

#: The exact raw Round-5 T6 prompt, preserved verbatim from the retained
#: black-box stdin artifact.  Never paraphrase it: the whole failure mode is
#: that ordinary prose words ("at", "back", "repository", "writes") coincide
#: with identifier tokens, so shortening the sentence removes the defect.
ROUND5_T6_PROMPT = (
    "When I point the agent at a repository that uses 2-space indentation, the "
    "patches it writes come back using 4-space indentation instead. Something "
    "looks wrong with the way repo style gets detected. Please find the root "
    "cause and fix it."
)

#: The RETRIEVE.LIVE.2 closure query, which already worked before this phase.
CONCISE_T6_QUERY = "2-space indentation is classified as 4-space"

T6_TARGET = "core/code_dna.py::_classify_indent"

#: Entry cap in production CONTROL.  RETRIEVE.LIVE.4 does not move it.
ENTRY_CAP = 6


def _graph(*node_ids: str) -> ProgramGraph:
    graph = ProgramGraph()
    for node_id in node_ids:
        graph.add_node(node_id, "function")
    return graph


def _ordered(population, query: str, *, limit: int = ENTRY_CAP) -> list[str]:
    result = resolve_identifier_recall(query, population, entry_limit=limit)
    return [match.node_id for match in result.matches]


def _index(population, query: str) -> LexicalSpecificityIndex:
    return resolve_identifier_recall(
        query, population, entry_limit=len(list(population))
    ).specificity


def _match(node_id: str, query: str):
    prepared = prepare_identifier_query(extract_query_symbol_candidates(query))
    return match_identifier_entry(node_id, prepared)


# ---------------------------------------------------------------------------
# Section 5/6 - repository-local document frequency and the IDF formula
# ---------------------------------------------------------------------------


def test_document_frequency_counts_each_candidate_once_per_token():
    index = build_lexical_specificity_index(
        [
            ("indent", "indent", "indent"),
            ("indent", "other"),
            ("unrelated",),
        ],
        tracked_tokens=("indent", "other", "missing"),
    )

    assert index.candidate_count == 3
    # Three occurrences inside one identifier are still one document.
    assert index.token_document_frequency["indent"] == 2
    assert index.token_document_frequency["other"] == 1
    assert index.token_document_frequency.get("missing", 0) == 0


def test_only_tracked_query_tokens_are_indexed():
    index = build_lexical_specificity_index(
        [("alpha", "beta"), ("beta", "gamma")],
        tracked_tokens=("beta",),
    )

    assert dict(index.token_document_frequency) == {"beta": 2}
    assert index.candidate_count == 2


def test_token_idf_is_the_pinned_round5_formula():
    index = build_lexical_specificity_index(
        [("rare",)] + [("common",)] * 9,
        tracked_tokens=("rare", "common"),
    )

    assert index.candidate_count == 10
    # idf(token) = log(N / (1 + df(token))), natural log, exactly as measured.
    assert index.token_idf("rare") == pytest.approx(math.log(10 / 2))
    assert index.token_idf("common") == pytest.approx(math.log(10 / 10))
    # An unseen token is the most specific value the formula can produce.
    assert index.token_idf("absent") == pytest.approx(math.log(10 / 1))


def test_rare_token_is_more_specific_than_a_common_one():
    index = build_lexical_specificity_index(
        [("indent",), ("indent",)] + [("repository",)] * 40,
        tracked_tokens=("indent", "repository"),
    )

    assert index.token_idf("indent") > index.token_idf("repository")


def test_idf_is_floored_at_zero_for_ubiquitous_tokens():
    index = build_lexical_specificity_index(
        [("everywhere",)] * 4,
        tracked_tokens=("everywhere",),
    )

    # log(4/5) is negative; a negative specificity would invert the precision
    # multiplication and rank long identifiers above short ones.
    assert math.log(4 / 5) < 0
    assert index.token_idf("everywhere") == 0.0


def test_empty_population_yields_no_specificity_and_does_not_divide_by_zero():
    index = build_lexical_specificity_index([], tracked_tokens=("indent",))

    assert index.candidate_count == 0
    assert index.token_idf("indent") == 0.0


# ---------------------------------------------------------------------------
# Section 10/16 - max match specificity and identifier precision
# ---------------------------------------------------------------------------


def test_max_match_specificity_uses_the_strongest_matched_query_token():
    population = [f"m{i}.py::repository_helper_{i}" for i in range(40)]
    population.append("core/code_dna.py::_classify_indent")
    result = resolve_identifier_recall(
        "indentation in the repository", population, entry_limit=len(population)
    )
    index = result.specificity
    target = next(m for m in result.matches if m.node_id == T6_TARGET)

    assert target.matched_query_tokens == ("indentation",)
    assert index.max_match_specificity(target) == pytest.approx(
        index.token_idf("indentation")
    )


def test_identifier_precision_is_matched_query_tokens_over_identifier_tokens():
    precise = _match("core/code_dna.py::_classify_indent", "indentation")
    diluted = _match(
        "core/x.py::_classify_indent_repository_configuration_manager", "indentation"
    )
    index = build_lexical_specificity_index([], tracked_tokens=())

    assert precise.identifier_tokens == ("classify", "indent")
    assert index.identifier_precision(precise) == pytest.approx(1 / 2)
    assert diluted.identifier_tokens == (
        "classify",
        "indent",
        "repository",
        "configuration",
        "manager",
    )
    assert index.identifier_precision(diluted) == pytest.approx(1 / 5)


def test_precision_prefers_the_tight_identifier_over_the_diluted_one():
    precise = "core/code_dna.py::_classify_indent"
    diluted = "core/x.py::_classify_indent_repository_configuration_manager"
    population = [diluted, precise]

    assert _ordered(population, "indentation") == [precise, diluted]


def test_precision_is_the_measured_ratio_and_is_not_clamped_to_one():
    """Characterises the reproduced Round-5 definition, quirk included.

    The numerator counts matched *query* tokens and the denominator counts
    *identifier* tokens, so a query carrying both a token and its morphology
    source can push the ratio above 1.  Clamping it to [0, 1] would be a
    different formula from the one that was measured, and would fail here.
    """
    population = ["a.py::indent_of", "b.py::indent"]
    result = resolve_identifier_recall(
        "indent and indentation problems", population, entry_limit=len(population)
    )
    whole = next(m for m in result.matches if m.node_id == "b.py::indent")

    assert whole.matched_query_tokens == ("indent", "indentation")
    assert whole.identifier_tokens == ("indent",)
    assert result.specificity.identifier_precision(whole) == pytest.approx(2.0)
    # The inflated candidate is the one whose identifier is entirely the
    # matched concept, so the ordering it produces is still the intended one.
    assert [m.node_id for m in result.matches][0] == "b.py::indent"


def test_lexical_specificity_score_is_max_specificity_times_precision():
    population = [f"m{i}.py::repository_writer_{i}" for i in range(40)]
    population.append("core/code_dna.py::_classify_indent")
    result = resolve_identifier_recall(
        "indentation in the repository", population, entry_limit=len(population)
    )
    index = result.specificity
    target = next(m for m in result.matches if m.node_id == T6_TARGET)

    assert index.lexical_specificity_score(target) == pytest.approx(
        index.max_match_specificity(target) * index.identifier_precision(target)
    )


# ---------------------------------------------------------------------------
# Sections 12/24/25 - exact identity remains strongest
# ---------------------------------------------------------------------------


def test_exact_symbol_reference_outranks_every_high_specificity_partial():
    population = [
        "core/rareword.py::rareword",
        "core/code_dna.py::_classify_indent",
    ]

    ordered = _ordered(population, "core/code_dna.py::_classify_indent rareword")

    assert ordered[0] == T6_TARGET


def test_exact_tail_reference_outranks_every_high_specificity_partial():
    population = [
        "core/rareword.py::rareword",
        "core/code_dna.py::_classify_indent",
    ]

    ordered = _ordered(population, "_classify_indent is wrong, see rareword")

    assert ordered[0] == T6_TARGET
    match = _match(T6_TARGET, "_classify_indent is wrong, see rareword")
    assert match.entry_match_kind == EXACT_TAIL


def test_exact_identity_beats_a_strictly_higher_specificity_score():
    population = [f"core/f{i}.py::plain_helper_{i}" for i in range(20)]
    population += ["a.py::singleton_token_helper", "b.py::plain"]
    index = _index(population, "plain singleton_token")
    partial = _match("a.py::singleton_token_helper", "plain singleton_token")
    exact = _match("b.py::plain", "plain singleton_token")

    # The partial candidate genuinely scores higher on lexical specificity ...
    assert index.lexical_specificity_score(partial) > index.lexical_specificity_score(
        exact
    )
    # ... and still loses, because "plain" is an explicit symbol reference.
    assert exact.entry_match_kind == EXACT_TAIL
    assert _ordered(population, "plain singleton_token")[0] == "b.py::plain"


# ---------------------------------------------------------------------------
# Sections 13/14 - match-kind treatment and morphology strength
# ---------------------------------------------------------------------------


def test_morphology_beats_generic_multi_token_coincidence():
    """The measured Round-5 failure, reduced to its mechanism."""
    population = [
        f"tests/t{i}.py::test_ordering_falls_back_to_path_when_created_at_{i}"
        for i in range(60)
    ]
    population += [f"core/repo_{i}.py::repository_writes_{i}" for i in range(60)]
    population.append(T6_TARGET)

    query = (
        "When I point the agent at a repository that uses 2-space indentation, "
        "the patches it writes come back using 4-space indentation instead."
    )
    target_match = _match(T6_TARGET, query)

    assert target_match.entry_match_kind == BOUNDED_MORPHOLOGY
    assert _ordered(population, query)[0] == T6_TARGET


def test_morphology_loses_the_tie_break_to_exact_token_equality():
    population = ["a.py::_indentation_signature", "b.py::_indent_of"]
    exact_token = _match("a.py::_indentation_signature", "indentation")
    morphology = _match("b.py::_indent_of", "indentation")
    index = _index(population, "indentation")

    # Identical specificity: one matched query token over two identifier tokens.
    assert index.lexical_specificity_score(exact_token) == pytest.approx(
        index.lexical_specificity_score(morphology)
    )
    assert exact_token.entry_match_kind == IDENTIFIER_TOKEN
    assert morphology.entry_match_kind == BOUNDED_MORPHOLOGY
    assert _ordered(population, "indentation") == [
        "a.py::_indentation_signature",
        "b.py::_indent_of",
    ]


def test_match_kind_information_is_still_reported():
    population = [T6_TARGET, "a.py::_indentation_signature"]
    result = resolve_identifier_recall(CONCISE_T6_QUERY, population)

    kinds = result.as_debug_dict()["entry_match_kind"]
    assert kinds[T6_TARGET] in {
        EXACT_SYMBOL,
        EXACT_TAIL,
        IDENTIFIER_TOKEN,
        MULTI_TOKEN_IDENTIFIER,
        BOUNDED_MORPHOLOGY,
    }


# ---------------------------------------------------------------------------
# Sections 22/23 - rare tokens dominate, without overcorrecting
# ---------------------------------------------------------------------------


def test_rare_meaningful_token_dominates_common_incidental_coincidence():
    population = [f"core/store_{i}.py::repository_index_{i}" for i in range(200)]
    population.append("core/style.py::_indent_width")

    query = (
        "The agent writes into the repository but the indent width the "
        "repository reports back looks wrong."
    )

    assert _ordered(population, query)[0] == "core/style.py::_indent_width"


def test_rare_accidental_token_does_not_beat_a_precise_multi_token_match():
    population = [f"core/v{i}.py::validation_helper_{i}" for i in range(40)]
    population += ["core/a.py::detect_validation_command", "core/b.py::rare_validation_widget"]

    ordered = _ordered(population, "validation command")

    assert ordered[0] == "core/a.py::detect_validation_command"


# ---------------------------------------------------------------------------
# Sections 2/17/18 - matched population, cap and fallback are unchanged
# ---------------------------------------------------------------------------


def test_matched_population_is_identical_before_the_cap():
    population = [f"core/m{i}.py::repository_writes_{i}" for i in range(40)]
    population += [T6_TARGET, "a.py::_indentation_signature", "b.py::unrelated_symbol"]
    prepared = prepare_identifier_query(
        extract_query_symbol_candidates(ROUND5_T6_PROMPT)
    )

    expected = {
        node_id
        for node_id in population
        if match_identifier_entry(node_id, prepared) is not None
    }
    resolved = resolve_identifier_candidates(
        population, prepared.raw_candidates, limit=len(population)
    )

    assert {match.node_id for match in resolved.matches} == expected
    assert "b.py::unrelated_symbol" not in expected


def test_entry_cap_is_unchanged_at_six():
    population = [f"core/m{i}.py::indent_helper_{i}" for i in range(50)]

    assert len(_ordered(population, "indentation")) == ENTRY_CAP
    assert (
        inspect.signature(resolve_identifier_recall).parameters["entry_limit"].default
        == ENTRY_CAP
    )
    assert (
        inspect.signature(control_engine.select_entry_nodes).parameters["limit"].default
        == ENTRY_CAP
    )


def test_structural_and_malformed_candidates_still_cannot_enter():
    graph = ProgramGraph()
    graph.add_node("core/code_dna.py::_classify_indent", "function")
    graph.add_node("call::_classify_indent", "call")
    graph.add_node("core/code_dna.py::_classify_indent::expr::0", "expression")

    eligible = control_engine.eligible_localization_nodes(graph)

    assert "core/code_dna.py::_classify_indent" in eligible
    assert "call::_classify_indent" not in eligible
    assert "core/code_dna.py::_classify_indent::expr::0" not in eligible


def test_unresolved_query_still_falls_back_and_resolved_query_does_not(monkeypatch):
    graph = _graph(T6_TARGET, "core/other.py::unrelated_symbol")
    monkeypatch.setattr(
        control_engine, "load_project_map", lambda repo_path: "hotspot map"
    )
    monkeypatch.setattr(
        control_engine,
        "extract_hotspots_from_project_map",
        lambda project_map, limit=6: ["core/other.py::unrelated_symbol"],
    )
    monkeypatch.setattr(
        control_engine,
        "deep_project_understand",
        lambda *a, **k: {"findings": []},
    )

    resolved = control_engine.select_entry_nodes(
        ROUND5_T6_PROMPT, str(PROJECT_ROOT), graph=graph, return_details=True
    )

    assert T6_TARGET in resolved["query_derived_entry_nodes"]
    assert resolved["fallback_used"] is False
    assert resolved["hotspot_only"] is False


# ---------------------------------------------------------------------------
# Section 19 - query-length robustness
# ---------------------------------------------------------------------------


def _paired_population() -> list[str]:
    population = [f"core/store_{i}.py::repository_writes_at_{i}" for i in range(120)]
    population += [
        f"tests/t{i}.py::test_ordering_falls_back_to_path_when_created_at_{i}"
        for i in range(120)
    ]
    population.append(T6_TARGET)
    return population


def test_concise_symptom_query_keeps_the_meaningful_target():
    assert _ordered(_paired_population(), CONCISE_T6_QUERY)[0] == T6_TARGET


def test_long_filler_heavy_query_keeps_the_meaningful_target():
    ordered = _ordered(_paired_population(), ROUND5_T6_PROMPT)

    assert T6_TARGET in ordered
    assert ordered.index(T6_TARGET) < ENTRY_CAP


# ---------------------------------------------------------------------------
# Sections 26/27 - small repositories and test symbols
# ---------------------------------------------------------------------------


def test_small_calc_repository_still_localizes_add():
    population = ["calc.py::add", "calc.py::subtract", "main.py::main"]

    assert _ordered(population, "calc.py add returns the wrong result")[0] == "calc.py::add"


def test_flat_pytest_repository_still_localizes_the_solution_symbol():
    population = [
        "solution.py::length_of_longest_substring",
        "test_solution.py::test_length_of_longest_substring",
        "main.py::main",
    ]

    ordered = _ordered(population, "length_of_longest_substring returns a wrong length")

    assert ordered[0] == "solution.py::length_of_longest_substring"


def test_test_symbols_are_not_demoted_by_filename():
    population = [
        "tests/test_indent_policy.py::test_indent_policy",
        "core/unrelated.py::unrelated_symbol",
    ]

    assert (
        _ordered(population, "test_indent_policy")[0]
        == "tests/test_indent_policy.py::test_indent_policy"
    )


# ---------------------------------------------------------------------------
# Sections 28/29 - Unicode and case semantics
# ---------------------------------------------------------------------------


def test_unicode_identifier_tokens_carry_specificity():
    population = [f"m{i}.py::compute_単位_{i}" for i in range(30)]
    population.append("core/geometry.py::面積_calculator")
    index = _index(population, "面積 単位")

    assert index.token_idf("面積") > index.token_idf("単位")
    assert _ordered(population, "面積 単位")[0] == "core/geometry.py::面積_calculator"


def test_specificity_uses_the_canonical_case_folded_token_policy():
    population = ["core/http.py::HTTPResponseParser", "core/x.py::other_symbol"]
    index = _index(population, "HTTPResponseParser")

    assert decompose_identifier("HTTPResponseParser") == ("http", "response", "parser")
    assert index.token_document_frequency.get("HTTP") is None
    assert index.token_document_frequency.get("http") == 1


# ---------------------------------------------------------------------------
# Section 39 - determinism
# ---------------------------------------------------------------------------


def test_ordering_is_deterministic_and_tie_breaks_on_canonical_identity():
    population = [f"m{i}.py::_indent_of" for i in range(10)]
    first = _ordered(population, "indentation", limit=len(population))
    second = _ordered(list(reversed(population)), "indentation", limit=len(population))

    assert first == second == sorted(population)


# ---------------------------------------------------------------------------
# Section 38 - bounded observability
# ---------------------------------------------------------------------------


def test_entry_ordering_debug_facts_are_bounded_and_named_as_navigation():
    population = [f"core/m{i}.py::repository_writes_{i}" for i in range(40)]
    population.append(T6_TARGET)
    debug = resolve_identifier_recall(ROUND5_T6_PROMPT, population).as_debug_dict()

    ordering = debug["entry_ordering"]
    assert len(ordering) <= ENTRY_CAP
    row = next(item for item in ordering if item["node_id"] == T6_TARGET)
    assert row["rank"] >= 1
    assert row["matched_query_tokens"] == ["indentation"]
    assert row["strongest_match_token"] == "indentation"
    assert row["strongest_match_token_df"] >= 0
    assert row["identifier_precision"] == pytest.approx(0.5)
    assert row["lexical_specificity_score"] > 0

    # The 19k-symbol vocabulary is never dumped: only query terms are reported.
    frequencies = debug["query_token_document_frequency"]
    assert set(frequencies) <= set(debug["normalized_query_terms"])

    serialized = repr(debug).lower()
    for forbidden in ("confidence", "probability", "authority", "patch_basis"):
        assert forbidden not in serialized


# ---------------------------------------------------------------------------
# Sections 4/33/34/36/37/46 - frozen neighbours and static boundaries
# ---------------------------------------------------------------------------


def test_no_stopwords_were_added_for_the_round5_prompt():
    from core.identifier_recall import _QUERY_STOP_WORDS

    for filler in ("at", "back", "repository", "writes", "point", "come", "using"):
        assert filler not in _QUERY_STOP_WORDS
    assert _QUERY_STOP_WORDS == frozenset(
        {
            "a", "an", "and", "are", "as", "bug", "fix", "for", "from", "how",
            "in", "is", "it", "not", "of", "on", "or", "that", "the", "this",
            "to", "was", "were", "what", "when", "where", "why", "with",
        }
    )


def test_bounded_morphology_and_low_information_policy_are_unchanged():
    from core.identifier_recall import (
        _BOUNDED_QUERY_MORPHOLOGY,
        LOW_INFORMATION_IDENTIFIER_TOKENS,
    )

    assert _BOUNDED_QUERY_MORPHOLOGY == {
        "classification": "classify",
        "classified": "classify",
        "indentation": "indent",
    }
    assert LOW_INFORMATION_IDENTIFIER_TOKENS == frozenset(
        {"data", "get", "item", "main", "run", "set", "test", "value"}
    )


def test_downstream_control_ranking_coefficients_are_unchanged():
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
    assert (
        control_engine.relevance_bonus(
            T6_TARGET, control_engine.query_words(CONCISE_T6_QUERY)
        )
        == 0
    )


def test_specificity_never_becomes_confidence_or_authority():
    fields = set(LexicalSpecificityIndex.__dataclass_fields__)
    for field in fields:
        lowered = field.lower()
        for forbidden in ("confidence", "probability", "author", "patch", "ground"):
            assert forbidden not in lowered

    source = inspect.getsource(LexicalSpecificityIndex).lower()
    for forbidden in ("confidence", "probability", "authority"):
        assert forbidden not in source


def test_entry_ordering_contains_no_target_specific_literal():
    for function in (
        LexicalSpecificityIndex,
        build_lexical_specificity_index,
        entry_match_order_key,
    ):
        source = inspect.getsource(function)
        for literal in ("_classify_indent", "indentation", "2space", "4space", "code_dna"):
            assert literal not in source


def test_specificity_adds_no_model_network_embedding_or_traversal():
    module = PROJECT_ROOT / "core" / "identifier_recall.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    forbidden_imports = {
        "agents", "aiohttp", "anthropic", "chromadb", "database", "faiss",
        "google", "http", "httpx", "json", "numpy", "ollama", "openai", "os",
        "pathlib", "pickle", "requests", "sentence_transformers", "shutil",
        "socket", "sqlite3", "subprocess", "torch", "urllib",
    }
    assert not (imported & forbidden_imports)
    assert "math" in imported

    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls.intersection(
        {"glob", "iterdir", "listdir", "open", "rglob", "scandir", "walk", "write_text"}
    )


def test_classify_indent_remains_intentionally_unfixed():
    from core.code_dna import _classify_indent

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
    assert 'counts["4space"] += 1' in inspect.getsource(_classify_indent)


# ---------------------------------------------------------------------------
# Sections 20/43/44 - the real repository population
# ---------------------------------------------------------------------------


#: Pinned Round-5 reproduction over the *current* eligible population.  The
#: recorded Round-5 run measured 19,177 eligible nodes / 734 matches; the
#: population has since grown by the ANSWER.GROUND.LIVE.2 files, so the legacy
#: rank moved 723 -> 736 while the corrected ordering reproduces the recorded
#: top-6 exactly.
#:
#: ANSWER.GROUND.LIVE.3 grew it again (19,655 nodes), and the sixth slot moved
#: with it.  Ranks 1-5 and the target's rank 2 are untouched; slot 6 is the tail
#: of the cap, held by whichever symbol matches the prompt's *incidental* word
#: "point" ("When I point the agent at a repository ..."), not "indent".  The
#: new ``_annotation_point`` matches that word exactly as ``_point_lines``
#: does, so it takes the slot.  This is a real-population snapshot moving
#: because the repository gained a symbol, not an ordering behaviour change -
#: RETRIEVE ranking code is untouched by that phase.  The tuple is updated
#: rather than dodged by renaming the new helper: choosing identifier names to
#: satisfy this fixture would be hidden coupling that recurs for every future
#: ``*point*`` symbol.
#:
#: INDENT.SEMANTICS.1 added seven symbols carrying the exact token
#: "indentation" (df 11 -> 18), so the prompt's incidental "point" (df 13) is
#: now the rarer word.  Its two 2-token carriers lead, and the target moves from
#: rank 2 to rank 4 — still inside the cap.  That is the snapshot kind of move
#: and the tuple is updated.  What was *not* accepted: that phase first named
#: its oracle ``IndentationObservation``/``IndentationAssessment``/
#: ``observe_indentation``.  As 2-token exact "indentation" identifiers they tied
#: the target on specificity and beat it on exact overlap, which measured rank 7,
#: outside the cap, with the oracle offered as the place to fix T6.  That is a
#: behaviour change for T6, not a snapshot move, so the names got a third word
#: instead.  tests/test_indent_semantics1.py pins the reason.
ROUND5_TOP_SIX = (
    "core/answer_entity_grounding.py::_annotation_point",
    "core/mirror_tunnel_derailment_score.py::_point_lines",
    "core/check_oracle_assessment.py::_indentation_signature",
    "core/code_dna.py::_classify_indent",
    "core/harness_controls.py::_indent_of",
    "core/pipeline.py::_indent_of",
)


@pytest.fixture(scope="module")
def real_eligible_population() -> list[str]:
    """The real eligible population, built once and then released.

    Built directly rather than through ``get_cached_graph`` so a 28k-node graph
    is not parked in the shared process cache for the rest of the suite; only
    the node-id list survives the fixture.
    """
    from core.treesitter_parse import parse_code_with_treesitter
    from graph.builder import build_graph_from_repo

    parsed = parse_code_with_treesitter("def probe():\n    return 1\n", "python")
    if "probe" not in [symbol.get("name") for symbol in parsed.get("symbols", [])]:
        pytest.skip("tree-sitter python grammar unavailable in this environment")

    graph = build_graph_from_repo(str(PROJECT_ROOT))
    population = list(control_engine.eligible_localization_nodes(graph))
    del graph
    if T6_TARGET not in population:
        pytest.skip("real repository graph does not expose the dogfood target")
    return population


def test_round5_long_prompt_puts_the_target_inside_the_entry_cap(
    real_eligible_population,
):
    ordered = _ordered(real_eligible_population, ROUND5_T6_PROMPT)

    assert T6_TARGET in ordered
    assert ordered.index(T6_TARGET) + 1 <= ENTRY_CAP
    assert tuple(ordered) == ROUND5_TOP_SIX


def test_round5_long_prompt_recall_population_is_unchanged(real_eligible_population):
    prepared = prepare_identifier_query(
        extract_query_symbol_candidates(ROUND5_T6_PROMPT)
    )
    expected = {
        node_id
        for node_id in real_eligible_population
        if match_identifier_entry(node_id, prepared) is not None
    }
    resolved = resolve_identifier_candidates(
        real_eligible_population,
        prepared.raw_candidates,
        limit=len(real_eligible_population),
    )

    assert {match.node_id for match in resolved.matches} == expected
    assert T6_TARGET in expected


def test_real_repository_specificity_matches_the_measured_frequencies(
    real_eligible_population,
):
    index = _index(real_eligible_population, ROUND5_T6_PROMPT)
    frequency = index.token_document_frequency

    assert frequency["indentation"] < frequency["indent"] < frequency["repository"]
    assert frequency["writes"] > 100
    assert index.token_idf("indentation") > index.token_idf("repository")
    # The non-negativity floor is inactive on the real measured population.
    assert index.token_idf("repository") > 0


def test_real_repository_concise_and_exact_queries_still_rank_the_target_first(
    real_eligible_population,
):
    assert _ordered(real_eligible_population, CONCISE_T6_QUERY)[0] == T6_TARGET
    assert (
        _ordered(real_eligible_population, "fix _classify_indent in core/code_dna.py")[0]
        == T6_TARGET
    )
    assert (
        _ordered(
            real_eligible_population, "core/code_dna.py::_classify_indent is wrong"
        )[0]
        == T6_TARGET
    )
