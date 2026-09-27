"""OPS.PATCH.1 - byte-preserving multi-file apply & rollback.

Field-test defect (2026-08-30 black-box run): the multi-file patch path wrote
every touched file through ``Path.write_text()``.  In text mode with the
default ``newline=None`` Python translates every ``\\n`` to ``os.linesep``, so
on Windows an LF repository silently became CRLF the moment a patch touched it
- and a failed validation rolled back through the *same* faulty write path, so
"rollback restored the original content" still left a whole-file line-ending
diff.  One dogfood feature request left three files with ~117 changed lines and
zero semantic difference.

The invariant these tests defend is stated in bytes, not in text:

    successful patch  -> only the intended replacement bytes differ
    rolled-back patch -> the file is byte-identical to its original state

Every assertion therefore reads ``read_bytes()``.  ``read_text()`` applies the
same universal-newline translation that hid the defect in the first place, so a
text-level assertion would pass against the broken executor.

Fixtures build LF and CRLF byte payloads explicitly rather than relying on the
host's own newline translation, so the invariant is testable on Windows and on
POSIX CI alike.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_PATH = PROJECT_ROOT / "patching" / "patch_plan_executor.py"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> bytes:
    """Create a file from explicit bytes; return exactly what landed on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _replace(rel: str, old: str, new: str) -> dict:
    return {
        "op": "replace_snippet",
        "relative_path": rel,
        "target_snippet": old,
        "patched_snippet": new,
    }


def _create(rel: str, content: str) -> dict:
    return {"op": "create_file", "relative_path": rel, "content": content}


def _fail_validation(monkeypatch) -> str:
    """Force the one validation to fail, without touching validation policy.

    The executor reaches the shell only through
    ``core.validator.run_validation_command``; replacing that boundary is a
    test fixture for exercising rollback, not a change to how validation
    classifies real output.
    """
    import core.validator as validator

    monkeypatch.setattr(
        validator,
        "run_validation_command",
        lambda command, cwd, timeout=30: (False, "1 failed"),
    )
    return "pytest -q"


def _pass_validation(monkeypatch) -> str:
    import core.validator as validator
    from core.validator import ValidationRun

    monkeypatch.setattr(
        validator,
        "run_validation_command_detailed",
        lambda command, cwd, timeout=30: ValidationRun(
            ok=True, output="2 passed", exit_code=0
        ),
    )
    return "pytest -q"


# --------------------------------------------------------------------------- #
# 11. LF success regression  (primary acceptance test)
# --------------------------------------------------------------------------- #
def test_lf_file_keeps_lf_after_a_successful_replace(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"one\nold\nthree\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "old", "new")])

    assert result["success"] is True
    after = target.read_bytes()
    assert after == b"one\nnew\nthree\n"
    assert after.count(b"\r\n") == 0
    assert b"\r" not in after


# --------------------------------------------------------------------------- #
# 12. CRLF success regression
# --------------------------------------------------------------------------- #
def test_crlf_file_keeps_crlf_after_a_successful_replace(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"one\r\nold\r\nthree\r\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "old", "new")])

    assert result["success"] is True
    after = target.read_bytes()
    assert after == b"one\r\nnew\r\nthree\r\n"
    # The fix must not flip CRLF to LF either.
    assert after.count(b"\r\n") == 3


def test_crlf_file_renders_a_multi_line_patched_snippet_in_crlf(tmp_path):
    """A CRLF file stays internally consistent when new lines are inserted."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"head\r\nold\r\ntail\r\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "old\n", "new1\nnew2\n")])

    assert result["success"] is True
    assert target.read_bytes() == b"head\r\nnew1\r\nnew2\r\ntail\r\n"


def test_lf_file_renders_a_multi_line_patched_snippet_in_lf(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"head\nold\ntail\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "old\n", "new1\nnew2\n")])

    assert result["success"] is True
    assert target.read_bytes() == b"head\nnew1\nnew2\ntail\n"


# --------------------------------------------------------------------------- #
# 13/14. Rollback restores original BYTES, not merely original content
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "original",
    [
        pytest.param(b"one\nold\nthree\n", id="lf"),
        pytest.param(b"one\r\nold\r\nthree\r\n", id="crlf"),
    ],
)
def test_failed_validation_rollback_restores_exact_original_bytes(
    tmp_path, monkeypatch, original
):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, original)
    original_sha = _sha(original)

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo),
        [_replace("a.py", "old", "new")],
        validation_command=command,
    )

    assert result["success"] is False
    assert result["rollback_performed"] is True
    final = target.read_bytes()
    assert final == original
    assert _sha(final) == original_sha


# --------------------------------------------------------------------------- #
# 15. Multi-file success: intended lines change, everything else is byte-stable
# --------------------------------------------------------------------------- #
def test_multi_file_success_changes_only_the_intended_lines(tmp_path, monkeypatch):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    originals = {
        "A.py": b"import os\n\n\ndef a():\n    return 1\n",
        "B.py": b"import sys\n\n\ndef b():\n    return 2\n",
        "C.py": b"import io\n\n\ndef c():\n    return 3\n",
    }
    for name, data in originals.items():
        _write(repo / name, data)

    command = _pass_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo),
        [
            _replace("A.py", "return 1", "return 11"),
            _replace("B.py", "return 2", "return 22"),
            _replace("C.py", "return 3", "return 33"),
        ],
        validation_command=command,
    )

    assert result["success"] is True
    expected = {
        "A.py": b"import os\n\n\ndef a():\n    return 11\n",
        "B.py": b"import sys\n\n\ndef b():\n    return 22\n",
        "C.py": b"import io\n\n\ndef c():\n    return 33\n",
    }
    for name, before in originals.items():
        after = (repo / name).read_bytes()
        assert after == expected[name], name
        # No whole-file newline churn: no CRLF appeared and no line was added.
        assert b"\r" not in after, name
        assert after.count(b"\n") == before.count(b"\n"), name


# --------------------------------------------------------------------------- #
# 16/38. Field-test reproduction: three LF files, failed validation, no residue
# --------------------------------------------------------------------------- #
def test_field_test_shape_multi_file_failed_validation_leaves_no_residual_diff(
    tmp_path, monkeypatch
):
    """The observed 2026-08-30 failure class, reduced to its essentials.

    A five-operation feature plan applied cleanly across models.py / store.py /
    cli.py, validation then failed for unrelated plumbing, rollback ran - and
    all three files were left with line-ending-only changes.  The semantics of
    the requested feature are irrelevant; the residue is what is under test.
    """
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    originals = {
        "models.py": (
            b"from dataclasses import dataclass\n"
            b"\n"
            b"\n"
            b"@dataclass\n"
            b"class Note:\n"
            b"    title: str\n"
            b"    body: str\n"
        ),
        "store.py": (
            b"from models import Note\n"
            b"\n"
            b"\n"
            b"class Store:\n"
            b"    def add(self, note):\n"
            b"        self._notes.append(note)\n"
        ),
        "cli.py": (
            b"import sys\n"
            b"from store import Store\n"
            b"\n"
            b"\n"
            b"def main(argv):\n"
            b"    return 0\n"
        ),
    }
    for name, data in originals.items():
        _write(repo / name, data)
    shas = {name: _sha(data) for name, data in originals.items()}

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo),
        [
            _replace("models.py", "    body: str\n", "    body: str\n    tag: str\n"),
            _replace(
                "store.py",
                "self._notes.append(note)",
                "self._notes.insert(0, note)",
            ),
            _replace("cli.py", "    return 0\n", "    print(argv)\n    return 0\n"),
        ],
        validation_command=command,
    )

    assert result["success"] is False
    assert result["rollback_performed"] is True
    for name, before in originals.items():
        after = (repo / name).read_bytes()
        assert after == before, f"{name} left a residual diff after rollback"
        assert _sha(after) == shas[name], name


# --------------------------------------------------------------------------- #
# 17. Mixed-newline file: untouched bytes stay exactly as found
# --------------------------------------------------------------------------- #
def test_mixed_newline_file_is_not_silently_normalised(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "mixed.py"
    _write(target, b"lf_line\ncrlf_line\r\nold\nlast\r\n")

    result = apply_patch_plan(str(repo), [_replace("mixed.py", "old", "new")])

    assert result["success"] is True
    # Only `old` -> `new`; every other byte, including the mixed terminators,
    # survives untouched.
    assert target.read_bytes() == b"lf_line\ncrlf_line\r\nnew\nlast\r\n"


def test_mixed_newline_file_rolls_back_to_exact_original_bytes(tmp_path, monkeypatch):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "mixed.py"
    original = _write(target, b"lf\ncrlf\r\nold\nend\r\n")

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo), [_replace("mixed.py", "old", "new")], validation_command=command
    )

    assert result["rollback_performed"] is True
    assert target.read_bytes() == original


# --------------------------------------------------------------------------- #
# 18. Only the targeted bytes may change
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("eol", [b"\n", b"\r\n"], ids=["lf", "crlf"])
def test_prefix_and_suffix_bytes_are_untouched_by_a_replace(tmp_path, eol):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    prefix = eol.join([b"# header", b"import os", b"", b""])
    suffix = eol.join([b"", b"# trailer", b""])
    _write(target, prefix + b"MARKER" + suffix)

    result = apply_patch_plan(str(repo), [_replace("a.py", "MARKER", "REPLACED")])

    assert result["success"] is True
    after = target.read_bytes()
    assert after[: len(prefix)] == prefix
    assert after[len(prefix) + len(b"REPLACED") :] == suffix
    assert after == prefix + b"REPLACED" + suffix


def test_non_ascii_bytes_outside_the_edit_survive_verbatim(tmp_path):
    """Byte localisation must account for multi-byte UTF-8 before the match."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, "# héllo ✓ naïve\nold\n# ünicode ✔\n".encode("utf-8"))

    result = apply_patch_plan(str(repo), [_replace("a.py", "old", "new")])

    assert result["success"] is True
    assert target.read_bytes() == (
        "# héllo ✓ naïve\nnew\n# ünicode ✔\n".encode("utf-8")
    )


# --------------------------------------------------------------------------- #
# 7. Created-file newline policy: the payload's own bytes, verbatim
# --------------------------------------------------------------------------- #
def test_created_file_writes_the_payload_newlines_verbatim(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()

    result = apply_patch_plan(str(repo), [_create("pkg/new.py", "x = 1\ny = 2\n")])

    assert result["success"] is True
    after = (repo / "pkg" / "new.py").read_bytes()
    assert after == b"x = 1\ny = 2\n"
    assert b"\r\n" not in after, "host OS silently converted the model payload"


def test_created_file_preserves_an_explicit_crlf_payload(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()

    result = apply_patch_plan(str(repo), [_create("new.py", "x = 1\r\ny = 2\r\n")])

    assert result["success"] is True
    assert (repo / "new.py").read_bytes() == b"x = 1\r\ny = 2\r\n"


# --------------------------------------------------------------------------- #
# 6. Created-file rollback restores absence, not an empty file
# --------------------------------------------------------------------------- #
def test_created_file_is_absent_again_after_rollback(tmp_path, monkeypatch):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    created = repo / "pkg" / "new.py"

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo), [_create("pkg/new.py", "x = 1\n")], validation_command=command
    )

    assert result["rollback_performed"] is True
    assert not created.exists()


# --------------------------------------------------------------------------- #
# 33. create then replace the same file -> rollback leaves it absent
# --------------------------------------------------------------------------- #
def test_create_then_replace_same_file_rolls_back_to_absent(tmp_path, monkeypatch):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    created = repo / "new.py"

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo),
        [
            _create("new.py", "value = 1\n"),
            _replace("new.py", "value = 1", "value = 2"),
        ],
        validation_command=command,
    )

    assert result["rollback_performed"] is True
    assert not created.exists(), "rollback left an intermediate created file behind"


# --------------------------------------------------------------------------- #
# 32/34. repeated operations on one file roll back to the TRUE original
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("eol", [b"\n", b"\r\n"], ids=["lf", "crlf"])
def test_two_replacements_on_one_file_roll_back_to_the_first_original(
    tmp_path, monkeypatch, eol
):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    original = _write(target, eol.join([b"alpha", b"beta", b"gamma", b""]))
    original_sha = _sha(original)

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo),
        [
            _replace("a.py", "alpha", "ALPHA"),
            _replace("a.py", "beta", "BETA"),
        ],
        validation_command=command,
    )

    assert result["rollback_performed"] is True
    final = target.read_bytes()
    assert final == original, "rollback baseline was the second op, not the first"
    assert _sha(final) == original_sha


def test_two_replacements_on_one_file_both_land_on_success(tmp_path):
    """Operation ordering semantics are unchanged by the byte-fidelity fix."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"alpha\nbeta\n")

    result = apply_patch_plan(
        str(repo),
        [_replace("a.py", "alpha", "ALPHA"), _replace("a.py", "beta", "BETA")],
    )

    assert result["success"] is True
    assert target.read_bytes() == b"ALPHA\nBETA\n"


# --------------------------------------------------------------------------- #
# 35. Partial apply failure: op C fails before validation
# --------------------------------------------------------------------------- #
def test_partial_apply_failure_restores_every_earlier_file_exactly(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    a = _write(repo / "A.py", b"a_old\nkeep_a\n")
    b = _write(repo / "B.py", b"b_old\nkeep_b\n")
    c = _write(repo / "C.py", b"c_untouched\n")

    result = apply_patch_plan(
        str(repo),
        [
            _replace("A.py", "a_old", "a_new"),
            _replace("B.py", "b_old", "b_new"),
            # C fails: the snippet is not present verbatim.
            _replace("C.py", "not_present_anywhere", "irrelevant"),
        ],
    )

    assert result["success"] is False
    assert result["failed_op_index"] == 2
    assert result["rollback_performed"] is True
    assert (repo / "A.py").read_bytes() == a
    assert (repo / "B.py").read_bytes() == b
    assert (repo / "C.py").read_bytes() == c


# --------------------------------------------------------------------------- #
# 10. BOM regression - the executor supports UTF-8 BOM files today
# --------------------------------------------------------------------------- #
def test_utf8_bom_survives_a_successful_replace(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"\xef\xbb\xbfone\nold\nthree\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "old", "new")])

    assert result["success"] is True
    after = target.read_bytes()
    assert after.startswith(b"\xef\xbb\xbf"), "BOM was stripped by the write path"
    assert after == b"\xef\xbb\xbfone\nnew\nthree\n"


def test_utf8_bom_survives_rollback(tmp_path, monkeypatch):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    original = _write(target, b"\xef\xbb\xbfone\r\nold\r\n")

    command = _fail_validation(monkeypatch)
    result = apply_patch_plan(
        str(repo), [_replace("a.py", "old", "new")], validation_command=command
    )

    assert result["rollback_performed"] is True
    after = target.read_bytes()
    assert after == original
    assert after.count(b"\xef\xbb\xbf") == 1, "rollback added or removed a BOM"


# --------------------------------------------------------------------------- #
# 19. Literal matching is unchanged - no fuzzy newline rescue was introduced
# --------------------------------------------------------------------------- #
def test_absent_snippet_still_fails_and_writes_nothing(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    original = _write(target, b"def f():\n    return 1\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "return 2", "return 3")])

    assert result["success"] is False
    assert "not found verbatim" in result["error"]
    assert target.read_bytes() == original


def test_whitespace_differing_snippet_is_still_rejected(tmp_path):
    """Literal grounding, not whitespace-normalised matching."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    original = _write(target, b"def f():\n    return 1\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "def  f():", "def g():")])

    assert result["success"] is False
    assert target.read_bytes() == original


def test_lf_snippet_still_matches_a_crlf_file_as_it_did_before(tmp_path):
    """The pre-existing matching contract is preserved exactly.

    ``Path.read_text()`` applied universal-newline translation, so a model
    snippet written with ``\\n`` has always matched a CRLF file.  The byte
    fidelity fix must not silently revoke that, or patches that used to apply
    would start failing on CRLF checkouts.
    """
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"def f():\r\n    return 1\r\n")

    result = apply_patch_plan(
        str(repo),
        [_replace("a.py", "def f():\n    return 1\n", "def f():\n    return 2\n")],
    )

    assert result["success"] is True
    assert target.read_bytes() == b"def f():\r\n    return 2\r\n"


# --------------------------------------------------------------------------- #
# 31. Failure safety - no write happens when the original cannot be captured
# --------------------------------------------------------------------------- #
def test_undecodable_target_fails_before_any_write(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    original = _write(target, b"\xff\xfe\x00bad utf-8\nold\n")

    result = apply_patch_plan(str(repo), [_replace("a.py", "old", "new")])

    assert result["success"] is False
    assert target.read_bytes() == original


# --------------------------------------------------------------------------- #
# 25. run_lifecycle integration - the real production multi-file path
# --------------------------------------------------------------------------- #
def test_lifecycle_multi_file_failed_validation_restores_bytes(tmp_path, monkeypatch):
    """Through run_patch_plan_with_artifacts, not the helper in isolation."""
    import core.run_lifecycle as lifecycle

    repo = tmp_path / "repo"
    repo.mkdir()
    originals = {
        "A.py": b"import os\n\n\ndef a():\n    return 1\n",
        "B.py": b"import sys\n\n\ndef b():\n    return 2\n",
        "C.py": b"import io\n\n\ndef c():\n    return 3\n",
    }
    for name, data in originals.items():
        _write(repo / name, data)

    command = _fail_validation(monkeypatch)
    result = lifecycle.run_patch_plan_with_artifacts(
        str(repo),
        [
            _replace("A.py", "return 1", "return 11"),
            _replace("B.py", "return 2", "return 22"),
            _replace("C.py", "return 3", "return 33"),
        ],
        validation_command=command,
        user_query="ops.patch.1 byte fidelity",
        source="test",
    )

    assert result["success"] is False
    assert result["rollback_performed"] is True
    for name, before in originals.items():
        assert (repo / name).read_bytes() == before, name


def test_lifecycle_multi_file_success_keeps_lf(tmp_path, monkeypatch):
    import core.run_lifecycle as lifecycle

    repo = tmp_path / "repo"
    repo.mkdir()
    for name, data in {
        "A.py": b"def a():\n    return 1\n",
        "B.py": b"def b():\n    return 2\n",
    }.items():
        _write(repo / name, data)

    command = _pass_validation(monkeypatch)
    result = lifecycle.run_patch_plan_with_artifacts(
        str(repo),
        [
            _replace("A.py", "return 1", "return 11"),
            _replace("B.py", "return 2", "return 22"),
        ],
        validation_command=command,
        user_query="ops.patch.1 byte fidelity",
        source="test",
    )

    assert result["success"] is True
    assert (repo / "A.py").read_bytes() == b"def a():\n    return 11\n"
    assert (repo / "B.py").read_bytes() == b"def b():\n    return 22\n"


# --------------------------------------------------------------------------- #
# 37. Static regression - the three unsafe write patterns cannot come back
# --------------------------------------------------------------------------- #
def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in patch_plan_executor")


def _attribute_calls(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            names.add(child.func.attr)
    return names


def _executor_tree() -> ast.AST:
    return ast.parse(EXECUTOR_PATH.read_text(encoding="utf-8"))


def test_rollback_restores_through_write_bytes_not_write_text():
    transaction = ast.parse((PROJECT_ROOT / "patching/patch_plan_transaction.py").read_text(encoding="utf-8"))
    calls = _attribute_calls(_function(transaction, "restore_target"))
    assert "write_bytes" in calls, "rollback must restore original bytes"
    assert "write_text" not in calls, (
        "rollback through write_text re-applies host newline translation"
    )


def test_apply_writes_and_reads_bytes_only():
    apply_fn = _function(_executor_tree(), "_execute_prepared_operations")
    calls = _attribute_calls(apply_fn)
    assert "write_bytes" in calls
    assert "read_bytes" in calls
    assert "write_text" not in calls, "create/replace must not use text-mode writes"
    assert "read_text" not in calls, (
        "read_text applies universal-newline translation and loses the "
        "original terminators needed for exact rollback"
    )


def test_no_text_mode_write_survives_anywhere_in_the_executor():
    """None of the three field-test write surfaces may reintroduce text mode."""
    for node in ast.walk(_executor_tree()):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"write_text", "read_text"}, (
                f"text-mode file access reintroduced at line {node.lineno}"
            )
            if node.func.attr == "open":
                modes = [
                    arg.value
                    for arg in node.args
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ]
                kwargs = {kw.arg for kw in node.keywords}
                binary = any("b" in mode for mode in modes)
                assert binary or "newline" in kwargs, (
                    f"unguarded text-mode open() at line {node.lineno}"
                )


def test_rollback_entries_carry_bytes_not_text():
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert "RollbackEntry = tuple[Path, bytes | None]" in source, (
        "the rollback baseline must be typed as bytes so it cannot silently "
        "become a lossy decode/re-encode round trip again"
    )


# --------------------------------------------------------------------------- #
# 24/30. The single-file reference path is untouched, and no traversal was added
# --------------------------------------------------------------------------- #
def test_executor_adds_no_repository_traversal():
    calls = _attribute_calls(_executor_tree())
    for traversal in ("rglob", "glob", "walk", "iterdir"):
        assert traversal not in calls, (
            f"{traversal} would scan beyond the patch target set"
        )


def test_patch_engine_single_file_newline_behaviour_still_holds(tmp_path):
    """Compatibility: the already-correct single-file path is unchanged."""
    from patching.patch_engine import apply_patch_from_json

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "a.py"
    _write(target, b"def f():\n    return 1\n")

    result = apply_patch_from_json(
        str(repo),
        {
            "relative_path": "a.py",
            "file": "a.py",
            "target_snippet": "    return 1",
            "patched_snippet": "    return 2",
        },
    )

    assert result["success"] is True
    assert target.read_bytes() == b"def f():\n    return 2\n"


# --------------------------------------------------------------------------- #
# 17 (continued). Exotic terminators: CR-only and three-way mixed files
# --------------------------------------------------------------------------- #
def test_lone_cr_terminators_are_preserved(tmp_path):
    """Classic-Mac CR is a terminator `read_text()` also collapsed to LF."""
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "cr.py"
    _write(target, b"one\rold\rthree\r")

    result = apply_patch_plan(str(repo), [_replace("cr.py", "old", "new")])

    assert result["success"] is True
    assert target.read_bytes() == b"one\rnew\rthree\r"


def test_file_mixing_cr_crlf_and_lf_keeps_every_untouched_terminator(tmp_path):
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "chaos.py"
    _write(target, b"a\rb\r\nc\nold\nd\r\n")

    result = apply_patch_plan(str(repo), [_replace("chaos.py", "old", "new")])

    assert result["success"] is True
    assert target.read_bytes() == b"a\rb\r\nc\nnew\nd\r\n"


def test_snippet_spanning_a_crlf_boundary_consumes_both_bytes(tmp_path):
    """A match ending on a translated CRLF must take the CR with it.

    If only the LF were consumed, the orphaned CR would survive into the
    output - the sort of off-by-one a text-level assertion never sees.
    """
    from patching.patch_plan_executor import apply_patch_plan

    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "span.py"
    _write(target, b"keep\r\nold1\r\nold2\r\nkeep2\n")

    result = apply_patch_plan(
        str(repo), [_replace("span.py", "old1\nold2\n", "NEW\n")]
    )

    assert result["success"] is True
    assert target.read_bytes() == b"keep\r\nNEW\r\nkeep2\n"
