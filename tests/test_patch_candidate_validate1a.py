"""Compile infrastructure only: exact synthetic virtual inputs, never a Java test."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import core.structural_compile_validation as owner
from core.structural_candidate_materialization import materialize_structural_candidate
from scripts.replay_oop_intent_detect2 import BANK
from scripts.replay_patch_candidate_materialize1 import (
    SCENARIOS, no_materialization_effects, synthetic_candidate_case,
)
from web import preflight_request as preflight


needs_javac = pytest.mark.skipif(preflight.resolve_javac() is None,
    reason="trusted javac is unavailable; no installation is attempted")


def disk_fixture(root, name="preserve_base_compatibility", *, source=None):
    """Create only explicitly named synthetic before-state files in an isolated fixture root."""
    root.mkdir(parents=True, exist_ok=True)
    scope, fresh, candidate = synthetic_candidate_case(name, root=root, source=source)
    path = root / fresh["current_context"].file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fresh["current_source"])
    materialized = materialize_structural_candidate(candidate, admitted_scope=scope,
        repository_root=root, **fresh)
    return scope, fresh, candidate, materialized


def compile_fixture(root, fixture, **changes):
    scope, fresh, candidate, materialized = fixture
    return owner.compile_materialized_structural_candidate(materialized, candidate=candidate,
        admitted_scope=scope, repository_root=root, **{**fresh, **changes})


def pure_fixture():
    scope, fresh, candidate = synthetic_candidate_case()
    return scope, fresh, candidate, materialize_structural_candidate(candidate,
        admitted_scope=scope, **fresh)


def bound_dependency_fixture(root, *, deprecated=False):
    """Bind an exact synthetic neighbor through the entire frozen prerequisite chain."""
    from core.class_semantic_context import project_class_semantic_context
    from core.repository_identity import derive_repository_id
    from core.treesitter_parse import structural_definitions
    import scripts.replay_patch_scope_refresh1 as refresh_replay
    import scripts.replay_patch_scope_plan1 as plan_replay
    root.mkdir(parents=True, exist_ok=True)
    raw = b"@Deprecated class Missing {}" if deprecated else b"class Missing {}"
    context = project_class_semantic_context(raw=raw, language="java", file="Missing.java",
        target=structural_definitions(raw.decode(), "java")["definitions"][0],
        expected_source_fingerprint=sha256(raw).hexdigest(), repository_id=derive_repository_id(root))
    related = ((context, raw),)
    scenario = plan_replay._scenario
    functions = {name: getattr(refresh_replay, name) for name in (
        "propose_structural_scope_expansion", "recheck_scope_semantics", "continue_scope_transition")}

    def augment(name):
        return lambda **kwargs: functions[name](**{**kwargs, "related_contexts": related})

    def bound_scenario(*args, **kwargs):
        result = scenario(*args, **kwargs)
        return (*result[:-1], {**result[-1], "related_contexts": related})

    with ExitStack() as stack:
        stack.enter_context(patch.object(plan_replay, "_scenario", bound_scenario))
        for name in functions:
            stack.enter_context(patch.object(refresh_replay, name, augment(name)))
        scope, fresh, candidate = synthetic_candidate_case(root=root,
            source=BANK.replace("  private double balance;", "  Missing dependency;\n  private double balance;"))
    (root / "Missing.java").write_bytes(raw)
    (root / "bank.java").write_bytes(fresh["current_source"])
    materialized = materialize_structural_candidate(candidate, admitted_scope=scope,
        repository_root=root, **fresh)
    return scope, fresh, candidate, materialized


def synthetic_result(**changes):
    identity = owner.JavacIdentity(str(Path("C:/trusted/javac.exe")), "a" * 64, "javac 23.0.2")
    return owner.CompilerResult(**{ "compiler": identity, "exit_code": 0, **changes})


def normalize(fixture, result, **changes):
    scope, fresh, candidate, materialized = fixture
    return owner.normalize_structural_compile_result(materialized, compiler_result=result,
        candidate=candidate, admitted_scope=scope, **{**fresh, **changes})


def validate(receipt, fixture, **changes):
    scope, fresh, candidate, materialized = fixture
    return owner.validate_structural_compile_receipt(receipt, materialized=materialized,
        candidate=candidate, admitted_scope=scope, **{**fresh, **changes})


@contextmanager
def forbid_noncompile_effects():
    """Real javac is allowed; discovery, models, authors, network and repair are not."""
    def forbidden(*args, **kwargs):
        raise AssertionError("compile validation attempted an unrelated effect")
    targets = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.structural_patch_author.StructuralAuthorInvocation.run", "socket.create_connection",
        "socket.socket.connect", "subprocess.run", "os.system", "os.listdir",
        "pathlib.Path.glob", "pathlib.Path.rglob", "pathlib.Path.iterdir")
    real_walk = os.walk

    def cleanup_walk(path, *args, **kwargs):
        # Python 3.14's normal TemporaryDirectory cleanup walks its own tree.
        temporary = Path(path).resolve()
        assert temporary.name.startswith("patch-candidate-validate1a-")
        assert temporary.parent == Path(tempfile.gettempdir()).resolve()
        return real_walk(path, *args, **kwargs)

    with ExitStack() as stack:
        for target in targets:
            stack.enter_context(patch(target, forbidden))
        stack.enter_context(patch("os.walk", cleanup_walk))
        yield


@pytest.fixture(scope="module")
def pure_case():
    return pure_fixture()


@needs_javac
@pytest.mark.parametrize("name", SCENARIOS)
def test_exact_frozen_materialize_outputs_compile_without_source_repair(tmp_path, name):
    fixture = disk_fixture(tmp_path, name)
    scope, fresh, candidate, materialized = fixture
    snapshots = scope.to_json(), candidate.to_json(), materialized.to_json(), fresh["plan"].to_json()
    with forbid_noncompile_effects():
        receipt = compile_fixture(tmp_path, fixture)
    assert receipt.status == "compile_validated", receipt.as_dict()
    assert receipt.compile_success is True
    assert receipt.compiler_result.exit_code == 0
    assert receipt.compiler_result.compiler.version.startswith("javac ")
    assert receipt.materialization_fingerprint == materialized.fingerprint
    assert receipt.candidate_fingerprint == candidate.fingerprint
    assert {entry.path for entry in receipt.input_manifest} == {f.path for f in materialized.virtual_files}
    for entry in receipt.input_manifest:
        virtual = next(f for f in materialized.virtual_files if f.path == entry.path)
        assert (entry.sha256, entry.size) == (virtual.after_sha256, len(virtual.after_bytes))
        assert entry.provenance == "materialized_virtual_file"
    assert snapshots == (scope.to_json(), candidate.to_json(), materialized.to_json(), fresh["plan"].to_json())
    assert (tmp_path / fresh["current_context"].file).read_bytes() == fresh["current_source"]
    for virtual in materialized.virtual_files:
        if virtual.before_state == "absent":
            assert not (tmp_path / virtual.path).exists()
    assert not (tmp_path / "SavingAccountBehaviorTest.java").exists()
    assert receipt.behavioral_validation_pending is True and receipt.behavior_validated is False
    assert receipt.javac_evidence_satisfaction
    assert receipt.javac_invocation_count == 1 and receipt.version_probe_count == 1
    assert receipt.author_calls == receipt.model_calls == receipt.repository_traversals == 0
    assert receipt.arbitrary_command_execution_count == 0
    assert receipt.authority == "diagnostic_evidence_only"
    for field in ("write_authority", "filesystem_write_authority", "filesystem_file_creation_authority",
                  "execution_authorized", "apply_authority", "test_write_authority"):
        assert getattr(receipt, field) is False
    assert validate(receipt.as_dict(), fixture) == receipt


@needs_javac
def test_fixed_javac_argv_exact_projection_and_ephemeral_cleanup(tmp_path, monkeypatch):
    source = "// $(touch injected) ; & echo comment is source only\n" + BANK
    fixture = disk_fixture(tmp_path, source=source)
    materialized = fixture[-1]
    real_start = preflight._start
    real_popen = preflight.subprocess.Popen
    invocations, workspaces = [], []

    def record_start(argv, **kwargs):
        invocations.append((tuple(argv), kwargs))
        executable = Path(argv[0]).name.lower()
        assert executable in {"javac", "javac.exe", "javac.com"}
        working = Path(kwargs["cwd"]).resolve()
        assert working != tmp_path.resolve() and tmp_path.resolve() not in working.parents
        assert Path(kwargs["env"]["TEMP"]).is_dir()
        workspaces.append(Path(kwargs["env"]["TEMP"]))
        assert not {"JDK_JAVAC_OPTIONS", "JAVA_TOOL_OPTIONS", "CLASSPATH"} & kwargs["env"].keys()
        if "-version" not in argv:
            assert "-d" in argv and "-proc:none" in argv and "-implicit:none" in argv
            assert not {"-Xlint", "-Werror"} & set(argv)
            output = Path(argv[argv.index("-d") + 1])
            assert output.is_dir() and output.resolve() != working
            exact = [arg for arg in argv[1:] if arg.endswith(".java")]
            assert len(exact) == len(materialized.virtual_files)
            for arg in exact:
                path = Path(arg)
                if not path.is_absolute():
                    path = working / path
                logical = next(v for v in materialized.virtual_files if path.name == Path(v.path).name)
                assert path.read_bytes() == logical.after_bytes
                assert sha256(path.read_bytes()).hexdigest() == logical.after_sha256
            assert all("BehaviorTest" not in arg for arg in argv)
        return real_start(argv, **kwargs)

    monkeypatch.setattr(preflight, "_start", record_start)

    def record_launch(argv, **kwargs):
        assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["close_fds"] is True
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(preflight.subprocess, "Popen", record_launch)
    with forbid_noncompile_effects():
        receipt = compile_fixture(tmp_path, fixture)
    assert receipt.compile_success and len(invocations) == 2
    assert all(not workspace.exists() for workspace in workspaces)
    assert "patch-candidate-validate" not in receipt.to_json()
    assert validate(receipt, fixture) == receipt


@needs_javac
def test_existing_source_compile_error_is_preserved_without_candidate_revision(tmp_path):
    source = BANK.replace("balance += amount;", 'balance += "broken";', 1)
    fixture = disk_fixture(tmp_path, source=source)
    before = fixture[-1].to_json(), fixture[2].to_json()
    with forbid_noncompile_effects():
        receipt = compile_fixture(tmp_path, fixture)
    assert receipt.status == "compile_failed" and receipt.compile_success is False
    assert receipt.compiler_result.exit_code != 0
    assert "incompatible types" in receipt.compiler_result.stderr
    assert any(d.file == "bank.java" and d.owner == "BankAccount" and d.member == "deposit"
        for d in receipt.diagnostics)
    assert not receipt.javac_evidence_satisfaction
    assert before == (fixture[-1].to_json(), fixture[2].to_json())


@pytest.mark.parametrize("mutation", ("source", "collision", "after_source", "after_sha256", "lineage", "candidate"))
def test_freshness_and_tampering_fail_before_workspace_or_javac(tmp_path, mutation):
    scope, fresh, candidate, materialized = disk_fixture(tmp_path)
    if mutation == "source":
        (tmp_path / "bank.java").write_bytes(fresh["current_source"] + b"\n// stale")
    elif mutation == "collision":
        (tmp_path / "SavingAccount.java").write_bytes(b"occupied")
    elif mutation in {"after_source", "after_sha256", "lineage"}:
        payload = materialized.as_dict()
        if mutation == "lineage":
            payload["candidate_fingerprint"] = "wrong"
        else:
            payload["virtual_files"][0][mutation] += "forged"
        materialized = payload
    else:
        candidate = {**candidate.as_dict(), "admission_fingerprint": "wrong"}
    with patch("tempfile.TemporaryDirectory", side_effect=AssertionError("workspace before freshness")), \
            patch.object(owner, "_run_javac", side_effect=AssertionError("javac before freshness")):
        with pytest.raises(owner.CompileValidationError) as rejected:
            owner.compile_materialized_structural_candidate(materialized, candidate=candidate,
                admitted_scope=scope, repository_root=tmp_path, **fresh)
    expected = {"reacquisition_required"} if mutation == "source" else \
        {"materialization_conflict_existing_path", "validation_stale"} if mutation == "collision" else \
        {"materialization_stale", "candidate_stale", "validation_stale"}
    assert rejected.value.code in expected


@needs_javac
@pytest.mark.parametrize("unbound_file_exists", (False, True))
def test_missing_exact_dependency_never_discovers_or_compiles_neighbor(tmp_path, unbound_file_exists):
    source = BANK.replace("  private double balance;", "  Missing dependency;\n  private double balance;")
    fixture = disk_fixture(tmp_path, source=source)
    unbound = tmp_path / "Missing.java"
    if unbound_file_exists:
        unbound.write_bytes(b"class Missing {}")
    reads, original = [], Path.read_bytes

    def record_read(path):
        reads.append(path.resolve())
        return original(path)

    with forbid_noncompile_effects(), patch.object(Path, "read_bytes", record_read):
        receipt = compile_fixture(tmp_path, fixture)
    assert receipt.status == "compile_evidence_incomplete" and not receipt.compile_success
    assert "cannot find symbol" in receipt.compiler_result.stderr and "Missing" in receipt.compiler_result.stderr
    assert unbound.resolve() not in reads
    assert {entry.path for entry in receipt.input_manifest} == {"bank.java", "SavingAccount.java"}
    assert receipt.repository_traversals == 0


@needs_javac
@pytest.mark.parametrize("deprecated", (False, True))
def test_exact_bound_unchanged_dependency_is_copied_byte_for_byte_as_read_only(tmp_path, deprecated):
    fixture = bound_dependency_fixture(tmp_path, deprecated=deprecated)
    before = (tmp_path / "Missing.java").read_bytes()
    with forbid_noncompile_effects():
        receipt = compile_fixture(tmp_path, fixture)
    assert receipt.status == "compile_validated" and receipt.compile_success
    dependency = next(entry for entry in receipt.input_manifest if entry.path == "Missing.java")
    assert dependency.provenance == "read_only_compile_dependency"
    assert (dependency.sha256, dependency.size) == (sha256(before).hexdigest(), len(before))
    assert (tmp_path / "Missing.java").read_bytes() == before
    if deprecated:
        assert receipt.warnings and "deprecated API" in receipt.compiler_result.stderr
    assert validate(receipt, fixture) == receipt


def test_changed_bound_dependency_rejects_before_workspace_and_javac(tmp_path):
    fixture = bound_dependency_fixture(tmp_path)
    (tmp_path / "Missing.java").write_bytes(b"class Missing { int changed; }")
    with patch("tempfile.TemporaryDirectory", side_effect=AssertionError("workspace before dependency freshness")), \
            patch.object(owner, "_run_javac", side_effect=AssertionError("javac before dependency freshness")):
        with pytest.raises(owner.CompileValidationError, match="reacquisition_required"):
            compile_fixture(tmp_path, fixture)


def test_pure_success_warning_failure_and_diagnostic_owner_mapping(pure_case):
    success = normalize(pure_case, synthetic_result())
    warning_output = "SavingAccount.java:14: warning: synthetic compile warning\n    savingBalance += amount;\n    ^\n1 warning\n"
    warning = normalize(pure_case, synthetic_result(stderr=warning_output))
    assert success.status == warning.status == "compile_validated"
    assert success.compile_success is warning.compile_success is True
    assert warning.warnings and all(d.kind == "warning" for d in warning.warnings)
    failure_output = "SavingAccount.java:6: error: incompatible types: String cannot be converted to double\n    super(opening);\n          ^\n1 error\n"
    failure = normalize(pure_case, synthetic_result(exit_code=1, stderr=failure_output))
    assert failure.status == "compile_failed" and not failure.compile_success
    diagnostic = failure.diagnostics[0]
    assert diagnostic.file == "SavingAccount.java" and diagnostic.owner == "SavingAccount"
    assert diagnostic.member == "SavingAccount" and diagnostic.definition_ids
    virtual = next(v for v in pure_case[-1].virtual_files if v.path == diagnostic.file)
    assert diagnostic.source_sha256 == virtual.after_sha256
    assert diagnostic.compiler_receipt_fingerprint == failure.compiler_receipt_fingerprint
    assert diagnostic.materialization_fingerprint == pure_case[-1].fingerprint
    assert failure.compiler_result.stderr == failure_output
    for receipt in (success, warning, failure):
        assert validate(receipt.as_dict(), pure_case) == receipt


def test_exact_cross_file_constructor_relation_is_retained(pure_case):
    stderr = ("SavingAccount.java:6: error: constructor BankAccount in class BankAccount cannot be applied to given types;\n"
        "    super(opening);\n          ^\n  required: String\n  found: double\n"
        "  reason: argument mismatch; double cannot be converted to String\n1 error\n")
    receipt = normalize(pure_case, synthetic_result(exit_code=1, stderr=stderr))
    diagnostic = receipt.diagnostics[0]
    assert diagnostic.file == "SavingAccount.java" and diagnostic.member == "SavingAccount"
    bank_hash = next(v.after_sha256 for v in pure_case[-1].virtual_files if v.path == "bank.java")
    assert any(reference.file == "bank.java" and reference.source_sha256 == bank_hash
        and reference.owner == "BankAccount" for reference in diagnostic.related_sources)


def test_absolute_temporary_diagnostics_normalize_to_same_semantic_receipt(pure_case):
    receipts = []
    for suffix in ("first", "second"):
        workspace = Path("C:/diagnostic-workspaces") / suffix
        source_root = workspace / "sources"
        raw = (str(source_root / "SavingAccount.java") + ":6: error: synthetic failure\n"
            "    super(opening);\n    ^\n1 error\n").encode()
        result = preflight._ProcessRun(1, False, b"", raw, 0, len(raw), 0.0, 0.0)
        stdout, stderr, overflow = owner._captured(result, source_root, workspace)
        assert str(workspace) not in stderr and stderr.startswith("SavingAccount.java:6:")
        receipts.append(normalize(pure_case, synthetic_result(exit_code=1, stdout=stdout,
            stderr=stderr, output_overflow=overflow)))
    assert receipts[0].fingerprint == receipts[1].fingerprint


@pytest.mark.parametrize("result,status", (
    ({"compiler": None, "exit_code": None, "unavailable_reason": "javac_not_found",
      "javac_invocation_count": 0, "version_probe_count": 0}, "validator_unavailable"),
    ({"exit_code": None, "timed_out": True}, "compile_timeout"),
    ({"output_overflow": True}, "compile_output_bounded"),
))
def test_pure_infrastructure_failures_are_typed_and_fail_closed(pure_case, result, status):
    receipt = normalize(pure_case, synthetic_result(**result))
    assert receipt.status == status and receipt.compile_success is False
    assert not receipt.javac_evidence_satisfaction
    assert validate(receipt.as_dict(), pure_case) == receipt


def test_unavailable_javac_is_measured_without_installation(tmp_path, monkeypatch):
    fixture = disk_fixture(tmp_path)
    monkeypatch.setattr(preflight, "resolve_javac", lambda excluded_root=None: None)
    with forbid_noncompile_effects(), patch.object(owner, "_run_javac", side_effect=AssertionError("unavailable javac")):
        receipt = compile_fixture(tmp_path, fixture)
    assert receipt.status == "validator_unavailable" and not receipt.compile_success
    assert receipt.javac_invocation_count == receipt.version_probe_count == 0


@needs_javac
@pytest.mark.parametrize("issue,status", (("timeout", "compile_timeout"), ("overflow", "compile_output_bounded")))
def test_bounded_provider_failures_are_measured_and_workspace_removed(tmp_path, monkeypatch, issue, status):
    fixture = disk_fixture(tmp_path)
    calls, workspaces = [], []
    real = owner._run_javac

    def provider(argv, **kwargs):
        calls.append(tuple(argv))
        workspaces.append(Path(kwargs["workspace"]))
        if "-version" in argv:
            return real(argv, **kwargs)
        if issue == "timeout":
            return preflight._ProcessRun(None, True, b"", b"", 0, 0, 0.0, 0.0)
        return preflight._ProcessRun(0, False, b"", b"x" * (owner.MAX_OUTPUT_BYTES + 1),
            0, owner.MAX_OUTPUT_BYTES + 1, 0.0, 0.0)

    monkeypatch.setattr(owner, "_run_javac", provider)
    receipt = compile_fixture(tmp_path, fixture)
    assert receipt.status == status and not receipt.compile_success
    assert receipt.javac_invocation_count == 1 and len(calls) == 2
    assert all(not p.exists() for p in workspaces)


def test_temporary_byte_integrity_mismatch_rejects_before_javac(tmp_path, monkeypatch):
    fixture = disk_fixture(tmp_path)
    original = Path.write_bytes

    def corrupt_virtual_write(path, raw):
        if path.suffix == ".java" and tmp_path.resolve() not in path.resolve().parents:
            return original(path, raw + b"\n// corruption")
        return original(path, raw)

    monkeypatch.setattr(Path, "write_bytes", corrupt_virtual_write)
    with patch.object(owner, "_run_javac", side_effect=AssertionError("javac on corrupt workspace")):
        with pytest.raises(owner.CompileValidationError, match="validation_workspace_integrity_failure"):
            compile_fixture(tmp_path, fixture)


def test_repository_relative_temporary_parent_is_rejected_before_workspace_creation(tmp_path, monkeypatch):
    fixture = disk_fixture(tmp_path)
    monkeypatch.setattr(owner.tempfile, "gettempdir", lambda: str(tmp_path))
    with patch("tempfile.TemporaryDirectory", side_effect=AssertionError("workspace inside repository")), \
            patch.object(owner, "_run_javac", side_effect=AssertionError("javac inside repository")):
        with pytest.raises(owner.CompileValidationError, match="validation_workspace_integrity_failure"):
            compile_fixture(tmp_path, fixture)


def test_process_timeout_only_kills_the_started_javac_and_bounds_reaping(tmp_path, monkeypatch):
    events = []

    def wait(*, timeout):
        events.append(("wait", timeout))
        raise subprocess.TimeoutExpired(["javac"], timeout)

    process = SimpleNamespace(wait=wait, kill=lambda: events.append(("kill",)))
    monkeypatch.setattr(preflight, "_start", lambda argv, **kwargs: process)
    run = owner._run_javac(["javac"], cwd=str(tmp_path), env={}, workspace=tmp_path,
        label="timeout", timeout=0.02)
    assert run.timed_out and run.exit_status is None
    assert events == [("wait", 0.02), ("kill",), ("wait", 10)]


@pytest.mark.parametrize("version", ("javac 23\nexecute something", "javac ", "java 23"))
def test_javac_identity_rejects_malformed_version_claims(version):
    with pytest.raises(owner.CompileValidationError):
        owner.JavacIdentity(str(Path("C:/trusted/javac.exe")), "a" * 64, version)


@pytest.mark.parametrize("field,value", (
    ("write_authority", True), ("filesystem_write_authority", True),
    ("filesystem_file_creation_authority", True), ("execution_authorized", True),
    ("apply_authority", True), ("test_write_authority", True),
    ("authority", "write_authorized"), ("compile_success", False),
    ("candidate_fingerprint", "wrong"), ("validation_fingerprint", "wrong"),
))
def test_authority_and_receipt_tampering_are_independently_rejected(pure_case, field, value):
    receipt = normalize(pure_case, synthetic_result())
    tampered = receipt.as_dict()
    tampered[field] = value
    with pytest.raises(owner.CompileValidationError):
        validate(tampered, pure_case)


@pytest.mark.parametrize("part", ("manifest", "diagnostic", "compiler", "result"))
def test_nested_receipt_tampering_is_rejected(pure_case, part):
    stderr = "SavingAccount.java:6: error: synthetic failure\n    super(opening);\n    ^\n1 error\n"
    receipt = normalize(pure_case, synthetic_result(exit_code=1, stderr=stderr))
    payload = deepcopy(receipt.as_dict())
    if part == "manifest":
        payload["input_manifest"][0]["sha256"] = "b" * 64
    elif part == "diagnostic":
        payload["diagnostics"][0]["member"] = "invented"
    elif part == "compiler":
        payload["compiler_result"]["compiler"]["version"] = "javac invented"
    else:
        payload["compiler_result"]["exit_code"] = 0
    with pytest.raises(owner.CompileValidationError):
        validate(payload, pure_case)


def test_receipt_immutable_idempotent_and_timing_excluded(pure_case):
    timings_a, timings_b = {}, {}
    a = normalize(pure_case, synthetic_result(), timings=timings_a)
    b = normalize(pure_case, synthetic_result(), timings=timings_b)
    assert a == b and a.fingerprint == b.fingerprint
    assert json.loads(a.to_json()) == a.as_dict()
    assert set(timings_a) == set(timings_b) == set(owner.TIMING_FIELDS)
    assert all(type(value) is float and value >= 0 for value in timings_a.values())
    with pytest.raises(FrozenInstanceError):
        a.status = "write_authorized"
    with pytest.raises(FrozenInstanceError):
        a.input_manifest[0].sha256 = "b" * 64
    with pytest.raises(owner.CompileValidationError):
        replace(a, input_manifest=list(a.input_manifest))


def test_pure_normalization_and_receipt_gate_have_zero_effects(pure_case):
    with no_materialization_effects():
        receipt = normalize(pure_case, synthetic_result())
        assert validate(receipt.as_dict(), pure_case) == receipt


def test_stale_after_compile_preserves_history_and_requires_reacquisition(tmp_path):
    fixture = disk_fixture(tmp_path)
    receipt = normalize(fixture, synthetic_result())
    history = receipt.to_json(), fixture[-1].to_json()
    (tmp_path / "bank.java").write_bytes(fixture[1]["current_source"] + b"\n// newer source")
    with pytest.raises(owner.CompileValidationError, match="reacquisition_required"):
        validate(receipt, fixture, repository_root=tmp_path)
    assert history == (receipt.to_json(), fixture[-1].to_json())


def test_bookkeeping_reversal_preserves_exact_dirty_entry_receipts():
    from tests._patch_candidate_validate1a_maintenance import before_patch_candidate_validate1a
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_candidate_validate1a_reversal.json").read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        restored = before_patch_candidate_validate1a(record["path"], (root / record["path"]).read_bytes())
        assert sha256(restored).hexdigest() == record["entry_sha256"]


def test_diagnostic_record_count_overflow_preserves_raw_output_and_fails_closed(pure_case):
    stderr = "".join("SavingAccount.java:6: warning: synthetic bounded diagnostic " + str(index) +
        "\n    super(opening);\n    ^\n" for index in range(owner.MAX_DIAGNOSTICS + 1))
    assert len(stderr.encode("utf-8")) < owner.MAX_OUTPUT_BYTES
    with no_materialization_effects():
        receipt = normalize(pure_case, synthetic_result(stderr=stderr))
        assert validate(receipt.as_dict(), pure_case) == receipt
    assert receipt.status == "compile_output_bounded" and receipt.compile_success is False
    assert receipt.compiler_result.stderr == stderr and receipt.compiler_result.output_overflow is False
    assert not receipt.diagnostics and not receipt.javac_evidence_satisfaction


def test_exact_packaged_class_reference_maps_to_bound_cross_file_hash():
    scope, fresh, candidate = synthetic_candidate_case("packaged")
    materialized = materialize_structural_candidate(candidate, admitted_scope=scope, **fresh)
    fixture = scope, fresh, candidate, materialized
    stderr = ("edu/SavingAccount.java:15: error: cannot find symbol\n"
        "    if (!debitForSavings(amount)) return false;\n         ^\n"
        "  symbol: method debitForSavings(double)\n  location: class edu.BankAccount\n1 error\n")
    with no_materialization_effects():
        receipt = normalize(fixture, synthetic_result(exit_code=1, stderr=stderr))
        assert validate(receipt.as_dict(), fixture) == receipt
    assert receipt.status == "compile_failed" and not receipt.compile_success
    diagnostic = receipt.diagnostics[0]
    assert diagnostic.file == "edu/SavingAccount.java"
    source_hash = next(v.after_sha256 for v in materialized.virtual_files if v.path == "edu/SavingAccount.java")
    bank_hash = next(v.after_sha256 for v in materialized.virtual_files if v.path == "edu/bank.java")
    assert diagnostic.source_sha256 == source_hash
    assert len(diagnostic.related_sources) == 1
    reference = diagnostic.related_sources[0]
    assert (reference.file, reference.source_sha256, reference.owner) == ("edu/bank.java", bank_hash, "BankAccount")


def test_pure_compiler_identity_inside_repository_root_is_rejected(pure_case):
    root = Path(pure_case[1]["repository_evidence"].canonical_root)
    identity = owner.JavacIdentity(str(root / "tools" / "javac.exe"), "a" * 64, "javac 23.0.2")
    with no_materialization_effects():
        with pytest.raises(owner.CompileValidationError, match="repository cannot supply the compiler"):
            normalize(pure_case, synthetic_result(compiler=identity))
