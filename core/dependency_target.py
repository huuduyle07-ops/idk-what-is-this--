from __future__ import annotations

from dataclasses import dataclass
import os
import posixpath
import re
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DependencyTarget:
    raw_target: str
    target_file: Optional[str]
    target_symbol: Optional[str]
    is_internal: bool
    resolution_kind: str


_JS_TS_LANGUAGES = {
    "javascript",
    "typescript",
    "js",
    "ts",
    "jsx",
    "tsx",
}

_JS_TS_EXTENSIONS = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)

_KNOWN_SOURCE_EXTENSIONS = {
    ".py",
    *_JS_TS_EXTENSIONS,
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".cs",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
}

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_QUOTED_MODULE_RE = re.compile(r"""['"]([^'"]+)['"]""")


def _is_absolute_like(value: str) -> bool:
    text = (value or "").strip()
    return (
        text.startswith("/")
        or text.startswith("\\\\")
        or bool(_WINDOWS_DRIVE_RE.match(text))
    )


def _normalize_repo_relative(value: str) -> Optional[str]:
    text = (value or "").strip().replace("\\", "/")
    if not text or _is_absolute_like(text):
        return None

    normalized = posixpath.normpath(text)

    if normalized in {"", ".", ".."}:
        return None

    if normalized.startswith("../"):
        return None

    return normalized


def _extract_import_target(
    raw_target: str,
    language: str,
) -> str:
    """Extract the module/path portion from parser fallback forms."""
    text = (raw_target or "").strip().rstrip(";").strip()
    if not text:
        return ""

    lang = (language or "").lower().strip()

    # JS/TS and several fallback parser forms preserve a quoted specifier.
    quoted = _QUOTED_MODULE_RE.findall(text)
    if quoted:
        if lang in _JS_TS_LANGUAGES:
            return quoted[-1]

        if text.startswith(("import ", "from ", "use ")):
            return quoted[-1]

    if text.startswith("from ") and " import " in text:
        module, imported = text[5:].split(" import ", 1)
        module = module.strip()

        # `from . import utils` should resolve as `.utils`.
        if module and set(module) == {"."}:
            first_name = (
                imported.split(",", 1)[0]
                .strip()
                .split(" as ", 1)[0]
                .strip()
            )
            if first_name and first_name != "*":
                return module + first_name

        return module

    if text.startswith("import "):
        target = text[7:].split(",", 1)[0].strip()
        target = target.split(" as ", 1)[0].strip()
        return target.strip("'\"")

    return text.strip("'\"")


def _repository_file_index(
    repository_files: set[str] | None,
) -> dict[str, str] | None:
    if repository_files is None:
        return None

    index: dict[str, str] = {}

    for item in repository_files:
        normalized = _normalize_repo_relative(item)
        if normalized is None:
            continue

        # normcase is meaningful on Windows and a no-op on normal Linux.
        key = os.path.normcase(normalized)
        index.setdefault(key, normalized)

    return index


def _existing_candidate(
    *,
    root: Path,
    candidate: str,
    file_index: dict[str, str] | None,
) -> Optional[str]:
    normalized = _normalize_repo_relative(candidate)
    if normalized is None:
        return None

    if file_index is not None:
        return file_index.get(os.path.normcase(normalized))

    path = (root / Path(normalized)).resolve()

    try:
        relative = path.relative_to(root)
    except ValueError:
        return None

    if not path.is_file():
        return None

    return relative.as_posix()


def _resolve_unique(
    *,
    root: Path,
    candidates: list[str],
    file_index: dict[str, str] | None,
) -> tuple[Optional[str], bool]:
    """Return `(target, ambiguous)` for existing candidate files."""
    matches: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        existing = _existing_candidate(
            root=root,
            candidate=candidate,
            file_index=file_index,
        )
        if existing is None or existing in seen:
            continue

        seen.add(existing)
        matches.append(existing)

    if len(matches) == 1:
        return matches[0], False

    return None, len(matches) > 1


def _unresolved(
    *,
    raw_target: str,
    symbol: Optional[str],
    kind: str = "external_or_unresolved",
) -> DependencyTarget:
    return DependencyTarget(
        raw_target=raw_target,
        target_file=None,
        target_symbol=symbol or None,
        is_internal=False,
        resolution_kind=kind,
    )


def _internal(
    *,
    raw_target: str,
    target_file: str,
    kind: str,
) -> DependencyTarget:
    return DependencyTarget(
        raw_target=raw_target,
        target_file=target_file,
        target_symbol=None,
        is_internal=True,
        resolution_kind=kind,
    )


def _resolve_python_target(
    *,
    root: Path,
    source_file: str,
    raw_target: str,
    module: str,
    file_index: dict[str, str] | None,
) -> DependencyTarget:
    source_dir = posixpath.dirname(source_file)

    if module.startswith("."):
        dot_count = len(module) - len(module.lstrip("."))
        source_parts = [
            part
            for part in source_dir.split("/")
            if part
        ]

        if dot_count > len(source_parts):
            return _unresolved(
                raw_target=raw_target,
                symbol=None,
                kind="unsafe_target",
            )

        suffix = module[dot_count:]

        anchor = source_dir
        for _ in range(dot_count - 1):
            anchor = posixpath.dirname(anchor)

        module_path = suffix.replace(".", "/")
        base = (
            posixpath.join(anchor, module_path)
            if module_path
            else anchor
        )
        kind = "python_relative_module"
    else:
        base = module.replace(".", "/")
        kind = "python_module"

    candidates = [
        f"{base}.py",
        posixpath.join(base, "__init__.py"),
    ]

    target, ambiguous = _resolve_unique(
        root=root,
        candidates=candidates,
        file_index=file_index,
    )

    if target:
        return _internal(
            raw_target=raw_target,
            target_file=target,
            kind=kind,
        )

    return _unresolved(
        raw_target=raw_target,
        symbol=module,
        kind="ambiguous" if ambiguous else "external_or_unresolved",
    )


def _resolve_js_ts_target(
    *,
    root: Path,
    source_file: str,
    raw_target: str,
    specifier: str,
    file_index: dict[str, str] | None,
) -> DependencyTarget:
    normalized_specifier = specifier.replace("\\", "/")
    is_relative = normalized_specifier.startswith(".")

    # Bare module specifiers are packages or aliases unless alias metadata
    # proves otherwise. Do not guess them into repository files.
    if not is_relative:
        return _unresolved(
            raw_target=raw_target,
            symbol=specifier,
            kind="external_or_unresolved",
        )

    source_dir = posixpath.dirname(source_file)
    base = posixpath.normpath(
        posixpath.join(
            source_dir,
            normalized_specifier,
        )
    )

    if not base or base == ".." or base.startswith("../"):
        return _unresolved(
            raw_target=raw_target,
            symbol=None,
            kind="unsafe_target",
        )

    suffix = Path(base).suffix.lower()

    if suffix in _KNOWN_SOURCE_EXTENSIONS:
        candidates = [base]
    else:
        candidates = [base]
        candidates.extend(
            base + ext
            for ext in _JS_TS_EXTENSIONS
        )
        candidates.extend(
            posixpath.join(base, "index" + ext)
            for ext in _JS_TS_EXTENSIONS
        )

    target, ambiguous = _resolve_unique(
        root=root,
        candidates=candidates,
        file_index=file_index,
    )

    if target:
        return _internal(
            raw_target=raw_target,
            target_file=target,
            kind="relative_file",
        )

    return _unresolved(
        raw_target=raw_target,
        symbol=specifier,
        kind=(
            "ambiguous"
            if ambiguous
            else "external_or_unresolved"
        ),
    )

def resolve_dependency_target(
    *,
    repo_root: str | Path,
    source_file: str,
    language: str,
    raw_target: str,
    repository_files: set[str] | None = None,
) -> DependencyTarget:
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(
            f"Repository root is not a directory: {repo_root}"
        )

    source_rel = _normalize_repo_relative(source_file)
    if source_rel is None:
        raise ValueError(
            f"source_file must be repository-relative: {source_file!r}"
        )

    raw = (raw_target or "").strip()
    target = _extract_import_target(raw, language)

    if not target:
        return _unresolved(
            raw_target=raw,
            symbol=None,
            kind="empty_target",
        )

    if _is_absolute_like(target):
        return _unresolved(
            raw_target=raw,
            symbol=None,
            kind="unsafe_target",
        )

    file_index = _repository_file_index(repository_files)
    lang = (language or "").lower().strip()

    if lang == "python":
        return _resolve_python_target(
            root=root,
            source_file=source_rel,
            raw_target=raw,
            module=target,
            file_index=file_index,
        )

    if lang in _JS_TS_LANGUAGES:
        return _resolve_js_ts_target(
            root=root,
            source_file=source_rel,
            raw_target=raw,
            specifier=target,
            file_index=file_index,
        )

    # Conservative generic exact-file support. Unknown package/module forms
    # remain symbolic rather than being guessed into target_file.
    normalized_target = _normalize_repo_relative(target)
    if normalized_target is not None:
        suffix = Path(normalized_target).suffix.lower()

        if suffix in _KNOWN_SOURCE_EXTENSIONS:
            exact, _ = _resolve_unique(
                root=root,
                candidates=[normalized_target],
                file_index=file_index,
            )
            if exact:
                return _internal(
                    raw_target=raw,
                    target_file=exact,
                    kind="exact_file",
                )

    return _unresolved(
        raw_target=raw,
        symbol=target,
    )