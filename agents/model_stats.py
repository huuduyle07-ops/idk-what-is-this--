"""Context-scoped recorder for LLM model call attempts and token cost.

Lets the benchmark runner (or any caller) collect per-attempt stats: which
model was tried, whether it succeeded, what role it served in the pipeline,
token usage, and a best-effort paid-tier cost estimate. This avoids threading
a stats object through every client API.

Usage from the caller side:

    with ModelStatsScope() as stats:
        run_agent_web(...)
    # stats is now a list[dict] of all attempts that happened inside.

Usage from a client at each attempt:

    from agents.model_stats import record_model_call
    record_model_call(
        "gemini-3-flash-preview",
        success=True,
        role="draft",
        provider="google",
        usage={"input_tokens": 100, "output_tokens": 50},
    )

Outside of a scope, record_model_call is a no-op, so production code keeps
working when no one is listening.
"""
from __future__ import annotations

import contextvars
import json
import os
from typing import Any, Optional

_current: contextvars.ContextVar[Optional[list[dict]]] = contextvars.ContextVar(
    "model_call_stats", default=None
)

# Paid-tier text/image/video rates from Google Gemini Developer API pricing,
# captured 2026-05-18. Costs are estimates: free-tier usage, Batch/Flex/Priority
# modes, cached-context pricing, tool charges, and Vertex AI pricing may differ.
_GEMINI_PRICING_USD_PER_1M: dict[str, dict[str, float | str]] = {
    "gemini-3.1-flash-lite": {
        "input_per_1m": 0.25,
        "output_per_1m": 1.50,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-3.1-flash-lite-preview": {
        "input_per_1m": 0.25,
        "output_per_1m": 1.50,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-3-flash-preview": {
        "input_per_1m": 0.50,
        "output_per_1m": 3.00,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-2.5-flash": {
        "input_per_1m": 0.30,
        "output_per_1m": 2.50,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-2.5-flash-preview": {
        "input_per_1m": 0.30,
        "output_per_1m": 2.50,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-2.5-flash-preview-09-2025": {
        "input_per_1m": 0.30,
        "output_per_1m": 2.50,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-2.5-flash-lite": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-2.5-flash-lite-preview": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
    "gemini-2.5-flash-lite-preview-09-2025": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "source": "google_gemini_paid_standard_2026-05-18",
    },
}

_LOCAL_PRICING_SOURCE = "local_model_no_api_charge"


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, n)


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _get(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _canonical_model_name(model: str) -> str:
    name = (model or "").strip().lower()
    if name.startswith("models/"):
        name = name.split("/", 1)[1]
    return name


def _infer_provider(model: str, provider: Optional[str] = None) -> str:
    if provider:
        return provider
    name = _canonical_model_name(model)
    if name.startswith("gemini-") or name.startswith("gemma-"):
        return "google"
    if name.startswith("deepseek") or ":" in name:
        return "local"
    return "unknown"


def _pricing_overrides() -> dict[str, dict[str, float | str]]:
    raw = (
        os.getenv("MODEL_COST_OVERRIDES_JSON")
        or os.getenv("LLM_COST_OVERRIDES_JSON")
        or ""
    ).strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    out: dict[str, dict[str, float | str]] = {}
    for model, pricing in data.items():
        if not isinstance(model, str) or not isinstance(pricing, dict):
            continue
        input_rate = _as_float(
            pricing.get("input_per_1m")
            if "input_per_1m" in pricing
            else pricing.get("input")
        )
        output_rate = _as_float(
            pricing.get("output_per_1m")
            if "output_per_1m" in pricing
            else pricing.get("output")
        )
        if input_rate is None or output_rate is None:
            continue
        out[_canonical_model_name(model)] = {
            "input_per_1m": input_rate,
            "output_per_1m": output_rate,
            "source": str(pricing.get("source") or "env_override"),
        }
    return out


def pricing_for_model(
    model: str,
    *,
    provider: Optional[str] = None,
) -> Optional[dict[str, float | str]]:
    """Return USD-per-1M-token pricing for a model, if known."""
    inferred = _infer_provider(model, provider)
    if inferred == "local":
        return {
            "input_per_1m": 0.0,
            "output_per_1m": 0.0,
            "source": _LOCAL_PRICING_SOURCE,
        }

    name = _canonical_model_name(model)
    overrides = _pricing_overrides()
    if name in overrides:
        return overrides[name]

    if name in _GEMINI_PRICING_USD_PER_1M:
        return _GEMINI_PRICING_USD_PER_1M[name]
    return None


def estimate_cost_usd(
    model: str,
    *,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    provider: Optional[str] = None,
) -> tuple[Optional[float], Optional[dict[str, float | str]], Optional[str]]:
    """Estimate token cost for one call.

    Returns (estimated_cost_usd, pricing, note). Cost is None when pricing is
    unknown or token usage is absent.
    """
    pricing = pricing_for_model(model, provider=provider)
    if pricing is None:
        return None, None, "pricing_unknown"

    in_tokens = _as_int(input_tokens)
    out_tokens = _as_int(output_tokens)
    if in_tokens is None and out_tokens is None:
        return None, pricing, "token_usage_unavailable"

    input_rate = float(pricing["input_per_1m"])
    output_rate = float(pricing["output_per_1m"])
    cost = ((in_tokens or 0) * input_rate + (out_tokens or 0) * output_rate) / 1_000_000
    return round(cost, 10), pricing, None


def usage_from_gemini_response(response: Any) -> dict[str, int]:
    """Extract token usage from a Google GenAI GenerateContentResponse."""
    usage = _get(response, "usage_metadata", "usageMetadata")
    if usage is None:
        return {}

    prompt_tokens = _as_int(_get(usage, "prompt_token_count", "promptTokenCount"))
    candidate_tokens = _as_int(
        _get(usage, "candidates_token_count", "candidatesTokenCount")
    )
    thought_tokens = _as_int(_get(usage, "thoughts_token_count", "thoughtsTokenCount"))
    total_tokens = _as_int(_get(usage, "total_token_count", "totalTokenCount"))
    cached_tokens = _as_int(
        _get(usage, "cached_content_token_count", "cachedContentTokenCount")
    )

    output_tokens = (candidate_tokens or 0) + (thought_tokens or 0)
    out: dict[str, int] = {}
    if prompt_tokens is not None:
        out["input_tokens"] = prompt_tokens
    if output_tokens:
        out["output_tokens"] = output_tokens
    elif candidate_tokens is not None:
        out["output_tokens"] = candidate_tokens
    if thought_tokens:
        out["thinking_tokens"] = thought_tokens
    if cached_tokens:
        out["cached_input_tokens"] = cached_tokens
    if total_tokens is not None:
        out["total_tokens"] = total_tokens
    elif prompt_tokens is not None or output_tokens:
        out["total_tokens"] = (prompt_tokens or 0) + output_tokens
    return out


def usage_from_ollama_response(response: Any) -> dict[str, int]:
    """Extract token counts returned by Ollama generate/chat responses."""
    if response is None:
        return {}

    prompt_tokens = _as_int(_get(response, "prompt_eval_count", "promptEvalCount"))
    output_tokens = _as_int(_get(response, "eval_count", "evalCount"))
    total_tokens = None
    if prompt_tokens is not None or output_tokens is not None:
        total_tokens = (prompt_tokens or 0) + (output_tokens or 0)

    out: dict[str, int] = {}
    if prompt_tokens is not None:
        out["input_tokens"] = prompt_tokens
    if output_tokens is not None:
        out["output_tokens"] = output_tokens
    if total_tokens is not None:
        out["total_tokens"] = total_tokens
    return out


def record_model_call(
    model: str,
    *,
    success: bool,
    role: str = "unknown",
    error: Optional[str] = None,
    provider: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    usage: Optional[dict[str, Any]] = None,
) -> None:
    """Append one model-attempt record to the active scope, if any."""
    stats = _current.get()
    if stats is None:
        return
    usage = usage or {}
    provider_name = _infer_provider(model, provider)
    in_tokens = _as_int(input_tokens if input_tokens is not None else usage.get("input_tokens"))
    out_tokens = _as_int(output_tokens if output_tokens is not None else usage.get("output_tokens"))
    total = _as_int(total_tokens if total_tokens is not None else usage.get("total_tokens"))
    if total is None and (in_tokens is not None or out_tokens is not None):
        total = (in_tokens or 0) + (out_tokens or 0)

    estimated, pricing, cost_note = estimate_cost_usd(
        model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        provider=provider_name,
    )

    entry: dict = {
        "model": model,
        "provider": provider_name,
        "role": role,
        "success": success,
    }
    if in_tokens is not None:
        entry["input_tokens"] = in_tokens
    if out_tokens is not None:
        entry["output_tokens"] = out_tokens
    if total is not None:
        entry["total_tokens"] = total
    for key in ("thinking_tokens", "cached_input_tokens"):
        value = _as_int(usage.get(key))
        if value:
            entry[key] = value
    if estimated is not None:
        entry["estimated_cost_usd"] = estimated
    if pricing is not None:
        entry["cost_rates_per_1m"] = {
            "input": pricing["input_per_1m"],
            "output": pricing["output_per_1m"],
        }
        entry["cost_source"] = pricing.get("source")
    if cost_note:
        entry["cost_note"] = cost_note
    if error:
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
    - `models_by_role`: {role: winning_model}
    - token and cost totals: summed across all recorded calls
    """
    attempts = len(stats)
    fallback_count = 0
    selected_model: Optional[str] = None
    models_by_role: dict[str, str] = {}
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    known_cost = 0.0
    costed_calls = 0
    unknown_cost_calls = 0
    by_role: dict[str, dict[str, int | float]] = {}

    per_role_seen: dict[str, int] = {}
    for entry in stats:
        role = entry.get("role") or "unknown"
        per_role_seen[role] = per_role_seen.get(role, 0) + 1
        if per_role_seen[role] > 1:
            fallback_count += 1
        if entry.get("success"):
            selected_model = entry.get("model")
            models_by_role[role] = entry.get("model") or ""

        in_tokens = _as_int(entry.get("input_tokens")) or 0
        out_tokens = _as_int(entry.get("output_tokens")) or 0
        total = _as_int(entry.get("total_tokens")) or (in_tokens + out_tokens)
        input_tokens += in_tokens
        output_tokens += out_tokens
        total_tokens += total

        role_bucket = by_role.setdefault(
            role,
            {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
        )
        role_bucket["calls"] = int(role_bucket["calls"]) + 1
        role_bucket["input_tokens"] = int(role_bucket["input_tokens"]) + in_tokens
        role_bucket["output_tokens"] = int(role_bucket["output_tokens"]) + out_tokens
        role_bucket["total_tokens"] = int(role_bucket["total_tokens"]) + total

        cost = _as_float(entry.get("estimated_cost_usd"))
        if cost is not None:
            known_cost += cost
            costed_calls += 1
            role_bucket["estimated_cost_usd"] = float(role_bucket["estimated_cost_usd"]) + cost
        elif entry.get("success") and (in_tokens or out_tokens):
            unknown_cost_calls += 1

    for role_bucket in by_role.values():
        role_bucket["estimated_cost_usd"] = round(
            float(role_bucket["estimated_cost_usd"]),
            10,
        )

    return {
        "attempts": attempts,
        "fallback_count": fallback_count,
        "selected_model": selected_model,
        "models_by_role": models_by_role,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(known_cost, 10),
        "costed_calls": costed_calls,
        "unknown_cost_calls": unknown_cost_calls,
        "by_role": by_role,
    }


def format_usd(value: Any) -> str:
    amount = _as_float(value)
    if amount is None:
        return "n/a"
    if amount == 0:
        return "$0.00"
    if abs(amount) < 0.01:
        return f"${amount:.6f}"
    return f"${amount:.4f}"


def build_usage_report(stats: list[dict]) -> dict:
    """Return a JSON-serializable report with summary plus per-call details."""
    return {
        "summary": summarize(stats),
        "calls": [
            {"call": idx, **entry}
            for idx, entry in enumerate(stats, start=1)
        ],
    }


def format_usage_report(stats: list[dict]) -> str:
    """Pretty JSON string for web tabs and saved sessions."""
    return json.dumps(build_usage_report(stats), indent=2, ensure_ascii=False)
