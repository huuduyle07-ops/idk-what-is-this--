"""INPUT.2 — opt-in live client for the Semantic Waiter.

The narrowest possible transport: one configured model, one call, raw text
back.  Two providers are supported, selected by configuration:

``ollama`` (default)
    Local, via the existing :class:`agents.ollama_client.OllamaClient`, which
    already talks to a single configured model and does no model-list fallback
    of its own.

``gemini``
    One pinned cloud model on the Google GenAI API, with native JSON response
    mode.

What this deliberately is not
-----------------------------

Not a provider framework.  There is no model list, no cheap-then-strong
escalation, no provider A to provider B failover, and no automatic retry.
Selecting a provider is a configuration act by a human — an environment
variable or an explicit argument — resolved once before the request starts.
One request uses one provider and one model from start to finish; if that model
fails, the request fails and says so. INPUT.2 adds a Semantic Waiter
implementation; it adds no Driver or model-routing authority.

Any other provider can be used without changing INPUT.2: implement
:class:`~core.semantic_waiter_adapter.SemanticModelClient` and hand it to
:class:`~core.semantic_waiter_adapter.SemanticWaiterModelAdapter`.

Inertness
---------

Nothing here is imported or contacted until :meth:`LocalSemanticModelClient.complete`
runs. Importing this module, constructing a client, and building an adapter all
stay offline, so the default test suite never needs a network or a provider
library.
"""

from __future__ import annotations

import os

from core.semantic_waiter_adapter import SemanticWaiterModelAdapter


PHASE_ID = "INPUT.2"

#: Operator-facing configuration for the one semantic model.
SEMANTIC_WAITER_MODEL_ENV = "SEMANTIC_WAITER_MODEL"
SEMANTIC_WAITER_HOST_ENV = "SEMANTIC_WAITER_HOST"
SEMANTIC_WAITER_TIMEOUT_ENV = "SEMANTIC_WAITER_TIMEOUT_SECONDS"
SEMANTIC_WAITER_NUM_CTX_ENV = "SEMANTIC_WAITER_NUM_CTX"
SEMANTIC_WAITER_PROVIDER_ENV = "SEMANTIC_WAITER_PROVIDER"

#: Where the one configured semantic model lives. Selecting a provider is a
#: configuration act by a human, never a runtime decision by the waiter, and
#: never a failover: one request uses one provider, start to finish.
PROVIDER_LOCAL = "ollama"
PROVIDER_GEMINI = "gemini"
SEMANTIC_WAITER_PROVIDERS: tuple[str, ...] = (PROVIDER_LOCAL, PROVIDER_GEMINI)

#: Local by default, so an interpretation pass never silently spends on cloud.
DEFAULT_SEMANTIC_WAITER_PROVIDER = PROVIDER_LOCAL

#: The one cloud model used when the gemini provider is selected.
DEFAULT_GEMINI_SEMANTIC_MODEL = "gemma-4-31b-it"
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"

#: The local model used when nothing is configured. Local by default so an
#: interpretation pass never silently spends on a cloud provider.
DEFAULT_SEMANTIC_WAITER_MODEL = "deepseek-r1:1.5b"
DEFAULT_SEMANTIC_WAITER_TIMEOUT = 60

#: Context window requested for the interpretation call.
#:
#: A reasoning model bills its hidden ``thinking`` block against the same
#: window as the prompt and the answer. Measured on the dogfood case with
#: qwen3.5:4b: 939 prompt tokens plus ~3.2k thinking tokens hits the stock 4096
#: window exactly, so generation stops at ``done_reason=length`` before the
#: answer is written and ``response`` comes back empty — indistinguishable from
#: an unreachable model. At 16384 the same request completes normally in about
#: 4k generated tokens. Widen further via the environment for chattier models.
DEFAULT_SEMANTIC_WAITER_NUM_CTX = 16_384

#: Sentinel the existing agent clients return instead of raising.
_AGENT_ERROR_PREFIX = "AGENT_ERROR:"


class SemanticTransportError(RuntimeError):
    """The configured semantic model could not be reached.

    The adapter converts this into ``SemanticModelUnavailable``.
    """


def resolve_semantic_model_id(env: dict[str, str] | None = None) -> str:
    """Return the configured semantic model id.

    Configuration only — this never compares, ranks, or selects between models.
    """
    source = os.environ if env is None else env
    configured = (source.get(SEMANTIC_WAITER_MODEL_ENV) or "").strip()
    return configured or DEFAULT_SEMANTIC_WAITER_MODEL


def _positive_int(raw: str, default: int) -> int:
    text = (raw or "").strip()
    if not text:
        return default
    try:
        return max(1, int(text))
    except ValueError:
        return default


def _resolve_timeout() -> int:
    return _positive_int(
        os.environ.get(SEMANTIC_WAITER_TIMEOUT_ENV, ""), DEFAULT_SEMANTIC_WAITER_TIMEOUT
    )


def resolve_semantic_num_ctx(env: dict[str, str] | None = None) -> int:
    """Return the configured context window for the interpretation call."""
    source = os.environ if env is None else env
    return _positive_int(
        source.get(SEMANTIC_WAITER_NUM_CTX_ENV, ""), DEFAULT_SEMANTIC_WAITER_NUM_CTX
    )


def resolve_semantic_provider(env: dict[str, str] | None = None) -> str:
    """Return the configured provider, or fail closed on an unknown one.

    An unrecognised provider is an error rather than a quiet fall back to the
    default: silently running somewhere the operator did not ask for is exactly
    the behaviour this phase refuses to have.
    """
    source = os.environ if env is None else env
    configured = (source.get(SEMANTIC_WAITER_PROVIDER_ENV) or "").strip().casefold()
    if not configured:
        return DEFAULT_SEMANTIC_WAITER_PROVIDER
    if configured not in SEMANTIC_WAITER_PROVIDERS:
        raise ValueError(
            f"unsupported semantic waiter provider {configured!r}; "
            f"expected one of {', '.join(SEMANTIC_WAITER_PROVIDERS)}"
        )
    return configured


def _load_dotenv_if_available() -> None:
    """Best-effort .env load, matching how the agent clients bootstrap."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _google_api_key() -> str:
    """Read the cloud credential at call time; never stored on an instance."""
    value = (os.environ.get(GOOGLE_API_KEY_ENV) or "").strip()
    if value:
        return value
    _load_dotenv_if_available()
    value = (os.environ.get(GOOGLE_API_KEY_ENV) or "").strip()
    if not value:
        raise SemanticTransportError(
            f"{GOOGLE_API_KEY_ENV} is not set; the cloud semantic provider cannot run"
        )
    return value


class LocalSemanticModelClient:
    """One configured local model, one completion, no routing."""

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        num_ctx: int | None = None,
    ) -> None:
        self._model = (model or "").strip() or resolve_semantic_model_id()
        self._base_url = base_url or os.environ.get(SEMANTIC_WAITER_HOST_ENV) or None
        self._timeout = timeout if timeout is not None else _resolve_timeout()
        self._num_ctx = num_ctx if num_ctx is not None else resolve_semantic_num_ctx()

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def num_ctx(self) -> int:
        return self._num_ctx

    def complete(self, system_instruction: str, user_message: str) -> str:
        """Run one completion against the single configured model.

        Transport failures propagate; the adapter classifies them.
        """
        # Imported here so that importing this module, constructing a client,
        # and building an adapter all stay completely offline.
        from agents.ollama_client import OllamaClient

        client = OllamaClient(
            model=self._model,
            base_url=self._base_url,
            timeout=self._timeout,
        )
        answer = client.generate(
            user_message,
            system_prompt=system_instruction,
            options={"num_ctx": self._num_ctx},
        )

        if isinstance(answer, str) and answer.startswith(_AGENT_ERROR_PREFIX):
            raise SemanticTransportError(answer)
        return answer


class GeminiSemanticModelClient:
    """One configured cloud model on the Google GenAI API, one completion.

    Deliberately not built on ``agents.gemini_client.run_gemini_request``: that
    helper walks a list of models until one answers, which is precisely the
    model routing this phase must not perform. Here the model is pinned and a
    failure is a failure.
    """

    def __init__(self, *, model: str | None = None, temperature: float = 0.0) -> None:
        self._model = (model or "").strip() or _resolve_cloud_model_id()
        self._temperature = temperature

    @property
    def model_id(self) -> str:
        return self._model

    def complete(self, system_instruction: str, user_message: str) -> str:
        """Run one completion against the single configured cloud model."""
        # Imported here so this module stays inert and importable without the
        # provider SDK installed.
        import google.genai as genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=_google_api_key())
        response = client.models.generate_content(
            model=self._model,
            contents=[user_message],
            config=genai_types.GenerateContentConfig(
                temperature=self._temperature,
                system_instruction=system_instruction,
                response_mime_type="application/json",
            ),
        )
        return getattr(response, "text", None) or ""


def _resolve_cloud_model_id(env: dict[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    configured = (source.get(SEMANTIC_WAITER_MODEL_ENV) or "").strip()
    return configured or DEFAULT_GEMINI_SEMANTIC_MODEL


def build_live_semantic_adapter(
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int | None = None,
    num_ctx: int | None = None,
) -> SemanticWaiterModelAdapter:
    """Build the opt-in live Semantic Waiter over one configured model.

    ``provider`` selects where that model lives; it defaults to the configured
    provider, which defaults to local. The choice is made once, here, by
    configuration or by the caller — the waiter never reconsiders it mid-request
    and never retries somewhere else.

    Constructing the adapter contacts nothing.
    """
    chosen = (provider or "").strip().casefold() or resolve_semantic_provider()
    if chosen not in SEMANTIC_WAITER_PROVIDERS:
        raise ValueError(
            f"unsupported semantic waiter provider {chosen!r}; "
            f"expected one of {', '.join(SEMANTIC_WAITER_PROVIDERS)}"
        )

    if chosen == PROVIDER_GEMINI:
        return SemanticWaiterModelAdapter(GeminiSemanticModelClient(model=model))

    return SemanticWaiterModelAdapter(
        LocalSemanticModelClient(
            model=model, base_url=base_url, timeout=timeout, num_ctx=num_ctx
        )
    )
