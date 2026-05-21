from __future__ import annotations

import re


IDENTITY_PROMPT_HINT = (
    "For project identity questions, treat README.md and docs/ as authoritative. "
    "Benchmarks are the evaluation lab, not the whole product."
)

IDENTITY_ANSWER_FRAMING = """\
You are answering a high-level project identity question.
Treat README.md and docs as authoritative when present.
Start with what the product is for a human user.
Then describe major subsystems.
Do not start from main.py, benchmark cases, or low-level patch pipeline details.
Benchmarks are the evaluation lab, not the whole product.
Mention operator-gated workflow, human learning mode, agent patching mode, Dream/proposal/lesson memory, Mayor Mode handoffs, Patch Safety, and web workspace if present in context.

Expected opening style when supported by context:
"C.A.T.T.U.S is an operator-gated AI coding mentor workspace. It helps a human user understand code, generate safe patch proposals, validate them, record evidence, and promote useful lessons into advisory memory. It also includes a benchmark lab used to evaluate the repair pipeline."
"""

_BENCHMARK_CASE_RE = re.compile(
    r"\b(?:cpp|go|html|javascript|js|python|py|rust|rs|typescript|ts)"
    r"_[a-z0-9]+(?:_[a-z0-9]+)+\b"
)


def infer_context_profile(query: str) -> str:
    """Infer a coarse retrieval/scoring profile from a user query."""
    q = _normalize_text(query)

    strong_benchmark_signals = (
        "benchmark",
        "benchmarks/",
        "validate.py",
        "case.json",
        "failed case",
    )
    test_signals = (
        "pytest",
        "unit test",
        "unit tests",
        "tests/",
        "test fail",
        "test fails",
        "test failure",
        "failing test",
        "why test fails",
    )
    identity_signals = (
        "what is this project",
        "what does this project do",
        "what is this repo",
        "what does this repo do",
        "summarize this repo",
        "summarise this repo",
        "explain architecture",
        "project overview",
        "repo overview",
        "architecture overview",
        "codebase overview",
        "system identity",
    )

    if any(signal in q for signal in test_signals) and not any(
        signal in q for signal in strong_benchmark_signals
    ):
        return "test"

    if (
        any(signal in q for signal in strong_benchmark_signals)
        or _BENCHMARK_CASE_RE.search(q)
        or re.search(r"\bcase\b", q)
    ):
        return "benchmark"

    if any(signal in q for signal in identity_signals):
        return "identity"

    return "default"


def score_multiplier_for_path(path: str, profile: str) -> float:
    """Return a path-sensitive score multiplier for the inferred profile."""
    if profile != "identity":
        return 1.0

    normalized = _normalize_path(path)

    downweighted_prefixes = (
        "benchmarks/cases/",
        "tests/",
        ".agent/",
        ".git/",
        "node_modules/",
        "target/",
    )
    if normalized.startswith(downweighted_prefixes) or _has_path_part(
        normalized, "__pycache__"
    ):
        return 0.05

    boosted_exact = {
        "readme.md": 4.0,
        "core/handoff_notes.py": 3.5,
        "core/worker_runs.py": 3.5,
        "core/lesson_store.py": 3.5,
        "core/lesson_retrieval.py": 3.5,
        "core/dream_artifacts.py": 3.5,
        "web/templates/index.html": 3.5,
        "web/app.py": 3.5,
        "benchmarks/run_benchmarks.py": 1.8,
        "core/control_engine.py": 2.0,
    }
    if normalized in boosted_exact:
        return boosted_exact[normalized]

    boosted_prefixes = {
        "docs/": 3.0,
        "core/": 1.6,
        "web/": 1.6,
        "scripts/": 1.4,
    }
    for prefix, multiplier in boosted_prefixes.items():
        if normalized.startswith(prefix):
            return multiplier

    return 1.0


def should_downweight_path_for_profile(path: str, profile: str) -> bool:
    return score_multiplier_for_path(path, profile) < 1.0


def identity_prompt_hint(query: str) -> str:
    if infer_context_profile(query) == "identity":
        return IDENTITY_PROMPT_HINT
    return ""


def identity_answer_framing(query: str = "", profile: str | None = None) -> str:
    if (profile or infer_context_profile(query)) == "identity":
        return IDENTITY_ANSWER_FRAMING.strip()
    return ""


def _normalize_text(value: str) -> str:
    return str(value or "").replace("\\", "/").lower()


def _normalize_path(path: str) -> str:
    normalized = _normalize_text(path).strip("/")
    if "::" in normalized:
        normalized = normalized.split("::", 1)[0]
    return normalized


def _has_path_part(path: str, part: str) -> bool:
    return part in path.strip("/").split("/")
