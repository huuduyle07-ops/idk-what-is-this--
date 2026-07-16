from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pathspec import PathSpec

ANY_DEPTH_HARD_EXCLUDES = frozenset(
    {
        ".git",
        ".agent",
        ".tmp",
        ".temp",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "Obsidian Graph",
        "obsidian_graph",
    }
)

ROOT_ONLY_HARD_EXCLUDES = frozenset(
    {
        ".vscode",
        ".gemini",
        ".idea",
        ".vs",
        ".claude",
        "build",
        "dist",
        "target",
        "bin",
        "obj",
        "storage",
    }
)

_ANY_DEPTH_HARD_EXCLUDES_CASEFOLDED = frozenset(
    name.casefold() for name in ANY_DEPTH_HARD_EXCLUDES
)

_ROOT_ONLY_HARD_EXCLUDES_CASEFOLDED = frozenset(
    name.casefold() for name in ROOT_ONLY_HARD_EXCLUDES
)

@dataclass(frozen=True)
class IgnoreDecision:
    ignored: bool
    source: str | None = None
    pattern: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class RepoIgnorePolicy:
    repo_root: Path
    gitignore_spec: PathSpec
    cattusignore_spec: PathSpec

    @classmethod
    def load(cls, repo_root: Path) -> "RepoIgnorePolicy":
        root = repo_root.expanduser().resolve()

        return cls(
            repo_root=root,
            gitignore_spec=_load_ignore_spec(root / ".gitignore"),
            cattusignore_spec=_load_ignore_spec(root / ".cattusignore"),
        )

    def classify(
        self,
        rel_path: Path,
        *,
        is_dir: bool,
    ) -> IgnoreDecision:
        rel = _normalize_relative_path(
            self.repo_root,
            rel_path,
        )

        if rel is None:
            return IgnoreDecision(
                ignored=True,
                source="repository_boundary",
                reason="path is outside the repository root",
            )

        # Hard exclusions always win and cannot be reopened
        # by .gitignore or .cattusignore negation patterns.
        for original_part in rel.parts:
            if (
                original_part.casefold()
                in _ANY_DEPTH_HARD_EXCLUDES_CASEFOLDED
            ):
                return IgnoreDecision(
                    ignored=True,
                    source="hard_exclude",
                    pattern=original_part,
                    reason=(
                        "matched a non-overridable "
                        "C.A.T.T.U.S any-depth exclusion"
                    ),
                )

        if rel.parts:
            root_part = rel.parts[0]

            if (
                root_part.casefold()
                in _ROOT_ONLY_HARD_EXCLUDES_CASEFOLDED
            ):
                return IgnoreDecision(
                    ignored=True,
                    source="hard_exclude",
                    pattern=root_part,
                    reason=(
                        "matched a non-overridable "
                        "C.A.T.T.U.S repository-root exclusion"
                    ),
                )

        candidate = rel.as_posix()

        # Directory patterns such as build/ require a trailing slash.
        if is_dir:
            candidate = candidate.rstrip("/") + "/"

        gitignore_decision = _match_spec(
            self.gitignore_spec,
            candidate,
            source=".gitignore",
        )

        if (
            gitignore_decision is not None
            and gitignore_decision.ignored
        ):
            return gitignore_decision

        cattusignore_decision = _match_spec(
            self.cattusignore_spec,
            candidate,
            source=".cattusignore",
        )

        if (
            cattusignore_decision is not None
            and cattusignore_decision.ignored
        ):
            return cattusignore_decision

        return IgnoreDecision(ignored=False)


def _load_ignore_spec(path: Path) -> PathSpec:
    if not path.is_file():
        return PathSpec([])

    try:
        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError:
        # Fail soft: an unreadable optional ignore file must not crash
        # repository discovery.
        return PathSpec([])

    return PathSpec.from_lines("gitwildmatch", lines)


def _normalize_relative_path(
    repo_root: Path,
    path: Path,
) -> Path | None:
    candidate = Path(path)

    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(repo_root)
        except (OSError, ValueError):
            return None

    if any(part == ".." for part in candidate.parts):
        return None

    return candidate


def _match_spec(
    spec: PathSpec,
    candidate: str,
    *,
    source: str,
) -> IgnoreDecision | None:
    result = spec.check_file(candidate)

    if result.include is None or result.index is None:
        return None

    matched_pattern = spec.patterns[result.index].pattern

    # include=False is a Gitignore negation such as !keep.py.
    if result.include is False:
        return IgnoreDecision(
            ignored=False,
            source=source,
            pattern=matched_pattern,
            reason="explicitly re-included by ignore policy",
        )

    return IgnoreDecision(
        ignored=True,
        source=source,
        pattern=matched_pattern,
        reason=f"matched {source} pattern",
    )