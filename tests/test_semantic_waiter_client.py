"""INPUT.2 — opt-in live semantic model client tests.

Nothing here opens a socket.  The client is inert until ``complete`` is called,
so importing or constructing it is safe in any environment, with or without
provider libraries installed.
"""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

from core.semantic_waiter_adapter import SemanticModelClient, SemanticWaiterModelAdapter
from core.semantic_waiter_client import (
    DEFAULT_SEMANTIC_WAITER_MODEL,
    SEMANTIC_WAITER_MODEL_ENV,
    LocalSemanticModelClient,
    build_live_semantic_adapter,
    resolve_semantic_model_id,
)


MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "semantic_waiter_client.py"


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


def test_constructing_a_client_makes_no_call():
    client = LocalSemanticModelClient(model="probe-model")

    assert client.model_id == "probe-model"


def test_building_the_live_adapter_makes_no_call():
    adapter = build_live_semantic_adapter(model="probe-model")

    assert isinstance(adapter, SemanticWaiterModelAdapter)
    assert adapter.model_id == "probe-model"
    assert adapter.call_count == 0


def test_client_satisfies_the_model_client_protocol():
    assert isinstance(LocalSemanticModelClient(model="probe-model"), SemanticModelClient)


# ══ configuration, not selection ══════════════════════════════════════════════

def test_env_var_name_is_stable():
    assert SEMANTIC_WAITER_MODEL_ENV == "SEMANTIC_WAITER_MODEL"


def test_environment_supplies_the_model(monkeypatch):
    monkeypatch.setenv(SEMANTIC_WAITER_MODEL_ENV, "configured-by-operator")

    assert resolve_semantic_model_id() == "configured-by-operator"


def test_default_model_is_used_when_unset(monkeypatch):
    monkeypatch.delenv(SEMANTIC_WAITER_MODEL_ENV, raising=False)

    assert resolve_semantic_model_id() == DEFAULT_SEMANTIC_WAITER_MODEL


def test_explicit_construction_beats_the_environment(monkeypatch):
    monkeypatch.setenv(SEMANTIC_WAITER_MODEL_ENV, "from-env")

    assert build_live_semantic_adapter(model="explicit").model_id == "explicit"


def test_client_holds_no_credentials():
    client = LocalSemanticModelClient(model="probe-model")

    for attribute in vars(client):
        assert "key" not in attribute.lower()
        assert "token" not in attribute.lower()
        assert "secret" not in attribute.lower()


# ══ single model, no routing ══════════════════════════════════════════════════

def test_source_declares_no_model_fallback_list():
    source = MODULE_PATH.read_text(encoding="utf-8")

    for banned in ("MODELS", "DEEPSEEK_MODELS", "_max_model_fallbacks", "for model_name in"):
        assert banned not in source, f"{banned} would make this a model router"


def _fake_ollama(answer: str | None = None, error: Exception | None = None):
    module = types.ModuleType("agents.ollama_client")

    class FakeOllamaClient:
        instances: list = []

        def __init__(self, model=None, base_url=None, timeout=None):
            self.model = model
            FakeOllamaClient.instances.append(self)

        def generate(self, prompt, system_prompt=None, options=None):
            if error is not None:
                raise error
            return answer

    module.OllamaClient = FakeOllamaClient
    return module, FakeOllamaClient


@pytest.fixture
def patched_ollama(monkeypatch):
    def _install(answer=None, error=None):
        module, fake = _fake_ollama(answer=answer, error=error)
        monkeypatch.setitem(sys.modules, "agents.ollama_client", module)
        return fake

    return _install


def test_complete_uses_the_single_configured_model(patched_ollama):
    fake = patched_ollama(answer='{"task": {"type": "question"}}')
    client = LocalSemanticModelClient(model="only-this-model")

    result = client.complete("system", "user")

    assert result == '{"task": {"type": "question"}}'
    assert [instance.model for instance in fake.instances] == ["only-this-model"]


def test_complete_passes_the_system_instruction_through(patched_ollama):
    captured: dict = {}
    module, fake = _fake_ollama(answer="{}")

    class Recording(fake):  # type: ignore[misc,valid-type]
        def generate(self, prompt, system_prompt=None, options=None):
            captured["system"] = system_prompt
            captured["user"] = prompt
            return "{}"

    module.OllamaClient = Recording
    sys.modules["agents.ollama_client"] = module
    try:
        LocalSemanticModelClient(model="m").complete("SYS", "USR")
    finally:
        sys.modules.pop("agents.ollama_client", None)

    assert captured["system"] == "SYS"
    assert captured["user"] == "USR"


def test_transport_error_propagates_for_the_adapter_to_classify(patched_ollama):
    patched_ollama(error=ConnectionError("down"))
    client = LocalSemanticModelClient(model="m")

    with pytest.raises(ConnectionError):
        client.complete("system", "user")


def test_agent_error_sentinel_is_treated_as_unavailable(patched_ollama):
    patched_ollama(answer="AGENT_ERROR: Ollama unreachable")
    client = LocalSemanticModelClient(model="m")

    with pytest.raises(Exception) as info:
        client.complete("system", "user")

    assert "AGENT_ERROR" in str(info.value) or "unavailable" in str(info.value).lower()


def test_adapter_over_a_broken_client_reports_model_unavailable(patched_ollama):
    from core.semantic_waiter_adapter import SemanticModelUnavailable
    from core.explicit_evidence import extract_explicit_evidence

    patched_ollama(error=ConnectionError("down"))
    adapter = build_live_semantic_adapter(model="m")

    with pytest.raises(SemanticModelUnavailable):
        adapter.interpret("Compare A against B", extract_explicit_evidence("Compare A against B"))


# ══ context window sizing for reasoning models ════════════════════════════════

def test_num_ctx_env_var_name_is_stable():
    from core.semantic_waiter_client import SEMANTIC_WAITER_NUM_CTX_ENV

    assert SEMANTIC_WAITER_NUM_CTX_ENV == "SEMANTIC_WAITER_NUM_CTX"


def test_default_context_window_fits_a_reasoning_model(monkeypatch):
    from core.semantic_waiter_client import (
        DEFAULT_SEMANTIC_WAITER_NUM_CTX,
        resolve_semantic_num_ctx,
    )

    monkeypatch.delenv("SEMANTIC_WAITER_NUM_CTX", raising=False)

    assert resolve_semantic_num_ctx() == DEFAULT_SEMANTIC_WAITER_NUM_CTX
    # A stock 4096 window is exhausted by prompt plus hidden thinking.
    assert DEFAULT_SEMANTIC_WAITER_NUM_CTX >= 8192


def test_environment_can_size_the_context_window(monkeypatch):
    from core.semantic_waiter_client import resolve_semantic_num_ctx

    monkeypatch.setenv("SEMANTIC_WAITER_NUM_CTX", "32768")

    assert resolve_semantic_num_ctx() == 32768


def test_a_nonsense_context_window_falls_back_to_the_default(monkeypatch):
    from core.semantic_waiter_client import (
        DEFAULT_SEMANTIC_WAITER_NUM_CTX,
        resolve_semantic_num_ctx,
    )

    monkeypatch.setenv("SEMANTIC_WAITER_NUM_CTX", "not-a-number")

    assert resolve_semantic_num_ctx() == DEFAULT_SEMANTIC_WAITER_NUM_CTX


def test_complete_widens_the_context_window(patched_ollama):
    from core.semantic_waiter_client import DEFAULT_SEMANTIC_WAITER_NUM_CTX

    captured: dict = {}
    module, fake = _fake_ollama(answer="{}")

    class Recording(fake):  # type: ignore[misc,valid-type]
        def generate(self, prompt, system_prompt=None, options=None):
            captured["options"] = options
            return "{}"

    module.OllamaClient = Recording
    sys.modules["agents.ollama_client"] = module
    try:
        LocalSemanticModelClient(model="m").complete("system", "user")
    finally:
        sys.modules.pop("agents.ollama_client", None)

    assert captured["options"]["num_ctx"] == DEFAULT_SEMANTIC_WAITER_NUM_CTX


def test_explicit_num_ctx_beats_the_environment(monkeypatch):
    monkeypatch.setenv("SEMANTIC_WAITER_NUM_CTX", "8192")
    client = LocalSemanticModelClient(model="m", num_ctx=24576)

    assert client.num_ctx == 24576


def test_adapter_builder_accepts_a_context_window():
    adapter = build_live_semantic_adapter(model="m", num_ctx=12288)

    assert adapter.model_id == "m"


# ══ configured cloud provider (no runtime escalation) ═════════════════════════

def _fake_genai(text="{}", error=None, captured=None):
    """Stand in for google.genai without importing or contacting anything."""
    captured = {} if captured is None else captured

    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    types_mod = types.ModuleType("google.genai.types")

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            captured["config"] = kwargs
            self.__dict__.update(kwargs)

    types_mod.GenerateContentConfig = GenerateContentConfig

    class _Models:
        def generate_content(self, model=None, contents=None, config=None):
            captured.setdefault("models_called", []).append(model)
            captured["contents"] = contents
            if error is not None:
                raise error
            return types.SimpleNamespace(text=text)

    class Client:
        def __init__(self, api_key=None):
            captured["api_key_supplied"] = bool(api_key)
            self.models = _Models()

    genai_mod.Client = Client
    genai_mod.types = types_mod
    google_mod.genai = genai_mod
    return {
        "google": google_mod,
        "google.genai": genai_mod,
        "google.genai.types": types_mod,
    }, captured


@pytest.fixture
def patched_genai(monkeypatch):
    def _install(text="{}", error=None):
        modules, captured = _fake_genai(text=text, error=error)
        for name, module in modules.items():
            monkeypatch.setitem(sys.modules, name, module)
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-real")
        return captured

    return _install


def test_provider_vocabulary_is_stable():
    from core.semantic_waiter_client import (
        DEFAULT_SEMANTIC_WAITER_PROVIDER,
        PROVIDER_GEMINI,
        PROVIDER_LOCAL,
        SEMANTIC_WAITER_PROVIDERS,
        SEMANTIC_WAITER_PROVIDER_ENV,
    )

    assert SEMANTIC_WAITER_PROVIDER_ENV == "SEMANTIC_WAITER_PROVIDER"
    assert SEMANTIC_WAITER_PROVIDERS == (PROVIDER_LOCAL, PROVIDER_GEMINI)
    # Local by default so an interpretation never silently spends on cloud.
    assert DEFAULT_SEMANTIC_WAITER_PROVIDER == PROVIDER_LOCAL


def test_provider_defaults_to_local(monkeypatch):
    from core.semantic_waiter_client import PROVIDER_LOCAL, resolve_semantic_provider

    monkeypatch.delenv("SEMANTIC_WAITER_PROVIDER", raising=False)

    assert resolve_semantic_provider() == PROVIDER_LOCAL


def test_environment_selects_the_cloud_provider(monkeypatch):
    from core.semantic_waiter_client import PROVIDER_GEMINI, resolve_semantic_provider

    monkeypatch.setenv("SEMANTIC_WAITER_PROVIDER", "gemini")

    assert resolve_semantic_provider() == PROVIDER_GEMINI


def test_unknown_provider_fails_closed_rather_than_defaulting(monkeypatch):
    from core.semantic_waiter_client import resolve_semantic_provider

    monkeypatch.setenv("SEMANTIC_WAITER_PROVIDER", "mystery-cloud")

    with pytest.raises(ValueError):
        resolve_semantic_provider()


def test_building_a_cloud_adapter_makes_no_call():
    from core.semantic_waiter_client import DEFAULT_GEMINI_SEMANTIC_MODEL

    adapter = build_live_semantic_adapter(provider="gemini")

    assert adapter.model_id == DEFAULT_GEMINI_SEMANTIC_MODEL
    assert adapter.call_count == 0


def test_cloud_client_satisfies_the_model_client_protocol():
    from core.semantic_waiter_client import GeminiSemanticModelClient

    assert isinstance(GeminiSemanticModelClient(model="gemma-test"), SemanticModelClient)


def test_cloud_client_holds_no_credentials():
    from core.semantic_waiter_client import GeminiSemanticModelClient

    client = GeminiSemanticModelClient(model="gemma-test")

    for attribute in vars(client):
        assert "key" not in attribute.lower()
        assert "token" not in attribute.lower()
        assert "secret" not in attribute.lower()


def test_cloud_complete_uses_exactly_one_model(patched_genai):
    from core.semantic_waiter_client import GeminiSemanticModelClient

    captured = patched_genai(text='{"task": {"type": "question"}}')
    result = GeminiSemanticModelClient(model="gemma-test").complete("SYS", "USR")

    assert result == '{"task": {"type": "question"}}'
    assert captured["models_called"] == ["gemma-test"]


def test_cloud_complete_sends_the_system_instruction_and_requests_json(patched_genai):
    from core.semantic_waiter_client import GeminiSemanticModelClient

    captured = patched_genai()
    GeminiSemanticModelClient(model="gemma-test").complete("SYS", "USR")

    assert captured["config"]["system_instruction"] == "SYS"
    assert captured["config"]["response_mime_type"] == "application/json"
    assert captured["contents"] == ["USR"]


def test_cloud_complete_without_a_key_fails_closed(monkeypatch, patched_genai):
    from core.semantic_waiter_client import GeminiSemanticModelClient, SemanticTransportError

    patched_genai()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "core.semantic_waiter_client._load_dotenv_if_available", lambda: None
    )

    with pytest.raises(SemanticTransportError):
        GeminiSemanticModelClient(model="gemma-test").complete("SYS", "USR")


def test_cloud_transport_error_propagates(patched_genai):
    from core.semantic_waiter_client import GeminiSemanticModelClient

    patched_genai(error=TimeoutError("upstream timeout"))

    with pytest.raises(TimeoutError):
        GeminiSemanticModelClient(model="gemma-test").complete("SYS", "USR")


def test_cloud_adapter_reports_unavailable_on_transport_failure(patched_genai):
    from core.explicit_evidence import extract_explicit_evidence
    from core.semantic_waiter_adapter import SemanticModelUnavailable

    patched_genai(error=TimeoutError("upstream timeout"))
    adapter = build_live_semantic_adapter(provider="gemini", model="gemma-test")

    with pytest.raises(SemanticModelUnavailable):
        adapter.interpret("Compare A against B", extract_explicit_evidence("Compare A against B"))


def test_selecting_a_provider_never_escalates_between_them(patched_genai):
    """One request, one provider: there is no local-to-cloud failover path."""
    source = MODULE_PATH.read_text(encoding="utf-8")

    for banned in ("except SemanticTransportError", "fallback_provider", "escalate"):
        assert banned not in source, f"{banned} would make this a provider router"
