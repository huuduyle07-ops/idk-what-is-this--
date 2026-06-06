"""Pytest-wide environment defaults.

Some local harness toggles are intentionally editable in `.env`, but invariant
tests assert the project's shipped defaults. Pin those defaults before test
modules import `config`, because `python-dotenv` does not override existing
process environment values.
"""
from __future__ import annotations

import os


os.environ["MEMORY_TEMPERATURE_RETRIEVAL_ENABLED"] = "false"
