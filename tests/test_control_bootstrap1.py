"""CONTROL.BOOTSTRAP.1: explicit-target direct context bootstrap for a fresh Generate.

CONTROL.FRESH.1 made ``control=null`` a typed fresh state that stops at the
bootstrap boundary.  This phase owns the next transition only:

    fresh_control_required + the task the request transports
        -> the WAITER.LIVE.1 route over the INPUT.1 Task Contract (intent, explicit files)
        -> exact grounding of every requested file in the current repository
        -> CTX.READ.1 descriptor-bound reads of exactly those files
        -> one CONTROL-authoring model call
        -> the CONTROL.FRESH.1 validator, then admission
        -> the first CONTROL, handed to the unchanged CONTROL-dependent pipeline

These tests drive the owner (web/control_bootstrap.py) directly and the production
routes through the Flask test client.  A deterministic author stands in for the
provider everywhere; no live model, network, compiler or test runner is used.
"""
from __future__ import annotations

import builtins
import glob
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys

import pytest

from tests.test_auth_web1 import _tree, configure_offline_web

TASK_FIELD = "query"
FRESH_WIRE = "null"
FRESH_STATE = "fresh_bootstrap_required"
BOOTSTRAPPED = "control_bootstrapped"
DISCOVERY = "bootstrap_discovery_required"
UNRESOLVED = "bootstrap_target_unresolved"
UNSUPPORTED = "bootstrap_target_unsupported"
BUDGET = "bootstrap_target_budget_exceeded"
CHANGED = "bootstrap_source_changed"
PROVIDER_FAILED = "bootstrap_provider_failed"
CONTROL_INVALID = "bootstrap_control_invalid"
REQUEST_INVALID = "bootstrap_request_invalid"
DEMOTION = "context reference; not the localized target"

TWOSUM = (
    b"import java.util.HashMap;\n"
    b"import java.util.Map;\n"
    b"\n"
    b"public class Twosum {\n"
    b"    public int[] twoSum(int[] nums, int target) {\n"
    b"        Map<Integer, Integer> seen = new HashMap<>();\n"
    b"        for (int i = 0; i < nums.length; i++) {\n"
    b"            int complement = target - nums[i];\n"
    b"            if (seen.containsKey(complement)) {\n"
    b"                return new int[] { seen.get(complement), i };\n"
    b"            }\n"
    b"            seen.put(nums[i], i);\n"
    b"        }\n"
    b"        return new int[0];\n"
    b"    }\n"
    b"}\n"
)
MAINAPP = (
    b"public class MainApp {\n"
    b"    private int counter = 0;\n"
    b"\n"
    b"    public void increment() {\n"
    b"        counter++;\n"
    b"    }\n"
    b"\n"
    b"    public static void main(String[] args) {\n"
    b"        increment();\n"
    b"        System.out.println(\"Counter: \" + counter);\n"
    b"    }\n"
    b"}\n"
)
JAVA_TASK = "Help me check if the code in Twosum.java and MainApp.java is ok, then fix them"
JAVA_REPLY = {
    "hypotheses": [{
        "symbol": "MainApp.java::main",
        "likely_issue": "static main calls the instance method increment() and reads the instance field "
                        "counter without an instance (suspected static-context problem, from source reading)",
        "reasons": ["main is static", "increment() and counter are instance members"],
    }],
    "evidence_gaps": [{
        "need": "compile_evidence",
        "detail": "no compiler ran; the static-context problem is a source-reading hypothesis until "
                  "compile evidence exists",
        "targets": ["MainApp.java", "Twosum.java"],
    }],
}
A_PY = b"def value():\n    return 1\n"


def _owner():
    from web import control_bootstrap

    return control_bootstrap


class Author:
    """Deterministic CONTROL author: records every prompt and answers from a script."""

    def __init__(self, reply=None, *, raises=None, on_call=None):
        self.reply, self.raises, self.on_call = reply, raises, on_call
        self.prompts: list[str] = []
        self.kwargs: list[dict] = []

    def __call__(self, prompt, *args, **kwargs):
        self.prompts.append(prompt)
        self.kwargs.append(dict(kwargs))
        if self.on_call is not None:
            self.on_call(prompt)
        if self.raises is not None:
            raise self.raises
        reply = self.reply(prompt) if callable(self.reply) else self.reply
        return reply if isinstance(reply, str) else json.dumps(reply)


def _sources_in(prompt: str) -> dict[str, str]:
    """Every labelled source block in a bootstrap prompt, exactly as the author received it."""
    found: dict[str, str] = {}
    index = 1
    while True:
        begin = f"<<<CATTUS SOURCE {index} BEGIN: "
        start = prompt.find(begin)
        if start < 0:
            return found
        path = prompt[start + len(begin): prompt.index(">>>", start)]
        body_start = prompt.index(">>>\n", start) + 4
        end = prompt.index(f"\n<<<CATTUS SOURCE {index} END: {path}>>>", body_start)
        found[path] = prompt[body_start:end]
        index += 1


def _repo(tmp_path, files: dict[str, bytes], name="repo"):
    root = tmp_path / name
    root.mkdir()
    for relative, raw in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return root


def _bootstrap(root, task, author):
    owner = _owner()
    return owner.bootstrap_fresh_control(owner.FreshControlBootstrapRequest(task, str(root)), provider=author)


def _hypothesis(path, name="value", issue="value() returns 1 where the task asks for 2"):
    return {"symbol": f"{path}::{name}", "likely_issue": issue, "reasons": ["read from the requested source"]}


def _reply_for(*paths):
    return {"hypotheses": [_hypothesis(path) for path in paths], "evidence_gaps": []}


# -- the fresh bootstrap: first CONTROL from explicit targets ------------------------------------------

def test_one_explicit_target_bootstraps_a_first_control_the_frozen_parser_accepts(tmp_path):
    from core.live_task_routing import safe_route_live_task
    from web.control_context import normalize_control_values

    root = _repo(tmp_path, {"a.py": A_PY})
    task = "Make value() in a.py return 2"
    author = Author(_reply_for("a.py"))
    result = _bootstrap(root, task, author)
    assert (result.code, result.reason, result.model_calls) == (BOOTSTRAPPED, None, 1)
    control = result.control
    # The exact CONTROL.FRESH.1 parser accepts it as prior CONTROL: one material schema.
    parsed = normalize_control_values([json.dumps(control)])
    assert parsed.state == "prior_control" and parsed.control == control
    assert control["query"] == task
    assert control["repo_path"] == str(root.resolve())
    assert control["live_route"] == safe_route_live_task(task, repository_available=True).as_dict()
    assert control["related_snippets"] == [{
        "file": "a.py", "symbol": "", "role": "requested_target", "language": "python",
        "snippet": A_PY.decode("utf-8"),
    }]
    assert control["target_scope"] == {
        "requested_targets": ["a.py"], "evidence_targets": ["a.py"], "localized_patch_targets": None,
    }
    assert control["top_hypothesis"]["symbol"] == "a.py::value"
    assert control["hypotheses"][0]["defect_established"] is False
    assert control["evidence_gaps"] == []
    # Provenance and authority live in the receipt, never in the CONTROL material.
    for key in ("provenance", "control_bootstrap", "preflight_validation", "patch_intent", "patch_candidate_state",
                "defect_probe", "grounded_hypothesis"):
        assert key not in control, key
    receipt = result.receipt()
    assert receipt["provenance"] == "fresh_bootstrap" and receipt["status"] == BOOTSTRAPPED
    assert receipt["control_sha256"] == hashlib.sha256(
        json.dumps(control, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    # One authoring opportunity, through the provider's own JSON transport.
    assert len(author.prompts) == 1 and author.kwargs == [{"response_mime_type": "application/json"}]


def test_two_unrelated_files_are_both_read_and_labelled_in_the_order_the_user_named_them(tmp_path):
    zeta, alpha = b"ZETA = 'last letter'\n", b"def alpha():\n    return 'first letter'\n"
    root = _repo(tmp_path, {"zeta.py": zeta, "alpha.py": alpha, "unnamed.py": b"SECRET_NEIGHBOUR = 1\n"})
    author = Author(_reply_for("zeta.py"))
    result = _bootstrap(root, "Review zeta.py and alpha.py, then fix whatever is wrong", author)
    assert result.code == BOOTSTRAPPED
    prompt = author.prompts[0]
    # Commitment order, not lexicographic order; each file is a separately labelled block.
    assert _sources_in(prompt) == {"zeta.py": zeta.decode(), "alpha.py": alpha.decode()}
    assert prompt.index("=== FILE 1 of 2: zeta.py ===") < prompt.index("=== FILE 2 of 2: alpha.py ===")
    assert "unnamed.py" not in prompt and "SECRET_NEIGHBOUR" not in prompt
    scope = result.control["target_scope"]
    assert scope["requested_targets"] == scope["evidence_targets"] == ["zeta.py", "alpha.py"]
    assert [item["file"] for item in result.control["related_snippets"]] == ["zeta.py", "alpha.py"]
    assert [source["path"] for source in result.receipt()["sources"]] == ["zeta.py", "alpha.py"]
    assert result.bytes_read == len(zeta) + len(alpha)


def test_source_reaches_the_author_byte_exact_with_separate_language_and_path_metadata(tmp_path):
    raw = "﻿def naïve():\r\n    return 'ünïcode'\r\n\r\n# trailing, no newline".encode("utf-8")
    root = _repo(tmp_path, {"pkg/mod.py": raw})
    author = Author(_reply_for("pkg/mod.py"))
    result = _bootstrap(root, "Fix pkg/mod.py", author)
    assert result.code == BOOTSTRAPPED
    exact = raw.decode("utf-8-sig")
    assert _sources_in(author.prompts[0]) == {"pkg/mod.py": exact}
    assert result.control["related_snippets"][0]["snippet"] == exact
    source = result.receipt()["sources"][0]
    assert source["sha256"] == hashlib.sha256(raw).hexdigest() and source["size_bytes"] == len(raw)
    assert (source["language"], source["path"], source["freshness"]) == ("python", "pkg/mod.py", "fresh")
    block = author.prompts[0][author.prompts[0].index("=== FILE 1 of 1: pkg/mod.py ==="):]
    assert "language: python" in block and f"sha256: {hashlib.sha256(raw).hexdigest()}" in block


# -- Java dogfood: both requested files survive into the first CONTROL -----------------------------------

def _java_repo(tmp_path, name="java_repo"):
    return _repo(tmp_path, {"Twosum.java": TWOSUM, "MainApp.java": MAINAPP}, name)


class JavaAuthor(Author):
    """The deterministic author proves what it saw: both complete, labelled sources."""

    def __init__(self, reply=JAVA_REPLY):
        super().__init__(reply)
        self.seen: dict[str, str] = {}

    def __call__(self, prompt, *args, **kwargs):
        self.seen = _sources_in(prompt)
        return super().__call__(prompt, *args, **kwargs)


def test_java_dogfood_preserves_reads_and_presents_both_unrelated_files(tmp_path, monkeypatch):
    def no_process(*args, **kwargs):
        raise AssertionError("CONTROL.BOOTSTRAP.1 runs no compiler, test, linter or command")

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, no_process)
    monkeypatch.setattr(os, "system", no_process)
    root = _java_repo(tmp_path)
    author = JavaAuthor()
    result = _bootstrap(root, JAVA_TASK, author)
    assert result.code == BOOTSTRAPPED and result.model_calls == 1
    # The Task Contract kept both explicit commitments, in the user's order.
    route = result.control["live_route"]
    assert route["requested_paths"] == ["Twosum.java", "MainApp.java"] and route["preservation_passed"] is True
    # The author received both complete sources, labelled, with no dependency between them.
    assert author.seen == {"Twosum.java": TWOSUM.decode(), "MainApp.java": MAINAPP.decode()}
    assert b"Twosum" not in MAINAPP and b"MainApp" not in TWOSUM
    prompt = author.prompts[0]
    assert DEMOTION not in prompt and "not localized" not in prompt
    scope = result.control["target_scope"]
    assert scope == {"requested_targets": ["Twosum.java", "MainApp.java"],
                     "evidence_targets": ["Twosum.java", "MainApp.java"], "localized_patch_targets": None}
    assert [item["role"] for item in result.control["related_snippets"]] == ["requested_target"] * 2
    # A suspected issue is recorded; the compiler claim stays an explicit evidence gap.
    assert result.control["top_hypothesis"]["symbol"] == "MainApp.java::main"
    assert result.control["hypotheses"][0]["defect_established"] is False
    assert result.control["evidence_gaps"] == JAVA_REPLY["evidence_gaps"]
    assert "preflight_validation" not in result.control
    receipt = result.receipt()
    assert receipt["authority"] == {"defect_established": False, "patch_basis_established": False,
                                    "write_authority": False, "patch_authority": False,
                                    "human_approval_granted": False, "execution_performed": False}
    assert receipt["executable_commands_accepted"] == 0
    assert receipt["evidence_gap_needs"] == ["compile_evidence"]
    assert (root / "Twosum.java").read_bytes() == TWOSUM and (root / "MainApp.java").read_bytes() == MAINAPP


def test_the_bootstrap_prompt_claims_no_compiler_or_test_evidence(tmp_path):
    root = _java_repo(tmp_path)
    author = JavaAuthor()
    _bootstrap(root, JAVA_TASK, author)
    prompt = author.prompts[0]
    assert "No compiler, test, linter or program was run" in prompt
    for claim in ("javac failed", "compilation failed", "test failed", "preflight failed"):
        assert claim not in prompt.casefold()


def test_a_model_command_is_never_accepted_as_executable_authority(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("executed")))
    reply = json.loads(json.dumps(JAVA_REPLY))
    reply["evidence_gaps"][0]["command"] = "javac MainApp.java Twosum.java && rm -rf /"
    result = _bootstrap(_java_repo(tmp_path), JAVA_TASK, Author(reply))
    assert result.code == BOOTSTRAPPED
    # The semantic need is retained; the command text is not transported anywhere.
    assert result.control["evidence_gaps"] == JAVA_REPLY["evidence_gaps"]
    assert "javac" not in json.dumps(result.control)
    receipt = result.receipt()
    assert receipt["discarded_item_keys"] == ["evidence_gaps[0].command"]
    assert receipt["executable_commands_accepted"] == 0 and "javac" not in json.dumps(receipt)


@pytest.mark.skipif(os.name != "nt", reason="case-insensitive filesystem grounding")
def test_a_case_insensitive_filesystem_grounds_the_literal_to_the_canonical_path(tmp_path):
    root = _repo(tmp_path, {"Twosum.java": TWOSUM})
    author = Author({"hypotheses": [_hypothesis("Twosum.java", "twoSum")], "evidence_gaps": []})
    result = _bootstrap(root, "check twosum.java", author)
    assert result.code == BOOTSTRAPPED
    assert result.control["target_scope"]["requested_targets"] == ["twosum.java"]
    assert result.control["target_scope"]["evidence_targets"] == ["Twosum.java"]
    assert list(_sources_in(author.prompts[0])) == ["Twosum.java"]


# -- no explicit target: typed, bounded, no discovery ---------------------------------------------------

@pytest.mark.parametrize(("task", "reason"), [
    ("", "empty_task"), ("   \n\t", "empty_task"),
    ("fix the login bug", "no_explicit_target"),
    ("Why is the build slow?", "no_explicit_target"),
])
def test_no_explicit_target_is_a_typed_discovery_requirement_with_no_reads_or_model(tmp_path, task, reason):
    root = _repo(tmp_path, {"a.py": A_PY})
    author = Author(_reply_for("a.py"))
    result = _bootstrap(root, task, author)
    assert (result.code, result.reason) == (DISCOVERY, reason)
    assert result.control is None and result.model_calls == 0 and author.prompts == []
    assert result.bytes_read == 0
    answer = result.response()
    assert answer["code"] == DISCOVERY and answer["reason"] == reason
    assert answer["control_context"] == FRESH_STATE
    assert "Invalid control JSON" not in answer["error"]


@pytest.mark.parametrize("task", ["", "fix the login bug"])
def test_a_task_without_explicit_targets_touches_no_file_and_no_provider(tmp_path, monkeypatch, task):
    root = _repo(tmp_path, {"a.py": A_PY})
    touched: list[str] = []

    def denied(name):
        def call(*args, **kwargs):
            touched.append(name)
            raise AssertionError(f"a task without explicit targets touched the filesystem with {name}")
        return call

    owner = _owner()  # module imports happen before the filesystem is denied
    request = owner.FreshControlBootstrapRequest(task, str(root))
    author = Author(_reply_for("a.py"))
    with monkeypatch.context() as no_filesystem:
        for name in ("stat", "lstat", "open", "scandir", "listdir", "walk"):
            no_filesystem.setattr(os, name, denied(f"os.{name}"))
        no_filesystem.setattr(builtins, "open", denied("open"))
        no_filesystem.setattr(io, "open", denied("io.open"))
        result = owner.bootstrap_fresh_control(request, provider=author)
    assert result.code == DISCOVERY and touched == [] and author.prompts == []
    assert result.repository_root is None and result.targets == () and result.model_calls == 0


# -- target not found, unsafe, unsupported: fail closed, never a partial review ----------------------------

def test_a_missing_explicit_target_fails_closed_without_reading_the_others(tmp_path):
    root = _repo(tmp_path, {"MainApp.java": MAINAPP})
    author = Author(JAVA_REPLY)
    result = _bootstrap(root, "check Missing.java and MainApp.java", author)
    assert (result.code, result.reason) == (UNRESOLVED, "not_found")
    assert result.model_calls == 0 and author.prompts == [] and result.bytes_read == 0 and result.control is None
    targets = {item["requested"]: item for item in result.receipt()["targets"]}
    assert targets["Missing.java"]["status"] == "not_found"
    assert targets["MainApp.java"]["status"] == "grounded"
    assert "Missing.java" in result.response()["error"]


@pytest.mark.parametrize(("task", "setup", "reason"), [
    ("fix ../outside.py", None, "unsafe_path"),
    ("fix con.py", None, "unsafe_path"),
    ("fix pkg.py", "directory", "not_a_file"),
])
def test_unsafe_or_non_file_targets_are_unresolved(tmp_path, task, setup, reason):
    root = _repo(tmp_path, {"a.py": A_PY})
    (tmp_path / "outside.py").write_bytes(b"OUTSIDE = True\n")
    if setup == "directory":
        (root / "pkg.py").mkdir()
    author = Author(_reply_for("a.py"))
    result = _bootstrap(root, task, author)
    assert (result.code, result.reason) == (UNRESOLVED, reason)
    assert result.model_calls == 0 and result.bytes_read == 0


def test_a_symlinked_target_is_never_followed(tmp_path):
    root = _repo(tmp_path, {"a.py": A_PY})
    (tmp_path / "secret.py").write_bytes(b"SECRET = 'outside the repository'\n")
    try:
        os.symlink(tmp_path / "secret.py", root / "link.py")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not creatable here")
    result = _bootstrap(root, "fix link.py", Author(_reply_for("link.py")))
    assert (result.code, result.reason) == (UNRESOLVED, "unsafe_path")
    assert result.model_calls == 0 and result.bytes_read == 0


def test_a_path_whose_final_component_is_a_link_is_refused_before_it_is_opened(tmp_path, monkeypatch):
    import stat as stat_module

    root = _repo(tmp_path, {"a.py": A_PY, "link.py": b"LINK = 1\n"})
    real_lstat = os.lstat

    def lstat(path, *args, **kwargs):
        info = real_lstat(path, *args, **kwargs)
        if pathlib.Path(path).name == "link.py":  # what lstat reports for a symbolic link
            fields = list(info)
            fields[0] = stat_module.S_IFLNK | 0o777
            return os.stat_result(fields)
        return info

    monkeypatch.setattr(os, "lstat", lstat)
    result = _bootstrap(root, "fix link.py", Author(_reply_for("link.py")))
    assert (result.code, result.reason) == (UNRESOLVED, "unsafe_path")
    assert result.receipt()["targets"][0]["reason"] == "symbolic links are never followed"
    assert result.bytes_read == 0 and result.model_calls == 0


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are a Windows alias")
@pytest.mark.parametrize(("inside", "reason"), [(True, "the path resolves through a link or alias"),
                                                (False, "the path resolves outside the repository")])
def test_a_path_through_a_directory_alias_is_refused(tmp_path, inside, reason):
    import _winapi

    root = _repo(tmp_path, {"real/f.py": A_PY})
    target = root / "real" if inside else _repo(tmp_path, {"f.py": A_PY}, "elsewhere")
    _winapi.CreateJunction(str(target), str(root / "alias"))
    result = _bootstrap(root, "fix alias/f.py", Author(_reply_for("alias/f.py")))
    assert (result.code, result.reason) == (UNRESOLVED, "unsafe_path")
    assert result.receipt()["targets"][0]["reason"] == reason
    assert result.bytes_read == 0 and result.model_calls == 0


def test_the_repository_itself_must_exist(tmp_path):
    result = _bootstrap(tmp_path / "no_such_repo", "fix a.py", Author(_reply_for("a.py")))
    assert (result.code, result.reason) == (UNRESOLVED, "repository_unavailable")
    assert result.model_calls == 0


@pytest.mark.parametrize(("files", "task", "reason"), [
    ({"blob.txt": b"\x00\x01\x02binary\x00" * 8}, "read blob.txt", "binary_or_opaque"),
    ({"latin.txt": b"caf\xe9 au lait\n"}, "read latin.txt", "encoding_unsupported"),
    ({"secrets.json": b"{\"token\": \"x\"}\n"}, "review secrets.json", "sensitive_file_blocked"),
    ({".gitignore": b"ignored.py\n", "ignored.py": b"IGNORED = 1\n"}, "fix ignored.py",
     "ignored_by_repository_policy"),
    ({"build/gen.py": b"GENERATED = 1\n"}, "fix build/gen.py", "ignored_by_repository_policy"),
])
def test_a_target_that_cannot_safely_enter_source_context_is_reported_not_reviewed(tmp_path, files, task, reason):
    root = _repo(tmp_path, {"a.py": A_PY, **files})
    author = Author(_reply_for("a.py"))
    result = _bootstrap(root, task, author)
    assert (result.code, result.reason) == (UNSUPPORTED, reason)
    assert result.model_calls == 0 and author.prompts == [] and result.control is None
    target = result.receipt()["targets"][0]
    assert target["status"] == reason
    assert target["path"] in result.response()["error"]


# -- the direct-context bound: explicit escalation, never truncation ------------------------------------

def test_more_targets_than_the_direct_context_file_bound_escalate_without_reading(tmp_path):
    files = {f"m{index}.py": b"X = %d\n" % index for index in range(1, 10)}
    root = _repo(tmp_path, files)
    task = "fix " + " and ".join(files)
    result = _bootstrap(root, task, Author(_reply_for("m1.py")))
    assert (result.code, result.reason) == (BUDGET, "file_count")
    assert result.bytes_read == 0 and result.model_calls == 0
    budget = result.receipt()["budget"]
    assert budget["requested_target_count"] == 9 and budget["accepted_file_limit"] == 8
    assert budget["requested_target_count_complete"] is True
    assert budget["aggregate_requested_bytes"] == sum(len(raw) for raw in files.values())


def test_a_commitment_set_the_task_contract_truncated_escalates_with_an_incomplete_count(tmp_path):
    files = {f"f{index}.py": b"X = 1\n" for index in range(1, 35)}
    root = _repo(tmp_path, files)
    result = _bootstrap(root, "fix " + " ".join(files), Author(_reply_for("f1.py")))
    assert (result.code, result.reason) == (BUDGET, "file_count")
    budget = result.receipt()["budget"]
    assert budget["requested_target_count"] == 32 and budget["requested_target_count_complete"] is False
    assert result.bytes_read == 0 and result.model_calls == 0


def test_aggregate_bytes_over_the_bound_escalate_without_reading(tmp_path):
    files = {f"big{index}.py": b"#" * 220_000 + b"\n" for index in range(1, 6)}
    root = _repo(tmp_path, files)
    result = _bootstrap(root, "fix " + " and ".join(files), Author(_reply_for("big1.py")))
    assert (result.code, result.reason) == (BUDGET, "aggregate_bytes")
    budget = result.receipt()["budget"]
    assert budget["aggregate_requested_bytes"] == 5 * 220_001 and budget["max_total_bytes"] == 1_048_576
    assert result.bytes_read == 0 and result.model_calls == 0


def test_one_file_over_the_per_file_bound_escalates_without_reading(tmp_path):
    root = _repo(tmp_path, {"huge.py": b"#" * 262_145})
    result = _bootstrap(root, "fix huge.py", Author(_reply_for("huge.py")))
    assert (result.code, result.reason) == (BUDGET, "file_bytes")
    assert result.receipt()["budget"]["max_bytes_per_file"] == 262_144
    assert result.bytes_read == 0 and result.model_calls == 0


def test_a_file_the_bounded_read_would_truncate_escalates_instead_of_being_summarized(tmp_path):
    root = _repo(tmp_path, {"long.py": b"x = 1\n" * 4001})
    author = Author(_reply_for("long.py"))
    result = _bootstrap(root, "fix long.py", author)
    assert (result.code, result.reason) == (BUDGET, "file_lines")
    assert result.model_calls == 0 and author.prompts == [] and result.control is None


# -- provider and CONTROL failures: structured, one call, no retry ----------------------------------------

@pytest.mark.parametrize(("author", "reason"), [
    (Author(raises=RuntimeError("provider unavailable")), "provider_exception"),
    (Author("AGENT_ERROR: GOOGLE_API_KEY is missing."), "provider_error"),
    (Author(""), "empty_response"),
    (Author("   \n"), "empty_response"),
])
def test_a_provider_failure_is_structured_and_never_retried(tmp_path, author, reason):
    result = _bootstrap(_repo(tmp_path, {"a.py": A_PY}), "fix a.py", author)
    assert (result.code, result.reason) == (PROVIDER_FAILED, reason)
    assert result.model_calls == 1 and len(author.prompts) == 1 and result.control is None


@pytest.mark.parametrize(("reply", "reason", "field"), [
    ("{", "malformed_json", None),
    ("```json\n{\"hypotheses\": []}\n```", "malformed_json", None),
    ('{"hypotheses": [], "score": NaN}', "malformed_json", None),
    ("[]", "wrong_top_level_type", None),
    ("null", "wrong_top_level_type", None),
    ('{"evidence_gaps": []}', "missing_required_fields", None),
    ('{"hypotheses": null}', "missing_required_fields", None),
    ('{"hypotheses": {}}', "invalid_field_type", "hypotheses"),
    ('{"hypotheses": ["a.py::value"]}', "invalid_field_type", "hypotheses"),
    ('{"hypotheses": [], "preflight_validation": {"ran": true, "ok": false}}', "unadmitted_field",
     "preflight_validation"),
    ('{"hypotheses": [], "patch_intent": {"relative_path": "a.py"}}', "unadmitted_field", "patch_intent"),
    ('{"hypotheses": [], "related_snippets": [{"file": "a.py", "snippet": "x"}]}', "unadmitted_field",
     "related_snippets"),
    ('{"hypotheses": [], "live_route": {}}', "unadmitted_field", "live_route"),
    ('{"hypotheses": [{"symbol": "other.py::f", "likely_issue": "x"}]}', "ungrounded_hypothesis",
     "hypotheses[0].symbol"),
    ('{"hypotheses": [{"symbol": "a.py", "likely_issue": "x"}]}', "invalid_hypothesis", "hypotheses[0].symbol"),
    ('{"hypotheses": [{"symbol": "a.py::value"}]}', "invalid_hypothesis", "hypotheses[0].likely_issue"),
    ('{"hypotheses": [], "evidence_gaps": [{"need": "run_javac", "detail": "x"}]}', "invalid_evidence_gap",
     "evidence_gaps[0].need"),
    ('{"hypotheses": [], "evidence_gaps": [{"need": "compile_evidence", "detail": "x", "targets": ["b.py"]}]}',
     "invalid_evidence_gap", "evidence_gaps[0].targets"),
])
def test_bootstrap_output_passes_the_same_control_validator_then_admission(tmp_path, reply, reason, field):
    result = _bootstrap(_repo(tmp_path, {"a.py": A_PY}), "fix a.py", Author(reply))
    assert (result.code, result.reason, result.field) == (CONTROL_INVALID, reason, field)
    assert result.control is None and result.model_calls == 1
    answer = result.response()
    assert answer["code"] == CONTROL_INVALID and answer["reason"] == reason
    assert answer["control_context"] == FRESH_STATE


def test_admission_uses_the_frozen_control_fresh1_validator(tmp_path, monkeypatch):
    from web import control_context

    seen = []
    original = control_context.normalize_control_values

    def spy(values):
        seen.append(list(values))
        return original(values)

    monkeypatch.setattr(control_context, "normalize_control_values", spy)
    result = _bootstrap(_repo(tmp_path, {"a.py": A_PY}), "fix a.py", Author(_reply_for("a.py")))
    assert result.code == BOOTSTRAPPED
    # Once for the author's raw output, once for the composed CONTROL the pipeline receives.
    assert len(seen) == 2
    assert seen[0] == [json.dumps(_reply_for("a.py"))]
    assert json.loads(seen[1][0]) == result.control


def test_a_source_that_changes_before_binding_fails_closed(tmp_path):
    root = _repo(tmp_path, {"a.py": A_PY})

    def edit(prompt):
        (root / "a.py").write_bytes(b"def value():\n    return 3  # edited while the author ran\n")

    result = _bootstrap(root, "fix a.py", Author(_reply_for("a.py"), on_call=edit))
    assert (result.code, result.reason) == (CHANGED, "changed")
    assert result.control is None and result.model_calls == 1
    assert result.receipt()["sources"][0]["freshness"] == "changed"


# -- zero graph, index, embedding, traversal; exact named reads only ---------------------------------------

def test_bootstrap_reads_exactly_the_named_files_and_traverses_nothing(tmp_path, monkeypatch):
    import core.repo_librarian  # noqa: F401  (loaded before the traversal primitives are denied)

    root = _java_repo(tmp_path)
    (root / "Unrelated.java").write_bytes(b"class Unrelated {}\n")
    opened: list[str] = []

    def denied(name):
        def call(*args, **kwargs):
            raise AssertionError(f"CONTROL.BOOTSTRAP.1 traversed the repository with {name}")
        return call

    for module, name in ((os, "walk"), (os, "scandir"), (os, "listdir"), (glob, "glob"), (glob, "iglob")):
        monkeypatch.setattr(module, name, denied(name))
    for name in ("iterdir", "glob", "rglob", "walk"):
        monkeypatch.setattr(pathlib.Path, name, denied(f"Path.{name}"))
    for module in tuple(sys.modules.values()):
        module_name = getattr(module, "__name__", "") or ""
        if module_name.startswith(("core.", "graph.", "reasoning.", "web.")):
            for name in ("build_graph_from_repo", "get_cached_graph", "select_entry_nodes", "run_control_structured",
                         "index_repository", "run_preflight_validation", "retrieve_context", "create_repository_inventory",
                         "collect_analysis_evidence", "execute_bounded_lexical_search", "build_related_snippets"):
                if callable(getattr(module, name, None)):
                    monkeypatch.setattr(module, name, denied(name))
    real_open, real_os_open = io.open, os.open

    def recording_open(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):  # an int is a descriptor os.open already recorded
            opened.append(pathlib.Path(os.fsdecode(file)).name)
        return real_open(file, *args, **kwargs)

    def recording_os_open(path, *args, **kwargs):
        opened.append(pathlib.Path(os.fsdecode(path)).name)
        return real_os_open(path, *args, **kwargs)

    # builtins.open and io.open (Path.read_text/read_bytes) are both content reads.
    monkeypatch.setattr(builtins, "open", recording_open)
    monkeypatch.setattr(io, "open", recording_open)
    monkeypatch.setattr(os, "open", recording_os_open)
    result = _bootstrap(root, JAVA_TASK, JavaAuthor())
    assert result.code == BOOTSTRAPPED
    # Content reads: exactly the two named files; everything else is root ignore-policy metadata.
    assert set(opened) - {".gitignore", ".cattusignore"} == {"Twosum.java", "MainApp.java"}
    assert "Unrelated.java" not in opened
    assert result.bytes_read == len(TWOSUM) + len(MAINAPP)
    receipt = result.receipt()
    assert receipt["repository_traversals"] == 0 and receipt["graph_operations"] == 0
    assert receipt["index_operations"] == 0 and receipt["embedding_operations"] == 0


def test_bootstrap_is_deterministic(tmp_path):
    root = _java_repo(tmp_path)
    first, second = JavaAuthor(), JavaAuthor()
    one, two = _bootstrap(root, JAVA_TASK, first), _bootstrap(root, JAVA_TASK, second)
    assert first.prompts == second.prompts
    assert one.control == two.control and one.receipt() == two.receipt()


def test_the_owner_imports_no_selector_graph_index_or_provider_module():
    import ast

    source = (pathlib.Path(__file__).resolve().parents[1] / "web/control_bootstrap.py").read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    forbidden = {"core.context_selection", "core.file_actionability", "core.file_candidate_selector",
                 "core.file_capabilities", "core.control_engine", "core.retriever", "core.pipeline",
                 "graph.builder", "agents.gemini_client", "agents.deepseek_client", "subprocess", "socket"}
    assert not imported & forbidden, imported & forbidden
    assert not any(name.startswith(("graph.", "agents.", "database.", "reasoning.")) for name in imported)


# -- the form seam: CONTROL.FRESH.1 stays frozen ------------------------------------------------------------

class Form:
    def __init__(self, fields):
        self.fields = fields

    def getlist(self, name):
        return list(self.fields.get(name, []))


def _fresh_context():
    from web.control_context import normalize_control_values

    return normalize_control_values([FRESH_WIRE])


def test_a_fresh_request_without_a_task_field_keeps_the_control_fresh1_answer(tmp_path):
    owner = _owner()
    author = Author(_reply_for("a.py"))
    assert owner.bootstrap_fresh_control_from_form(Form({}), _fresh_context(), str(tmp_path), provider=author) is None
    assert author.prompts == []


def test_only_the_fresh_state_may_bootstrap(tmp_path):
    from web.control_context import normalize_control_values

    owner = _owner()
    author = Author(_reply_for("a.py"))
    form = Form({TASK_FIELD: ["fix a.py"]})
    for values in (["{"], [json.dumps({"patch_intent": {"file": "a.py"}})], []):
        context = normalize_control_values(values)
        assert owner.bootstrap_fresh_control_from_form(form, context, str(tmp_path), provider=author) is None
    assert author.prompts == []


def test_a_repeated_task_field_is_a_structured_request_rejection(tmp_path):
    owner = _owner()
    author = Author(_reply_for("a.py"))
    result = owner.bootstrap_fresh_control_from_form(
        Form({TASK_FIELD: ["fix a.py", "fix b.py"]}), _fresh_context(), str(tmp_path), provider=author)
    assert (result.code, result.reason) == (REQUEST_INVALID, "repeated_task")
    assert author.prompts == [] and result.response()["control_context"] == FRESH_STATE


def test_the_task_text_is_transported_losslessly(tmp_path):
    owner = _owner()
    root = _repo(tmp_path, {"a.py": A_PY})
    task = "  Fix a.py:\r\n  make value() return 2 — exactly  \n"
    author = Author(_reply_for("a.py"))
    result = owner.bootstrap_fresh_control_from_form(
        Form({TASK_FIELD: [task]}), _fresh_context(), str(root), provider=author)
    assert result.code == BOOTSTRAPPED and result.control["query"] == task
    assert result.receipt()["task"]["sha256"] == hashlib.sha256(task.encode("utf-8")).hexdigest()
    assert task in author.prompts[0]


# -- the production routes ---------------------------------------------------------------------------------

ROUTES = ("/generate_patch", "/generate_candidates")
ROUTE_IDS = ["generate_patch", "generate_candidates"]
DOWNSTREAM_REPLY = json.dumps({
    "summary": "CONTROL.BOOTSTRAP.1 deterministic downstream author",
    "issues": [],
    "patch_candidate": None,
    "patch_plan": None,
    "confidence": 0.0,
    "needs_escalation": True,
})
FRESH1_ANSWER = {
    "error": ("Fresh start: this request carries no prior CONTROL context, and Generate cannot create CONTROL yet. "
              "Run CONTROL for this repository or select one of its runs, then Generate again."),
    "code": "fresh_control_required",
    "control_context": FRESH_STATE,
}
CONTROL_A = {
    "run_marker": "CONTROL.BOOTSTRAP.1 CONTROL context of the repository A run",
    "query": "make value() return 2",
    "top_hypothesis": {"symbol": "a.py::value", "confidence": 0.82},
    "patch_intent": {"relative_path": "a.py", "source_snippet": "def value():\n    return 1\n"},
    "related_snippets": [{"file": "a.py", "snippet": "def value():\n    return 1\n"}],
}
# Graph, index, retrieval, preflight and agent entry points: none may run for a fresh request.
FORBIDDEN_ENTRY_POINTS = (
    "build_graph_from_repo", "get_cached_graph", "select_entry_nodes", "run_control_structured", "run_control",
    "index_repository", "run_preflight_validation", "retrieve_context", "collect_analysis_evidence",
    "deep_project_understand", "run_agent_web", "build_related_snippets", "create_repository_inventory",
    "execute_bounded_lexical_search",
)
PIPELINE_STAGES = ("decide_harness_mode", "build_control_prompt", "extract_json_block",
                   "enforce_control_grounding_on_payload")


def observe_bootstrap_boundary(state, monkeypatch):
    """Forbid analysis entry points, record pipeline stages and answer through deterministic authors."""
    wa = state.wa
    state.stages, state.analysis, state.prompts, state.provider_kwargs = [], [], [], []
    state.bootstrap_reply, state.bootstrap_seen = None, {}

    def forbidden(name):
        def call(*args, **kwargs):
            state.analysis.append(name)
            raise AssertionError(f"CONTROL.BOOTSTRAP.1: {name} must not run for a fresh request")
        return call

    for module in tuple(sys.modules.values()):
        module_name = getattr(module, "__name__", "") or ""
        if module_name.startswith(("web.", "core.", "graph.", "reasoning.", "agents.")) and module_name != "web.app":
            for name in FORBIDDEN_ENTRY_POINTS:
                if callable(getattr(module, name, None)):
                    monkeypatch.setattr(module, name, forbidden(name))
    for name in FORBIDDEN_ENTRY_POINTS:
        if callable(getattr(wa, name, None)):
            monkeypatch.setattr(wa, name, forbidden(name))

    def recorded(name, original):
        def call(*args, **kwargs):
            state.stages.append(name)
            return original(*args, **kwargs)
        return call

    for name in PIPELINE_STAGES:
        monkeypatch.setattr(wa, name, recorded(name, getattr(wa, name)))

    def provider(prompt, *args, **kwargs):
        state.prompts.append(prompt)
        state.provider_kwargs.append(dict(kwargs))
        if prompt.startswith(_owner().BOOTSTRAP_PROMPT_HEADER):
            state.bootstrap_seen = _sources_in(prompt)
            reply = state.bootstrap_reply
            return reply if isinstance(reply, str) else json.dumps(reply)
        return DOWNSTREAM_REPLY

    monkeypatch.setattr(wa, "run_gemini_request", provider)
    monkeypatch.setattr(wa, "run_deepseek_review", provider)
    return state


@pytest.fixture
def web(tmp_path, monkeypatch):
    state = observe_bootstrap_boundary(configure_offline_web(tmp_path, monkeypatch), monkeypatch)
    state.client = state.wa.app.test_client()
    yield state
    assert state.calls == []  # the raising provider configure_offline_web installed never ran


def _route_body(route, repo, control, query=None):
    """Each production handler's exact field order; a fresh page appends its task last."""
    if route == "/generate_patch":
        body = [("repo_path", str(repo)), ("runtime_environment", "auto"), ("control", control),
                ("anti_lesson_control_requested", "false")]
    else:
        body = [("control", control), ("repo_path", str(repo)), ("runtime_environment", "auto")]
    if query is not None:
        body.extend(("query", value) for value in ([query] if isinstance(query, str) else query))
    values: dict[str, list[str]] = {}
    for key, value in body:
        values.setdefault(key, []).append(value)
    return values


def _send(state, route, body, *, roots=()):
    trees = [(root, _tree(root)) for root in roots]
    response = state.client.post(route, data=body)
    for root, before in trees:
        assert _tree(root) == before, "a Generate request mutated repository files"
    assert response.status_code == 200 and response.is_json
    return response.get_json()


def _entry_views(state, raw=None, label="_control_bootstrap1_entry"):
    """The CONTROL.FRESH.1-era Generate routes (or those of the given web/app.py bytes), executed from their bytes."""
    import ast

    from tests._control_bootstrap1_maintenance import before_control_bootstrap1

    raw = before_control_bootstrap1("web/app.py") if raw is None else raw
    tree = ast.parse(raw.decode("utf-8"))
    namespace = dict(state.wa.__dict__)  # after every adapter above is installed
    views = {}
    for name in ("generate_patch", "generate_candidates"):
        node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), f"{label}_{name}", "exec"), namespace)
        views[name] = namespace[name]
    return views


def _use_entry_routes(state, monkeypatch):
    for name, view in _entry_views(state).items():
        monkeypatch.setitem(state.app.view_functions, name, view)


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_pre_control_fresh1_routes_stop_a_fresh_task_at_the_bootstrap_boundary(web, monkeypatch, route):
    root = _repo(web.root, {"a.py": A_PY}, "repo_pre")
    _use_entry_routes(web, monkeypatch)
    answer = _send(web, route, _route_body(route, root, FRESH_WIRE, "fix a.py"), roots=(root,))
    # The entry routes had nowhere to take the task: no CONTROL, no model, no pipeline.
    assert answer == FRESH1_ANSWER
    assert web.stages == [] and web.analysis == [] and web.prompts == []


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_post_a_fresh_task_with_an_explicit_target_bootstraps_and_reaches_the_control_pipeline(web, route):
    root = _repo(web.root, {"a.py": A_PY}, "repo_post")
    web.bootstrap_reply = _reply_for("a.py")
    answer = _send(web, route, _route_body(route, root, FRESH_WIRE, "fix a.py: value() must return 2"),
                   roots=(root,))
    receipt = answer["control_bootstrap"]
    assert receipt["status"] == BOOTSTRAPPED and receipt["provenance"] == "fresh_bootstrap"
    assert receipt["model_calls"] == 1 and receipt["evidence_targets"] == ["a.py"]
    downstream = 1 if route == "/generate_patch" else 3
    # One bootstrap authoring call, then the unchanged CONTROL-dependent pipeline.
    assert len(web.prompts) == 1 + downstream and web.analysis == []
    assert web.prompts[0].startswith(_owner().BOOTSTRAP_PROMPT_HEADER)
    assert web.provider_kwargs[0] == {"response_mime_type": "application/json"}
    assert web.stages[:2] == ["decide_harness_mode", "build_control_prompt"]
    assert web.stages.count("extract_json_block") == downstream
    for prompt in web.prompts[1:]:
        assert "role=requested_target" in prompt and "file=a.py" in prompt and A_PY.decode() in prompt
    if route == "/generate_patch":
        assert set(answer) == {"patch", "usage", "anti_lesson_control", "control_bootstrap"}
        assert json.loads(answer["patch"]) == json.loads(DOWNSTREAM_REPLY)
    else:
        assert set(answer) == {"candidates", "usage", "control_bootstrap"}
        assert [item["name"] for item in answer["candidates"]] == ["gemini_default", "gemini_minimal",
                                                                    "deepseek_review"]
    assert not (web.root / "sessions.json").exists()


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_the_downstream_pipeline_treats_a_bootstrapped_control_exactly_like_prior_control(web, route):
    root = _repo(web.root, {"a.py": A_PY}, "repo_same")
    web.bootstrap_reply = _reply_for("a.py")
    fresh = _send(web, route, _route_body(route, root, FRESH_WIRE, "fix a.py: value() must return 2"))
    fresh_prompts, fresh_stages = web.prompts[1:], list(web.stages)
    control = _owner()
    # Replay the very CONTROL the bootstrap produced as ordinary continuation input.
    web.prompts.clear()
    web.stages.clear()
    web.bootstrap_reply = None
    result = control.bootstrap_fresh_control(
        control.FreshControlBootstrapRequest("fix a.py: value() must return 2", str(root)),
        provider=Author(_reply_for("a.py")))
    prior = _send(web, route, _route_body(route, root, json.dumps(result.control)))
    assert web.prompts == fresh_prompts and web.stages == fresh_stages
    assert {key: value for key, value in fresh.items() if key != "control_bootstrap"} == prior


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_a_fresh_request_without_a_task_keeps_the_frozen_control_fresh1_answer(web, route):
    root = _repo(web.root, {"a.py": A_PY}, "repo_no_task")
    answer = _send(web, route, _route_body(route, root, FRESH_WIRE), roots=(root,))
    assert answer == FRESH1_ANSWER
    assert web.stages == [] and web.analysis == [] and web.prompts == []


FAILURE_CASES = [
    pytest.param({"a.py": A_PY}, "Why is the build slow?", None, (DISCOVERY, "no_explicit_target"), 0, id="discovery"),
    pytest.param({"a.py": A_PY}, "", None, (DISCOVERY, "empty_task"), 0, id="empty_task"),
    pytest.param({"a.py": A_PY}, "fix Missing.java", None, (UNRESOLVED, "not_found"), 0, id="missing"),
    pytest.param({"a.py": A_PY}, "fix ../escape.py", None, (UNRESOLVED, "unsafe_path"), 0, id="unsafe"),
    pytest.param({"blob.txt": b"\x00bin\x00" * 16}, "read blob.txt", None, (UNSUPPORTED, "binary_or_opaque"), 0,
                 id="binary"),
    pytest.param({f"m{i}.py": b"X = 1\n" for i in range(1, 10)}, "fix " + " ".join(f"m{i}.py" for i in range(1, 10)),
                 None, (BUDGET, "file_count"), 0, id="too_many"),
    pytest.param({"a.py": A_PY}, "fix a.py", "AGENT_ERROR: all models failed", (PROVIDER_FAILED, "provider_error"),
                 1, id="provider_failure"),
    pytest.param({"a.py": A_PY}, "fix a.py", "{", (CONTROL_INVALID, "malformed_json"), 1, id="malformed"),
    pytest.param({"a.py": A_PY}, "fix a.py", {"hypotheses": [], "preflight_validation": {"ran": True}},
                 (CONTROL_INVALID, "unadmitted_field"), 1, id="invalid_control"),
]


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize(("files", "task", "reply", "expected", "calls"), FAILURE_CASES)
def test_fresh_bootstrap_failures_are_typed_answers_that_reach_no_pipeline_stage(web, route, files, task, reply,
                                                                                 expected, calls):
    root = _repo(web.root, files, "repo_failure")
    web.bootstrap_reply = reply
    answer = _send(web, route, _route_body(route, root, FRESH_WIRE, task), roots=(root,))
    assert (answer["code"], answer["reason"]) == expected
    assert answer["control_context"] == FRESH_STATE and answer["error"]
    assert "Invalid control JSON" not in answer["error"] and answer["error"] != FRESH1_ANSWER["error"]
    assert answer["control_bootstrap"]["status"] == expected[0]
    assert answer["control_bootstrap"]["model_calls"] == calls == len(web.prompts)
    assert web.stages == [] and web.analysis == []
    assert not (web.root / "sessions.json").exists()


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_a_repeated_task_field_is_a_structured_rejection(web, route):
    root = _repo(web.root, {"a.py": A_PY}, "repo_repeat")
    answer = _send(web, route, _route_body(route, root, FRESH_WIRE, ["fix a.py", "fix b.py"]))
    assert (answer["code"], answer["reason"]) == (REQUEST_INVALID, "repeated_task")
    assert web.stages == [] and web.prompts == []


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize("control", ["", "{", "[]", "{}", " null"], ids=["empty", "malformed", "array", "object",
                                                                         "padded_null"])
def test_malformed_control_is_still_rejected_before_any_stage_even_with_a_task(web, route, control):
    from web.control_context import normalize_control_values

    root = _repo(web.root, {"a.py": A_PY}, "repo_malformed")
    answer = _send(web, route, _route_body(route, root, control, "fix a.py"))
    assert answer == normalize_control_values([control]).response()
    assert web.stages == [] and web.prompts == [] and web.analysis == []


def _continue_prior(state, route, root, query=None):
    (root / "a.py").write_bytes(A_PY)
    stages, prompts = len(state.stages), len(state.prompts)
    answer = _send(state, route, _route_body(route, root, json.dumps(CONTROL_A, indent=2), query))
    return answer, state.stages[stages:], state.prompts[prompts:]


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_same_repository_continuation_is_unchanged_and_never_bootstraps(web, monkeypatch, route):
    root = _repo(web.root, {"a.py": A_PY}, "repo_continue")
    post = _continue_prior(web, route, root)
    with_task = _continue_prior(web, route, root, "fix a.py")
    assert post == with_task  # a task field beside prior CONTROL changes nothing
    assert not any(prompt.startswith(_owner().BOOTSTRAP_PROMPT_HEADER) for prompt in web.prompts)
    _use_entry_routes(web, monkeypatch)
    entry = _continue_prior(web, route, root)
    # Same answer, same stages and byte-identical provider prompts as CONTROL.FRESH.1.
    assert post == entry
    assert "control_bootstrap" not in post[0]


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_java_dogfood_fresh_generate_reads_both_files_and_reaches_the_downstream_gate(web, monkeypatch, route):
    def no_process(*args, **kwargs):
        raise AssertionError("no compiler, test or command runs in CONTROL.BOOTSTRAP.1")

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, no_process)
    # PREFLIGHT.REQUEST.1 now measures this compile gap on the live routes (proven in its own suite);
    # this phase's claim is replayed on its own post-state routes.
    for name, view in _entry_views(web, _post_state("web/app.py"), "_control_bootstrap1_post").items():
        monkeypatch.setitem(web.app.view_functions, name, view)
    root = _java_repo(web.root)
    web.bootstrap_reply = JAVA_REPLY
    answer = _send(web, route, _route_body(route, root, FRESH_WIRE, JAVA_TASK), roots=(root,))
    receipt = answer["control_bootstrap"]
    assert receipt["status"] == BOOTSTRAPPED
    assert receipt["requested_targets"] == receipt["evidence_targets"] == ["Twosum.java", "MainApp.java"]
    assert receipt["localized_patch_targets"] is None and receipt["evidence_gap_needs"] == ["compile_evidence"]
    # The deterministic author proves it saw both complete, unrelated sources.
    assert web.bootstrap_seen == {"Twosum.java": TWOSUM.decode(), "MainApp.java": MAINAPP.decode()}
    assert DEMOTION not in web.prompts[0]
    # The downstream CONTROL gate still decides: without executed evidence it inspects, it does not patch.
    for prompt in web.prompts[1:]:
        assert "file=Twosum.java" in prompt and "file=MainApp.java" in prompt
        assert TWOSUM.decode() in prompt and MAINAPP.decode() in prompt
        assert "auto_patch_candidate_allowed=false" in prompt
    if route == "/generate_patch":
        assert json.loads(answer["patch"])["patch_candidate"] is None
    assert web.analysis == [] and not (web.root / "sessions.json").exists()


def test_repository_b_bootstraps_only_from_its_own_files(web):
    repo_a = _repo(web.root, {"a.py": A_PY}, "repo_a")
    repo_b = _repo(web.root, {"b.py": b"def b():\n    return 'B'\n"}, "repo_b")
    route = "/generate_patch"
    # A file that exists only in repository A is not found in repository B.
    answer = _send(web, route, _route_body(route, repo_b, FRESH_WIRE, "fix a.py"), roots=(repo_a, repo_b))
    assert (answer["code"], answer["reason"]) == (UNRESOLVED, "not_found") and web.prompts == []
    web.bootstrap_reply = {"hypotheses": [_hypothesis("b.py", "b")], "evidence_gaps": []}
    answer = _send(web, route, _route_body(route, repo_b, FRESH_WIRE, "fix b.py"), roots=(repo_a, repo_b))
    receipt = answer["control_bootstrap"]
    assert receipt["status"] == BOOTSTRAPPED
    assert receipt["repository"]["canonical_root"] == str(repo_b.resolve())
    assert web.bootstrap_seen == {"b.py": "def b():\n    return 'B'\n"}
    assert all("def value():" not in prompt for prompt in web.prompts)


# -- one owner, contained production change -------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TEMPLATE = "web/templates/index.html"
STATE_MODULE = "web/static/workbench_state.js"
PIPELINE_TAIL = "    harness_block = _patch_generation_harness_block("
FRESH_TICKET_CONTROL = "control: ticket.requestRun ? ticket.requestRun.context : JSON.stringify(null),"
EXISTING_FILES_CHANGED = (
    "web/app.py",
    "web/templates/index.html",
    "web/static/workbench_state.js",
    "docs/roadmap/phase_registry.json",
    "tests/test_phase_registry.py",
    "tests/test_phase_picker.py",
    "tests/_control_fresh1_maintenance.py",
    "tests/test_control_fresh1.py",
    "tests/test_ux_context1_browser.py",
)
NEW_FILES = (
    "web/control_bootstrap.py",
    "tests/test_control_bootstrap1.py",
    "tests/test_control_bootstrap1_browser.py",
    "tests/_control_bootstrap1_maintenance.py",
    "tests/fixtures/control_bootstrap1_reversal.json",
    "tests/fixtures/control_bootstrap1_frozen_boundaries.json",
    "tests/fixtures/control_bootstrap1_completion.json",
    "docs/designs/2026-09-18-explicit-target-direct-context-bootstrap.md",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _control_fresh1_bytes(relative: str) -> bytes:
    from tests._control_bootstrap1_maintenance import before_control_bootstrap1

    return before_control_bootstrap1(relative)


def _post_state(relative: str) -> bytes:
    """This phase's own post-state bytes: later phases (PREFLIGHT.REQUEST.1 first) are reversed."""
    from tests._preflight_request1_maintenance import before_preflight_request1

    return before_preflight_request1(relative)


def _definitions(raw: bytes) -> tuple[dict[str, str], list[str]]:
    import ast

    definitions: dict[str, list[str]] = {}
    statements: list[str] = []
    for node in ast.parse(raw.decode("utf-8")).body:
        dump = ast.dump(node, include_attributes=False)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(node.name, []).append(_sha(dump.encode()))
        else:
            statements.append(dump)
    return {name: "|".join(values) for name, values in definitions.items()}, statements


def _source_of(raw: bytes, name: str) -> str:
    import ast

    source = raw.decode("utf-8")
    node = next(item for item in ast.parse(source).body if isinstance(item, ast.FunctionDef) and item.name == name)
    return ast.get_source_segment(source, node)


def test_web_app_adds_the_bootstrap_seam_and_moves_each_generate_tail_verbatim():
    entry, post = _control_fresh1_bytes("web/app.py"), _post_state("web/app.py")
    old, old_statements = _definitions(entry)
    new, new_statements = _definitions(post)
    assert set(new) - set(old) == {"_bootstrap_fresh_control", "_generate_patch_from_control",
                                   "_generate_candidates_from_control"}
    assert set(old) - set(new) == set()
    assert {name for name in old if old[name] != new[name]} == {"generate_patch", "generate_candidates"}
    assert [statement for statement in old_statements if statement not in new_statements] == []
    added = [statement for statement in new_statements if statement not in old_statements]
    assert len(added) == 1
    assert added[0].startswith(
        "ImportFrom(module='web.control_bootstrap', names=[alias(name='bootstrap_fresh_control_from_form')]")
    for route, tail in (("generate_patch", "_generate_patch_from_control"),
                        ("generate_candidates", "_generate_candidates_from_control")):
        before, helper, after = _source_of(entry, route), _source_of(post, tail), _source_of(post, route)
        # The whole CONTROL-dependent pipeline (harness, prompt, provider, grounding, answer) is byte-identical.
        assert helper[helper.index(PIPELINE_TAIL):] == before[before.index(PIPELINE_TAIL):], route
        assert after.count("control_context_from_form(request.form)") == 1
        assert after.count("_bootstrap_fresh_control(control_context, repo_path)") == 1
        assert after.count(f"{tail}(repo_path, control_context.control)") == 1
        assert after.count(f"bootstrap.attach({tail}(repo_path, bootstrap.control))") == 1
        assert PIPELINE_TAIL not in after and "json.loads" not in after and '"query"' not in after
    seam = _source_of(post, "_bootstrap_fresh_control")
    assert "provider=run_gemini_request" in seam and "ModelStatsScope()" in seam and '"query"' not in seam


def test_only_the_owner_reads_the_task_field_of_a_generate_request():
    owner = (ROOT / "web/control_bootstrap.py").read_text(encoding="utf-8")
    assert owner.count('TASK_FIELD = "query"') == 1 and owner.count("form.getlist(TASK_FIELD)") == 1
    app = (ROOT / "web/app.py").read_bytes()
    for name in ("generate_patch", "generate_candidates", "_bootstrap_fresh_control", "_generate_patch_from_control",
                 "_generate_candidates_from_control"):
        assert "query" not in _source_of(app, name), name


def _js_function(source: str, signature: str) -> str:
    from tests.test_ux_state1 import _function

    return _function(source, signature)


def test_the_page_changes_only_the_generate_handlers_task_transport():
    entry = _control_fresh1_bytes(TEMPLATE).decode("utf-8")
    from tests._repair_intent1_maintenance import before_repair_intent1
    post = before_repair_intent1(TEMPLATE, (ROOT / TEMPLATE).read_bytes()).decode("utf-8")
    helpers = [_js_function(post, "function _mainIntentText("), _js_function(post, "function _withFreshTask(")]
    assert 'document.querySelector("textarea[name=\'query\']")?.value ?? ""' in helpers[0]
    assert 'if (ticket.task !== null) params.append("query", ticket.task);' in helpers[1]
    for name, kind in (("generatePatch", "generate"), ("generateCandidates", "candidates")):
        body = _js_function(post, f"function {name}(")
        assert body.count(f'WorkbenchState.begin("{kind}", {{ task: _mainIntentText() }})') == 1, name
        assert body.count("_withFreshTask(new URLSearchParams({") == 1 and body.count("}), ticket)") == 1, name
        # The fresh form itself is CONTROL.FRESH.1's; freshness still comes from the ticket alone.
        assert body.count(FRESH_TICKET_CONTROL) == 1 and 'getElementById("context")' not in body, name
    # Everything else, markup included, is the CONTROL.FRESH.1 page byte for byte.
    restored = post
    for name in ("generatePatch", "generateCandidates"):
        restored = restored.replace(_js_function(post, f"function {name}("),
                                    _js_function(entry, f"function {name}("), 1)
    for helper, comment in zip(helpers, (
            "// CONTROL.BOOTSTRAP.1: the Main Intent text exactly as typed (never trimmed or parsed).\r\n",
            "// CONTROL.BOOTSTRAP.1: a fresh ticket (no eligible run) also transports the task\r\n"
            "// it snapshotted at dispatch; a continuation body is unchanged.\r\n")):
        restored = restored.replace(comment + helper + "\r\n\r\n", "", 1)
    assert restored == entry


def test_the_state_owner_changes_only_the_fresh_ticket_task_snapshot():
    entry = _control_fresh1_bytes(STATE_MODULE).decode("utf-8")
    post = (ROOT / STATE_MODULE).read_text(encoding="utf-8")
    task_line = "            task: spec.requestRun && !requestRun() ? text(inputs && inputs.task) : null,\n"
    comment = post[post.index("    // CONTROL.BOOTSTRAP.1:"):post.index("    function begin(kind, inputs) {")]
    assert post.count(task_line) == 1 and comment.count("\n") == 4
    restored = post.replace(task_line, "").replace(comment, "").replace(
        "function begin(kind, inputs) {", "function begin(kind) {")
    assert restored == entry
    # Still a state owner only: the added lines bring no transport, DOM, storage or parsing.
    for forbidden in ("fetch(", "document.", "window.", "localStorage", "JSON.parse(", "trim(", "split(", "match("):
        assert forbidden not in task_line + comment, forbidden


def test_bootstrap_stage_overhead_is_milliseconds(tmp_path):
    import statistics
    import time

    owner = _owner()
    root = _java_repo(tmp_path).resolve()
    request = owner.FreshControlBootstrapRequest(JAVA_TASK, str(root))
    raw = json.dumps(JAVA_REPLY)
    route = owner.task_route(JAVA_TASK)
    requested = tuple(route.shape.contract.explicit_evidence.file_paths)
    targets = owner.ground_explicit_targets(root, requested)
    full = owner.bootstrap_fresh_control(request, provider=lambda prompt, **kwargs: raw)
    context = owner.FreshControlBootstrapContext(request, str(root), full.repository_id, route, requested,
                                                 full.sources)

    def per_call_us(operation, size=20, batches=7):
        samples = []
        for _ in range(batches):
            started = time.perf_counter()
            for _ in range(size):
                operation()
            samples.append((time.perf_counter() - started) / size * 1e6)
        return statistics.median(samples)

    measured = {
        "task_contract_transport_us": per_call_us(lambda: owner.task_route(JAVA_TASK)),
        "target_grounding_us": per_call_us(lambda: owner.ground_explicit_targets(root, requested)),
        "named_file_reads_us": per_call_us(lambda: owner.acquire_explicit_sources(root, targets, request.task_sha256)),
        "prompt_rendering_us": per_call_us(lambda: owner.render_bootstrap_prompt(context)),
        "control_validation_us": per_call_us(lambda: owner.admit_bootstrap_control(raw, context)),
        "end_to_end_without_model_us": per_call_us(
            lambda: owner.bootstrap_fresh_control(request, provider=lambda prompt, **kwargs: raw)),
        "bytes_read": full.bytes_read,
        "prompt_bytes": len(owner.render_bootstrap_prompt(context).encode("utf-8")),
    }
    print("CONTROL_BOOTSTRAP1_PERFORMANCE=" + json.dumps(measured, sort_keys=True))
    assert measured["bytes_read"] == len(TWOSUM) + len(MAINAPP)
    assert measured["prompt_rendering_us"] < 5_000 and measured["control_validation_us"] < 20_000
    assert measured["task_contract_transport_us"] < 50_000 and measured["target_grounding_us"] < 50_000
    assert measured["named_file_reads_us"] < 250_000 and measured["end_to_end_without_model_us"] < 500_000


# -- registry, reversal, frozen boundaries and completion ---------------------------------------------------

def test_registry_has_one_complete_control_bootstrap1_phase_directly_after_control_fresh1():
    from core.phase_picker import pick_phase_candidates
    from core.phase_registry import load_phase_registry, validate_phase_registry

    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phases = [phase for phase in registry["phases"] if phase["phase_id"] == "CONTROL.BOOTSTRAP.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["prerequisites"] == ["CONTROL.FRESH.1"]
    ids = [entry["phase_id"] for entry in registry["phases"]]
    assert ids.index("CONTROL.BOOTSTRAP.1") == ids.index("CONTROL.FRESH.1") + 1
    # One production authoring opportunity per fresh request, and the registry's price for it.
    assert phase["model_calls_allowed"] is True and phase["budget_tier"] == "strong_model_requires_approval"
    assert phase["network_allowed"] is False and phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True and phase["writes_real_repo"] is True
    assert {"web/control_bootstrap.py", "web/app.py", TEMPLATE, STATE_MODULE} <= set(phase["allowed_files"])
    for frozen in ("core/", "patching/", "agents/", "web/control_context.py", "web/routes/", "web/runner.py",
                   "web/session_store.py", "web/static/request_integrity.js", "web/static/safe_content.js"):
        assert frozen in phase["forbidden_files"], frozen
    notes = " ".join(phase["notes"]) + phase["summary"]
    for claim in ("PREFLIGHT.REQUEST.1", "fresh_control_required", "no run, session or history entry"):
        assert claim in notes, claim
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_reversal_receipt_reconstructs_every_entry_file_on_the_control_fresh1_post_state():
    receipt = json.loads((FIXTURES / "control_bootstrap1_reversal.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "CONTROL.BOOTSTRAP.1"
    assert set(receipt["files"]) == set(EXISTING_FILES_CHANGED)
    anchors: dict[str, str] = {}
    for name, key in (("control_fresh1_frozen_boundaries.json", "sha256"),
                      ("control_fresh1_completion.json", "source_sha256")):
        anchors.update(json.loads((FIXTURES / name).read_text(encoding="utf-8"))[key])  # newest pin wins
    for relative, record in receipt["files"].items():
        restored = _control_fresh1_bytes(relative)
        # Each entry digest is an independent CONTROL.FRESH.1-era pin, not a digest this phase chose.
        assert _sha(restored) == record["entry_sha256"] == anchors[relative], relative
        assert _sha(_post_state(relative)) == record["post_sha256"], relative


def test_frozen_phase_boundaries_are_byte_exact():
    manifest = json.loads((FIXTURES / "control_bootstrap1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "CONTROL.BOOTSTRAP.1"
    for relative, digest in manifest["sha256"].items():
        assert _sha(_post_state(relative)) == digest, relative
    groups = manifest["groups"]
    for group in ("CONTROL.FRESH.1", "UX.CONTEXT.1", "UX.STATE.1", "AUTH.WEB.1", "AUTH.WEB.READ.1", "SEC.UI.1",
                  "DATA.UNDO.1", "EXEC.PLAN.1", "AUTH.DREAM.1", "DATA.ROLLBACK.1", "Track_A", "control_pipeline",
                  "intent_owner", "direct_context", "backend_web", "static_assets", "reversal_chain", "audit"):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group
    assert {"web/control_context.py", "core/live_task_routing.py", "core/input_understanding.py",
            "core/explicit_evidence.py", "core/task_contract.py", "core/direct_context_runtime.py",
            "core/direct_file_reader.py", "core/direct_read_receipt.py", "core/repository_inventory.py",
            "core/control_engine.py", "core/harness_modes.py", "core/pipeline.py", "agents/gemini_client.py",
            "web/routes/patch_routes.py", "web/runner.py", "web/session_store.py",
            "web/static/request_integrity.js"} <= set(manifest["sha256"])
    assert not set(manifest["sha256"]) & set(EXISTING_FILES_CHANGED + NEW_FILES)
    # Everything CONTROL.FRESH.1 froze and this phase did not touch still carries CONTROL.FRESH.1's own digest.
    previous = json.loads((FIXTURES / "control_fresh1_frozen_boundaries.json").read_text(encoding="utf-8"))["sha256"]
    for relative, digest in previous.items():
        if relative not in EXISTING_FILES_CHANGED:
            assert manifest["sha256"][relative] == digest, relative


def test_completion_receipt_pins_every_phase_source_and_records_the_bootstrap():
    receipt = json.loads((FIXTURES / "control_bootstrap1_completion.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "CONTROL.BOOTSTRAP.1"
    assert receipt["fresh_generate_executable_with_explicit_targets"] is True
    assert receipt["required_follow_up"] == ["PREFLIGHT.REQUEST.1"]
    assert receipt["model_calls_in_tests"] == 0 and receipt["external_network_requests"] == 0
    assert receipt["production_bootstrap_model_calls_per_fresh_request"] == 1
    assert set(receipt["frozen_production_deltas"].values()) == {0}
    assert receipt["graph_index_embedding_traversal_delta"] == {
        "canonical_graph_operations": 0, "activation_graph_operations": 0, "indexing_operations": 0,
        "embedding_operations": 0, "repository_membership_traversals": 0}
    assert set(receipt["existing_files_changed"]) == set(EXISTING_FILES_CHANGED)
    assert set(receipt["new_files"]) == set(NEW_FILES)
    expected = set(EXISTING_FILES_CHANGED + NEW_FILES)
    expected.remove("tests/fixtures/control_bootstrap1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert _sha(_post_state(relative)) == digest, relative
