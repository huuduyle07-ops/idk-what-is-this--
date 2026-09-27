"""OPS.VALIDATE.2 — validation executes the current source, not old bytecode.

CPython decides whether a cached ``.pyc`` may be reused by comparing two
numbers in its header against the source file: the source's size in bytes and
its mtime truncated to whole seconds.  Both are cheap, and both are blind to a
patch that changes bytes without changing either.  That is not a hypothetical
shape — it is exactly the shape this project's patches have::

    return a - b        # baseline, imported once, cached
    return a + b        # same-size replacement inside one timestamp second

The header still matches, so the interpreter loads the *old* bytecode and the
validation that was supposed to judge the patch never sees it.  Reproduced on
CPython 3.14: a same-size, same-mtime replacement of ``return "A"`` with
``return "B"`` kept returning ``"A"``.

``PYTHONDONTWRITEBYTECODE`` / ``-B`` do not fix this.  They suppress *writes*;
the stale file is already on disk and is still *read*.  Both were measured
against the reproduction above and both still observed ``"A"``.

So freshness is bought by moving where the interpreter looks.
``PYTHONPYCACHEPREFIX`` (``sys.pycache_prefix``) redirects the whole cache —
reads included — into a mirror tree at a path of our choosing.  A **fresh
empty directory per validation execution** therefore has nothing in it to be
stale: every module the run imports is compiled from the source bytes that are
on disk right now.

What this deliberately does not do
----------------------------------

The repository's own ``__pycache__`` directories are **not** read, **not**
trusted, and **not** deleted.  They are simply not consulted, which is the
whole difference between this and ``rm -rf`` over somebody's working tree.
Nothing is traversed to find them: this module never looks at the repository at
all, so the freshness guarantee costs zero repository walks.

Validation-produced bytecode lands in the temporary tree and dies with it.
Cleanup is best-effort and can only ever touch the directory this module
created under the system temp root; a cleanup failure leaves a temp directory
behind and cannot mutate the repository.

This is not a caching framework.  It is one environment variable, one
directory, and a context manager that removes it.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PHASE_ID = "OPS.VALIDATE.2"

#: The interpreter-level switch.  Named once so no call site spells it inline.
PYCACHE_PREFIX_ENV = "PYTHONPYCACHEPREFIX"

#: Recognisable in a temp listing, and the prefix a cleanup guard checks for.
VALIDATION_PYCACHE_DIR_PREFIX = "cattus-validation-pycache-"


def _is_owned_cache_dir(path: Path) -> bool:
    """True only for a directory this module could have created.

    The guard is on removal, not on creation: nothing outside the system temp
    root and nothing without our own name prefix is ever handed to ``rmtree``,
    however a caller mangled the value in between.
    """
    try:
        resolved = Path(path).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
    except (OSError, ValueError, TypeError):
        return False
    if not resolved.name.startswith(VALIDATION_PYCACHE_DIR_PREFIX):
        return False
    try:
        resolved.relative_to(temp_root)
    except ValueError:
        return False
    return resolved.is_dir()


def create_validation_bytecode_cache_dir() -> str:
    """Make one fresh, empty, uniquely named bytecode cache directory.

    Returns an empty string when the temp directory cannot be created.  A
    missing cache directory means the run falls back to the interpreter's
    ordinary behaviour rather than failing: validation still executes, it just
    executes without the freshness guarantee, and the caller records that as a
    bounded boolean instead of raising.
    """
    try:
        return tempfile.mkdtemp(prefix=VALIDATION_PYCACHE_DIR_PREFIX)
    except OSError:
        return ""


def discard_validation_bytecode_cache_dir(path: str | os.PathLike[str] | None) -> bool:
    """Remove a cache directory this module created.  Never raises.

    Returns whether the directory is gone.  A directory that was never created
    (empty path) counts as gone; anything that is not one of ours is refused
    and reported as not removed, because silently deleting an unexpected path
    is the failure mode this whole module exists to avoid.
    """
    if not path:
        return True
    target = Path(path)
    if not _is_owned_cache_dir(target):
        return False
    shutil.rmtree(target, ignore_errors=True)
    return not target.exists()


def apply_validation_bytecode_cache_env(
    env: dict[str, str],
    cache_dir: str | None,
) -> dict[str, str]:
    """Point one child process's bytecode cache at ``cache_dir``.

    Applied last, over anything the caller supplied or the parent environment
    carried, because a stale prefix inherited from elsewhere is exactly the
    state this defends against.  With no cache directory the variable is left
    exactly as the environment already had it — nothing is invented.
    """
    if cache_dir:
        env[PYCACHE_PREFIX_ENV] = str(cache_dir)
    return env


@contextmanager
def validation_bytecode_cache() -> Iterator[str]:
    """Own one validation execution's bytecode cache for its lifetime.

    Yields the directory path, or ``""`` when one could not be made.  The
    directory is removed on the way out whatever happened inside — a normal
    finish, a timeout that killed the child, or an exception — so a validation
    that ran out of budget leaves no more behind than one that passed.
    """
    cache_dir = create_validation_bytecode_cache_dir()
    try:
        yield cache_dir
    finally:
        discard_validation_bytecode_cache_dir(cache_dir)


def validation_bytecode_cache_guarantees() -> dict[str, bool]:
    """Bounded, path-free statement of what the mechanism does and refuses."""
    return {
        "repository_pycache_read": False,
        "repository_pycache_deleted": False,
        "repository_traversed": False,
        "source_files_mutated": False,
        "validation_bytecode_written_outside_repository": True,
        "fresh_cache_per_validation_execution": True,
        "temp_cache_cleanup_best_effort": True,
        "cleanup_can_mutate_repository": False,
    }


__all__ = [
    "PHASE_ID",
    "PYCACHE_PREFIX_ENV",
    "VALIDATION_PYCACHE_DIR_PREFIX",
    "create_validation_bytecode_cache_dir",
    "discard_validation_bytecode_cache_dir",
    "apply_validation_bytecode_cache_env",
    "validation_bytecode_cache",
    "validation_bytecode_cache_guarantees",
]
