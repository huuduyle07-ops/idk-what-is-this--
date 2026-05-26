"""Phase 9.1b — Pluggable embedding provider.

Three modes, selected by the ``EMBEDDING_PROVIDER`` environment variable:

* ``off``           — no embeddings; ``embed_texts`` raises with a clear hint.
* ``local_minilm``  — the existing ``sentence-transformers/all-MiniLM-L6-v2``
                      path (requires ``requirements_embeddings.txt`` install).
* ``gemini``        — Google Gemini embeddings via the already-bundled
                      ``google-genai`` SDK (requires ``GOOGLE_API_KEY``).

Design rules baked into this module (see Phase 9.1b spec):

* No silent fallback. If the configured provider can't run, the call raises
  :class:`EmbeddingProviderError` with an actionable message — we never quietly
  pick a different provider.
* Provider, model, and dimension are stored alongside the vector index as
  ``embedding_index_meta.json``. Before any retrieval, callers must verify
  that the stored signature still matches the current provider; on mismatch
  the index must be re-built.
* No Docker image bloat. The Gemini path only needs ``google-genai`` (already
  a hard dependency); ``sentence-transformers``/Torch stay opt-in.
* No Ollama coupling. This module is independent of the local critic.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OFF_PROVIDER_ID = "off"
LOCAL_MINILM_PROVIDER_ID = "local_minilm"
GEMINI_PROVIDER_ID = "gemini"

VALID_PROVIDER_IDS: tuple[str, ...] = (
    OFF_PROVIDER_ID,
    LOCAL_MINILM_PROVIDER_ID,
    GEMINI_PROVIDER_ID,
)

DEFAULT_LOCAL_MINILM_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LOCAL_MINILM_DIMENSION = 384

DEFAULT_GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_GEMINI_EMBEDDING_DIMENSION = 3072

INDEX_METADATA_FILENAME = "embedding_index_meta.json"


# ---------------------------------------------------------------------------
# Errors + base class
# ---------------------------------------------------------------------------


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot fulfil a request.

    The message is always actionable — it tells the caller what env var or
    install step would make the provider work.
    """


class EmbeddingProvider:
    """Common surface area for every embedding provider.

    Subclasses set ``provider_id``, ``model``, and ``dimension`` and
    implement :meth:`embed_texts`. Use :meth:`signature` when you need a
    JSON-safe (provider, model, dimension) triple — that's what gets written
    into the index metadata so drift detection works.
    """

    provider_id: str = "unknown"
    model: str = ""
    dimension: int = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def signature(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model": self.model,
            "dimension": int(self.dimension),
        }


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class OffProvider(EmbeddingProvider):
    """Embeddings explicitly disabled. Calling ``embed_texts`` is a programming
    error and surfaces a clear hint."""

    provider_id = OFF_PROVIDER_ID
    model = ""
    dimension = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingProviderError(
            "Embeddings are disabled (EMBEDDING_PROVIDER=off). "
            "Set EMBEDDING_PROVIDER=local_minilm or EMBEDDING_PROVIDER=gemini "
            "to enable vector retrieval."
        )


class LocalMiniLMProvider(EmbeddingProvider):
    """Existing ``sentence-transformers``/MiniLM path. Heavy dependency — the
    Docker image does not install it unless ``INSTALL_EMBEDDINGS=true`` is
    passed at build time."""

    provider_id = LOCAL_MINILM_PROVIDER_ID

    def __init__(self, model: str | None = None) -> None:
        self.model = (
            model
            or os.getenv("EMBEDDING_MODEL", "").strip()
            or DEFAULT_LOCAL_MINILM_MODEL
        )
        self.dimension = DEFAULT_LOCAL_MINILM_DIMENSION
        self._st_model: Any = None

    # ----- testable seam ----------------------------------------------------
    @staticmethod
    def _import_sentence_transformer() -> Any:
        """Lazy import so the rest of the app stays light. Tests monkeypatch
        this method to simulate the missing dependency."""
        from sentence_transformers import SentenceTransformer  # type: ignore

        return SentenceTransformer

    # ----- public API -------------------------------------------------------
    def _load(self) -> Any:
        if self._st_model is not None:
            return self._st_model
        try:
            SentenceTransformer = self._import_sentence_transformer()
        except ImportError as exc:
            raise EmbeddingProviderError(
                "EMBEDDING_PROVIDER=local_minilm requires the "
                "`sentence-transformers` package. Install it with "
                "`pip install -r requirements_embeddings.txt`, or switch to "
                "EMBEDDING_PROVIDER=gemini for a no-install remote backend."
                f" ({exc})"
            ) from exc
        hf_token = os.getenv("HF_TOKEN") or None
        try:
            self._st_model = SentenceTransformer(self.model, token=hf_token)
        except TypeError:
            # Older sentence-transformers used a different kwarg name.
            self._st_model = SentenceTransformer(
                self.model, use_auth_token=hf_token
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Failed to load local MiniLM model {self.model!r}: {exc}"
            ) from exc
        return self._st_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(list(texts))
        return [list(map(float, v)) for v in vectors]


class GeminiProvider(EmbeddingProvider):
    """Remote Gemini embedding provider using the bundled ``google-genai`` SDK.

    Does not require ``sentence-transformers``/Torch — the recommended path
    for Docker Compose / Codespaces where image bloat matters. Requires
    ``GOOGLE_API_KEY`` (or ``GEMINI_API_KEY``) to be set.
    """

    provider_id = GEMINI_PROVIDER_ID

    def __init__(
        self,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        self.model = (
            model
            or os.getenv("GEMINI_EMBEDDING_MODEL", "").strip()
            or DEFAULT_GEMINI_EMBEDDING_MODEL
        )
        if dimension is None:
            dim_env = os.getenv("GEMINI_EMBEDDING_DIMENSION", "").strip()
            if dim_env:
                try:
                    dimension = int(dim_env)
                except ValueError:
                    dimension = None
        self.dimension = int(dimension or DEFAULT_GEMINI_EMBEDDING_DIMENSION)
        self._client: Any = None

    # ----- testable seam ----------------------------------------------------
    @staticmethod
    def _import_genai() -> Any:
        from google import genai  # type: ignore

        return genai

    # ----- public API -------------------------------------------------------
    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = (
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise EmbeddingProviderError(
                "EMBEDDING_PROVIDER=gemini requires GOOGLE_API_KEY (or "
                "GEMINI_API_KEY). Set it in your environment or .env and "
                "retry."
            )
        try:
            genai = self._import_genai()
        except ImportError as exc:
            raise EmbeddingProviderError(
                f"`google-genai` is not installed: {exc}"
            ) from exc
        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Failed to initialise Gemini client: {exc}"
            ) from exc
        return self._client

    @staticmethod
    def _extract_values(emb: Any) -> list[float] | None:
        values = getattr(emb, "values", None)
        if values is None and isinstance(emb, dict):
            values = emb.get("values")
        if values is None:
            return None
        try:
            return [float(x) for x in values]
        except (TypeError, ValueError):
            return None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        text_list = list(texts)
        if not text_list:
            return []
        client = self._get_client()
        try:
            result = client.models.embed_content(
                model=self.model,
                contents=text_list,
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Gemini embed_content failed: {exc}"
            ) from exc

        raw_embeddings = getattr(result, "embeddings", None) or []
        out: list[list[float]] = []
        for emb in raw_embeddings:
            values = self._extract_values(emb)
            if values is None:
                raise EmbeddingProviderError(
                    "Gemini response missing 'values' on an embedding entry"
                )
            out.append(values)

        if len(out) != len(text_list):
            raise EmbeddingProviderError(
                f"Gemini returned {len(out)} embeddings for "
                f"{len(text_list)} input(s)"
            )
        # Self-correct dimension from the live response so the signature we
        # later persist reflects reality. We never silently coerce vectors.
        if out and len(out[0]) != self.dimension:
            self.dimension = len(out[0])
        return out


# ---------------------------------------------------------------------------
# Factory + env parsing
# ---------------------------------------------------------------------------


def _normalize_provider_id(raw: str | None) -> str:
    text = (raw or "").strip().lower()
    if not text:
        return OFF_PROVIDER_ID
    if text in VALID_PROVIDER_IDS:
        return text
    raise EmbeddingProviderError(
        f"Unknown EMBEDDING_PROVIDER {raw!r}. Valid values: "
        + ", ".join(VALID_PROVIDER_IDS)
    )


def get_provider(provider_id: str | None = None) -> EmbeddingProvider:
    """Build the provider named by ``provider_id`` (or ``EMBEDDING_PROVIDER``).

    Returns :class:`OffProvider` when nothing is configured so callers can ask
    for the provider unconditionally and check ``provider.provider_id`` before
    embedding.
    """
    raw = provider_id if provider_id is not None else os.getenv("EMBEDDING_PROVIDER")
    pid = _normalize_provider_id(raw)
    if pid == OFF_PROVIDER_ID:
        return OffProvider()
    if pid == LOCAL_MINILM_PROVIDER_ID:
        return LocalMiniLMProvider()
    if pid == GEMINI_PROVIDER_ID:
        return GeminiProvider()
    raise EmbeddingProviderError(f"Unhandled provider id: {pid!r}")


# ---------------------------------------------------------------------------
# Index metadata + drift detection
# ---------------------------------------------------------------------------


def write_index_metadata(
    metadata_path: str | Path, provider: EmbeddingProvider
) -> Path:
    """Persist the provider signature next to a vector index.

    Always overwrites — the caller is expected to invoke this only after a
    successful (re-)index.
    """
    path = Path(metadata_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = provider.signature()
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def read_index_metadata(metadata_path: str | Path) -> dict[str, Any] | None:
    """Return the stored signature dict, or ``None`` when absent / malformed.

    Malformed metadata is treated as missing (rather than an exception) so a
    corrupt file forces a re-index instead of crashing reads.
    """
    path = Path(metadata_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def signatures_match(
    stored: dict[str, Any] | None, provider: EmbeddingProvider
) -> bool:
    if not stored:
        return False
    try:
        stored_dim = int(stored.get("dimension") or 0)
    except (TypeError, ValueError):
        return False
    return (
        stored.get("provider_id") == provider.provider_id
        and stored.get("model") == provider.model
        and stored_dim == int(provider.dimension)
    )


def verify_index_metadata(
    metadata_path: str | Path,
    provider: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    """Return ``{ok, stored, current, reindex_required, reason}``.

    Callers MUST refuse to read from the vector index when ``ok`` is False —
    embedding drift between providers/models/dimensions would yield silently
    wrong neighbours.
    """
    provider = provider or get_provider()
    stored = read_index_metadata(metadata_path)
    current = provider.signature()

    if stored is None:
        return {
            "ok": False,
            "stored": None,
            "current": current,
            "reindex_required": True,
            "reason": (
                f"no embedding metadata at {metadata_path} — "
                "run re-index before using vector retrieval"
            ),
        }
    if signatures_match(stored, provider):
        return {
            "ok": True,
            "stored": stored,
            "current": current,
            "reindex_required": False,
            "reason": "",
        }
    diffs: list[str] = []
    for field in ("provider_id", "model", "dimension"):
        if stored.get(field) != current.get(field):
            diffs.append(
                f"{field}: stored={stored.get(field)!r} "
                f"current={current.get(field)!r}"
            )
    return {
        "ok": False,
        "stored": stored,
        "current": current,
        "reindex_required": True,
        "reason": "embedding signature mismatch — re-index required: "
        + "; ".join(diffs),
    }
