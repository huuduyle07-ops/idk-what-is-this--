"""Pure repository-relative path-shape policy shared by inventory consumers."""

from __future__ import annotations

import os
from pathlib import Path


MAX_CANONICAL_RELATIVE_PATH_LENGTH = 1024


def is_safe_repository_relative_path(
    value: str | os.PathLike[str],
) -> bool:
    """Validate one portable canonical repository-relative spelling.

    This performs lexical validation only.  Canonical inventory construction
    separately owns filesystem containment and symlink resolution.
    """

    rendered = value if isinstance(value, str) else Path(value).as_posix()
    if (
        not isinstance(rendered, str)
        or not rendered
        or len(rendered) > MAX_CANONICAL_RELATIVE_PATH_LENGTH
        or "\\" in rendered
        or "\x00" in rendered
        or ":" in rendered
        or any(ord(char) < 32 or ord(char) == 127 for char in rendered)
    ):
        return False
    path = Path(rendered)
    if (
        path.is_absolute()
        or path.drive
        or not path.parts
        or path.as_posix() != rendered
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return False

    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CONIN$",
        "CONOUT$",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
    is_reserved = getattr(os.path, "isreserved", None)
    for part in path.parts:
        if callable(is_reserved) and is_reserved(part):
            return False
        if (
            part.rstrip(" .") != part
            or any(char in part for char in '?*|<>"')
            or part.split(".", 1)[0].rstrip(" .").upper() in reserved_names
        ):
            return False
    return True

