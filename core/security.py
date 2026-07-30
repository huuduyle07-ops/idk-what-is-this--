import os
from pathlib import Path

# Files that should NEVER be read or uploaded by the AI
BLACKLIST = {
    ".env", 
    ".git", 
    ".venv", 
    "venv", 
    "node_modules",
    ".gitignore",
    "memory_file_for_agent.txt",
    "session_log.txt",
    "postgres_auth.txt" # Any other secrets
}

def has_safe_path_components(path_value: str | os.PathLike[str]) -> bool:
    """Apply the production filename/component deny rules without I/O."""
    path = Path(path_value)
    path_parts = {
        part.name.lower()
        for part in list(path.parents) + [path]
        if part.name
    }
    if any(black.lower() in path_parts for black in BLACKLIST):
        return False

    name_lower = path.name.lower()
    if name_lower == ".env" or name_lower.startswith(".env."):
        return False
    if any(
        key in name_lower
        for key in (
            "secret",
            "credential",
            "password",
            "token",
            "auth_key",
        )
    ):
        return False

    if path.name.startswith("."):
        if path.name not in {".gitignore", ".github"}:
            if path.suffix not in {".py", ".md", ".txt", ".json"}:
                return False
    return True


def is_safe_path(file_path_str: str, allowed_roots: list[str] | None = None) -> bool:
    """
    Checks if a file path is safe to read/upload.
    1. Must exist.
    2. Must be within one of the allowed_roots (if provided).
    3. Must not be in the BLACKLIST.
    """
    if not file_path_str:
        return False

    # Get absolute path for security (handles symlinks and ..)
    path = Path(file_path_str).expanduser().resolve()
    
    # Rule 0: Must exist
    if not path.exists():
        return False

    # Rule 1: Jail check - Must be within allowed roots
    if allowed_roots:
        resolved_roots = [Path(r).resolve() for r in allowed_roots]
        is_inside = any(path == root or root in path.parents for root in resolved_roots)
        if not is_inside:
            return False
    else:
        # Default fallback: check against application root if no roots provided
        app_root = Path(__file__).parent.parent.resolve()
        if not (path == app_root or app_root in path.parents):
            return False

    # Rules 2-3: deny sensitive components, names, and unsafe dotfiles.
    return has_safe_path_components(path)

