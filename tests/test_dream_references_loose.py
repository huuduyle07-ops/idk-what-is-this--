"""Phase 4.7e-a — Loose Research Note Normalizer.

Tests that the Zapier/Discord-style parser extracts the right fields,
deduplicates URLs, infers source type/reliability conservatively, fills
in missing risks / do_not_assume with conservative warnings, and still
respects explicit caller-supplied structured fields. No URL fetching is
permitted.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from core import dream_references


# A realistic Zapier/Discord-style block, including duplicated URLs and a
# couple of "Key Insights" bullets so we can assert dedup + extraction at once.
ZAPIER_NOTES = """
Research Results

Summary:
Modern grep implementations include GNU grep and BSD grep. Regex engines
trade backtracking for speed, with notable differences across PCRE and POSIX.

Key Papers & Articles:
1. https://www.gnu.org/software/grep/manual/grep.html - GNU grep manual
2. Mastering Regular Expressions - https://www.oreilly.com/library/view/mastering-regular-expressions/0596528124/
3. Regex tutorial - https://www.regular-expressions.info/

Key Insights:
- GNU grep uses Boyer-Moore for literal patterns.
- Backtracking engines can hit catastrophic complexity on adversarial inputs.

Resources & Links:
- https://www.gnu.org/software/grep/manual/grep.html
- https://catb.org/~esr/writings/taoup/

Risks / Weaknesses:
- Performance claims vary across hardware.

What C.A.T.T.U.S Should Not Assume:
- Do not assume PCRE features are available in POSIX grep.

Suggested Dream Trial Input:
Investigate whether switching to ripgrep would reduce indexing time.
"""


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    # Project-tag fingerprints empty `tmp_path/repo` dirs to the same hash,
    # so tests share `.agent/<tag>/dream_references/`. Clear it to keep each
    # test isolated (mirrors the fixture in test_dream_references_routes.py).
    refs_root = dream_references.references_root(str(r))
    if refs_root.exists():
        for sub in refs_root.iterdir():
            if sub.is_dir():
                for f in sub.iterdir():
                    try:
                        f.unlink()
                    except OSError:
                        pass
                try:
                    sub.rmdir()
                except OSError:
                    pass
    yield r


# ---------------------------------------------------------------------------
# 1. Summary extraction
# ---------------------------------------------------------------------------

def test_parses_zapier_style_summary():
    parsed = dream_references.normalize_loose_research_text(ZAPIER_NOTES, topic="grep")
    assert parsed["summary"]
    assert "GNU grep" in parsed["summary"]
    assert "Summary" not in parsed["summary"].splitlines()[0]


# ---------------------------------------------------------------------------
# 2. Numbered source lines
# ---------------------------------------------------------------------------

def test_parses_numbered_source_lines_with_urls():
    parsed = dream_references.normalize_loose_research_text(ZAPIER_NOTES, topic="grep")
    urls = {s["url"] for s in parsed["sources"]}
    assert "https://www.gnu.org/software/grep/manual/grep.html" in urls
    assert "https://www.regular-expressions.info/" in urls
    assert any(
        "oreilly.com" in s["url"] and "Mastering" in (s.get("title") or "")
        for s in parsed["sources"]
    )


# ---------------------------------------------------------------------------
# 3. Deduplication across sections
# ---------------------------------------------------------------------------

def test_deduplicates_repeated_gnu_grep_url():
    parsed = dream_references.normalize_loose_research_text(ZAPIER_NOTES, topic="grep")
    gnu = [s for s in parsed["sources"] if "gnu.org/software/grep" in s["url"]]
    assert len(gnu) == 1, parsed["sources"]


# ---------------------------------------------------------------------------
# 4. Key Insights → key_ideas
# ---------------------------------------------------------------------------

def test_extracts_key_insights_into_key_ideas():
    parsed = dream_references.normalize_loose_research_text(ZAPIER_NOTES, topic="grep")
    joined = " ".join(parsed["key_ideas"])
    assert "Boyer-Moore" in joined
    assert "catastrophic" in joined


# ---------------------------------------------------------------------------
# 5–6. Conservative default warnings when sections are missing
# ---------------------------------------------------------------------------

def test_adds_conservative_risks_when_section_is_missing():
    notes_without_risks = """
Summary:
Brief overview.

Key Insights:
- Something interesting.
"""
    parsed = dream_references.normalize_loose_research_text(
        notes_without_risks, topic="something",
    )
    risks_joined = " ".join(parsed["risks_or_weaknesses"]).lower()
    assert "not independently verified" in risks_joined
    assert "source labels may be inaccurate" in risks_joined
    assert "performance or quality" in risks_joined


def test_adds_do_not_assume_when_section_is_missing():
    notes_without = "Summary:\nJust a one-liner."
    parsed = dream_references.normalize_loose_research_text(notes_without, topic="x")
    do_not = " ".join(parsed["do_not_assume"]).lower()
    assert "verified truth" in do_not
    assert "auto-create patches or proposals" in do_not


def test_does_not_overwrite_present_risks_and_do_not_assume():
    parsed = dream_references.normalize_loose_research_text(ZAPIER_NOTES, topic="grep")
    risks = " ".join(parsed["risks_or_weaknesses"]).lower()
    assert "performance claims vary" in risks
    do_not = " ".join(parsed["do_not_assume"]).lower()
    assert "pcre" in do_not


# ---------------------------------------------------------------------------
# 7. No URL fetching is permitted
# ---------------------------------------------------------------------------

def test_normalize_does_not_fetch_urls():
    """The function must run with no network stack imported in its module.
    Combined with `test_module_still_has_no_forbidden_imports`, this nails
    down the no-fetch guarantee."""
    parsed = dream_references.normalize_loose_research_text(ZAPIER_NOTES, topic="grep")
    # And: the raw_input is preserved verbatim (no rewriting via fetched data).
    assert parsed["raw_input"] == ZAPIER_NOTES


# ---------------------------------------------------------------------------
# 8. Explicit structured fields override parsed values
# ---------------------------------------------------------------------------

def test_explicit_structured_fields_override_parsed_values(repo):
    explicit_idea = "Explicit caller-supplied key idea wins."
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="grep deep dive",
        raw_input=ZAPIER_NOTES,
        normalize_loose=True,
        key_ideas=[explicit_idea],
        risks_or_weaknesses=["Explicit risk only."],
        do_not_assume=["Explicit do-not."],
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    assert data["key_ideas"] == [explicit_idea]
    assert data["risks_or_weaknesses"] == ["Explicit risk only."]
    assert data["do_not_assume"] == ["Explicit do-not."]


def test_normalize_loose_fills_missing_fields_when_not_overridden(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="grep deep dive",
        raw_input=ZAPIER_NOTES,
        normalize_loose=True,
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    # Parsed sources land on the reference, deduplicated.
    urls = {s["url"] for s in data["sources"]}
    assert "https://www.gnu.org/software/grep/manual/grep.html" in urls
    assert sum(1 for s in data["sources"] if "gnu.org/software/grep" in s["url"]) == 1
    # Parsed Key Insights land as key_ideas.
    joined = " ".join(data["key_ideas"])
    assert "Boyer-Moore" in joined or "catastrophic" in joined
    # Suggested trial input is captured.
    assert "ripgrep" in data["suggested_dream_trial_input"]


def test_source_type_inference_is_conservative(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="grep deep dive",
        raw_input=ZAPIER_NOTES,
        normalize_loose=True,
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    by_url = {s["url"]: s for s in data["sources"]}
    gnu = by_url["https://www.gnu.org/software/grep/manual/grep.html"]
    # GNU software manual → official_docs / high.
    assert gnu["source_type"] in {"official_docs", "docs"}
    assert gnu["reliability"] == "high"
    oreilly = next(s for url, s in by_url.items() if "oreilly.com" in url)
    assert oreilly["source_type"] in {"book"}
    assert oreilly["reliability"] in {"medium"}
    regex = by_url["https://www.regular-expressions.info/"]
    assert regex["source_type"] in {"web_guide", "blog"}
    assert regex["reliability"] in {"unknown"}


# ---------------------------------------------------------------------------
# 9. CLI flag
# ---------------------------------------------------------------------------

def _import_cli():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "import_dream_reference.py"
    if str(script_path.parent.parent) not in sys.path:
        sys.path.insert(0, str(script_path.parent.parent))
    spec = importlib.util.spec_from_file_location("import_dream_reference", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_normalize_loose_parses_zapier_notes(repo, tmp_path, capsys):
    notes_file = tmp_path / "zapier.md"
    notes_file.write_text(ZAPIER_NOTES, encoding="utf-8")
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(repo),
        "--topic", "grep loose import",
        "--input-file", str(notes_file),
        "--source-type", "zapier_discord",
        "--normalize-loose",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "reference.md:" in out

    # The created JSON should contain parsed sources from the Zapier text.
    summaries = dream_references.list_dream_references(str(repo))
    assert summaries, summaries
    latest_dir = Path(summaries[0]["reference_dir"])
    data = json.loads((latest_dir / "reference.json").read_text(encoding="utf-8"))
    urls = {s["url"] for s in data["sources"]}
    assert "https://www.gnu.org/software/grep/manual/grep.html" in urls
    assert sum(1 for s in data["sources"] if "gnu.org/software/grep" in s["url"]) == 1


# ---------------------------------------------------------------------------
# 10. Web import route accepts normalize_loose
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_web_import_route_supports_normalize_loose(client, repo):
    resp = client.post(
        "/dream/references/import",
        json={
            "repo_path": str(repo),
            "topic": "grep web normalize",
            "raw_input": ZAPIER_NOTES,
            "source_type": "zapier_discord",
            "normalize_loose": True,
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    json_path = Path(body["reference_dir"]) / "reference.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    urls = {s["url"] for s in data["sources"]}
    assert "https://www.gnu.org/software/grep/manual/grep.html" in urls
    # Deduped: only one GNU entry even though the raw text mentions it twice.
    assert sum(1 for s in data["sources"] if "gnu.org/software/grep" in s["url"]) == 1
    risks = " ".join(data["risks_or_weaknesses"]).lower()
    # Either the parsed risk OR the conservative defaults are present.
    assert "performance" in risks or "not independently verified" in risks


def test_web_import_route_defaults_normalize_loose_off(client, repo):
    """Without the flag, the existing un-parsed behavior is preserved — the
    reference still gets created but no automatic source parsing happens."""
    resp = client.post(
        "/dream/references/import",
        json={
            "repo_path": str(repo),
            "topic": "grep web no-normalize",
            "raw_input": ZAPIER_NOTES,
            "source_type": "zapier_discord",
        },
    )
    body = resp.get_json()
    assert body["ok"] is True
    data = json.loads(Path(body["reference_dir"]).joinpath("reference.json").read_text(encoding="utf-8"))
    # Without normalize_loose, sources stay empty (caller didn't pass any
    # structured sources, and the parser was never invoked).
    assert data["sources"] == []


# ---------------------------------------------------------------------------
# 11. Forbidden imports stay absent
# ---------------------------------------------------------------------------

def test_module_still_has_no_forbidden_imports():
    root = Path(__file__).resolve().parents[1]
    targets = [
        Path(dream_references.__file__),
        root / "scripts" / "import_dream_reference.py",
        root / "web" / "routes" / "dream_references_routes.py",
    ]
    forbidden = [
        "subprocess",
        "patch_engine",
        "patch_plan_executor",
        "patch_planner",
        "run_patch_plan",
        "run_benchmarks",
        "benchmark_runner",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
    ]
    for target in targets:
        src = target.read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle.lower() not in src, f"{target} leaked {needle}"
