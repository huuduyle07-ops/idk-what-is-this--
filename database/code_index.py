"""Strict canonical code-index database boundary.

Production canonical callers use this module and must supply a non-empty
``index_scope``. The physical database column is still named ``project_tag``
for schema compatibility, but semantic project labels never enter this API.

The older functions in ``database.memory`` remain compatibility primitives for
non-canonical callers. This facade prevents canonical reads, writes, deletes,
and reconciliation from reaching their unscoped branches.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import os
from typing import Any

from core.repository_identity import is_code_index_scope
from database import memory as _memory


def _require_index_scope(index_scope: object) -> str:
    if not isinstance(index_scope, str) or not index_scope.strip():
        raise ValueError(
            "index_scope is required for canonical code-index access"
        )
    canonical = index_scope.strip()
    if not is_code_index_scope(canonical):
        raise ValueError(
            "index_scope is required to be a canonical code-index scope"
        )
    return canonical


def _require_current_files(
    current_files: Iterable[object] | None,
) -> set[str]:
    if (
        current_files is None
        or isinstance(
            current_files,
            (str, bytes, os.PathLike),
        )
    ):
        raise ValueError(
            "current_files must not be empty for reconciliation"
        )
    canonical = set()
    try:
        iterator = iter(current_files)
    except TypeError as exc:
        raise ValueError(
            "current_files must contain repository-relative paths"
        ) from exc

    for file_path in iterator:
        if not isinstance(file_path, (str, os.PathLike)):
            raise ValueError(
                "current_files must contain repository-relative paths"
            )
        rendered = os.fspath(file_path)
        if not isinstance(rendered, str) or not rendered.strip():
            raise ValueError(
                "current_files must contain non-blank paths"
            )
        canonical.add(rendered.replace("\\", "/"))

    if not canonical:
        raise ValueError(
            "current_files must not be empty for reconciliation"
        )
    return canonical


def db_enabled() -> bool:
    return _memory.db_enabled()


def init_db() -> None:
    _memory.init_db()


def replace_code_index_for_file(
    *,
    file_path: str,
    index_scope: str,
    code_units: Sequence[Mapping[str, Any]],
    dependencies: Sequence[Mapping[str, Any]],
) -> int:
    scope = _require_index_scope(index_scope)
    if not db_enabled():
        return 0
    return _memory.replace_code_index_for_file(
        file_path=file_path,
        index_scope=scope,
        code_units=[dict(unit) for unit in code_units],
        dependencies=[
            dict(dependency)
            for dependency in dependencies
        ],
    )


def delete_code_index_for_file(
    *,
    file_path: str,
    index_scope: str,
) -> bool:
    scope = _require_index_scope(index_scope)
    if not db_enabled():
        return False
    return _memory.delete_code_index_for_file(
        file_path=file_path,
        index_scope=scope,
    )


def reconcile_code_index_scope(
    *,
    index_scope: str,
    current_files: Iterable[object],
) -> dict[str, int]:
    scope = _require_index_scope(index_scope)
    canonical_files = _require_current_files(current_files)
    if not db_enabled():
        return {
            "dependencies_deleted": 0,
            "code_units_deleted": 0,
        }
    return _memory.reconcile_code_index_scope(
        index_scope=scope,
        current_files=canonical_files,
    )


def search_code_units(
    query_text: str,
    *,
    index_scope: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    scope = _require_index_scope(index_scope)
    if not db_enabled():
        return []
    return _memory.search_code_units(
        query_text,
        limit=limit,
        project_tag=scope,
    )


def search_dependencies(
    query_text: str,
    *,
    index_scope: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    scope = _require_index_scope(index_scope)
    if not db_enabled():
        return []
    return _memory.search_dependencies(
        query_text,
        limit=limit,
        project_tag=scope,
    )
