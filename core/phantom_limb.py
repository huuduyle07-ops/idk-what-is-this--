# core/phantom_limb.py
"""Phantom Limb scanner: surfaces *missing* structural pieces (suggestions, not bugs).

Rules are precision-first — we'd rather miss a real issue than emit a false positive.
Each rule is gated by language, file role (test vs. non-test), and structural pre-checks
before any regex matches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------- public types ----------

@dataclass
class ScanContext:
    repo_path: str
    file_summaries: list[dict]
    _text_cache: dict[str, str] = field(default_factory=dict)

    def file_text(self, rel_path: str) -> str:
        if rel_path in self._text_cache:
            return self._text_cache[rel_path]
        try:
            text = (Path(self.repo_path) / rel_path).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            text = ""
        self._text_cache[rel_path] = text
        return text


@dataclass
class Rule:
    name: str
    languages: tuple[str, ...]                                  # () means any language
    detect: Callable[["ScanContext", dict], list[str]]
    severity: str = "info"                                      # info | warn


# ---------- helpers ----------

_TEST_PATTERNS = (
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"_test\.py$"),
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)__tests__/"),
    re.compile(r"\.test\.[jt]sx?$"),
    re.compile(r"\.spec\.[jt]sx?$"),
    re.compile(r"Tests?\.cs$"),
    re.compile(r"_test\.go$"),
    re.compile(r"(^|/)tests\.rs$"),
    re.compile(r"_tests?\.rs$"),
    re.compile(r"_test\.(?:cpp|cc|cxx|c|h|hpp|hxx)$"),
    re.compile(r"Test\.(?:cpp|cc|cxx|c|h|hpp|hxx)$"),
)


def _is_test_file(rel_path: str) -> bool:
    p = rel_path.replace("\\", "/")
    return any(pat.search(p) for pat in _TEST_PATTERNS)


def _symbol_names(file_summary: dict) -> set[str]:
    out: set[str] = set()
    for sym in file_summary.get("main_symbols") or []:
        name = sym.get("name") if isinstance(sym, dict) else sym
        if isinstance(name, str) and name:
            out.add(name)
    return out


def _blank_keep_newlines(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def _strip_python(src: str) -> str:
    src = re.sub(r'""".*?"""', _blank_keep_newlines, src, flags=re.DOTALL)
    src = re.sub(r"'''.*?'''", _blank_keep_newlines, src, flags=re.DOTALL)
    src = re.sub(r"#[^\n]*", _blank_keep_newlines, src)
    return src


def _strip_c_like(src: str) -> str:
    # Replace block comments, line comments, and string literals with spaces
    # (keeping newlines) so regex rules don't match commented or quoted text.
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nx = src[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "*":
            end = src.find("*/", i + 2)
            end = (end + 2) if end != -1 else n
            out.append(re.sub(r"[^\n]", " ", src[i:end]))
            i = end
            continue
        if c == "/" and nx == "/":
            end = src.find("\n", i)
            end = end if end != -1 else n
            out.append(" " * (end - i))
            i = end
            continue
        if c in ('"', "'"):
            quote = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "\n" or src[j] == quote:
                    if src[j] == quote:
                        j += 1
                    break
                j += 1
            out.append(re.sub(r"[^\n]", " ", src[i:j]))
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out)


# ---------- detectors ----------

def _missing_teardown(ctx: ScanContext, s: dict) -> list[str]:
    if not _is_test_file(s["file"]):
        return []
    lang = s.get("language")
    if lang == "python":
        syms = _symbol_names(s)
        if "setUp" in syms and "tearDown" not in syms:
            return ["tearDown method"]
        return []
    if lang == "csharp":
        clean = _strip_c_like(ctx.file_text(s["file"]))
        if re.search(r"\[\s*SetUp\s*\]", clean) and not re.search(
            r"\[\s*TearDown\s*\]", clean
        ):
            return ["[TearDown] method"]
        return []
    return []


def _swallowed_exception(ctx: ScanContext, s: dict) -> list[str]:
    if _is_test_file(s["file"]):
        return []
    text = ctx.file_text(s["file"])
    if not text:
        return []
    lang = s.get("language")

    if lang == "python":
        clean = _strip_python(text)
        if re.search(
            r"except\b[^:\n]*:\s*\n(?:[ \t]+pass\b[ \t]*\n)+", clean
        ):
            return ["error handling — `except: pass` swallows the exception"]
        return []

    if lang in {"javascript", "typescript", "csharp"}:
        clean = _strip_c_like(text)
        if re.search(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}", clean):
            return ["error handling — empty catch block"]
        return []

    return []


def _cpp_virtual_no_virtual_dtor(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "cpp" or _is_test_file(s["file"]):
        return []
    clean = _strip_c_like(ctx.file_text(s["file"]))
    if not clean:
        return []

    findings: list[str] = []
    for m in re.finditer(r"\b(?:class|struct)\s+([A-Za-z_]\w*)[^{;]*\{", clean):
        cls = m.group(1)
        # Walk braces to find this class's body end.
        i, depth, n = m.end(), 1, len(clean)
        while i < n and depth:
            if clean[i] == "{":
                depth += 1
            elif clean[i] == "}":
                depth -= 1
            i += 1
        body = clean[m.end(): i - 1]

        if not re.search(r"\bvirtual\b", body):
            continue
        has_virtual_dtor = (
            re.search(rf"\bvirtual\s*~\s*{re.escape(cls)}\b", body)
            or re.search(rf"~\s*{re.escape(cls)}\b[^;{{]*\boverride\b", body)
        )
        if not has_virtual_dtor:
            findings.append(f"virtual destructor on `{cls}`")
    return findings[:3]


def _header_missing_include_guard(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") not in {"c", "cpp"}:
        return []
    if Path(s["file"]).suffix.lower() not in {".h", ".hpp", ".hxx"}:
        return []
    text = ctx.file_text(s["file"])
    if not text or "#pragma once" in text:
        return []
    if re.search(r"#\s*ifndef\s+\w+\s*[\r\n]+\s*#\s*define\s+\w+", text[:2000]):
        return []
    return ["include guard (`#pragma once` or `#ifndef`/`#define` pair)"]


def _html_head_missing_title(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "html":
        return []
    text = ctx.file_text(s["file"])
    head = re.search(r"<head\b[^>]*>(.*?)</head\s*>", text, flags=re.IGNORECASE | re.DOTALL)
    if not head:
        return []
    if re.search(r"<title\b[^>]*>.*?</title\s*>", head.group(1), flags=re.IGNORECASE | re.DOTALL):
        return []
    return ["<title> inside <head>"]


def _html_blank_target_no_noopener(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "html":
        return []
    text = ctx.file_text(s["file"])
    if not text:
        return []
    for tag in re.finditer(r"<a\b[^>]*>", text, flags=re.IGNORECASE):
        attrs = tag.group(0)
        if not re.search(r'target\s*=\s*["\']?_blank["\']?', attrs, flags=re.IGNORECASE):
            continue
        rel = re.search(r'rel\s*=\s*"([^"]*)"|rel\s*=\s*\'([^\']*)\'', attrs, flags=re.IGNORECASE)
        rel_val = ((rel.group(1) or rel.group(2)) if rel else "").lower()
        if "noopener" in rel_val:
            continue
        return ['rel="noopener" on `target="_blank"` anchor']
    return []


def _python_script_no_main_guard(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "python":
        return []
    file = s["file"].replace("\\", "/")
    if _is_test_file(file) or Path(file).name == "__init__.py":
        return []

    text = ctx.file_text(file)
    if not text:
        return []
    if re.search(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:', text):
        return []

    clean = _strip_python(text)
    # Top-level (zero-indent) markers that strongly imply "this file is a script".
    looks_like_script = bool(
        re.search(r"^\S.*=\s*argparse\.ArgumentParser\(", clean, flags=re.MULTILINE)
        or re.search(r"^asyncio\.run\(", clean, flags=re.MULTILINE)
        or re.search(r"^\S.*=\s*sys\.argv\b", clean, flags=re.MULTILINE)
    )
    if not looks_like_script:
        return []
    return ["`if __name__ == '__main__':` guard"]


def _ts_any_type(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "typescript":
        return []
    file = s["file"]
    if file.endswith(".d.ts") or _is_test_file(file):
        return []
    text = ctx.file_text(file)
    if not text or "@ts-nocheck" in text:
        return []

    clean = _strip_c_like(text)
    count = len(re.findall(r":\s*any\b", clean)) + len(re.findall(r"\bas\s+any\b", clean))
    if count == 0:
        return []
    return [f"explicit type — {count} `any` annotation(s)"]


def _rust_todo_or_unimplemented(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "rust" or _is_test_file(s["file"]):
        return []
    text = ctx.file_text(s["file"])
    if not text:
        return []
    findings: list[str] = []
    if re.search(r"\btodo!\s*\(", text):
        findings.append("implementation — `todo!()` placeholder still present")
    if re.search(r"\bunimplemented!\s*\(", text):
        findings.append("implementation — `unimplemented!()` placeholder still present")
    return findings


def _css_empty_rule(ctx: ScanContext, s: dict) -> list[str]:
    if s.get("language") != "css":
        return []
    text = ctx.file_text(s["file"])
    if not text:
        return []
    clean = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    empties = re.findall(r"[^{}\s][^{}]*\{\s*\}", clean)
    if not empties:
        return []
    return [f"declarations in {len(empties)} empty rule set(s)"]


# ---------- registry + entry point ----------

RULES: list[Rule] = [
    Rule("missing_teardown",                ("python", "csharp"),                 _missing_teardown),
    Rule("swallowed_exception",             ("python", "javascript", "typescript", "csharp"),
                                                                                  _swallowed_exception, "warn"),
    Rule("cpp_virtual_no_virtual_dtor",     ("cpp",),                             _cpp_virtual_no_virtual_dtor, "warn"),
    Rule("header_missing_include_guard",    ("c", "cpp"),                         _header_missing_include_guard),
    Rule("html_head_missing_title",         ("html",),                            _html_head_missing_title, "warn"),
    Rule("html_blank_target_no_noopener",   ("html",),                            _html_blank_target_no_noopener, "warn"),
    Rule("ts_any_type",                     ("typescript",),                      _ts_any_type),
    Rule("python_script_no_main_guard",     ("python",),                          _python_script_no_main_guard),
    Rule("rust_todo_or_unimplemented",      ("rust",),                            _rust_todo_or_unimplemented, "warn"),
    Rule("css_empty_rule",                  ("css",),                             _css_empty_rule),
]


def scan(file_summaries: list[dict], repo_path: str) -> list[dict]:
    ctx = ScanContext(repo_path=repo_path, file_summaries=file_summaries)
    findings: list[dict] = []

    for s in file_summaries:
        lang = s.get("language") or "unknown"
        for rule in RULES:
            if rule.languages and lang not in rule.languages:
                continue
            try:
                missing_items = rule.detect(ctx, s) or []
            except Exception as exc:
                # A buggy rule must not poison the whole scan.
                findings.append({
                    "rule": rule.name,
                    "file": s.get("file", "?"),
                    "missing": f"<rule error: {exc}>",
                    "severity": "error",
                })
                continue

            for missing in missing_items:
                findings.append({
                    "rule": rule.name,
                    "file": s["file"],
                    "missing": missing,
                    "severity": rule.severity,
                })

    return findings