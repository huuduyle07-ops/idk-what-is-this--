"""Context-scoped recorder for LLM model call attempts.

Lets the benchmark runner (or any caller) collect per-attempt stats —
which model was tried, whether it succeeded, what role it served in the
pipeline — without threading a stats object through every client API.

Usage from the caller side:

    with ModelStatsScope() as stats:
        run_agent_web(...)
    # stats is now a list[dict] of all attempts that happened inside.

Usage from a client at each attempt:

    from agents.model_stats import record_model_call
    record_model_call("gemini-3-flash-preview", success=True, role="draft")

Outside of a scope, record_model_call is a no-op — production code keeps
working when no one is listening.
"""
from __future__ import annotations

import contextvars
from typing import Optional

_current: contextvars.ContextVar[Optional[list[dict]]] = contextvars.ContextVar(
    "model_call_stats", default=None
)


def record_model_call(
    model: str,
    *,
    success: bool,
    role: str = "unknown",
    error: Optional[str] = None,
) -> None:
    """Append one model-attempt record to the active scope, if any."""
    stats = _current.get()
    if stats is None:
        return
    entry: dict = {"model": model, "role": role, "success": success}
    if error:
        # Keep errors short — full tracebacks blow up reports.
        entry["error"] = error[:200]
    stats.append(entry)


class ModelStatsScope:
    """Context manager that collects model-call records inside its body."""

    def __init__(self) -> None:
        self.stats: list[dict] = []
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> list[dict]:
        self._token = _current.set(self.stats)
        return self.stats

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._token is not None:
            _current.reset(self._token)
            self._token = None


def summarize(stats: list[dict]) -> dict:
    """Produce a per-case summary from a stats list.

    - `attempts`: total recorded attempts (across all roles)
    - `fallback_count`: attempts beyond the first per role, summed
    - `selected_model`: the model from the last successful attempt overall
    - `models_by_role`: {role: winning_model} — useful when one case
      involves draft + review + refine and you want to know which
      specific model each phase landed on
    """
    attempts = len(stats)
    fallback_count = 0
    selected_model: Optional[str] = None
    models_by_role: dict[str, str] = {}

    # Per-role iteration: anything beyond the first attempt within a role
    # counts as a fallback for that role.
    per_role_seen: dict[str, int] = {}
    for entry in stats:
        role = entry.get("role") or "unknown"
        per_role_seen[role] = per_role_seen.get(role, 0) + 1
        if per_role_seen[role] > 1:
            fallback_count += 1
        if entry.get("success"):
            selected_model = entry.get("model")
            models_by_role[role] = entry.get("model") or ""

    return {
        "attempts": attempts,
        "fallback_count": fallback_count,
        "selected_model": selected_model,
        "models_by_role": models_by_role,
    }
