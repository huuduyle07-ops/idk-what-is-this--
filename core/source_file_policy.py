"""Side-effect-free canonical source-extension metadata.

``SUPPORTED_EXTENSIONS`` remains the canonical parser/index allow-list.  It is
kept in this tiny module so pure planning code can reuse the exact metadata
without importing application configuration (which loads environment state).
Moving the constant here does not broaden or narrow canonical indexing.
"""

from __future__ import annotations


SUPPORTED_EXTENSIONS = {
    # text / docs
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".json",
    # python
    ".py",
    # rust
    ".rs",
    # mojo
    ".mojo",
    # lua
    ".lua",
    # c-family
    ".c",
    ".h",
    ".cpp",
    ".cxx",
    ".cc",
    ".hpp",
    ".hxx",
    # csharp
    ".cs",
    # web (JS/TS + React)
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    # markup / styles
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    # go
    ".go",
    # java / kotlin
    ".java",
    ".kt",
    ".kts",
}
