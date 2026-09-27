"""Side-effect-free canonical source-extension metadata.

``SUPPORTED_EXTENSIONS`` remains the canonical parser/index allow-list.  It is
kept in this tiny module so pure planning code can reuse the exact metadata
without importing application configuration (which loads environment state).
Moving the constant here does not broaden or narrow canonical indexing.
"""

from __future__ import annotations


#: Version of this project's symbol/call/import extraction semantics.
#:
#: It lives here, beside the extension allow-list, for the same reason: pure
#: modules - ``core.repo_ignore``'s policy fingerprint among them - need the
#: canonical parser/index metadata without importing application
#: configuration.  ``core.treesitter_parse`` re-exports it beside the code it
#: describes.
#:
#: Bump it when a change makes previously stored symbol artifacts incompatible
#: with what extraction now produces.  The bump reaches the repository manifest
#: through ``compute_policy_fingerprint``, so a stale index is re-indexed once
#: rather than reused forever - and rather than rebuilt on every run.
#:
#: ``v2`` fixed the byte/character offset defect: tree-sitter reports byte
#: offsets into the UTF-8 buffer it parsed, and extraction sliced the Python
#: ``str`` with them, so every symbol and call name extracted after the first
#: non-ASCII character in a file was a shifted fragment of the source.
SYMBOL_EXTRACTION_VERSION = "treesitter_extraction_v2_byte_offsets"


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


#: Indexing role of a supported extension.
#:
#: RETRIEVE.LIVE.1 needs to know whether a candidate's file is *source code*
#: without importing ``config`` (which loads environment state).  The roles
#: mirror ``config.LANGUAGE_MAP``: an extension whose language is ``document``,
#: ``text`` or ``json`` is not code, everything else is.
#: ``tests/test_localization_candidate_population.py`` pins the two together so
#: the derived view cannot drift from the map it mirrors.
SOURCE_ROLE_CODE = "code"
SOURCE_ROLE_DOCUMENT = "document"
SOURCE_ROLE_DATA = "data"

SOURCE_ROLE_BY_EXTENSION: dict[str, str] = {
    extension: (
        SOURCE_ROLE_DOCUMENT
        if extension in {".txt", ".md", ".pdf", ".docx"}
        else SOURCE_ROLE_DATA
        if extension in {".json"}
        else SOURCE_ROLE_CODE
    )
    for extension in SUPPORTED_EXTENSIONS
}
