"""Backward-compatible repository inventory facade.

The canonical implementation lives in ``core.repository_inventory`` and the
legacy summary shape remains exposed by ``core.repo_librarian``. This module
must not introduce a second recursive membership policy.
"""

from __future__ import annotations

from core.repo_librarian import (
    inspect_repo_inventory as _inspect_repo_inventory,
)


def inspect_repo_inventory(repo_path: str) -> dict:
    return _inspect_repo_inventory(repo_path)
