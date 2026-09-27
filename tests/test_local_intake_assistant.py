"""INPUT.3 — optional local Intake Assistant tests.

Nothing here opens a socket.  The assistant is inert until ``complete`` runs,
the default suite drives it with scripted responses, and the live smoke is
opt-in.

The point of these tests is the asymmetry: a working local model makes the
wording better, and every other outcome — unreachable, malformed, overreaching
— lands on the deterministic baseline without touching the decision.
"""

from __future__ import annotations

import ast
import json
import os
import sys
import types
from pathlib import Path

import pytest

from core.goal_brief_projection import project_goal_brief
from core.input_understanding import understand_request
from core.intake_assistant import (
    ASSISTANCE_GENERATED,
    ASSISTANCE_STATUS_INVALID,
    ASSISTANCE_STATUS_OK,
    ASSISTANCE_STATUS_REJECTED,
    ASSISTANCE_STATUS_UNAVAILABLE,
    IntakeAssistant,
)
from core.intake_completion import (
    STATE_ASK_CLARIFICATION,
    STATE_GOAL_BRIEF_ASSIST,
    decide_intake_completion,
)
from core.local_intake_assistant import (
    DEFAULT_INTAKE_ASSISTANT_MODEL,
    DEFAULT_INTAKE_ASSISTANT_NUM_CTX,
    FORBIDDEN_RESPONSE_KEYS,
    INTAKE_ASSISTANT_MODEL_ENV,
    INTAKE_ASSISTANT_NUM_CTX_ENV,
    LIVE_SMOKE_ENV_VAR,
    MAX_ASSISTANT_PROMPT_CHARS,
    IntakeAssistanceInvalid,
    IntakeAssistantClient,
    LocalIntakeAssistantClient,
    LocalModelIntakeAssistant,
    ScriptedIntakeAssistantClient,
    build_intake_assistance_request,
    build_live_intake_assistant,
    parse_intake_assistance_response,
    resolve_intake_assistant_model_id,
    resolve_intake_assistant_num_ctx,
)
from core.semantic_waiter import SemanticInterpretation, StaticSemanticInterpreter
from core.task_contract import (
    PROVENANCE_INFERRED,
    ExecutionRequirements,
    TaskClassification,
)


MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "local_intake_assistant.py"


def _contract(text: str, **kwargs):
    kwargs.setdefault(
        "task", TaskClassification(type="unknown", provenance=PROVENANCE_INFERRED)
    )
    return understand_request(
        text, interpreter=StaticSemanticInterpreter(SemanticInterpretation(**kwargs))
    )


def _broad(text: str, **kwargs):
    kwargs.setdefault(
        "task", TaskClassification(type="implementation", provenance=PROVENANCE_INFERRED)
    )
    kwargs.setdefault(
        "execution_requirements",
        ExecutionRequirements(
            multi_stage=True,
            repository_inspection_required=True,
            local_repository_required=True,
            provenance=PROVENANCE_INFERRED,
        ),
    )
    return _contract(text, **kwargs)


def _bundle(contract):
    decision = decide_intake_completion(contract)
    return contract, decision, project_goal_brief(contract, decision)


def _ambiguous():
    return _bundle(
        _contract("Replace it with the other one.", ambiguities=("'it' is unresolved",))
    )


# ══ inertness ═════════════════════════════════════════════════════════════════

def test_module_imports_no_transport_at_module_level():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    top_level = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]

    names: list[str] = []
    for node in top_level:
        if isinstance(node, ast.ImportFrom):
            names.append((node.module or "").split(".")[0])
        else:
            names.extend(alias.name.split(".")[0] for alias in node.names)

    for banned in ("requests", "httpx", "urllib", "socket", "agents", "google", "dotenv"):
        assert banned not in names, f"{banned} must not be imported at module level"


def test_constructing_the_live_assistant_contacts_nothing():
    assistant = build_live_intake_assistant(model="probe-model")

    assert isinstance(assistant, IntakeAssistant)
    assert assistant.model_id == "probe-model"
    assert assistant.call_count == 0


def test_no_cloud_provider_exists_in_input_3():
    source = MODULE_PATH.read_text(encoding="utf-8")

    for token in ("gemini", "genai", "GOOGLE_API_KEY", "openai", "anthropic"):
        assert token.lower() not in source.lower(), f"{token} must not appear in INPUT.3"


def test_the_client_satisfies_the_client_protocol():
    assert isinstance(LocalIntakeAssistantClient(model="m"), IntakeAssistantClient)


# ══ configuration ═════════════════════════════════════════════════════════════

def test_the_default_model_is_the_manual_local_contingency():
    assert DEFAULT_INTAKE_ASSISTANT_MODEL == "qwen3.5:4b"


def test_the_environment_supplies_the_model(monkeypatch):
    monkeypatch.setenv(INTAKE_ASSISTANT_MODEL_ENV, "some-other-local-model")

    assert resolve_intake_assistant_model_id() == "some-other-local-model"


def test_the_default_context_window_is_far_smaller_than_input_2s(monkeypatch):
    monkeypatch.delenv(INTAKE_ASSISTANT_NUM_CTX_ENV, raising=False)

    assert DEFAULT_INTAKE_ASSISTANT_NUM_CTX == 4_096
    assert resolve_intake_assistant_num_ctx() == 4_096


def test_the_environment_can_size_the_context_window(monkeypatch):
    monkeypatch.setenv(INTAKE_ASSISTANT_NUM_CTX_ENV, "2048")

    assert resolve_intake_assistant_num_ctx() == 2_048


def test_a_nonsense_context_window_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv(INTAKE_ASSISTANT_NUM_CTX_ENV, "huge")

    assert resolve_intake_assistant_num_ctx() == DEFAULT_INTAKE_ASSISTANT_NUM_CTX


def test_the_builder_offers_no_provider_choice():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    builder = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_live_intake_assistant"
    )
    params = [arg.arg for arg in builder.args.args + builder.args.kwonlyargs]

    assert "provider" not in params
    assert "providers" not in params


def test_no_module_level_collection_of_models_exists():
    """One configured model, never a list to walk down."""
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))

    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [item.id for item in targets if isinstance(item, ast.Name)]
        if not any("MODEL" in name or "PROVIDER" in name for name in names):
            continue
        assert not isinstance(node.value, (ast.List, ast.Tuple, ast.Set, ast.Dict)), names


# ══ the prompt stays tiny ═════════════════════════════════════════════════════

def test_the_prompt_carries_only_the_intake_slice():
    request = build_intake_assistance_request(*_broad_bundle())

    assert "INTAKE STATE" in request
    assert "OPEN NEEDS" in request
    for forbidden in (
        "repository",
        "project map",
        "index",
        "graph",
        "benchmark",
        "lesson",
        "dream",
        "def ",
        "import ",
    ):
        assert forbidden not in request.lower(), forbidden


def _broad_bundle():
    return _bundle(_broad("Migrate the storage backend to PostgreSQL."))


def test_the_prompt_is_small_enough_for_a_laptop_model():
    request = build_intake_assistance_request(*_broad_bundle())

    assert len(request) < 4_000


def test_a_very_long_request_is_truncated_in_the_prompt_only():
    long_text = "Migrate the storage backend. " * 400
    contract, decision, projection = _bundle(_broad(long_text))

    request = build_intake_assistance_request(contract, decision, projection)

    assert len(contract.raw_request.text) == len(long_text)
    assert len(request) < len(long_text)
    assert MAX_ASSISTANT_PROMPT_CHARS == 600


def test_the_prompt_names_every_open_need():
    contract, decision, projection = _broad_bundle()

    request = build_intake_assistance_request(contract, decision, projection)

    for need_id in decision.need_ids():
        assert need_id in request


# ══ parsing ═══════════════════════════════════════════════════════════════════

def test_a_well_formed_response_is_accepted():
    _, decision, _ = _ambiguous()
    need_id = decision.ambiguities[0].need_id

    assistance = parse_intake_assistance_response(
        json.dumps(
            {
                "summary": "I need one detail before I can act on this.",
                "questions": [
                    {"need_id": need_id, "text": "When you say 'it', which component?"}
                ],
            }
        ),
        decision,
    )

    assert assistance.generated_by_model is True
    assert assistance.status == ASSISTANCE_STATUS_OK
    assert assistance.questions[0].text == "When you say 'it', which component?"
    assert assistance.questions[0].provenance == ASSISTANCE_GENERATED


def test_a_fenced_response_is_accepted():
    _, decision, _ = _ambiguous()
    need_id = decision.ambiguities[0].need_id
    fenced = "Sure!\n```json\n" + json.dumps(
        {"summary": "ok", "questions": [{"need_id": need_id, "text": "Which one?"}]}
    ) + "\n```"

    assert parse_intake_assistance_response(fenced, decision).questions[0].text == "Which one?"


def test_prose_is_refused():
    _, decision, _ = _ambiguous()

    with pytest.raises(IntakeAssistanceInvalid, match="single JSON object"):
        parse_intake_assistance_response("I think you meant the database.", decision)


def test_an_empty_response_is_refused():
    _, decision, _ = _ambiguous()

    with pytest.raises(IntakeAssistanceInvalid, match="empty response"):
        parse_intake_assistance_response("   ", decision)


@pytest.mark.parametrize(
    "key",
    [
        "state",
        "ready_for_future_handoff",
        "semantic_evidence_valid",
        "handoff_blockers",
        "resolved",
        "mode",
        "model",
    ],
)
def test_a_response_claiming_authority_is_refused(key):
    _, decision, _ = _ambiguous()

    with pytest.raises(IntakeAssistanceInvalid, match="claim authority"):
        parse_intake_assistance_response(json.dumps({"summary": "x", key: "y"}), decision)


def test_the_forbidden_key_list_covers_the_decision_surface():
    for key in (
        "state",
        "owner",
        "ready_for_future_handoff",
        "semantic_evidence_status",
        "semantic_evidence_valid",
        "handoff_blockers",
        "contract_present",
        "resolved",
        "routing_allowed",
        "preservation_status",
        "required_before_handoff",
        "authority",
    ):
        assert key in FORBIDDEN_RESPONSE_KEYS


def test_an_unknown_top_level_key_is_refused():
    _, decision, _ = _ambiguous()

    with pytest.raises(IntakeAssistanceInvalid, match="unsupported keys"):
        parse_intake_assistance_response(json.dumps({"summary": "x", "advice": "go"}), decision)


def test_a_question_anchored_to_an_invented_need_is_refused():
    _, decision, _ = _ambiguous()

    with pytest.raises(IntakeAssistanceInvalid, match="unknown need"):
        parse_intake_assistance_response(
            json.dumps({"questions": [{"need_id": "missing:budget_1", "text": "?"}]}),
            decision,
        )


def test_a_question_may_not_carry_its_own_severity():
    _, decision, _ = _ambiguous()
    need_id = decision.ambiguities[0].need_id

    with pytest.raises(IntakeAssistanceInvalid, match="unsupported keys"):
        parse_intake_assistance_response(
            json.dumps(
                {"questions": [{"need_id": need_id, "text": "?", "optional": True}]}
            ),
            decision,
        )


def test_a_suggestion_may_not_carry_its_own_provenance():
    contract, decision, projection = _broad_bundle()

    with pytest.raises(IntakeAssistanceInvalid, match="unsupported keys"):
        parse_intake_assistance_response(
            json.dumps(
                {
                    "field_suggestions": [
                        {
                            "field": "validation",
                            "suggested_value": "pytest",
                            "provenance": "explicit",
                        }
                    ]
                }
            ),
            decision,
        )


def test_severity_is_taken_from_the_policy_not_the_model():
    contract, decision, projection = _broad_bundle()
    optional_need = next(item for item in decision.missing_requirements if not item.required)
    required_need = next(item for item in decision.missing_requirements if item.required)

    assistance = parse_intake_assistance_response(
        json.dumps(
            {
                "questions": [
                    {"need_id": required_need.need_id, "text": "Where should this happen?"},
                    {"need_id": optional_need.need_id, "text": "Any preference?"},
                ]
            }
        ),
        decision,
    )

    by_id = {item.need_id: item for item in assistance.questions}
    assert by_id[required_need.need_id].optional is False
    assert by_id[optional_need.need_id].optional is True


def test_too_many_suggestions_are_refused():
    _, decision, _ = _broad_bundle()

    with pytest.raises(IntakeAssistanceInvalid, match="more suggestions"):
        parse_intake_assistance_response(
            json.dumps(
                {
                    "field_suggestions": [
                        {"field": "validation", "suggested_value": str(index)}
                        for index in range(9)
                    ]
                }
            ),
            decision,
        )


# ══ fallback behaviour ════════════════════════════════════════════════════════

def test_a_working_model_supplies_the_wording():
    contract, decision, projection = _ambiguous()
    need_id = decision.ambiguities[0].need_id
    assistant = LocalModelIntakeAssistant(
        ScriptedIntakeAssistantClient(
            [
                json.dumps(
                    {
                        "summary": "One detail and I can carry on.",
                        "questions": [
                            {"need_id": need_id, "text": "Which component is 'it'?"}
                        ],
                    }
                )
            ]
        )
    )

    assistance = assistant.assist(contract, decision, projection)

    assert assistance.status == ASSISTANCE_STATUS_OK
    assert assistance.generated_by_model is True
    assert assistance.questions[0].text == "Which component is 'it'?"


def test_an_unreachable_model_still_produces_usable_questions():
    contract, decision, projection = _ambiguous()

    class Dead:
        model_id = "dead"

        def complete(self, system_instruction, user_message):
            raise ConnectionError("down")

    assistance = LocalModelIntakeAssistant(Dead()).assist(contract, decision, projection)

    assert assistance.status == ASSISTANCE_STATUS_UNAVAILABLE
    assert assistance.generated_by_model is False
    assert assistance.questions, "deterministic assistance must still ask the question"
    assert assistance.questions[0].need_id == decision.ambiguities[0].need_id


def test_malformed_assistance_falls_back_to_the_deterministic_baseline():
    contract, decision, projection = _ambiguous()
    assistant = LocalModelIntakeAssistant(
        ScriptedIntakeAssistantClient(["not json at all"])
    )

    assistance = assistant.assist(contract, decision, projection)

    assert assistance.status == ASSISTANCE_STATUS_INVALID
    assert assistance.generated_by_model is False
    assert assistance.questions[0].text.startswith("Clarify:")


def test_overreaching_assistance_falls_back_to_the_deterministic_baseline():
    contract, decision, projection = _broad_bundle()
    assistant = LocalModelIntakeAssistant(
        ScriptedIntakeAssistantClient(
            [
                json.dumps(
                    {
                        "summary": "done",
                        "field_suggestions": [
                            {"field": "what", "suggested_value": "migrate the database"}
                        ],
                    }
                )
            ]
        )
    )

    assistance = assistant.assist(contract, decision, projection)

    assert assistance.status == ASSISTANCE_STATUS_REJECTED
    assert assistance.generated_by_model is False
    assert assistance.field_suggestions == ()


def test_an_invented_target_stays_a_suggestion():
    contract, decision, projection = _broad_bundle()
    assistant = LocalModelIntakeAssistant(
        ScriptedIntakeAssistantClient(
            [
                json.dumps(
                    {
                        "summary": "Sounds like a PostgreSQL migration.",
                        "field_suggestions": [
                            {
                                "field": "validation",
                                "suggested_value": "preserve backward compatibility",
                            }
                        ],
                    }
                )
            ]
        )
    )

    assistance = assistant.assist(contract, decision, projection)
    payload = assistance.field_suggestions[0].as_dict()

    assert payload["provenance"] == ASSISTANCE_GENERATED
    assert payload["canonical"] is False
    assert projection.field("validation").entries == ()
    assert "backward compatibility" not in [item.text for item in contract.constraints]


def test_the_assistant_is_called_at_most_once_per_decision():
    contract, decision, projection = _ambiguous()
    assistant = LocalModelIntakeAssistant(ScriptedIntakeAssistantClient(["nope"]))

    assistant.assist(contract, decision, projection)

    assert assistant.call_count == 1


# ══ transport ═════════════════════════════════════════════════════════════════

def _fake_ollama(answer=None, error=None):
    module = types.ModuleType("agents.ollama_client")

    class FakeOllamaClient:
        instances: list = []

        def __init__(self, model=None, base_url=None, timeout=None):
            self.model = model
            self.options = None
            FakeOllamaClient.instances.append(self)

        def generate(self, prompt, system_prompt=None, options=None):
            self.options = options
            if error is not None:
                raise error
            return answer

    module.OllamaClient = FakeOllamaClient
    return module, FakeOllamaClient


@pytest.fixture
def patched_ollama(monkeypatch):
    def _install(answer=None, error=None):
        module, fake = _fake_ollama(answer=answer, error=error)
        fake.instances = []
        monkeypatch.setitem(sys.modules, "agents.ollama_client", module)
        return fake

    return _install


def test_complete_uses_the_single_configured_model(patched_ollama):
    fake = patched_ollama(answer='{"summary": "ok"}')

    result = LocalIntakeAssistantClient(model="only-this-model").complete("sys", "usr")

    assert result == '{"summary": "ok"}'
    assert [instance.model for instance in fake.instances] == ["only-this-model"]


def test_complete_requests_the_small_context_window(patched_ollama):
    fake = patched_ollama(answer="{}")

    LocalIntakeAssistantClient(model="m", num_ctx=2048).complete("sys", "usr")

    assert fake.instances[-1].options == {"num_ctx": 2048}


def test_an_agent_error_sentinel_is_treated_as_unavailable(patched_ollama):
    patched_ollama(answer="AGENT_ERROR: model not found")

    contract, decision, projection = _ambiguous()
    assistant = LocalModelIntakeAssistant(LocalIntakeAssistantClient(model="m"))
    assistance = assistant.assist(contract, decision, projection)

    assert assistance.status == ASSISTANCE_STATUS_UNAVAILABLE
    assert assistance.questions


# ══ live smoke — opt-in only, never required ══════════════════════════════════

def test_the_live_smoke_is_opt_in_and_off_by_default():
    assert LIVE_SMOKE_ENV_VAR == "RUN_LIVE_INTAKE_ASSISTANT_TESTS"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_INTAKE_ASSISTANT_TESTS") != "1",
    reason="live intake assistant smoke is opt-in; set RUN_LIVE_INTAKE_ASSISTANT_TESTS=1",
)
@pytest.mark.parametrize("case", ["ambiguity", "goal_brief"])
def test_live_local_intake_assistant_smoke(case):
    """One tiny bounded phrasing task against the configured local model.

    This is not a Semantic Waiter evaluation.  It measures whether a small
    local model can phrase a question, and — the part that matters — whether
    the canonical decision survived it untouched.
    """
    import time

    from core.input_completion import canonical_intake_fingerprint, complete_intake

    contract = (
        _contract("Replace it with the other one.", ambiguities=("'it' is unresolved",))
        if case == "ambiguity"
        else _broad("Migrate the storage backend to PostgreSQL.")
    )
    baseline = complete_intake(contract)

    assistant = build_live_intake_assistant()
    started = time.monotonic()
    assisted = complete_intake(contract, assistant=assistant)
    elapsed = time.monotonic() - started

    prompt = build_intake_assistance_request(
        contract, baseline.decision, baseline.projection
    )
    print(
        f"\nlive intake assistant smoke [{case}]: model={assistant.model_id} "
        f"status={assisted.assistance_status} latency={elapsed:.1f}s "
        f"prompt_chars={len(prompt)} summary={assisted.assistance.summary!r} "
        f"questions={assisted.questions()}"
    )

    assert assisted.state in (STATE_ASK_CLARIFICATION, STATE_GOAL_BRIEF_ASSIST)
    assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)
