"""Tests for Phase 9.1b — Pluggable embedding provider.

Every Gemini test uses a stubbed ``google-genai`` client; no real API key
is ever required, no network request is ever made. The MiniLM path is
exercised in two modes — when ``sentence_transformers`` is importable (the
provider must still surface a clear error if the user passes an unloadable
model) and when it isn't (clear ``EmbeddingProviderError``).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import embedding_providers as ep
from core import health


# ---------------------------------------------------------------------------
# Helpers — mock genai client
# ---------------------------------------------------------------------------


class _FakeEmbedding(SimpleNamespace):
    """SimpleNamespace already has ``values``; subclassing just for clarity."""


class _FakeModels:
    def __init__(self, dim: int):
        self.dim = dim
        self.calls: list[dict] = []

    def embed_content(self, *, model: str, contents):
        text_list = list(contents)
        self.calls.append({"model": model, "contents": text_list})
        return SimpleNamespace(
            embeddings=[
                _FakeEmbedding(values=[float(i) / 100.0 for i in range(self.dim)])
                for _ in text_list
            ]
        )


class _FakeClient:
    def __init__(self, *, dim: int = 768):
        self.models = _FakeModels(dim=dim)


def _install_fake_genai(monkeypatch, *, dim: int = 768) -> _FakeClient:
    """Return a fake client instance and wire ``_import_genai`` to a stub
    namespace whose ``Client(...)`` constructor returns it."""
    fake = _FakeClient(dim=dim)

    fake_genai = SimpleNamespace(Client=lambda api_key=None: fake)
    monkeypatch.setattr(
        ep.GeminiProvider, "_import_genai", staticmethod(lambda: fake_genai)
    )
    return fake


# ---------------------------------------------------------------------------
# Provider id normalisation + factory
# ---------------------------------------------------------------------------


def test_normalize_provider_id_defaults_to_off(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    assert ep._normalize_provider_id(None) == "off"
    assert ep._normalize_provider_id("") == "off"
    assert ep._normalize_provider_id("   ") == "off"


def test_normalize_provider_id_accepts_known_ids():
    assert ep._normalize_provider_id("off") == "off"
    assert ep._normalize_provider_id("LOCAL_MINILM") == "local_minilm"
    assert ep._normalize_provider_id("Gemini") == "gemini"


def test_normalize_provider_id_rejects_unknown():
    with pytest.raises(ep.EmbeddingProviderError) as exc_info:
        ep._normalize_provider_id("openai")
    assert "Unknown EMBEDDING_PROVIDER" in str(exc_info.value)
    assert "off" in str(exc_info.value)
    assert "local_minilm" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)


def test_get_provider_reads_environment(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    provider = ep.get_provider()
    assert isinstance(provider, ep.GeminiProvider)
    assert provider.provider_id == "gemini"


def test_get_provider_explicit_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    provider = ep.get_provider(provider_id="off")
    assert isinstance(provider, ep.OffProvider)


# ---------------------------------------------------------------------------
# Off provider
# ---------------------------------------------------------------------------


def test_off_provider_raises_with_actionable_hint():
    provider = ep.OffProvider()
    assert provider.provider_id == "off"
    assert provider.dimension == 0
    with pytest.raises(ep.EmbeddingProviderError) as exc_info:
        provider.embed_texts(["hello"])
    msg = str(exc_info.value)
    assert "EMBEDDING_PROVIDER=off" in msg
    assert "local_minilm" in msg
    assert "gemini" in msg


def test_off_provider_signature():
    sig = ep.OffProvider().signature()
    assert sig == {"provider_id": "off", "model": "", "dimension": 0}


# ---------------------------------------------------------------------------
# Local MiniLM provider
# ---------------------------------------------------------------------------


def test_local_minilm_signature_uses_default_model_and_dim(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    provider = ep.LocalMiniLMProvider()
    assert provider.provider_id == "local_minilm"
    assert provider.model == ep.DEFAULT_LOCAL_MINILM_MODEL
    assert provider.dimension == ep.DEFAULT_LOCAL_MINILM_DIMENSION


def test_local_minilm_respects_env_model(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "some/other-model")
    provider = ep.LocalMiniLMProvider()
    assert provider.model == "some/other-model"


def test_local_minilm_friendly_error_when_st_not_installed(monkeypatch):
    """Simulate the no-sentence-transformers state without actually
    uninstalling the package — monkeypatch the testable seam."""
    def boom():
        raise ImportError("No module named 'sentence_transformers'")

    monkeypatch.setattr(
        ep.LocalMiniLMProvider,
        "_import_sentence_transformer",
        staticmethod(boom),
    )

    provider = ep.LocalMiniLMProvider()
    with pytest.raises(ep.EmbeddingProviderError) as exc_info:
        provider.embed_texts(["hello"])
    msg = str(exc_info.value)
    assert "sentence-transformers" in msg
    assert "requirements_embeddings.txt" in msg
    # No silent fallback: the message tells the user to either install or
    # switch to gemini — it does not pretend to have done it for them.
    assert "gemini" in msg


def test_local_minilm_embed_texts_with_stubbed_model(monkeypatch):
    """Provider returns plain ``list[list[float]]`` whatever the underlying
    ``SentenceTransformer`` produces (numpy array vs list of lists)."""
    class FakeST:
        def __init__(self, *_args, **_kwargs):
            self.model_name = "fake-st"

        def encode(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    monkeypatch.setattr(
        ep.LocalMiniLMProvider,
        "_import_sentence_transformer",
        staticmethod(lambda: FakeST),
    )

    provider = ep.LocalMiniLMProvider()
    out = provider.embed_texts(["a", "b"])
    assert out == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]


def test_local_minilm_empty_input_returns_empty():
    provider = ep.LocalMiniLMProvider()
    # No model loading required for empty input.
    assert provider.embed_texts([]) == []


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


def test_gemini_signature_uses_default_model_and_dim(monkeypatch):
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_EMBEDDING_DIMENSION", raising=False)
    provider = ep.GeminiProvider()
    assert provider.provider_id == "gemini"
    assert provider.model == ep.DEFAULT_GEMINI_EMBEDDING_MODEL
    assert provider.dimension == ep.DEFAULT_GEMINI_EMBEDDING_DIMENSION


def test_gemini_respects_env_model_and_dim(monkeypatch):
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")
    monkeypatch.setenv("GEMINI_EMBEDDING_DIMENSION", "768")
    provider = ep.GeminiProvider()
    assert provider.model == "text-embedding-004"
    assert provider.dimension == 768


def test_gemini_raises_friendly_error_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = ep.GeminiProvider()
    with pytest.raises(ep.EmbeddingProviderError) as exc_info:
        provider.embed_texts(["hello"])
    msg = str(exc_info.value)
    assert "GOOGLE_API_KEY" in msg
    assert "GEMINI_API_KEY" in msg
    assert "gemini" in msg.lower()


def test_gemini_embed_texts_with_mocked_client(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-not-real")
    fake = _install_fake_genai(monkeypatch, dim=768)

    provider = ep.GeminiProvider(model="text-embedding-004", dimension=768)
    out = provider.embed_texts(["foo", "bar"])

    assert len(out) == 2
    assert all(len(v) == 768 for v in out)
    # The stub recorded exactly what we sent.
    assert fake.models.calls == [
        {"model": "text-embedding-004", "contents": ["foo", "bar"]}
    ]


def test_gemini_self_corrects_dimension_when_live_response_differs(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    _install_fake_genai(monkeypatch, dim=256)  # different from default 3072

    provider = ep.GeminiProvider()  # claims dim=3072
    provider.embed_texts(["foo"])

    # Signature now reflects what the live response actually returned, so the
    # value written into index metadata can't lie about the index's shape.
    assert provider.dimension == 256
    assert provider.signature()["dimension"] == 256


def test_gemini_does_not_fallback_to_local_minilm(monkeypatch):
    """Explicit spec rule: no silent provider fallback."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Even if MiniLM is fully available, Gemini's failure must NOT cause the
    # caller to receive MiniLM vectors.
    monkeypatch.setattr(
        ep.LocalMiniLMProvider,
        "_import_sentence_transformer",
        staticmethod(lambda: object()),
    )

    provider = ep.GeminiProvider()
    with pytest.raises(ep.EmbeddingProviderError):
        provider.embed_texts(["hello"])


def test_gemini_response_count_mismatch_raises(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    class BadModels:
        def embed_content(self, *, model, contents):
            return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])

    class BadClient:
        models = BadModels()

    fake_genai = SimpleNamespace(Client=lambda api_key=None: BadClient())
    monkeypatch.setattr(
        ep.GeminiProvider, "_import_genai", staticmethod(lambda: fake_genai)
    )

    provider = ep.GeminiProvider()
    with pytest.raises(ep.EmbeddingProviderError, match="returned 1 embeddings for 2"):
        provider.embed_texts(["a", "b"])


# ---------------------------------------------------------------------------
# Index metadata + drift detection
# ---------------------------------------------------------------------------


def test_write_and_read_index_metadata_roundtrip(tmp_path: Path):
    path = tmp_path / "embedding_index_meta.json"
    provider = ep.GeminiProvider(model="text-embedding-004", dimension=768)

    written_path = ep.write_index_metadata(path, provider)
    assert written_path == path

    stored = ep.read_index_metadata(path)
    assert stored == {
        "provider_id": "gemini",
        "model": "text-embedding-004",
        "dimension": 768,
    }


def test_read_index_metadata_missing_returns_none(tmp_path: Path):
    assert ep.read_index_metadata(tmp_path / "missing.json") is None


def test_read_index_metadata_malformed_returns_none(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert ep.read_index_metadata(path) is None

    path2 = tmp_path / "list.json"
    path2.write_text("[1,2,3]", encoding="utf-8")
    assert ep.read_index_metadata(path2) is None


def test_signatures_match_compares_all_three_fields(tmp_path: Path):
    provider = ep.GeminiProvider(model="text-embedding-004", dimension=768)
    good = {
        "provider_id": "gemini",
        "model": "text-embedding-004",
        "dimension": 768,
    }
    assert ep.signatures_match(good, provider)

    bad_dim = dict(good, dimension=3072)
    assert not ep.signatures_match(bad_dim, provider)

    bad_model = dict(good, model="gemini-embedding-001")
    assert not ep.signatures_match(bad_model, provider)

    bad_provider = dict(good, provider_id="local_minilm")
    assert not ep.signatures_match(bad_provider, provider)


def test_verify_index_metadata_ok_when_match(tmp_path: Path):
    provider = ep.GeminiProvider(model="text-embedding-004", dimension=768)
    path = tmp_path / "meta.json"
    ep.write_index_metadata(path, provider)

    report = ep.verify_index_metadata(path, provider=provider)
    assert report["ok"] is True
    assert report["reindex_required"] is False
    assert report["reason"] == ""


def test_verify_index_metadata_reports_reindex_when_missing(tmp_path: Path):
    provider = ep.GeminiProvider(model="text-embedding-004", dimension=768)
    report = ep.verify_index_metadata(tmp_path / "absent.json", provider=provider)
    assert report["ok"] is False
    assert report["reindex_required"] is True
    assert "run re-index" in report["reason"]


def test_verify_index_metadata_detects_provider_change(tmp_path: Path):
    """Provider switched from local_minilm → gemini: signature mismatch."""
    old = ep.LocalMiniLMProvider()
    path = tmp_path / "meta.json"
    ep.write_index_metadata(path, old)

    new = ep.GeminiProvider(model="text-embedding-004", dimension=768)
    report = ep.verify_index_metadata(path, provider=new)

    assert report["ok"] is False
    assert report["reindex_required"] is True
    assert "provider_id" in report["reason"]
    assert "stored=" in report["reason"]
    assert "current=" in report["reason"]


def test_verify_index_metadata_detects_dimension_change(tmp_path: Path):
    """Same provider, different dimension still forces re-index."""
    old = ep.GeminiProvider(model="text-embedding-004", dimension=768)
    path = tmp_path / "meta.json"
    ep.write_index_metadata(path, old)

    new = ep.GeminiProvider(model="text-embedding-004", dimension=3072)
    report = ep.verify_index_metadata(path, provider=new)

    assert report["reindex_required"] is True
    assert "dimension" in report["reason"]


# ---------------------------------------------------------------------------
# Health row
# ---------------------------------------------------------------------------


def test_health_check_reports_off_when_unset(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    for v in ("RETRIEVER_USE_EMBEDDINGS", "INDEX_USE_EMBEDDINGS", "ROUTER_USE_EMBEDDINGS"):
        monkeypatch.delenv(v, raising=False)

    row = health.check_embeddings()
    assert row["status"] == "off"
    assert "EMBEDDING_PROVIDER=off" in row["detail"]


def test_health_check_reports_provider_and_dim_for_gemini(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key-not-real")
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_EMBEDDING_DIMENSION", raising=False)

    row = health.check_embeddings()
    assert row["status"] == "available"
    assert "provider=gemini" in row["detail"]
    assert "model=gemini-embedding-001" in row["detail"]
    assert "dimension=3072" in row["detail"]
    assert "GOOGLE_API_KEY present" in row["detail"]


def test_health_check_reports_missing_api_key_for_gemini(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    row = health.check_embeddings()
    assert row["status"] == "missing"
    assert "GOOGLE_API_KEY" in row["detail"]


def test_health_check_reports_provider_for_local_minilm(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local_minilm")
    row = health.check_embeddings()
    # Whether the dep is installed locally varies; the row must surface the
    # provider id either way (available or error).
    assert row["status"] in {"available", "error"}
    if row["status"] == "available":
        assert "provider=local_minilm" in row["detail"]
        assert "dimension=384" in row["detail"]


def test_health_check_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    row = health.check_embeddings()
    assert row["status"] == "error"
    assert "Unknown EMBEDDING_PROVIDER" in row["detail"]
