"""WORKER.DECL.1 — native worker declaration source qualification.

CHECK.LIVE.1B built a typed seam through which an independently sourced
``WorkerChangeDeclaration`` may reach the frozen CHECK.1 reconciliation.  It
left one question open: *does the real worker/runtime already produce such a
declaration?*

This suite is the executable answer, and the answer is **no**.  Every test here
pins one load-bearing fact behind the classification
``WORKER_DECL_1_SOURCE_UNAVAILABLE``:

1. no worker or model response contract in this repository carries a field
   declaring intended or completed changes, separately from the executable
   patch operations themselves;
2. the last model invocation on every instrumented apply path happens strictly
   *before* patch application, and no worker survives it;
3. no production caller supplies a declaration, so live runs honestly report
   ``legacy_plan_derived``;
4. the model's own already-parsed response reaches the run lifecycle only as
   an opaque replay artifact, never as a declaration.

These are boundary markers, not decoration.  A future phase that changes the
worker protocol to emit a real declaration **must** update this suite — the
failures it produces are the signal that the qualification recorded in
``docs/designs/2026-08-28-native-worker-declaration-source-qualification.md``
has to be redone, not a nuisance to silence.

Nothing here calls a model, opens a socket, or writes outside ``tmp_path``.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Iterable

import pytest

import core.run_lifecycle as run_lifecycle
from core.live_worker_declaration import (
    DECLARATION_SOURCE_INDEPENDENT,
    DECLARATION_SOURCE_LEGACY_PLAN_DERIVED,
)
from core.post_run_reconciliation_shadow import (
    ENVIRONMENT_FLAG,
    RESULT_METADATA_KEYS,
    SHADOW_ARTIFACT_NAME,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

#: The production surfaces a worker/model output could plausibly arrive on.
_PRODUCTION_DIRECTORIES: tuple[str, ...] = (
    "core",
    "agents",
    "patching",
    "web",
    "scripts",
)

#: The one live apply entry point CHECK.LIVE.1B instrumented.
_APPLY_ENTRY_POINT = "run_patch_plan_with_artifacts"

#: Direct model-client entry points.  Everything that transitively calls one of
#: these is treated as a model invocation for ordering purposes.
_MODEL_CLIENT_ENTRY_POINTS: frozenset[str] = frozenset(
    {
        "run_gemini_request",
        "run_gemini_request_2",
        "run_deepseek_review",
        "run_local_critique",
        "generate_with_thought",
    }
)

#: Field names a genuine change declaration would have to use.  None of them
#: may appear in a worker or model *response* contract: if one does, the
#: qualification below is stale and must be redone.
_DECLARATION_FIELD_TOKENS: tuple[str, ...] = (
    "declared_changes",
    "declared_status",
    "declaration",
    "changed_files",
    "files_changed",
    "modified_files",
    "files_touched",
    "touched_files",
    "intended_changes",
    "intended_files",
    "completed_changes",
)


# ── Static helpers ────────────────────────────────────────────────────────────

def _production_sources() -> list[Path]:
    paths: list[Path] = []
    for directory in _PRODUCTION_DIRECTORIES:
        for path in sorted((_REPOSITORY_ROOT / directory).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            paths.append(path)
    return paths


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _call_graph() -> dict[tuple[str, str], set[str]]:
    """Map every production function to the bare names it calls.

    Name-based and deliberately over-approximate: two different functions
    sharing a name are merged, which can only *add* edges.  A test built on it
    therefore cannot miss a model call by being too generous — only by dynamic
    dispatch, which ``test_the_only_post_apply_model_turn_drives_a_different_engine``
    covers explicitly for the one production case that uses it.
    """
    graph: dict[tuple[str, str], set[str]] = {}
    for path in _production_sources():
        try:
            tree = _tree(path)
        except SyntaxError:  # pragma: no cover - a broken file is its own failure
            continue
        for function in _functions(tree):
            called = {
                name
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and (name := _called_name(node)) is not None
            }
            graph[(str(path), function.name)] = called
    return graph


def _model_reaching_names(graph: dict[tuple[str, str], set[str]]) -> frozenset[str]:
    reaching = set(_MODEL_CLIENT_ENTRY_POINTS)
    changed = True
    while changed:
        changed = False
        for (_path, name), called in graph.items():
            if name in reaching:
                continue
            if called & reaching:
                reaching.add(name)
                changed = True
    return frozenset(reaching)


def _module_constant(path: Path, name: str) -> str:
    """Read one module-level string constant without importing the module.

    ``core/prompter.py`` pulls in the project configuration, which needs
    optional third-party packages; the prompt contracts it holds are plain
    string literals, so they are read from the source instead.
    """
    for node in ast.walk(_tree(path)):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            continue
        value = ast.literal_eval(node.value)
        assert isinstance(value, str), f"{name} in {path.name} is not a string"
        return value
    raise AssertionError(f"{name} is not defined in {path.name}")


def _response_contract_literals(path: Path) -> list[str]:
    """Every string literal in a module that specifies a patch response shape.

    A contract is recognised structurally, by naming the executable patch
    fields the runtime later reads — not by where it happens to live.  This
    keeps the scan on prompt/response contracts and off unrelated code that
    merely mentions a path list.
    """
    literals: list[str] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        if '"patch_plan"' in text or '"patch_candidate"' in text:
            literals.append(text)
    return literals


def _apply_call_sites() -> list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, list[int]]]:
    sites: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, list[int]]] = []
    for path in _production_sources():
        if path == _REPOSITORY_ROOT / "core" / "run_lifecycle.py":
            continue  # the definition site, not a caller
        try:
            tree = _tree(path)
        except SyntaxError:  # pragma: no cover
            continue
        for function in _functions(tree):
            lines = [
                node.lineno
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and _called_name(node) == _APPLY_ENTRY_POINT
            ]
            if lines:
                sites.append((path, function, sorted(lines)))
    return sites


# ── Live harness (mirrors the CHECK.LIVE.1 suite) ─────────────────────────────

@pytest.fixture(autouse=True)
def _quiet_brain_stamp(monkeypatch):
    """The brain stamp shells out to git; it is irrelevant to this phase."""
    monkeypatch.setattr(
        run_lifecycle,
        "collect_brain_stamp",
        lambda repo: {"brain_stamp_id": "stamp", "schema_version": 2},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    project = tmp_path / "repo"
    project.mkdir()
    (project / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    return project


def _edit_main() -> list[dict]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": "main.py",
            "target_snippet": "VALUE = 1\n",
            "patched_snippet": "VALUE = 2\n",
        }
    ]


def _receipt(result: dict) -> dict:
    replay_dir = Path(result["replay_dir"])
    return json.loads(
        (replay_dir / SHADOW_ARTIFACT_NAME).read_text(encoding="utf-8")
    )


# ── 1. There is no declaration field to read ──────────────────────────────────

def test_the_patch_response_contract_declares_operations_and_nothing_else():
    """The writer's response schema has no change-declaration field.

    ``PATCH_RESPONSE_SCHEMA`` is the contract the patch-drafting model is held
    to.  Its six keys are a summary, diagnosed issues, the two executable patch
    shapes, a confidence and an escalation flag.  A path only ever appears
    inside ``patch_candidate``/``patch_plan`` — i.e. inside the patch plan
    itself, which §5 of this phase disqualifies as a declaration source.
    """
    # PATCH.AUTHOR.LIVE.2 moved the response envelope into the shared
    # authoring contract so the initial draft and the verification-guided
    # revision render it from one place; core/prompter.py re-exports it, so the
    # literal is read from its new home.
    PATCH_RESPONSE_SCHEMA = _module_constant(
        _REPOSITORY_ROOT / "core" / "patch_authoring_contract.py",
        "PATCH_RESPONSE_SCHEMA",
    )

    for key in (
        "summary",
        "issues",
        "patch_candidate",
        "patch_plan",
        "confidence",
        "needs_escalation",
    ):
        assert f'"{key}"' in PATCH_RESPONSE_SCHEMA

    for token in _DECLARATION_FIELD_TOKENS:
        assert token not in PATCH_RESPONSE_SCHEMA, (
            f"{token!r} appeared in the patch response contract; "
            "WORKER.DECL.1's source qualification must be redone"
        )


def test_only_2b_strict_response_contract_asks_for_a_change_declaration():
    """Only WORKER.DECL.2B carries the newly qualified declaration field.

    ``core/prompter.py`` holds the shared schemas; the dream and proposal-queue
    paths inline their own.  WORKER.DECL.1's original absence finding remains
    pinned for every frozen/legacy contract, while 2B is the single explicit
    additive exception that qualifies a pre-execution intent producer.
    """
    contracts: list[tuple[Path, str]] = []
    for path in _production_sources():
        for literal in _response_contract_literals(path):
            contracts.append((path, literal))

    named = {path.name for path, _literal in contracts}
    assert named == {
        "prompter.py",
        # PATCH.AUTHOR.LIVE.2 owns the one patch-authoring contract both
        # authoring calls render from, so the candidate wire literals live here
        # now. It is a response contract by this test's structural definition
        # and the token check below covers it like every other one.
        "patch_authoring_contract.py",
        "control_engine.py",
        "patch_gates.py",
        "run_patch_proposal_queue.py",
        # WORKER.DECL.2A.1 adds an opt-in output-transport block that restates
        # the patch_plan shape, so it is a response contract by this test's own
        # structural definition and belongs in the scan. The token check below
        # is what matters and still covers it: the block names no declaration
        # field, and WORKER.DECL.2B owns adding one.
        "strict_envelope_emission.py",
        "pre_execution_change_intent.py",
    }, f"the set of patch response contracts moved; saw {sorted(named)}"

    for path, literal in contracts:
        if path.name == "pre_execution_change_intent.py":
            continue
        for token in _DECLARATION_FIELD_TOKENS:
            assert f'"{token}"' not in literal, (
                f"{path.name} names a declaration field {token!r} in a patch "
                "response contract; WORKER.DECL.1's source qualification must "
                "be redone"
            )

    intent_contract = (
        _REPOSITORY_ROOT / "core" / "pre_execution_change_intent.py"
    ).read_text(encoding="utf-8")
    assert '"intended_changes"' in intent_contract
    assert '"pre_execution_intent"' in intent_contract


def test_the_nearest_near_miss_is_a_relevance_hypothesis_not_an_intent():
    """``likely_files`` is the closest candidate, and it still does not qualify.

    The dream planning pass is a genuinely separate model invocation that runs
    before any patch is drafted, and it emits a structured ``likely_files``
    list.  It is nonetheless not a §1.B pre-execution *intent*: the field asks
    which files are relevant to the problem, in a pass whose own prompt forbids
    writing a patch at all.  Reading "files I intend to change" out of it would
    infer a declaration from a field name, which §3 rules out — so this test
    pins what the field actually is, rather than letting a future reader
    mistake it for a wired source.
    """
    consultant = _REPOSITORY_ROOT / "core" / "sleeping_consultant.py"
    source = consultant.read_text(encoding="utf-8")
    planner = next(
        function
        for function in _functions(_tree(consultant))
        if function.name == "_generate_plan_analysis"
    )
    contract = ast.get_source_segment(source, planner) or ""
    assert '"likely_files"' in contract, "the dream planning contract moved"

    assert "Do not write any code patch" in contract
    for token in _DECLARATION_FIELD_TOKENS:
        assert f'"{token}"' not in contract

    # And it is never handed to the apply entry point as a declaration.  The
    # assertion is about declaration provenance, not about the argument list:
    # later phases may thread other bounded observations through this call, and
    # doing so must not silently make the planning payload a declaration.
    planning_names = {"plan_data", "plan_analysis", "likely_files"}
    for node in ast.walk(_tree(consultant)):
        if not isinstance(node, ast.Call) or _called_name(node) != _APPLY_ENTRY_POINT:
            continue
        supplied = {keyword.arg for keyword in node.keywords}
        assert "worker_declaration" not in supplied
        for keyword in node.keywords:
            referenced = {
                inner.id
                for inner in ast.walk(keyword.value)
                if isinstance(inner, ast.Name)
            }
            assert not referenced & planning_names, keyword.arg


def test_the_external_worker_output_contract_is_prose_plus_the_patch_plan():
    """A subprocess worker is asked for exactly two files, neither qualifying.

    ``proposal.md`` is prose (§6 forbids parsing it) and ``patch_plan.json`` is
    the executable plan (§5 forbids deriving a declaration from it).  There is
    no third, declaration-shaped output file in the contract.
    """
    from core.worker_runs import REQUIRED_FILES_FOR_IMPORT
    from scripts.run_subagent_handoff import _RUNNER_HANDOFF_FOOTER

    assert "proposal.md" in _RUNNER_HANDOFF_FOOTER
    assert "patch_plan.json" in _RUNNER_HANDOFF_FOOTER
    for token in _DECLARATION_FIELD_TOKENS:
        assert token not in _RUNNER_HANDOFF_FOOTER

    assert set(REQUIRED_FILES_FOR_IMPORT) == {
        "handoff.md",
        "worker_run.json",
        "proposal.md",
        "patch_plan.json",
    }


def test_the_worker_run_record_is_a_process_record_not_a_self_report():
    """``worker_run.json`` describes the subprocess, never the changes.

    Its keys are timing, exit status and the command line — runner-observed
    facts about a process, not worker-declared facts about a repository.  Even
    ``error`` is set by the runner, so it cannot stand in for §15's
    worker-declared status.
    """
    source = (_REPOSITORY_ROOT / "scripts" / "run_subagent_handoff.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    records = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "record"
        and isinstance(node.value, ast.Dict)
    ]
    assert len(records) == 1, "run_handoff should build exactly one record literal"

    keys = {
        key.value
        for key in records[0].keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert keys == {
        "dry_run",
        "started_at",
        "finished_at",
        "duration_sec",
        "exit_code",
        "timed_out",
        "command",
        "worker",
        "handoff_path",
        "artifact_dir",
        "timeout_sec",
        "error",
    }
    assert not keys & set(_DECLARATION_FIELD_TOKENS)


# ── 2. Every model invocation precedes patch application ──────────────────────

def test_no_apply_path_reaches_a_model_after_applying_its_patch_plan():
    """§3/§4: the last model turn on the instrumented path is pre-application.

    For every production function that calls ``run_patch_plan_with_artifacts``,
    no call that transitively reaches a model client appears after the apply
    call.  The call graph is name-based, so it over-approximates edges and can
    only fail loudly, never quietly pass — with one exception, dynamic
    dispatch, which the next test covers directly.
    """
    graph = _call_graph()
    model_reaching = _model_reaching_names(graph)
    assert _MODEL_CLIENT_ENTRY_POINTS <= model_reaching

    sites = _apply_call_sites()
    assert sites, "no production caller of the apply entry point was found"

    offenders: list[str] = []
    for path, function, apply_lines in sites:
        first_apply = apply_lines[0]
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            name = _called_name(node)
            if name and name in model_reaching and node.lineno > first_apply:
                offenders.append(
                    f"{path.relative_to(_REPOSITORY_ROOT).as_posix()}"
                    f"::{function.name} calls {name} at line {node.lineno}, "
                    f"after applying at line {first_apply}"
                )
    assert offenders == []


def test_the_only_post_apply_model_turn_drives_a_different_engine():
    """The self-correct loop is the one post-apply model turn, and is off-path.

    ``core/self_correct_loop.py`` re-invokes a model after an application to
    draft a *replacement patch*, not to report on the completed one.  It drives
    ``core.executor.Executor`` directly and never reaches the CHECK.LIVE.1B
    boundary, and the patch-plan branch that does reach that boundary returns
    before the loop can start.  So it changes nothing about this phase's
    classification — but it is the one dynamic-dispatch blind spot in the test
    above, so it is pinned explicitly rather than assumed.
    """
    loop_source = (_REPOSITORY_ROOT / "core" / "self_correct_loop.py").read_text(
        encoding="utf-8"
    )
    assert _APPLY_ENTRY_POINT not in loop_source
    assert "post_run_reconciliation" not in loop_source

    pipeline = _tree(_REPOSITORY_ROOT / "core" / "pipeline.py")
    auto_patch = next(
        function
        for function in _functions(pipeline)
        if function.name == "maybe_run_auto_patch"
    )
    plan_branch = next(
        node
        for node in ast.walk(auto_patch)
        if isinstance(node, ast.If)
        and any(
            isinstance(inner, ast.Call)
            and _called_name(inner) == _APPLY_ENTRY_POINT
            for inner in ast.walk(node)
        )
    )
    assert isinstance(plan_branch.body[-1], ast.Return), (
        "the patch-plan branch must return before the self-correct loop, or a "
        "post-apply model turn becomes reachable from an instrumented run"
    )


def test_no_worker_stays_alive_across_the_apply_boundary():
    """§3.4: the subprocess worker has exited long before anything is applied.

    ``run_subagent_handoff`` runs the worker to completion inside a throwaway
    clone and captures files it left behind.  The validation path that later
    applies that plan lives in a different module and starts from artifacts on
    disk, so there is no live worker to ask for a completion report.
    """
    handoff = _tree(_REPOSITORY_ROOT / "scripts" / "run_subagent_handoff.py")
    handoff_calls = {
        _called_name(node)
        for node in ast.walk(handoff)
        if isinstance(node, ast.Call)
    }
    assert "run" in handoff_calls  # subprocess.run — a completed process
    assert _APPLY_ENTRY_POINT not in handoff_calls

    worker_runs = _tree(_REPOSITORY_ROOT / "core" / "worker_runs.py")
    worker_run_calls = {
        _called_name(node)
        for node in ast.walk(worker_runs)
        if isinstance(node, ast.Call)
    }
    assert _APPLY_ENTRY_POINT in worker_run_calls
    assert not worker_run_calls & _MODEL_CLIENT_ENTRY_POINTS


# ── 3. Nothing populates the seam, so production stays legacy ─────────────────

def test_no_production_caller_supplies_a_worker_declaration():
    """§31: the CHECK.LIVE.1B seam has no production producer on the other side.

    This is the single fact that makes the phase outcome ``unavailable``.  When
    a future worker-protocol phase wires a real producer, this test fails — and
    that failure is the prompt to re-run the qualification, not to delete the
    assertion.
    """
    suppliers: list[str] = []
    for path, function, _lines in _apply_call_sites():
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            if _called_name(node) != _APPLY_ENTRY_POINT:
                continue
            for keyword in node.keywords:
                if keyword.arg == "worker_declaration":
                    suppliers.append(
                        f"{path.relative_to(_REPOSITORY_ROOT).as_posix()}"
                        f"::{function.name}"
                    )
    assert suppliers == []


def test_the_parsed_model_response_never_reaches_the_declaration_seam():
    """``control_result`` carries the model's parsed JSON, and is kept opaque.

    ``core/pipeline.py`` and the proposal queue both hand their parsed model
    payload to the run lifecycle as ``control_result``.  It is written to the
    replay bundle and read by nothing else — in particular it is never passed
    into ``LiveExecutionObservation``, so a prose-extracted JSON body cannot
    become a typed declaration by the back door.
    """
    lifecycle = _tree(_REPOSITORY_ROOT / "core" / "run_lifecycle.py")

    observation_calls = [
        node
        for node in ast.walk(lifecycle)
        if isinstance(node, ast.Call)
        and _called_name(node) == "LiveExecutionObservation"
    ]
    assert observation_calls, "the live observation should be built here"
    for call in observation_calls:
        for keyword in call.keywords:
            assert keyword.arg != "control_result"
            if keyword.arg == "worker_declaration":
                assert isinstance(keyword.value, ast.Name)
                assert keyword.value.id == "worker_declaration"

    attach = next(
        function
        for function in _functions(lifecycle)
        if function.name == "_attach_shadow_post_run_reconciliation"
    )
    parameters = {argument.arg for argument in attach.args.kwonlyargs}
    assert "control_result" not in parameters
    assert "worker_declaration" in parameters


def test_a_live_production_run_reports_a_legacy_plan_derived_declaration(
    repo, monkeypatch
):
    """§31: with no native source, a real run says so, every time.

    This drives the real apply engine over a real temporary repository with the
    shadow observer on, exactly as an instrumented dogfood run would.
    """
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _edit_main(), source="worker-decl-1"
    )

    assert result["success"] is True
    receipt = _receipt(result)
    assert receipt["worker_declaration_source"] == DECLARATION_SOURCE_LEGACY_PLAN_DERIVED
    assert receipt["worker_declaration_source"] != DECLARATION_SOURCE_INDEPENDENT
    assert receipt["worker_declaration_invalid"] is False
    assert receipt["independent_worker_declaration_missing"] is True
    assert receipt["authoritative_effect"] is False


def test_a_legacy_declaration_receipt_claims_no_measurable_fidelity(
    repo, monkeypatch
):
    """§9/§17: a plan-derived record must never read as a measured self-report.

    Neither self-report fidelity nor intent fidelity is measurable from a
    declaration the runtime derived from the patch plan it was about to apply.
    The receipt therefore serialises no truthy fidelity claim of any kind.
    """
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    result = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _edit_main(), source="worker-decl-1"
    )
    payload = _receipt(result)

    def _fidelity_claims(node: object, trail: str = "") -> Iterable[tuple[str, object]]:
        if isinstance(node, dict):
            for key, value in node.items():
                where = f"{trail}.{key}" if trail else str(key)
                if "fidelity" in str(key) or "honest" in str(key):
                    yield where, value
                yield from _fidelity_claims(value, where)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from _fidelity_claims(value, f"{trail}[{index}]")

    for where, value in _fidelity_claims(payload):
        assert value is not True, (
            f"{where} claims a measurable fidelity for a legacy plan-derived "
            "declaration"
        )

    assert "worker_honesty" not in json.dumps(payload)
    assert "trust_score" not in json.dumps(payload)


def test_the_qualification_changed_no_authoritative_run_behaviour(
    repo, tmp_path, monkeypatch
):
    """§33/§34/§44: the run is identical whether or not anything is observed.

    Two identical plans over two identical repositories, one observed and one
    not: same success, same applied operations in the same order, same diffs,
    same worktree.  A shadow-only qualification phase may not move any of them.
    """
    other = tmp_path / "other"
    other.mkdir()
    (other / "main.py").write_text("VALUE = 1\n", encoding="utf-8")

    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    unobserved = run_lifecycle.run_patch_plan_with_artifacts(
        str(other), _edit_main(), source="worker-decl-1"
    )

    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    observed = run_lifecycle.run_patch_plan_with_artifacts(
        str(repo), _edit_main(), source="worker-decl-1"
    )

    assert observed["success"] == unobserved["success"] is True
    assert observed["applied_ops"] == unobserved["applied_ops"]
    assert observed["diffs"] == unobserved["diffs"]
    assert observed["rollback_performed"] == unobserved["rollback_performed"]
    assert (repo / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert (other / "main.py").read_text(encoding="utf-8") == "VALUE = 2\n"

    # The observed run gained the existing shadow metadata and nothing else.
    assert set(observed) - set(unobserved) <= set(RESULT_METADATA_KEYS)
