def _embed_stub(text: str) -> list:
    """Return a deterministic fake embedding for testing (no external deps)."""
    return [float(ord(c) % 10) / 10 for c in (text or "x")[:4]]


PROVIDER_MAP = {
    "openai": _embed_stub,
    "cohere": _embed_stub,
    # BUG: "openai_v3" was added to provider_config.py but not registered here
}


def get_embedding(provider: str, text: str) -> list:
    fn = PROVIDER_MAP.get(provider)
    if fn is None:
        raise ValueError(f"Unsupported embedding provider: {provider!r}")
    return fn(text)
