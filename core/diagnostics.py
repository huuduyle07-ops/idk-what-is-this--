from __future__ import annotations

from pathlib import Path
import re
from typing import Any


def extract_locations_from_preflight(output: str, repo_path: str | None = None) -> list[dict[str, Any]]:
    text = output or ""
    locations: list[dict[str, Any]] = []

    repo = Path(repo_path).resolve() if repo_path else None

    def normalize_file(raw: str) -> str:
        raw = raw.strip().strip('"')

        # Convert .\game.go to absolute/relative readable path
        p = Path(raw)

        if repo and not p.is_absolute():
            p = (repo / p).resolve()

        if repo:
            try:
                return str(p.resolve().relative_to(repo)).replace("\\", "/")
            except Exception:
                pass

        return str(p).replace("\\", "/")

    # Node/JS stack trace:
    # at Movement.move (C:\...\movement.js:3:21)
    js_pattern = re.compile(
        r"at\s+(?P<symbol>[A-Za-z0-9_.$<>]+)\s+\((?P<file>.*?\.(?:js|jsx|ts|tsx)):(?P<line>\d+):(?P<col>\d+)\)"
    )

    for m in js_pattern.finditer(text):
        locations.append({
            "kind": "stack_frame",
            "language": "javascript",
            "symbol_hint": m.group("symbol"),
            "file": normalize_file(m.group("file")),
            "line": int(m.group("line")),
            "col": int(m.group("col")),
        })

    # C# compiler:
    # C:\...\game.cs(18,23): error CS1503 ...
    cs_pattern = re.compile(
        r"(?P<file>[A-Za-z]:\\.*?\.(?:cs))\((?P<line>\d+),(?P<col>\d+)\):\s+error\s+(?P<code>CS\d+)"
    )

    for m in cs_pattern.finditer(text):
        locations.append({
            "kind": "compiler_error",
            "language": "csharp",
            "error_code": m.group("code"),
            "file": normalize_file(m.group("file")),
            "line": int(m.group("line")),
            "col": int(m.group("col")),
        })

    # Go compiler:
    # .\game.go:10:18: cannot use ...
    go_pattern = re.compile(
        r"(?P<file>(?:\.\\|\.\/|/|[A-Za-z]:\\).*?\.go):(?P<line>\d+):(?P<col>\d+):"
    )

    for m in go_pattern.finditer(text):
        locations.append({
            "kind": "compiler_error",
            "language": "go",
            "file": normalize_file(m.group("file")),
            "line": int(m.group("line")),
            "col": int(m.group("col")),
        })

    # Rust compiler:
    #  --> src/main.rs:10:18
    rust_pattern = re.compile(
        r"(?:-->\s+)?(?P<file>(?:\.\\|\.\/|/|[A-Za-z]:\\|src/).*?\.rs):(?P<line>\d+):(?P<col>\d+)"
    )

    for m in rust_pattern.finditer(text):
        locations.append({
            "kind": "compiler_error",
            "language": "rust",
            "file": normalize_file(m.group("file")),
            "line": int(m.group("line")),
            "col": int(m.group("col")),
        })

    return dedupe_locations(locations)


def dedupe_locations(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []

    for loc in locations:
        key = (
            loc.get("kind"),
            loc.get("file"),
            loc.get("line"),
            loc.get("col"),
            loc.get("symbol_hint"),
        )
        if key in seen:
            continue

        seen.add(key)
        result.append(loc)

    return result