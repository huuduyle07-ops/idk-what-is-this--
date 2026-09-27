"""PATCH.BASIS.TARGET.1: structural short-identifier target source grounding.

DOGFOOD.JAVA.1 measured one blocker.  javac evidence grounded a real defect at
``MainApp.java::m1`` (``direct_location``, line 12), and then
``build_patch_intent`` threw the target away because ``len("m1") < 3``:

    grounded defect  ->  short-name rejection  ->  no source/snippet
                     ->  exact_source_grounded=false
                     ->  patch_basis=unresolved  ->  authoring never reached

This phase removes that arbitrary heuristic and replaces it with *structural*
grounding supplied by the repository's existing language-aware extractor
(``core.treesitter_parse``).  Identifier length is not evidence, and a short
spelling that merely *appears* in text still grounds nothing.

These tests drive the target-grounding owner directly against real source files
on disk.  No model call, no network call and no repository traversal is used.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from core.control_engine import (
    TARGET_GROUNDING_AMBIGUOUS,
    TARGET_GROUNDING_FILE_TARGET,
    TARGET_GROUNDING_LOCATION_MISMATCH,
    TARGET_GROUNDING_NOT_FOUND,
    TARGET_GROUNDING_RESOLVED,
    TARGET_GROUNDING_UNAVAILABLE,
    _source_is_exactly_grounded,
    build_patch_intent,
    ground_target_symbol,
)
from core.treesitter_parse import structural_definitions


ROOT = Path(__file__).resolve().parents[1]

# The exact DOGFOOD.JAVA.1 shape: three short methods, a compiler diagnostic at
# line 12 (inside m1), and a short local variable in each body.
MAINAPP_JAVA = """public class MainApp
{
    int no = 100;   //instance variable

    static int sno = 200;   //static variable

    void m1()
    {
        int no1 = 10;   //local variable
        System.out.println("Result 1 : "+(no1 + no));
        System.out.println("Result 2 : "+(no1 + no + sno));
        System.out.println("Result 3 : "+(no1 + no2));
    }

    void m2()
    {
        int no2 = 20;   //local variable
        System.out.println("Result 4 : "+(no2 + no));
        System.out.println("Result 5 : "+(no2 + no + sno));
        System.out.println("Result 6 : "+(no2 + no1));
    }

    static void m3()
    {
        int no3 = 30;   //local variable
        System.out.println("Result 7 : "+(no3 + no));
        System.out.println("Result 8 : "+(no3 + sno));
        System.out.println("Result 9 : "+(no1 + no2 + no3));
    }

    public static void main(String[] args)
    {
        MainApp obj = new MainApp();
        obj.m1();
        obj.m2();

        MainApp.m3();  //static method can be directly called by class name
    }
}
"""

# m1 owns lines 7-13 and the measured diagnostic sits on line 12.
M1_DIAGNOSTIC_LINE = 12
M2_DIAGNOSTIC_LINE = 20


def _java_repo(tmp_path: Path, text: str = MAINAPP_JAVA, name: str = "MainApp.java") -> Path:
    # Written exactly as the dogfood repository stores it: CRLF, no VCS.
    (tmp_path / name).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    return tmp_path


def _control(repo: Path, symbol: str, **extra) -> dict:
    result = {
        "repo_path": str(repo),
        "query": "Help me check if the code in twosum.java and MainApp.java is ok, then fix them",
        "top_hypothesis": {
            "symbol": symbol,
            "likely_issue": "compile_error",
            "recommended_action": "grounded_defect_candidate",
        },
    }
    result.update(extra)
    return result


def _location(file: str, line: int) -> dict:
    return {"file": file, "line": line, "col": 49, "kind": "compiler_diagnostic"}


# ---------------------------------------------------------------------------
# §15 / §16 / §17 — positive: short, structurally resolvable callables
# ---------------------------------------------------------------------------


def test_short_java_method_m1_is_structurally_grounded(tmp_path):
    """The exact DOGFOOD.JAVA.1 target: len("m1") == 2, defect on line 12."""
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo),
        rel_file="MainApp.java",
        symbol_name="m1",
        defect_location=_location("MainApp.java", M1_DIAGNOSTIC_LINE),
    )

    assert grounding["status"] == TARGET_GROUNDING_RESOLVED
    assert grounding["definition"]["name"] == "m1"
    assert grounding["definition"]["start_line"] == 7
    assert grounding["definition"]["end_line"] == 13
    assert grounding["matches"] == 1


def test_short_java_method_m1_produces_exact_patch_intent(tmp_path):
    repo = _java_repo(tmp_path)

    intent = build_patch_intent(
        _control(repo, "MainApp.java::m1"),
        defect_location=_location("MainApp.java", M1_DIAGNOSTIC_LINE),
    )

    assert intent["target_file"] == "MainApp.java"
    assert intent["target_symbol"] == "m1"
    assert "void m1()" in intent["source_snippet"]
    assert intent["language"] == "java"


@pytest.mark.parametrize(
    "symbol_name,start_line,end_line",
    [("m2", 15, 21), ("m3", 23, 29)],
)
def test_other_short_methods_are_structurally_grounded(
    tmp_path, symbol_name, start_line, end_line
):
    """§16 — m2/m3 prove the fix is not a literal ``m1`` exception.

    They are short-name structural controls; this does not claim either one is
    a DOGFOOD.JAVA.1 patch target.
    """
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="MainApp.java", symbol_name=symbol_name
    )

    assert grounding["status"] == TARGET_GROUNDING_RESOLVED
    assert grounding["definition"]["start_line"] == start_line
    assert grounding["definition"]["end_line"] == end_line

    intent = build_patch_intent(_control(repo, f"MainApp.java::{symbol_name}"))
    assert intent["target_symbol"] == symbol_name
    assert f"void {symbol_name}()" in intent["source_snippet"]


def test_one_character_callable_is_not_rejected_for_length(tmp_path):
    """§17 — the one-character control proves the threshold is really gone."""
    repo = _java_repo(
        tmp_path,
        text="public class Tiny\n{\n    int f()\n    {\n        return 1;\n    }\n}\n",
        name="Tiny.java",
    )

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="Tiny.java", symbol_name="f"
    )
    assert grounding["status"] == TARGET_GROUNDING_RESOLVED

    intent = build_patch_intent(_control(repo, "Tiny.java::f"))
    assert intent["target_symbol"] == "f"
    assert "int f()" in intent["source_snippet"]


def test_short_python_function_is_structurally_grounded(tmp_path):
    """§23 — the removal is generic, not a Java-only exception."""
    (tmp_path / "tiny.py").write_text(
        "def f(a):\n    return a + 1\n\n\ndef g(b):\n    return b\n", encoding="utf-8"
    )

    grounding = ground_target_symbol(
        repo_path=str(tmp_path), rel_file="tiny.py", symbol_name="f"
    )

    assert grounding["status"] == TARGET_GROUNDING_RESOLVED
    assert grounding["definition"]["start_line"] == 1

    intent = build_patch_intent(_control(tmp_path, "tiny.py::f"))
    assert intent["target_symbol"] == "f"
    assert "def f(a):" in intent["source_snippet"]


# ---------------------------------------------------------------------------
# §18 / §19 / §20 / §21 — negative: text, locals, ambiguity, wrong location
# ---------------------------------------------------------------------------


def test_short_spelling_in_a_comment_does_not_ground(tmp_path):
    repo = _java_repo(
        tmp_path,
        text="public class Doc\n{\n    // zz is mentioned here only\n    void run() {}\n}\n",
        name="Doc.java",
    )

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="Doc.java", symbol_name="zz"
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND
    assert build_patch_intent(_control(repo, "Doc.java::zz"))["target_file"] is None


def test_short_spelling_in_a_string_does_not_ground(tmp_path):
    repo = _java_repo(
        tmp_path,
        text='public class Str\n{\n    void run() { System.out.println("zz"); }\n}\n',
        name="Str.java",
    )

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="Str.java", symbol_name="zz"
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND
    assert build_patch_intent(_control(repo, "Str.java::zz"))["target_file"] is None


def test_short_spelling_in_a_python_docstring_does_not_ground(tmp_path):
    (tmp_path / "doc.py").write_text(
        '"""Mentions zz in prose only."""\n\n\ndef run():\n    return 1\n',
        encoding="utf-8",
    )

    grounding = ground_target_symbol(
        repo_path=str(tmp_path), rel_file="doc.py", symbol_name="zz"
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND


def test_short_local_variable_does_not_become_a_function_target(tmp_path):
    """§18 — ``int no1 = 10;`` is not an eligible patch target kind."""
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo),
        rel_file="MainApp.java",
        symbol_name="no1",
        defect_location=_location("MainApp.java", M1_DIAGNOSTIC_LINE),
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND
    assert build_patch_intent(_control(repo, "MainApp.java::no1"))["target_file"] is None


def test_short_instance_field_is_not_an_eligible_target_kind(tmp_path):
    """§10 / §18 — ``int no = 100;`` is a field, not a supported symbol kind."""
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="MainApp.java", symbol_name="no"
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND


def test_missing_short_symbol_is_unresolved(tmp_path):
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="MainApp.java", symbol_name="m9"
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND
    assert build_patch_intent(_control(repo, "MainApp.java::m9"))["target_file"] is None


def test_duplicate_short_definitions_are_ambiguous_not_first_match(tmp_path):
    """§20 — two plausible definitions and no location cannot be guessed."""
    repo = _java_repo(
        tmp_path,
        text=(
            "public class Dup\n{\n"
            "    void f(int a)\n    {\n        System.out.println(a);\n    }\n\n"
            "    void f(String b)\n    {\n        System.out.println(b);\n    }\n}\n"
        ),
        name="Dup.java",
    )

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="Dup.java", symbol_name="f"
    )

    assert grounding["status"] == TARGET_GROUNDING_AMBIGUOUS
    assert grounding["matches"] == 2
    assert grounding["definition"] is None
    assert build_patch_intent(_control(repo, "Dup.java::f"))["target_file"] is None


def test_overloads_are_disambiguated_by_the_grounded_location(tmp_path):
    """§8 — the measured diagnostic may identify one exact overload."""
    repo = _java_repo(
        tmp_path,
        text=(
            "public class Dup\n{\n"
            "    void f(int a)\n    {\n        System.out.println(a);\n    }\n\n"
            "    void f(String b)\n    {\n        System.out.println(b);\n    }\n}\n"
        ),
        name="Dup.java",
    )

    grounding = ground_target_symbol(
        repo_path=str(repo),
        rel_file="Dup.java",
        symbol_name="f",
        defect_location=_location("Dup.java", 9),
    )

    assert grounding["status"] == TARGET_GROUNDING_RESOLVED
    assert grounding["definition"]["start_line"] == 8
    assert grounding["definition"]["end_line"] == 11


def test_wrong_diagnostic_location_refuses_to_bind(tmp_path):
    """§21 — m1 exists, but the measured defect lives inside m2."""
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo),
        rel_file="MainApp.java",
        symbol_name="m1",
        defect_location=_location("MainApp.java", M2_DIAGNOSTIC_LINE),
    )

    assert grounding["status"] == TARGET_GROUNDING_LOCATION_MISMATCH
    assert (
        build_patch_intent(
            _control(repo, "MainApp.java::m1"),
            defect_location=_location("MainApp.java", M2_DIAGNOSTIC_LINE),
        )["target_file"]
        is None
    )


def test_a_location_owned_by_no_definition_discriminates_nothing(tmp_path):
    """§3 binds "belongs to another definition", not "is not inside this one".

    A diagnostic line at module level, on a blank line, or past the end of the
    file belongs to no definition at all. It is not evidence against the
    target, so the unambiguous structural result stands.
    """
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    grounding = ground_target_symbol(
        repo_path=str(tmp_path),
        rel_file="calc.py",
        symbol_name="add",
        defect_location=_location("calc.py", 12),  # the file has two lines
    )

    assert grounding["status"] == TARGET_GROUNDING_RESOLVED
    assert grounding["definition"]["name"] == "add"


def test_a_location_in_another_file_never_disambiguates(tmp_path):
    """A diagnostic about a different file cannot bind this file's symbol."""
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo),
        rel_file="MainApp.java",
        symbol_name="m1",
        defect_location=_location("Twosum.java", M1_DIAGNOSTIC_LINE),
    )

    # The foreign location is simply not evidence about MainApp.java, so the
    # unambiguous structural result stands on its own.
    assert grounding["status"] == TARGET_GROUNDING_RESOLVED
    assert grounding["definition"]["name"] == "m1"


# ---------------------------------------------------------------------------
# §4 — provenance: the model may not introduce a target by spelling alone
# ---------------------------------------------------------------------------


def test_grounding_reads_only_the_named_file(tmp_path):
    """§4 / §24 — no discovery: a symbol defined elsewhere does not resolve."""
    repo = _java_repo(tmp_path)
    (repo / "Other.java").write_bytes(
        b"public class Other\r\n{\r\n    void zz()\r\n    {\r\n    }\r\n}\r\n"
    )

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="MainApp.java", symbol_name="zz"
    )

    assert grounding["status"] == TARGET_GROUNDING_NOT_FOUND


def test_grounding_performs_no_repository_traversal(tmp_path, monkeypatch):
    """§24 / §40 — bounded to the one named file already in hand."""
    repo = _java_repo(tmp_path)

    for name in ("walk", "scandir", "listdir"):
        monkeypatch.setattr(
            __import__("os"),
            name,
            lambda *a, **k: pytest.fail(f"os.{name} used during target grounding"),
        )
    for name in ("glob", "rglob", "iterdir"):
        monkeypatch.setattr(
            Path,
            name,
            lambda *a, **k: pytest.fail(f"Path.{name} used during target grounding"),
        )

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="MainApp.java", symbol_name="m1"
    )
    assert grounding["status"] == TARGET_GROUNDING_RESOLVED


# ---------------------------------------------------------------------------
# §22 / §10 — preservation
# ---------------------------------------------------------------------------


def test_long_symbol_patch_intent_is_unchanged(tmp_path):
    """§22 — previously valid >=3-character symbols behave exactly as before."""
    (tmp_path / "svc.py").write_text(
        "def calculate_total(items):\n"
        "    return sum(items)\n"
        "\n"
        "\n"
        "def unrelated():\n"
        "    return None\n",
        encoding="utf-8",
    )

    intent = build_patch_intent(_control(tmp_path, "svc.py::calculate_total"))

    assert intent["target_file"] == "svc.py"
    assert intent["target_symbol"] == "calculate_total"
    assert intent["target_node_kind"] == "function"
    assert "def calculate_total(items):" in intent["source_snippet"]
    assert intent["patch_rules"]


def test_long_java_symbol_patch_intent_is_unchanged(tmp_path):
    repo = _java_repo(
        tmp_path,
        text=(
            "public class Svc\n{\n"
            "    void calculateTotal()\n    {\n        System.out.println(1);\n    }\n}\n"
        ),
        name="Svc.java",
    )

    intent = build_patch_intent(_control(repo, "Svc.java::calculateTotal"))

    assert intent["target_file"] == "Svc.java"
    assert intent["target_symbol"] == "calculateTotal"
    assert "void calculateTotal()" in intent["source_snippet"]


def test_file_only_target_behaviour_is_unchanged(tmp_path):
    """§10 — a file-stem target keeps the shape measured before this phase.

    ``MainApp.java::MainApp`` names the file, not a symbol, so the pre-existing
    ``infer_symbol_from_query_in_file`` branch rewrites it to ``main`` *before*
    any structural grounding runs.  That behaviour was measured against the
    entry bytes of ``core/control_engine.py`` and must survive unchanged: this
    phase only reaches spellings that branch leaves alone.
    """
    repo = _java_repo(tmp_path)

    grounding = ground_target_symbol(
        repo_path=str(repo), rel_file="MainApp.java", symbol_name="MainApp"
    )
    assert grounding["status"] == TARGET_GROUNDING_FILE_TARGET

    intent = build_patch_intent(_control(repo, "MainApp.java::MainApp"))
    assert intent["target_file"] == "MainApp.java"
    assert intent["target_symbol"] == "main"
    assert intent["source_snippet"].startswith("public static void main(")


def test_empty_symbol_still_fails_closed(tmp_path):
    repo = _java_repo(tmp_path)

    assert build_patch_intent(_control(repo, ""))["target_file"] is None


def test_language_without_structural_proof_preserves_prior_behaviour(tmp_path):
    """§23 — where no structural extractor exists nothing changes."""
    (tmp_path / "thing.mojo").write_text("fn handle():\n    pass\n", encoding="utf-8")

    grounding = ground_target_symbol(
        repo_path=str(tmp_path), rel_file="thing.mojo", symbol_name="handle"
    )

    assert grounding["status"] == TARGET_GROUNDING_UNAVAILABLE


# ---------------------------------------------------------------------------
# §11 / §12 — the existing downstream logic receives the source naturally
# ---------------------------------------------------------------------------


def test_m1_satisfies_exact_source_grounding_through_existing_logic(tmp_path):
    """§11 — the unchanged ``_source_is_exactly_grounded`` accepts the result."""
    repo = _java_repo(tmp_path)
    control = _control(repo, "MainApp.java::m1")

    intent = build_patch_intent(
        control, defect_location=_location("MainApp.java", M1_DIAGNOSTIC_LINE)
    )

    assert _source_is_exactly_grounded(control, intent) is True


def test_short_symbol_intent_uses_no_special_downstream_schema(tmp_path):
    """§11 — m1's intent carries exactly the long-symbol key set."""
    repo = _java_repo(tmp_path)
    (tmp_path / "svc.py").write_text(
        "def calculate_total(items):\n    return sum(items)\n", encoding="utf-8"
    )

    short = build_patch_intent(_control(repo, "MainApp.java::m1"))
    long = build_patch_intent(_control(tmp_path, "svc.py::calculate_total"))

    assert set(short) == set(long)
    assert short["target_node_kind"] == long["target_node_kind"] == "function"


def test_grounding_grants_no_authority(tmp_path):
    """§26 — structural grounding is not write or execution authority."""
    repo = _java_repo(tmp_path)

    intent = build_patch_intent(
        _control(repo, "MainApp.java::m1"),
        defect_location=_location("MainApp.java", M1_DIAGNOSTIC_LINE),
    )

    for forbidden in (
        "write_authority",
        "execution_authorized",
        "patch_application_authority",
        "auto_patch_candidate_allowed",
        "patch_eligibility_granted",
    ):
        assert forbidden not in intent


# ---------------------------------------------------------------------------
# §5 — the additive extractor API
# ---------------------------------------------------------------------------


def test_structural_definitions_reports_availability_and_spans():
    result = structural_definitions(MAINAPP_JAVA, "java")

    assert result["available"] is True
    by_name = {d["name"]: d for d in result["definitions"]}
    assert by_name["m1"]["start_line"] == 7
    assert by_name["m1"]["end_line"] == 13
    assert by_name["m1"]["kind"] == "function"
    assert "void m1()" in by_name["m1"]["content"]


def test_structural_definitions_reports_unavailable_for_unmapped_language():
    result = structural_definitions("fn handle():\n    pass\n", "mojo")

    assert result["available"] is False
    assert result["definitions"] == []


# ---------------------------------------------------------------------------
# §39 — bounded static regression against reintroducing a length threshold
# ---------------------------------------------------------------------------


_LENGTH_CALL = re.compile(r"len\(\s*symbol_name\s*\)")


def test_target_grounding_owner_has_no_identifier_length_threshold():
    """§39 — no arbitrary identifier-length rule in the grounding owner.

    Bounded deliberately: only the functions that decide whether a target
    symbol may supply patch source are inspected, not the whole module.
    """
    source = (ROOT / "core" / "control_engine.py").read_text(
        encoding="utf-8", errors="replace"
    )
    tree = ast.parse(source)

    owners = {
        "build_patch_intent",
        "ground_target_symbol",
        "_structural_target_definition",
    }
    inspected = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in owners:
            inspected.append(node.name)
            body = ast.get_source_segment(source, node) or ""
            assert not _LENGTH_CALL.search(body), (
                f"{node.name} compares the identifier's length; identifier "
                "length is not evidence (PATCH.BASIS.TARGET.1 §1)"
            )

    assert owners.issubset(set(inspected))


# ---------------------------------------------------------------------------
# Containment: what this phase moved, proved against the reconstructed entry
# ---------------------------------------------------------------------------


# CONTROL.LOCALIZE.LIVE.2 froze this digest; PATCH.BASIS.TARGET.1 is the phase
# authorised to move it, and moves it for exactly one reason: the grounded
# build_patch_intent call site now forwards the measured defect location.
REFRESH_CONTROL_SAFETY_ENTRY_DIGEST = (
    "00fdbb557f9a3b1e1f6c63fd32f0b631579253ffda3b819fd04424251b3fa700"
)


def _entry(relative: str) -> bytes:
    from tests._patch_basis_target1_maintenance import before_patch_basis_target1

    return before_patch_basis_target1(relative)


def _post_state(relative: str) -> bytes:
    """TARGET.1's post-state, before the later repair-scope seam."""
    from tests._patch_basis_scope1_maintenance import before_patch_basis_scope1

    return before_patch_basis_scope1(relative, (ROOT / relative).read_bytes())


def _definition_digests(raw: bytes) -> dict[str, str]:
    digests = {}
    for node in ast.parse(raw.decode("utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            digests[node.name] = hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest()
    return digests


def test_control_engine_delta_is_two_definitions_and_nothing_is_removed():
    pre = _definition_digests(_entry("core/control_engine.py"))
    post = _definition_digests(_post_state("core/control_engine.py"))

    changed = {name for name in pre if name in post and pre[name] != post[name]}
    assert changed == {"build_patch_intent", "refresh_control_safety"}
    assert set(post) - set(pre) == {
        "ground_target_symbol",
        "_structural_target_definition",
    }
    assert set(pre) - set(post) == set()
    assert len(pre) == 56 and len(post) == 58


def test_every_other_frozen_control_function_is_byte_identical():
    """The re-pin is bounded: 8 of CONTROL.LOCALIZE.LIVE.2's 9 pins never moved."""
    pins = json.loads(
        (ROOT / "tests/fixtures/control_localize_live2_boundaries.json").read_text(
            encoding="utf-8"
        )
    )["control_functions"]

    pre = _definition_digests(_entry("core/control_engine.py"))
    post = _definition_digests(_post_state("core/control_engine.py"))

    assert pre["refresh_control_safety"] == REFRESH_CONTROL_SAFETY_ENTRY_DIGEST
    assert pins["refresh_control_safety"] == post["refresh_control_safety"]

    others = [name for name in pins if name != "refresh_control_safety"]
    assert len(others) == 8
    for name in others:
        assert pre[name] == post[name] == pins[name], name


def test_the_structural_extractor_is_purely_additive():
    """§5 — no existing parsing definition moved."""
    pre = _definition_digests(_entry("core/treesitter_parse.py"))
    post = _definition_digests(_post_state("core/treesitter_parse.py"))

    assert {name for name in pre if pre[name] != post.get(name)} == set()
    assert set(post) - set(pre) == {"structural_definitions"}


def test_frozen_phase_boundaries_are_byte_exact():
    """§27 / §28 / §29 — everything this phase must not move, still unmoved."""
    manifest = json.loads(
        (ROOT / "tests/fixtures/patch_basis_target1_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["phase"] == "PATCH.BASIS.TARGET.1"

    for relative, digest in manifest["sha256"].items():
        raw = _post_state(relative)
        if relative not in {
            "core/control_engine.py",
            "tests/test_patch_basis_target1.py",
            "tests/test_phase_registry.py",
        }:
            assert hashlib.sha256(raw).hexdigest() == digest, relative

    groups = manifest["groups"]
    for group in (
        "patch_basis_and_defect_fact",
        "PATCH.MINIMAL_and_PATCH.AUTHOR",
        "authoring_prompt",
        "CONTROL.FRESH_BOOTSTRAP_PREFLIGHT",
        "authority",
        "backend_web",
        "static_and_template",
        "extractor_consumers",
        "audit",
    ):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group

    # The two files this phase did change can never appear in its own freeze list.
    assert not {"core/control_engine.py", "core/treesitter_parse.py"} & set(
        manifest["sha256"]
    )
    # The authoring prompt builder is frozen: the branch it takes is observed,
    # never engineered (§13, §32).
    assert "core/prompter.py" in manifest["sha256"]


def test_completion_receipt_pins_every_phase_source_and_records_the_measurement():
    """§30-§34 — the live dogfood replay's measured outcome, kept as evidence."""
    receipt = json.loads(
        (ROOT / "tests/fixtures/patch_basis_target1_completion.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["phase"] == "PATCH.BASIS.TARGET.1"
    assert receipt["identifier_length_used_as_criterion"] is False
    assert receipt["patch_basis_hardcoded"] is False
    assert receipt["model_calls_added"] == 0
    assert receipt["network_calls_added"] == 0
    assert receipt["repository_traversals_added"] == 0
    assert receipt["authority_delta"] == "none"
    assert set(receipt["statuses_that_refuse_a_target"]) == {
        TARGET_GROUNDING_NOT_FOUND,
        TARGET_GROUNDING_AMBIGUOUS,
        TARGET_GROUNDING_LOCATION_MISMATCH,
    }
    assert set(receipt["grounding_statuses"]) == {
        TARGET_GROUNDING_RESOLVED,
        TARGET_GROUNDING_NOT_FOUND,
        TARGET_GROUNDING_AMBIGUOUS,
        TARGET_GROUNDING_LOCATION_MISMATCH,
        TARGET_GROUNDING_FILE_TARGET,
        TARGET_GROUNDING_UNAVAILABLE,
    }

    dogfood = receipt["java_dogfood"]
    # PRE is DOGFOOD.JAVA.1's audited state; POST is this phase's replay.
    assert dogfood["pre"]["patch_basis"] == "unresolved"
    assert dogfood["pre"]["exact_source_grounded"] is False
    assert dogfood["pre"]["target_file"] is None
    assert dogfood["post"]["patch_basis"] == "grounded_defect"
    assert dogfood["post"]["exact_source_grounded"] is True
    assert dogfood["post"]["target_symbol"] == "m1"
    # Authority never moved, in either direction.
    for stage in ("pre", "post"):
        assert dogfood[stage]["write_authority"] is False
        assert dogfood[stage]["patch_application_authority"] is False
    assert dogfood["java_repository_byte_identical"] is True
    assert dogfood["applied"] is False

    self_path = "tests/fixtures/patch_basis_target1_completion.json"
    assert self_path not in receipt["source_sha256"]
    assert set(receipt["source_sha256"]) == set(
        receipt["existing_files_changed"] + receipt["new_files"]
    ) - {self_path}
    for relative, digest in receipt["source_sha256"].items():
        raw = _post_state(relative)
        if relative not in {
            "core/control_engine.py",
            "tests/test_patch_basis_target1.py",
            "tests/test_phase_registry.py",
        }:
            assert hashlib.sha256(raw).hexdigest() == digest, relative
