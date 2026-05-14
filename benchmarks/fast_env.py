"""
Fast-mode env vars for benchmark runs.

Kept in a stdlib-only leaf module so the --fast sys.argv pre-pass in
run_benchmarks.py can `from benchmarks.fast_env import ...` without
transitively loading config.py (which captures env values like
DB_ENABLED at import time — too late for --fast to take effect).
"""
from __future__ import annotations

import os

FAST_ENV: dict[str, str] = {
    "DB_ENABLED": "false",
    "RETRIEVER_USE_DB": "false",
    "ROUTER_USE_EMBEDDINGS": "false",
    "INDEX_USE_EMBEDDINGS": "false",
    "RETRIEVER_USE_EMBEDDINGS": "false",
    "BENCHMARK_SKIP_PHANTOM": "true",
    "BENCHMARK_SKIP_PROJECT_MAP": "true",
    "BENCHMARK_FAST_MODE": "true",
    "MAX_MODEL_FALLBACKS": "1",
}


def apply_fast_env() -> None:
    for k, v in FAST_ENV.items():
        os.environ[k] = v
