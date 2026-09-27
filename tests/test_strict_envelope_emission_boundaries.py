"""Static boundary regressions for WORKER.DECL.2A.1.

The focused suite owns behaviour.  These tests prove the experiment has only
the machinery needed to *ask*: it cannot reach a model, a provider SDK, the
network, a subprocess or the filesystem; it cannot re-run the legacy extractor;
it cannot loosen or shadow WORKER.DECL.2A's frozen parser; it cannot add a
second call or a repair turn; and it cannot change which patch a run applies.

Honest *negative* guardrail keys are intentionally permitted as literals:
``model_call_added = False`` is a denial, not a capability.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from core.strict_envelope_emission import (
    PROVIDER_NATIVE_JSON_MEDIA_TYPE,
    STRICT_ENVELOPE_PROMPT_BLOCK,
    TRANSPORT_STRATEGIES,
    strict_envelope_emission_guardrails,
)
from core.worker_patch_envelope import PARSE_STATUSES


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"

_EMISSION = _CORE_ROOT / "strict_envelope_emission.py"
_FROZEN_ENVELOPE = _CORE_ROOT / "worker_patch_envelope.py"
_WIRING_SITE = _CORE_ROOT / "run_lifecycle.py"
_LEGACY_EXTRACTOR = _CORE_ROOT / "json_utils.py"
_PROMPTER = _CORE_ROOT / "prompter.py"
_CONTROL_ENGINE = _CORE_ROOT / "control_engine.py"
_EXECUTOR = _REPOSITORY_ROOT / "patching" / "patch_plan_executor.py"
_GEMINI = _REPOSITORY_ROOT / "agents" / "gemini_client.py"
_BASELINE = _REPOSITORY_ROOT / "scripts" / "strict_envelope_emission_baseline.py"

#: Sites that ask a real, already-scheduled model call for the strict envelope.
_PRODUCER_SITES = (
    _CORE_ROOT / "pipeline.py",
    _CORE_ROOT / "sleeping_consultant.py",
    _REPOSITORY_ROOT / "scripts" / "run_patch_proposal_queue.py",
)

#: The one function at each producer site that performs the patch-generation call.
_GENERATOR_FUNCTIONS = {
    "pipeline.py": "run_draft_pipeline",
    "sleeping_consultant.py": "_generate_patch_plan",
    "run_patch_proposal_queue.py": "_generate_patch_payload",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _imported_modules(tree: ast.AST) -> Iterable[tuple[str, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module, node.lineno
            for alias in node.names:
                yield (f"{module}.{alias.name}" if module else alias.name), node.lineno


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _functions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _function(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(fn for fn in _functions(_tree(path)) if fn.name == name)


def _returns(fn: ast.AST) -> list[ast.Return]:
    """Return statements in source order (``ast.walk`` is breadth-first)."""
    found = [node for node in ast.walk(fn) if isinstance(node, ast.Return)]
    return sorted(found, key=lambda node: node.lineno)


# -- S10/S31: the contract cannot reach a model -------------------------------

def test_the_contract_imports_no_provider_sdk_or_agent():
    """S7: core must not import a provider SDK, native mode or not."""
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    for forbidden in (
        "google",
        "google.genai",
        "genai",
        "ollama",
        "openai",
        "anthropic",
    ):
        assert not any(
            name == forbidden or name.startswith(forbidden + ".") for name in modules
        ), forbidden
    assert not any(name.split(".")[0] == "agents" for name in modules)


def test_the_contract_reaches_no_network_or_subprocess():
    """S35: no request is added because none can be made from here."""
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    for forbidden in ("requests", "httpx", "urllib", "socket", "http", "subprocess"):
        assert not any(
            name == forbidden or name.startswith(forbidden + ".") for name in modules
        ), forbidden


def test_the_contract_traverses_no_repository():
    """S34: traversal delta is zero, structurally."""
    source = _EMISSION.read_text(encoding="utf-8")
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    assert "pathlib" not in modules
    assert "shutil" not in modules
    for forbidden in ("open(", "rglob(", "iterdir(", "os.walk(", "glob("):
        assert forbidden not in source, forbidden
    # os is imported for exactly one thing: reading the opt-in flag.
    environ_reads = [
        call for call, name in _calls(_tree(_EMISSION)) if name == "os.environ.get"
    ]
    assert len(environ_reads) == 1


def test_the_contract_makes_no_model_call_of_any_kind():
    source = _EMISSION.read_text(encoding="utf-8")
    for forbidden in (
        "run_gemini_request",
        "run_deepseek_review",
        "generate_content",
        "ollama.chat",
        "OllamaClient",
    ):
        assert forbidden not in source, forbidden
    guardrails = strict_envelope_emission_guardrails()
    assert guardrails["model_call_added"] is False
    assert guardrails["repair_call_added"] is False
    assert guardrails["formatting_call_added"] is False
    assert guardrails["retry_on_strict_rejection"] is False


def test_the_contract_carries_no_clock():
    """A replayed response must observe identically; no time may enter."""
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    assert "time" not in modules
    assert "datetime" not in modules
    assert "uuid" not in modules
    assert "random" not in modules


# -- S9: the frozen parser is used, never shadowed ----------------------------

def test_the_contract_is_not_a_second_reader():
    """S9: no fence reader, no brace scanner, no prose stripper lives here."""
    source = _EMISSION.read_text(encoding="utf-8")
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    assert "re" not in modules
    assert "json" not in modules
    for forbidden in (
        "json.loads",
        "raw_decode",
        "JSONDecoder",
        "strip_fence",
        "extract_json_block",
    ):
        assert forbidden not in source, forbidden


def test_the_only_fence_this_module_knows_is_a_sentence_asking_for_none():
    """The fence marker appears in the request text and in no code path.

    A module that both *asks* for unfenced output and *reads* fenced output
    would be exactly the second heuristic reader WORKER.DECL.2A refused, so the
    marker is confined to the module-level rule text no function can reach.
    """
    tree = _tree(_EMISSION)
    for function in _functions(tree):
        for node in ast.walk(function):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "```" not in node.value, function.name


def test_the_contract_defines_no_parse_status_of_its_own():
    """S9: adoption may not be raised by inventing a friendlier status."""
    source = _EMISSION.read_text(encoding="utf-8")
    for status in PARSE_STATUSES:
        assert f'= "{status}"' not in source, status
    assert "PARSE_STATUSES" in source


def test_the_frozen_parser_file_is_untouched_by_this_phase():
    source = _FROZEN_ENVELOPE.read_text(encoding="utf-8")
    assert "WORKER.DECL.2A.1" not in source
    assert "strict_envelope_emission" not in source
    assert "transport_strategy" not in source
    assert "response_mime_type" not in source


def test_the_legacy_extractor_is_still_untouched():
    source = _LEGACY_EXTRACTOR.read_text(encoding="utf-8")
    assert "WORKER.DECL" not in source
    assert "strict_envelope_emission" not in source
    assert "_find_balanced_json_objects" in source
    assert "def extract_json_block" in source


def test_the_contract_never_re_runs_the_legacy_extractor():
    """S12: both parsers read the response once, upstream; not again here."""
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    assert "core.json_utils" not in modules
    assert not any(name.startswith("core.json_utils.") for name in modules)


# -- S1/S2: authority stays exactly where it was ------------------------------

def test_the_contract_applies_no_patch_and_selects_no_plan():
    source = _EMISSION.read_text(encoding="utf-8")
    for forbidden in (
        "apply_patch_plan",
        "patch_plan_operations",
        "run_patch_plan_with_artifacts",
        "patch_plan_executor",
    ):
        assert forbidden not in source, forbidden
    guardrails = strict_envelope_emission_guardrails()
    assert guardrails["strict_plan_applied"] is False
    assert guardrails["patch_authority_changed"] is False
    assert guardrails["patch_semantics_changed"] is False
    assert guardrails["patch_schema_changed"] is False
    assert guardrails["authoritative_effect"] is False


def test_no_observation_field_names_an_authority():
    from core.strict_envelope_emission import StrictEnvelopeEmissionObservation

    for field in StrictEnvelopeEmissionObservation.__dataclass_fields__:
        lowered = field.lower()
        for authority_word in (
            "authority",
            "approved",
            "approval",
            "allowed",
            "permission",
            "merge",
            "grant",
        ):
            assert authority_word not in lowered, field


def test_the_prompt_block_grants_nothing_and_asks_only_for_a_format():
    """S39: the request may constrain the shape; it may not confer a power."""
    lowered = STRICT_ENVELOPE_PROMPT_BLOCK.lower()
    for granting in (
        "you may write",
        "you are authorised",
        "you are authorized",
        "approved to",
        "permission to",
        "merge is allowed",
        "may merge",
        "apply the patch",
        "bypass",
        "no review",
        "without approval",
    ):
        assert granting not in lowered, granting
    # Authority words appear once each, inside the sentence that refuses them.
    refusal = "do not add any field describing permission, approval, review,"
    assert refusal in lowered
    assert "rejected by name" in lowered
    for authority_word in ("permission", "approval", "merge", "authority"):
        assert lowered.count(authority_word) == 1, authority_word


def test_the_contract_promotes_no_checker():
    """S38: CHECK.1, CHECK.2, CHECK.LIVE.1 and 1B are untouched and unread."""
    source = _EMISSION.read_text(encoding="utf-8")
    modules = {name for name, _ in _imported_modules(_tree(_EMISSION))}
    for checker in (
        "core.post_run_reconciliation",
        "core.post_run_reconciliation_shadow",
        "core.post_run_observation",
        "core.live_worker_declaration",
        "core.live_worker_report",
        "core.goal_fidelity_review",
    ):
        assert checker not in modules, checker
    assert "CHECK.2" not in source
    assert strict_envelope_emission_guardrails()["checker_promoted"] is False


def test_the_contract_declares_no_change_intent():
    """S37: WORKER.DECL.2B owns the field; nothing here anticipates it."""
    source = _EMISSION.read_text(encoding="utf-8")
    # Named only in prose explaining that it is *not* implemented here.
    tree = _tree(_EMISSION)
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    for later_phase in ("CHANGE_INTENT", "DECLARED_CHANGES", "PRE_EXECUTION_INTENT"):
        assert later_phase not in assigned, later_phase
    assert '"change_intent"' not in source
    assert strict_envelope_emission_guardrails()["change_intent_declared"] is False


# -- S5/S22: the prompt is appended to, never rewritten -----------------------

def test_the_prompt_helper_only_appends():
    """The existing patch contract cannot be edited, reordered or dropped."""
    fn = _function(_EMISSION, "apply_strict_emission_to_prompt")
    body = ast.dump(fn)
    for rewriting in ("replace", "Subscript", "split", "format", "sub"):
        assert rewriting not in body, rewriting
    # Two returns: the untouched prompt, and prompt + suffix.
    returns = _returns(fn)
    assert len(returns) == 2
    assert isinstance(returns[0].value, ast.Name)
    assert returns[0].value.id == "prompt"
    assert isinstance(returns[1].value, ast.BinOp)


def test_the_client_keyword_helper_returns_nothing_when_off():
    returns = _returns(_function(_EMISSION, "strict_emission_client_kwargs"))
    assert len(returns) == 2
    assert isinstance(returns[0].value, ast.Dict)
    assert returns[0].value.keys == []


def test_the_patch_contract_files_are_untouched():
    """S4: the prompt's patch rules and schema stay exactly where they are."""
    for frozen in (_PROMPTER, _CONTROL_ENGINE, _EXECUTOR):
        source = frozen.read_text(encoding="utf-8")
        assert "WORKER.DECL.2A.1" not in source, frozen.name
        assert "strict_envelope_emission" not in source, frozen.name
        assert "STRICT_WORKER_PATCH_ENVELOPE_EMISSION" not in source, frozen.name


# -- S10/S11/S29: the producer sites ------------------------------------------

def test_every_producer_site_applies_the_directive_to_its_existing_prompt():
    for path in _PRODUCER_SITES:
        source = path.read_text(encoding="utf-8")
        assert "apply_strict_emission_to_prompt" in source, path.name
        assert "strict_emission_client_kwargs" in source, path.name
        # The guarded observer is what runs live; the raising one never appears.
        assert "safe_observe_strict_envelope_emission" in source, path.name
        assert " observe_strict_envelope_emission(" not in source.replace(
            "safe_observe_strict_envelope_emission(", "safe_observe("
        ), path.name


def test_no_producer_site_makes_a_second_model_call():
    """S10: model_call_delta = 0, function by function."""
    for path in _PRODUCER_SITES:
        fn = _function(path, _GENERATOR_FUNCTIONS[path.name])
        model_calls = [
            name
            for _call, name in _calls(fn)
            if name
            in {
                "run_gemini_request",
                "run_gemini_request_2",
                "run_deepseek_review",
                "run_local_critique",
            }
        ]
        assert len(model_calls) == 1, (path.name, model_calls)


def test_no_producer_site_retries_because_a_strict_parse_failed():
    """S11: a strict rejection is never a reason to ask the model again."""
    for path in _PRODUCER_SITES:
        source = path.read_text(encoding="utf-8")
        for retry_trigger in (
            "strict_status ==",
            "strict_status !=",
            "if strict_status",
            "not strict_available",
            "if not observation",
            "surrounding_prose_rejected",
        ):
            assert retry_trigger not in source, (path.name, retry_trigger)


def test_no_producer_site_applies_or_selects_a_strict_plan():
    for path in _PRODUCER_SITES:
        source = path.read_text(encoding="utf-8")
        assert "patch_plan_operations" not in source, path.name
        assert "parse_strict_worker_patch_envelope" not in source, path.name


# -- S7/S29: the provider adapter ---------------------------------------------

def test_the_provider_adapter_does_not_import_the_core_contract():
    """Provider transport and envelope semantics stay separable in both directions."""
    modules = {name for name, _ in _imported_modules(_tree(_GEMINI))}
    assert not any("strict_envelope_emission" in name for name in modules)
    assert "WORKER.DECL.2A.1" in _GEMINI.read_text(encoding="utf-8")


def test_the_provider_adapter_adds_no_second_request():
    """S35: the media type alters an existing request; it creates none."""
    tree = _tree(_GEMINI)
    generate_calls = [
        name for _call, name in _calls(tree) if name.endswith("generate_content")
    ]
    # Exactly the two pre-existing request sites: draft and reviewer.
    assert len(generate_calls) == 2


def test_the_provider_adapter_omits_the_argument_unless_asked():
    """S23: the off path constructs the config from exactly today's keywords."""
    fn = _function(_GEMINI, "_generation_config")
    body = ast.dump(fn)
    assert "temperature" in body
    assert "response_mime_type" in body
    conditionals = [node for node in ast.walk(fn) if isinstance(node, ast.If)]
    assert len(conditionals) == 1


def test_the_only_native_transport_implemented_is_the_one_advertised():
    """S17: a label must correspond to a code path that exists."""
    assert set(PROVIDER_NATIVE_JSON_MEDIA_TYPE) == {"google"}
    assert "provider_native_schema" not in TRANSPORT_STRATEGIES
    assert "response_schema" not in _EMISSION.read_text(encoding="utf-8")


# -- S16/S18/S27: the persistence sink ----------------------------------------

def test_the_wiring_site_only_accepts_an_already_typed_observation():
    renderer = _function(_WIRING_SITE, "_strict_envelope_emission_record")
    checks = [call for call, name in _calls(renderer) if name == "isinstance"]
    assert len(checks) == 1
    assert isinstance(checks[0].args[1], ast.Name)
    assert checks[0].args[1].id == "StrictEnvelopeEmissionObservation"


def test_the_emission_artifact_write_is_flag_guarded():
    tree = _tree(_WIRING_SITE)
    guarded = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and any(
            name == "is_strict_envelope_emission_enabled"
            for _call, name in _calls(node.test)
        )
    ]
    assert len(guarded) == 1
    assert "EMISSION_ARTIFACT_NAME" in ast.dump(guarded[0])


def test_the_observation_reaches_exactly_one_sink():
    """S18: no second unrestricted raw-response artifact, and no result key."""
    source = _WIRING_SITE.read_text(encoding="utf-8")
    assert source.count("EMISSION_ARTIFACT_NAME") == 2  # import + one write
    assert "result_metadata" not in source.split("_strict_envelope_emission_record")[1][:400]


# -- S21: the baseline tool ---------------------------------------------------

def test_the_baseline_performs_no_model_or_network_call():
    modules = {name for name, _ in _imported_modules(_tree(_BASELINE))}
    for forbidden in (
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "google",
        "ollama",
    ):
        assert not any(
            name == forbidden or name.startswith(forbidden + ".") for name in modules
        ), forbidden
    assert not any(name.split(".")[0] == "agents" for name in modules)


def test_the_baseline_never_feeds_its_shape_label_to_the_strict_parser():
    """The legacy reader explains a rejection; it cannot produce an acceptance."""
    fn = _function(_BASELINE, "classify_recorded_response")
    names = [name for _call, name in _calls(fn)]
    assert names.count("parse_strict_worker_patch_envelope") == 1
    strict_calls = [
        call
        for call, name in _calls(fn)
        if name == "parse_strict_worker_patch_envelope"
    ]
    # The strict parser reads the recorded text itself, not a cleaned-up copy.
    assert len(strict_calls) == 1
    assert isinstance(strict_calls[0].args[0], ast.Name)
    assert strict_calls[0].args[0].id == "text"


def test_the_baseline_lives_outside_every_run_path():
    for path in _PRODUCER_SITES + (_WIRING_SITE, _EMISSION):
        source = path.read_text(encoding="utf-8")
        assert "strict_envelope_emission_baseline" not in source, path.name
