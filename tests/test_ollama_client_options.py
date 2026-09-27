"""Additive per-call generation options for the local Ollama client.

Reasoning models spend their generation budget on a ``thinking`` block that is
billed against the same context window as the prompt and the answer.  At the
stock 4096-token window a request can be cut off mid-thought
(``done_reason=length``) and return an empty ``response``, which looks exactly
like an unreachable model.  Callers therefore need a way to widen the window.

The parameter is optional and merges over the existing defaults, so every
current caller keeps its exact behaviour.
"""

from __future__ import annotations

import pytest

from agents import ollama_client as ollama_module
from agents.ollama_client import OllamaClient


class _Recorder:
    """Stands in for ``requests.post`` and records the payload sent."""

    def __init__(self, response_text: str = "ok") -> None:
        self.payloads: list[dict] = []
        self._response_text = response_text

    def __call__(self, url, json=None, timeout=None):  # noqa: A002 - mirrors requests.post
        self.payloads.append(json)
        return _Reply(self._response_text)


class _Reply:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"response": self._response_text}


@pytest.fixture
def recorder(monkeypatch):
    recorder = _Recorder()
    monkeypatch.setattr(ollama_module, "requests", type("_R", (), {"post": staticmethod(recorder)}))
    return recorder


# ── backward compatibility ────────────────────────────────────────────────────

def test_existing_callers_still_send_only_the_default_options(recorder):
    OllamaClient(model="m").generate("prompt")

    assert recorder.payloads[0]["options"] == {"temperature": 0.2, "top_p": 0.9}


def test_existing_system_prompt_behaviour_is_unchanged(recorder):
    OllamaClient(model="m").generate("prompt", system_prompt="sys")

    assert recorder.payloads[0]["system"] == "sys"
    assert recorder.payloads[0]["prompt"] == "prompt"


def test_generate_with_thought_still_works(recorder):
    result = OllamaClient(model="m").generate_with_thought("prompt")

    assert result["answer"] == "ok"


def test_explicit_none_options_behaves_like_omitting_them(recorder):
    OllamaClient(model="m").generate("prompt", options=None)

    assert recorder.payloads[0]["options"] == {"temperature": 0.2, "top_p": 0.9}


# ── the additive passthrough ──────────────────────────────────────────────────

def test_supplied_options_are_merged_over_the_defaults(recorder):
    OllamaClient(model="m").generate("prompt", options={"num_ctx": 16384})

    assert recorder.payloads[0]["options"] == {
        "temperature": 0.2,
        "top_p": 0.9,
        "num_ctx": 16384,
    }


def test_supplied_options_may_override_a_default(recorder):
    OllamaClient(model="m").generate("prompt", options={"temperature": 0.0})

    assert recorder.payloads[0]["options"]["temperature"] == 0.0
    assert recorder.payloads[0]["options"]["top_p"] == 0.9


def test_supplied_options_do_not_leak_between_calls(recorder):
    client = OllamaClient(model="m")
    client.generate("first", options={"num_ctx": 16384})
    client.generate("second")

    assert recorder.payloads[1]["options"] == {"temperature": 0.2, "top_p": 0.9}


def test_transport_failure_still_returns_the_agent_error_sentinel(monkeypatch):
    def _boom(url, json=None, timeout=None):  # noqa: A002 - mirrors requests.post
        raise ConnectionError("down")

    monkeypatch.setattr(
        ollama_module, "requests", type("_R", (), {"post": staticmethod(_boom)})
    )

    result = OllamaClient(model="m").generate("prompt", options={"num_ctx": 16384})

    assert result.startswith("AGENT_ERROR:")
