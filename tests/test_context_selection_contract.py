"""End-to-end pure-contract tests for CTX.SELECT.1."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from core.context_selection import (
    CONTRACT_JSON_NAME,
    CONTRACT_MARKDOWN_NAME,
    DEFAULT_PATCH_SCORE_THRESHOLD,
    MAX_PROPOSED_READS,
    MAX_TOTAL_PROPOSED_READ_BYTES,
    build_candidate_selection_contract,
    build_context_selection_plan,
    build_proposed_read_set,
    classify_proposed_patch_files,
    render_candidate_selection_contract_json,
    render_candidate_selection_contract_markdown,
)
from core.file_capabilities import classify_file_capability
from scripts.create_context_selection_contract import run_create_context_selection_contract


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PURE_CORE_MODULES = (
    PROJECT_ROOT / "core" / "file_capabilities.py",
    PROJECT_ROOT / "core" / "file_actionability.py",
    PROJECT_ROOT / "core" / "file_candidate_selector.py",
    PROJECT_ROOT / "core" / "context_selection.py",
)
CTX_SEARCH_RUNTIME_MODULES = (
    PROJECT_ROOT / "core" / "bounded_lexical_search.py",
    PROJECT_ROOT / "core" / "context_search_runtime.py",
)
CTX_DIRECT_READ_RUNTIME_MODULES = (
    PROJECT_ROOT / "core" / "direct_file_reader.py",
    PROJECT_ROOT / "core" / "direct_context_runtime.py",
    PROJECT_ROOT / "core" / "direct_read_receipt.py",
)
CTX_PATCH_RUNTIME_MODULES = (
    PROJECT_ROOT / "core" / "file_patchability.py",
    PROJECT_ROOT / "core" / "direct_patch_candidate_gate.py",
    PROJECT_ROOT / "core" / "proposed_patch_set.py",
)


def _candidate(
    path: str,
    *,
    score: int = 80,
    size_bytes: int | None = 100,
    role: str = "primary_or_supporting_target",
    action: str = "propose_patch_candidate",
    editability: str = "editable",
    readability: str = "readable_text",
    direct_read_allowed: bool = True,
    repository_contained: bool = True,
    generated: bool = False,
    vendor: bool = False,
    evidence: tuple[str, ...] = ("direct_symbol_reference",),
    validation_candidates: tuple[str, ...] = ("tests/test_target.py",),
    warnings: tuple[str, ...] = (),
    authoritative_source: str | None = None,
) -> dict[str, object]:
    return {
        "path": path,
        "actionability_score": score,
        "size_bytes": size_bytes,
        "role": role,
        "action": action,
        "editability": editability,
        "readability": readability,
        "direct_read_allowed": direct_read_allowed,
        "repository_contained": repository_contained,
        "generated": generated,
        "vendor": vendor,
        "positive_evidence": [{"kind": kind, "detail": kind} for kind in evidence],
        "validation_candidates": list(validation_candidates),
        "warnings": list(warnings),
        "authoritative_source": authoritative_source,
    }


def _excluded_reasons(result: object) -> dict[str, str]:
    return {item.path: item.reason for item in result.excluded}


def test_proposed_read_set_respects_hard_file_limit() -> None:
    candidates = [
        _candidate(f"src/file_{index:02d}.py", score=100 - index)
        for index in range(12)
    ]

    result = build_proposed_read_set(candidates, max_files=999)

    assert result.max_files == MAX_PROPOSED_READS == 8
    assert len(result.selected) == MAX_PROPOSED_READS
    assert result.truncated is True
    assert set(_excluded_reasons(result).values()) == {"file_limit"}
    assert result.as_dict()["read_authority"] is False
    assert result.as_dict()["write_authority"] is False


def test_proposed_read_set_accepts_exact_byte_boundary_and_rejects_overflow() -> None:
    candidates = [
        _candidate("src/first.py", score=100, size_bytes=600_000),
        _candidate("src/second.py", score=90, size_bytes=448_576),
        _candidate("src/overflow.py", score=80, size_bytes=1),
    ]

    result = build_proposed_read_set(candidates, max_total_bytes=9_999_999)

    assert result.max_total_bytes == MAX_TOTAL_PROPOSED_READ_BYTES == 1_048_576
    assert result.paths == ("src/first.py", "src/second.py")
    assert result.total_estimated_bytes == 1_048_576
    assert _excluded_reasons(result)["src/overflow.py"] == "byte_limit"


def test_read_planner_preserves_security_exclusions_at_high_score() -> None:
    candidates = [
        _candidate(
            ".env",
            score=100,
            action="requires_human_approval",
            editability="sensitive_requires_approval",
            readability="sensitive",
            direct_read_allowed=False,
        ),
        _candidate(
            "certs/private.pem",
            score=100,
            action="exclude",
            editability="forbidden",
            readability="opaque_binary",
            direct_read_allowed=False,
        ),
        _candidate("src/router.py", score=70),
    ]

    result = build_proposed_read_set(candidates)

    assert result.paths == ("src/router.py",)
    assert _excluded_reasons(result)[".env"] == "security_or_readability_gate"
    assert _excluded_reasons(result)["certs/private.pem"] == "security_or_readability_gate"


@pytest.mark.parametrize("path", [".env", "certs/private.pem", "../outside.py"])
def test_planners_reclassify_untrusted_high_score_capability_hints(path: str) -> None:
    malicious_hint = _candidate(
        path,
        score=100,
        action="propose_patch_candidate",
        editability="editable",
        readability="readable_text",
        direct_read_allowed=True,
    )

    reads = build_proposed_read_set([malicious_hint])
    patches = classify_proposed_patch_files(
        [malicious_hint],
        proposed_read_set=reads,
    )

    assert reads.selected == ()
    assert patches.selected == ()
    assert all(item.write_authority is False for item in patches.selected)


def test_read_planner_favors_target_dependency_test_config_and_contrast_diversity() -> None:
    candidates = [
        _candidate("core/router.py", score=100),
        _candidate("core/near_duplicate.py", score=99),
        _candidate("core/caller.py", score=90, role="dependency_or_caller"),
        _candidate("tests/test_router.py", score=80, role="validation"),
        _candidate("pyproject.toml", score=70, role="configuration"),
        _candidate("docs/alternative.py", score=60),
    ]

    result = build_proposed_read_set(candidates, max_files=5, diversity_policy=True)

    assert result.paths == (
        "core/router.py",
        "core/caller.py",
        "tests/test_router.py",
        "pyproject.toml",
        "docs/alternative.py",
    )
    reasons = dict(result.selection_reasons)
    assert reasons["core/router.py"] == "primary likely target"
    assert reasons["core/caller.py"] == "immediate dependency or caller"
    assert reasons["tests/test_router.py"] == "corresponding validation or test"
    assert reasons["pyproject.toml"] == "task-relevant configuration"
    assert reasons["docs/alternative.py"] == "contrasting candidate for ambiguity"


def test_unknown_size_fails_closed_with_bounded_runtime_strategy() -> None:
    result = build_proposed_read_set([_candidate("src/unknown.py", size_bytes=None)])

    assert result.selected == ()
    assert result.total_estimated_bytes == 0
    assert result.excluded[0].reason == "unknown_size"
    assert "CTX.READ.1" in (result.excluded[0].recommended_strategy or "")


def test_read_planner_respects_a_negative_candidate_action_decision() -> None:
    candidate = _candidate(
        "src/zero_evidence.py",
        score=0,
        action="supporting_context_only",
    )
    candidate["decision"] = {"can_propose_read": False}

    result = build_proposed_read_set([candidate])

    assert result.selected == ()
    assert _excluded_reasons(result) == {
        "src/zero_evidence.py": "candidate_action_gate"
    }


def test_read_planner_is_deterministic_and_does_not_mutate_inputs() -> None:
    candidates = [
        _candidate("src/b.py", score=70),
        _candidate("tests/test_a.py", score=65, role="validation"),
        _candidate("src/a.py", score=90),
    ]
    before = copy.deepcopy(candidates)

    first = build_proposed_read_set(candidates)
    second = build_proposed_read_set(reversed(candidates))

    assert first == second
    assert first.as_dict() == second.as_dict()
    assert candidates == before


def test_proposed_patch_candidate_is_a_read_subset_and_has_no_write_authority() -> None:
    candidates = [
        _candidate("core/router.py", score=90),
        _candidate("core/support.py", score=45, action="propose_read"),
    ]
    reads = build_proposed_read_set(candidates)

    patches = classify_proposed_patch_files(candidates, proposed_read_set=reads)

    assert patches.paths == ("core/router.py",)
    assert set(patches.paths) <= set(reads.paths)
    assert patches.write_authority is False
    assert patches.selected[0].write_authority is False
    assert patches.selected[0].as_dict()["write_authority"] is False
    assert patches.as_dict()["write_authority"] is False


def test_read_only_file_cannot_become_a_patch_candidate() -> None:
    candidate = _candidate(
        "docs/policy.md",
        score=100,
        action="propose_read",
        editability="read_only",
    )
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert reads.paths == ("docs/policy.md",)
    assert patches.selected == ()
    assert _excluded_reasons(patches)["docs/policy.md"] == "editability_gate"


def test_sensitive_file_requires_approval_and_enters_neither_proposal_set() -> None:
    candidate = _candidate(
        ".env",
        score=100,
        action="requires_human_approval",
        editability="sensitive_requires_approval",
        readability="sensitive",
        direct_read_allowed=False,
    )
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert reads.selected == ()
    assert patches.selected == ()
    assert _excluded_reasons(reads)[".env"] == "security_or_readability_gate"
    assert _excluded_reasons(patches)[".env"] == "not_in_proposed_read_set"


def test_unsupported_readable_text_may_be_inspect_before_patch_with_warning() -> None:
    candidate = _candidate(
        "core/router.yaml",
        score=67,
        action="propose_inspect_then_patch",
        editability="editable_with_review",
        warnings=(
            "raw textual understanding only; AST and dependency completeness are unavailable",
        ),
    )
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert patches.paths == ("core/router.yaml",)
    selected = patches.selected[0]
    assert selected.recommended_action == "inspect_then_patch"
    assert selected.write_authority is False
    assert "editability review is required" in selected.warnings
    assert any("raw textual understanding only" in warning for warning in selected.warnings)


def test_validation_gap_is_explicit_without_blocking_candidate_classification() -> None:
    candidate = _candidate(
        "core/router.py",
        score=85,
        validation_candidates=(),
    )
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert patches.paths == ("core/router.py",)
    assert patches.selected[0].validation_candidates == ()
    assert "validation_gap: no validation candidate supplied" in patches.selected[0].warnings


def test_sensitive_or_nonvalidation_paths_cannot_suppress_validation_gap() -> None:
    target = _candidate(
        "core/router.py",
        score=85,
        validation_candidates=("tests/test_router.py", "docs/check.py"),
    )
    sensitive_test = _candidate(
        "tests/test_router.py",
        score=85,
        role="validation",
        action="requires_human_approval",
        editability="sensitive_requires_approval",
        readability="sensitive",
        direct_read_allowed=False,
        validation_candidates=(),
    )
    unrelated = _candidate(
        "docs/check.py",
        score=45,
        role="supporting_context",
        action="supporting_context_only",
        validation_candidates=(),
    )
    candidates = [target, sensitive_test, unrelated]
    reads = build_proposed_read_set(candidates)
    patches = classify_proposed_patch_files(candidates, proposed_read_set=reads)

    selected = next(item for item in patches.selected if item.path == "core/router.py")
    assert selected.validation_candidates == ()
    assert "validation_gap: no validation candidate supplied" in selected.warnings


def test_string_warning_is_preserved_as_one_warning() -> None:
    candidate = _candidate(
        "core/router.py",
        score=85,
        validation_candidates=(),
    )
    candidate["warnings"] = "one complete warning"
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert "one complete warning" in patches.selected[0].warnings
    assert "o" not in patches.selected[0].warnings


@pytest.mark.parametrize("score", [-1, 101])
def test_flat_candidate_adapter_rejects_out_of_range_scores(score: int) -> None:
    candidate = _candidate("core/router.py", score=score)

    with pytest.raises(ValueError, match="bounded 0-100"):
        build_proposed_read_set([candidate])


def test_filename_only_evidence_cannot_create_a_proposed_patch_file() -> None:
    candidate = _candidate(
        "core/router.py",
        score=100,
        evidence=("exact_filename_match", "filename_token_match"),
    )
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert patches.selected == ()
    assert _excluded_reasons(patches)["core/router.py"] == "filename_only_evidence"


def test_generated_file_redirects_to_known_authoritative_source() -> None:
    candidate = _candidate(
        "generated/client.py",
        score=95,
        action="redirect_to_authoritative_source",
        editability="generated_do_not_edit",
        generated=True,
        authoritative_source="schema/client.json",
    )
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files([candidate], proposed_read_set=reads)

    assert reads.paths == ("generated/client.py",)
    assert patches.selected == ()
    assert patches.excluded[0].reason == "generated_or_vendor"
    assert patches.excluded[0].redirect_path == "schema/client.json"


def test_patch_threshold_cannot_be_lowered_below_contract_minimum() -> None:
    candidate = _candidate("core/router.py", score=59)
    reads = build_proposed_read_set([candidate])
    patches = classify_proposed_patch_files(
        [candidate],
        proposed_read_set=reads,
        score_threshold=1,
    )

    assert patches.score_threshold == DEFAULT_PATCH_SCORE_THRESHOLD == 60
    assert patches.selected == ()
    assert _excluded_reasons(patches)["core/router.py"] == "below_patch_score_threshold"


def test_context_plan_preserves_candidate_read_patch_hierarchy_without_approval() -> None:
    capability = classify_file_capability("core/router.py", size_bytes=128)
    plan = build_context_selection_plan(
        [capability],
        task_terms=["router"],
        user_named_files=["core/router.py"],
    )
    rendered = plan.as_dict()

    candidate_paths = {item.path for item in plan.candidate_files}
    assert candidate_paths == {"core/router.py"}
    assert set(plan.proposed_read_files.paths) <= candidate_paths
    assert set(plan.proposed_patch_files.paths) <= set(plan.proposed_read_files.paths)
    assert plan.escalation == "direct_context_sufficient"
    assert rendered["write_authority"] is False
    assert "approved_writable_files" not in rendered
    assert "approved_writable_files" not in json.dumps(rendered)


def test_context_plan_expands_requested_prefix_to_exact_auto_readable_files() -> None:
    capabilities = [
        classify_file_capability("config/.env", size_bytes=32),
        classify_file_capability("config/app.py", size_bytes=64),
        classify_file_capability("core/router.py", size_bytes=64),
    ]

    plan = build_context_selection_plan(
        capabilities,
        task_terms=["app"],
        include_paths=["config/"],
    )

    request = plan.lexical_search_request
    assert request.include_paths == ("config/app.py",)
    assert request.scope_mode == "explicit_paths"
    assert "config/.env" not in request.include_paths


def test_context_plan_rejects_unbounded_one_shot_term_input() -> None:
    capability = classify_file_capability("core/router.py", size_bytes=64)

    with pytest.raises(ValueError, match="task_terms exceeds"):
        build_context_selection_plan(
            [capability],
            task_terms=(f"term_{index}" for index in range(513)),
        )


@pytest.mark.parametrize(
    "identity_state",
    [
        "uninitialized",
        "initial_confirmation_required",
        "major_change_confirmation_required",
        "blocked",
    ],
)
def test_plan_works_without_vector_embeddings_manifest_or_confirmed_identity(identity_state: str) -> None:
    capability = classify_file_capability("core/router.py", size_bytes=128)

    plan = build_context_selection_plan(
        [capability],
        user_named_files=["core/router.py"],
        vector_database_available=False,
        embedding_provider_enabled=False,
        canonical_manifest_available=False,
        canonical_identity_state=identity_state,
    )

    assert plan.candidate_files
    assert plan.proposed_read_files.paths == ("core/router.py",)
    assert any("vector database unavailable" in warning for warning in plan.warnings)
    assert any("embedding provider disabled" in warning for warning in plan.warnings)
    assert any("canonical manifest unavailable" in warning for warning in plan.warnings)
    assert not any("unknown canonical identity" in warning for warning in plan.warnings)


def test_contract_contains_all_required_sections_exact_limits_and_independence_flags() -> None:
    contract = build_candidate_selection_contract()

    assert contract["phase_id"] == "CTX.SELECT.1"
    assert contract["contract_status"] == "complete"
    assert contract["produced_sets"] == [
        "candidate_files",
        "proposed_read_files",
        "proposed_patch_files",
    ]
    assert set(contract) >= {
        "capability_states",
        "repository_size_strategy",
        "evidence_sources",
        "lexical_search_limits",
        "actionability_score",
        "editability_state_overrides",
        "read_set_budget",
        "patch_candidate_rules",
        "sensitive_file_rules",
        "vector_index_identity_independence",
        "escalation_policy",
        "deferred_runtime_work",
    }
    assert contract["lexical_search_limits"]["max_matches"] == 200
    assert contract["lexical_search_limits"]["max_files"] == 40
    assert contract["lexical_search_limits"]["max_match_length"] == 240
    assert contract["lexical_search_limits"]["max_expansion_rounds"] == 2
    assert contract["lexical_search_limits"]["match_kind"] == "literal"
    assert contract["lexical_search_limits"]["case_sensitive_option"] is True
    assert contract["lexical_search_limits"]["case_insensitive_option"] is True
    assert contract["lexical_search_limits"]["whole_token_preference_metadata"] is True
    assert contract["read_set_budget"]["max_files"] == 8
    assert contract["read_set_budget"]["max_total_bytes"] == 1_048_576
    assert contract["actionability_score"]["range"] == [0, 100]
    assert contract["actionability_score"]["integer_only"] is True
    assert contract["patch_candidate_rules"]["filename_only_evidence_sufficient"] is False
    assert contract["patch_candidate_rules"]["write_authority"] is False
    assert contract["authority_separation"] == {
        "invariant": "relevance_score != read_authority != write_authority",
        "read_authority_granted": False,
        "write_authority_granted": False,
        "approved_writable_files_produced": False,
    }
    independence = contract["vector_index_identity_independence"]
    for key in (
        "vector_database_required",
        "embedding_provider_required",
        "embedding_signature_required",
        "canonical_manifest_required",
        "canonical_identity_confirmation_required",
        "database_import_or_write",
        "manifest_operation",
        "activation_graph_construction",
    ):
        assert independence[key] is False
    assert all(value is False for value in contract["phase_boundaries"].values())
    assert contract["recommended_next_phase"] == "CTX.READ.1 - Bounded Direct File Read Runtime"


def test_contract_rendering_is_deterministic_and_round_trips_json() -> None:
    contract = build_candidate_selection_contract()

    first_json = render_candidate_selection_contract_json(contract)
    second_json = render_candidate_selection_contract_json(copy.deepcopy(contract))
    first_markdown = render_candidate_selection_contract_markdown(contract)
    second_markdown = render_candidate_selection_contract_markdown(copy.deepcopy(contract))

    assert first_json == second_json
    assert first_markdown == second_markdown
    assert first_json.endswith("\n")
    assert first_markdown.endswith("\n")
    assert json.loads(first_json) == contract
    assert "relevance score != read authority != write authority" in first_markdown
    assert "CTX.READ.1" in first_markdown


def test_contract_artifacts_are_byte_reproducible_with_fixed_names(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = run_create_context_selection_contract(output_root=first_root)
    second = run_create_context_selection_contract(output_root=second_root)
    first_json = Path(first["json_path"])
    first_markdown = Path(first["markdown_path"])
    second_json = Path(second["json_path"])
    second_markdown = Path(second["markdown_path"])

    assert first_json.name == second_json.name == CONTRACT_JSON_NAME
    assert first_markdown.name == second_markdown.name == CONTRACT_MARKDOWN_NAME
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_markdown.read_bytes() == second_markdown.read_bytes()
    assert first_json.read_bytes() == render_candidate_selection_contract_json().encode("utf-8")
    assert first_markdown.read_bytes() == render_candidate_selection_contract_markdown().encode("utf-8")


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _call_leaf(node: ast.Call) -> str | None:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def test_pure_selector_modules_have_static_no_io_db_graph_model_or_subprocess_edges() -> None:
    forbidden_import_roots = {
        "anthropic",
        "httpx",
        "openai",
        "psycopg",
        "requests",
        "socket",
        "sqlite3",
        "sqlalchemy",
        "subprocess",
        "urllib",
    }
    forbidden_project_imports = {
        "core.activation_graph",
        "core.database",
        "core.indexer",
        "core.patching",
        "core.repository_inventory",
        "core.vector_store",
    }
    forbidden_calls = {
        "Popen",
        "apply_patch",
        "build_activation_graph",
        "call",
        "check_call",
        "check_output",
        "connect",
        "create_repository_inventory",
        "exists",
        "glob",
        "index_repository",
        "is_dir",
        "is_file",
        "iterdir",
        "lstat",
        "mkdir",
        "open",
        "popen",
        "read_bytes",
        "read_text",
        "request",
        "resolve",
        "rglob",
        "run",
        "scandir",
        "stat",
        "system",
        "urlopen",
        "walk",
        "write_bytes",
        "write_text",
    }

    violations: list[str] = []
    for path in PURE_CORE_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in _imported_modules(tree):
            if module.split(".", 1)[0] in forbidden_import_roots or module in forbidden_project_imports:
                violations.append(f"{path.name}: import {module}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_leaf(node) in forbidden_calls:
                violations.append(f"{path.name}:{node.lineno}: call {_call_leaf(node)}")

    assert violations == []


def test_contract_generator_writes_only_contract_artifacts_and_has_no_read_or_external_edges() -> None:
    path = PROJECT_ROOT / "scripts" / "create_context_selection_contract.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = _imported_modules(tree)
    calls = {
        leaf
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and (leaf := _call_leaf(node)) is not None
    }

    assert not imports & {
        "subprocess",
        "requests",
        "httpx",
        "openai",
        "sqlite3",
        "core.indexer",
        "core.repository_inventory",
        "core.activation_graph",
    }
    assert not calls & {
        "open",
        "read_text",
        "read_bytes",
        "Popen",
        "run",
        "system",
        "connect",
        "index_repository",
        "build_activation_graph",
        "apply_patch",
    }
    assert calls & {"write_text"} == {"write_text"}


def test_production_python_does_not_activate_selector_runtime() -> None:
    selector_modules = {
        "core.context_selection",
        "core.file_actionability",
        "core.file_candidate_selector",
        "core.file_capabilities",
    }
    allowed = {
        *PURE_CORE_MODULES,
        *CTX_SEARCH_RUNTIME_MODULES,
        *CTX_DIRECT_READ_RUNTIME_MODULES,
        *CTX_PATCH_RUNTIME_MODULES,
        PROJECT_ROOT / "scripts" / "create_context_selection_contract.py",
    }
    violations: list[str] = []

    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if path in allowed or "tests" in path.parts or ".venv" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        used = _imported_modules(tree) & selector_modules
        if used:
            violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: {sorted(used)}")

    assert violations == []


def test_design_record_states_phase_boundaries_and_next_phase() -> None:
    design_path = PROJECT_ROOT / "docs" / "designs" / "2026-08-01-direct-file-candidate-selection.md"
    design = design_path.read_text(encoding="utf-8")

    assert "CTX.SELECT.1" in design
    assert "SUPPORTED_EXTENSIONS" in design
    assert "relevance score" in design
    assert "read authority" in design
    assert "write authority" in design
    assert "1,048,576" in design or "1048576" in design
    assert "CTX.READ.1" in design
    assert "production file contents" in design.casefold()
