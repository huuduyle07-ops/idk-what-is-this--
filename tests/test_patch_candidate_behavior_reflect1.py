"""Bounded reflection infrastructure; BANK planning is pure and never executed."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import time

import pytest

import core.read_only_reflection as owner
import core.read_only_reflection_java as java_owner
from scripts.replay_patch_candidate_behavior_exec_plan1 import (
    build, no_execution_planning_effects, planning_fixture,
)
from web.preflight_request import resolve_javac


ROOT = Path(__file__).resolve().parents[1]


def lineage(fixture, **changes):
    scope, fresh, candidate, materialized, receipt, specification = fixture
    return {"specification": specification, "compile_receipt": receipt,
        "materialized": materialized, "candidate": candidate,
        "admitted_scope": scope, **fresh, **changes}


def reflection_rows(plan):
    return [(scenario, observation) for scenario in plan.scenarios
        for observation in scenario.observations
        if observation.mechanism == "read_only_reflection"]


def representative_rows(plan):
    """One complete four-role observation set; every target still reconstructs."""
    first_scenario = reflection_rows(plan)[0][0]
    return [(scenario, observation) for scenario, observation in reflection_rows(plan)
        if scenario.scenario_id == first_scenario.scenario_id]


def request_for(fixture, plan, scenario, observation, **changes):
    return owner.build_read_only_reflection_request(plan,
        scenario_id=scenario.scenario_id, observation_id=observation.observation_id,
        **lineage(fixture, **changes))


def validate_request(request, fixture, plan, **changes):
    return owner.validate_read_only_reflection_request(request,
        execution_plan=plan, **lineage(fixture, **changes))


@pytest.fixture(scope="module")
def compatibility():
    fixture = planning_fixture()
    with no_execution_planning_effects():
        plan = build(fixture)
        requests = tuple(request_for(fixture, plan, scenario, observation)
            for scenario, observation in representative_rows(plan))
    return fixture, plan, requests


def test_every_request_reconstructs_exact_frozen_observation_and_all_roles(compatibility):
    fixture, plan, requests = compatibility
    before = (plan.to_json(), fixture[-1].to_json(), fixture[3].to_json(),
        fixture[4].to_json(), fixture[1]["current_source"])
    with no_execution_planning_effects():
        for (scenario, observation), request in zip(representative_rows(plan), requests):
            assert validate_request(request.as_dict(), fixture, plan) == request
            assert request.target == observation.target
            assert request.execution_plan_fingerprint == plan.fingerprint
            assert request.scenario_id == scenario.scenario_id
            assert request.obligation_ids == scenario.obligation_ids
            assert request.observation_id == observation.observation_id
            assert request.target.declared_type == "double"
            assert request.target.kind == "field" and request.target.visibility == "private"
            assert len(request.target.definition_sha256) == 64
            assert request.target.source_sha256 == next(v.after_sha256
                for v in fixture[3].virtual_files if v.path == request.target.path)
    assert {r.observation_role for r in requests} == {
        "ordinary_balance_before", "ordinary_balance_after",
        "savings_balance_before", "savings_balance_after"}
    assert {(r.target.owner, r.target.name) for r in requests} == {
        ("BankAccount", "balance"), ("SavingAccount", "savingBalance")}
    assert before == (plan.to_json(), fixture[-1].to_json(), fixture[3].to_json(),
        fixture[4].to_json(), fixture[1]["current_source"])


@pytest.mark.parametrize("name", ("preserve_base_compatibility", "nested", "packaged"))
def test_runtime_identity_uses_exact_declaring_owner_and_validated_inheritance(name):
    fixture = planning_fixture(name)
    with no_execution_planning_effects():
        plan = build(fixture)
        requests = [request_for(fixture, plan, scenario, observation)
            for scenario, observation in representative_rows(plan)]
        for request in requests:
            binding = request.runtime_binding
            assert binding.declaring_binary_owner == request.target.binary_owner
            assert binding.source_sha256 == next(v.after_sha256
                for v in fixture[3].virtual_files if v.path == binding.path)
            if request.target.owner == "BankAccount":
                assert binding.relationship == "exact_direct_superclass"
                assert binding.binary_owner != binding.declaring_binary_owner
            else:
                assert binding.relationship == "same_class"
                assert binding.binary_owner == binding.declaring_binary_owner
            assert validate_request(request, fixture, plan) == request
    if name == "nested":
        assert {r.runtime_binding.binary_owner for r in requests} == {"BankAccount$SavingAccount"}
    if name == "packaged":
        assert {r.runtime_binding.binary_owner for r in requests} == {"edu.SavingAccount"}


@pytest.mark.parametrize("key,value", (
    ("name", "password"), ("name", "accountHolder"), ("name", "arbitraryField"),
    ("owner", "SavingAccount"), ("qualified_owner", "SavingAccount"),
    ("declared_type", "int"), ("definition_id", "unplanned::field"),
    ("definition_sha256", "b" * 64), ("source_sha256", "b" * 64),
    ("owner", "System"), ("qualified_owner", "java.lang.System"),
    ("qualified_owner", "ClassLoader"), ("qualified_owner", "Runtime"),
    ("qualified_owner", "ProcessBuilder"),
))
def test_tampered_member_never_becomes_runtime_authority(compatibility, key, value):
    fixture, plan, requests = compatibility
    request = next(r for r in requests if r.target.owner == "BankAccount")
    payload = deepcopy(request.as_dict())
    payload["target"][key] = value
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_request(payload, fixture, plan)
    assert rejected.value.code in {"reflection_target_stale", "reflection_request_invalid",
        "reflection_target_mismatch", "reflection_invalid"}


@pytest.mark.parametrize("key,value", (
    ("execution_plan_fingerprint", "b" * 64), ("scenario_id", "another_scenario"),
    ("observation_id", "another_observation"), ("obligation_ids", []),
    ("observation_role", "arbitrary_label"),
))
def test_request_cannot_cross_plan_scenario_obligation_or_role(compatibility, key, value):
    fixture, plan, requests = compatibility
    payload = deepcopy(requests[0].as_dict())
    payload[key] = value
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_request(payload, fixture, plan)
    assert rejected.value.code in {"reflection_target_stale", "reflection_request_invalid", "reflection_invalid"}


@pytest.mark.parametrize("key,value", (
    ("binary_owner", "java.lang.System"), ("declaring_binary_owner", "SavingAccount"),
    ("relationship", "same_class"), ("source_sha256", "b" * 64),
    ("definition_sha256", "b" * 64),
))
def test_runtime_relationship_cannot_be_aliased_or_widened(compatibility, key, value):
    fixture, plan, requests = compatibility
    request = next(r for r in requests if r.target.owner == "BankAccount")
    payload = deepcopy(request.as_dict())
    payload["runtime_binding"][key] = value
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_request(payload, fixture, plan)
    assert rejected.value.code == "reflection_target_stale"


def test_changed_fresh_source_and_foreign_plan_reject_before_reflection(compatibility):
    fixture, plan, requests = compatibility
    foreign_fixture = planning_fixture("nested")
    with no_execution_planning_effects():
        foreign_plan = build(foreign_fixture)
        with pytest.raises(ValueError) as stale_source:
            validate_request(requests[0], fixture, plan,
                current_source=fixture[1]["current_source"] + b"\n// changed source")
        with pytest.raises(ValueError) as wrong_plan:
            validate_request(requests[0], foreign_fixture, foreign_plan)
    assert stale_source.value.code == "reflection_target_stale"
    assert wrong_plan.value.code == "reflection_target_stale"


@pytest.mark.parametrize("key,value", (
    ("operation", "enumerate_fields"), ("operation", "read_field_by_pattern"),
    ("operation", "write_field"), ("operation", "invoke_private_method"),
    ("operation", "construct_object"), ("operation", "call_method"),
    ("operation", "mutate_object"), ("mutate", True), ("write_value", 800.0),
    ("set_field", "balance"), ("product_mutation_authority", True),
    ("source_write_authority", True), ("reflection_write_authority", True),
    ("private_method_invocation_authority", True),
    ("arbitrary_member_discovery_authority", True),
    ("java_execution_authorized", True), ("apply_authority", True),
))
def test_closed_operation_and_authority_escalation_reject(compatibility, key, value):
    fixture, plan, requests = compatibility
    payload = deepcopy(requests[0].as_dict())
    payload[key] = value
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_request(payload, fixture, plan)
    assert rejected.value.code in {"reflection_authority_escalation", "reflection_request_invalid", "reflection_invalid"}


@pytest.mark.parametrize("key", ("getDeclaredFields", "getFields", "list_fields",
    "discover_private_members", "static", "is_static", "java_source", "shell_command"))
def test_unknown_transport_fields_do_not_extend_the_schema(compatibility, key):
    fixture, plan, requests = compatibility
    payload = deepcopy(requests[0].as_dict())
    payload[key] = True
    with no_execution_planning_effects(), pytest.raises(ValueError):
        validate_request(payload, fixture, plan)


def test_return_observation_is_not_a_private_field_read(compatibility):
    fixture, plan, _ = compatibility
    scenario, observation = next((s, o) for s in plan.scenarios for o in s.observations
        if o.mechanism == "direct_return")
    with no_execution_planning_effects(), pytest.raises(ValueError):
        request_for(fixture, plan, scenario, observation)


def test_request_is_immutable_and_repeated_reconstruction_is_deterministic(compatibility):
    fixture, plan, requests = compatibility
    scenario, observation = representative_rows(plan)[0]
    timings = {}
    with no_execution_planning_effects():
        repeated = request_for(fixture, plan, scenario, observation, timings=timings)
        assert repeated == requests[0]
        assert repeated.fingerprint == requests[0].fingerprint
        assert json.loads(repeated.to_json()) == repeated.as_dict()
        assert validate_request(repeated.as_dict(), fixture, plan) == repeated
    assert set(timings) == set(owner.TIMING_FIELDS)
    assert all(type(value) is float and value >= 0 for value in timings.values())
    assert "timings" not in repeated.as_dict()
    with pytest.raises(FrozenInstanceError):
        repeated.observation_id = "changed"
    with pytest.raises(FrozenInstanceError):
        repeated.runtime_binding.binary_owner = "java.lang.System"


def test_descriptor_reconstruction_improves_only_architecture_truth(compatibility):
    _, plan, _ = compatibility
    before = plan.to_json()
    with no_execution_planning_effects():
        descriptor = owner.get_read_only_reflection_capability_descriptor()
        architecture = owner.reconstruct_diagnostic_capability_availability(plan, descriptor=descriptor)
    payload = descriptor.as_dict()
    assert payload["capability"] == "read_only_reflection"
    assert payload["operation"] == "read_exact_bound_field"
    assert payload["supported_value_types"] == ["double"]
    assert payload["availability"] == "available_but_not_execution_admitted"
    assert all(payload[key] is False for key in (
        "product_mutation_authority", "source_write_authority", "reflection_write_authority",
        "private_method_invocation_authority", "arbitrary_member_discovery_authority",
        "mutation", "enumeration", "method_invocation", "execution_authorized"))
    assert "runtime_object" not in payload and "object_handle" not in payload
    architecture_payload = architecture.as_dict()
    assert "available_but_not_execution_admitted" in json.dumps(architecture_payload)
    assert "unavailable" in json.dumps(architecture_payload)
    assert plan.to_json() == before
    assert next(c.status for c in plan.required_diagnostic_capabilities
        if c.capability == "read_only_reflection") == "plannable_but_not_authorized"
    assert next(c.status for c in plan.required_diagnostic_capabilities
        if c.capability == "deterministic_console_input") == "unavailable"
    with pytest.raises(FrozenInstanceError):
        descriptor.operation = "write_field"


def test_bookkeeping_reversal_preserves_frozen_prerequisite_entry_receipts():
    from tests._patch_candidate_behavior_reflect1_maintenance import before_patch_candidate_behavior_reflect1
    receipt = json.loads((ROOT / "tests/fixtures/patch_candidate_behavior_reflect1_reversal.json")
        .read_text(encoding="utf-8"))
    for record in receipt["reversals"]:
        raw = (ROOT / record["path"]).read_bytes()
        restored = before_patch_candidate_behavior_reflect1(record["path"], raw)
        assert sha256(restored).hexdigest() == record["entry_sha256"]
        with pytest.raises(AssertionError):
            before_patch_candidate_behavior_reflect1(record["path"], raw + b"\n")


def rendered_adapter(request, fixture, plan):
    return java_owner.render_read_only_reflection_adapter(request,
        execution_plan=plan, **lineage(fixture))


def test_java_adapter_has_one_exact_read_surface_and_prohibited_paths_are_absent(compatibility):
    fixture, plan, requests = compatibility
    with no_execution_planning_effects():
        adapter = rendered_adapter(requests[0], fixture, plan)
        assert rendered_adapter(requests[0].as_dict(), fixture, plan) == adapter
    source = adapter.source
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", source, flags=re.S)
    assert adapter.request_fingerprint == requests[0].fingerprint
    assert adapter.source_sha256 == sha256(source.encode("utf-8")).hexdigest()
    assert "readExactBoundField(Object runtimeObject)" in code
    assert f'getDeclaredField("{requests[0].target.name}")' in code
    assert "runtimeObject.getClass() != EXPECTED_RUNTIME_CLASS" in code
    assert "EXPECTED_RUNTIME_CLASS.getSuperclass() == DECLARING_CLASS" in code
    assert "exactField.getType() != double.class" in code
    assert "Modifier.isStatic(exactField.getModifiers())" in code
    assert "exactField.trySetAccessible()" in code
    assert "finally" in code and "exactField.setAccessible(false)" in code
    assert not re.search(r"\b(?:getDeclaredFields|getFields|getDeclaredMethods|getMethods|"
        r"getDeclaredConstructor|getConstructor|forName|newInstance|invoke|setDouble|setInt|"
        r"setLong|setFloat|setBoolean|setByte|setShort|setChar|Unsafe|VarHandle|MethodHandle)\b", code)
    assert not re.search(r"\bexactField\s*\.\s*set\s*\(", code)
    assert "System.console" not in code and "System.in" not in code
    assert "public static void main" not in code
    assert "ClassLoader" not in code and "getModule" not in code
    assert "new BankAccount" not in code and "new SavingAccount" not in code
    assert "transferToSavings(" not in code and "accrueSavingsInterest(" not in code
    assert not re.search(r"static\s+(?:final\s+)?Field\s", code)


SYNTHETIC_FIXTURES = """class ReflectionFixture {
    private double balance;
    ReflectionFixture(double value) { balance = value; }
    final boolean ordinaryUnchanged(double expected) {
        return Double.doubleToRawLongBits(balance) == Double.doubleToRawLongBits(expected);
    }
}
class ReflectionChild extends ReflectionFixture {
    private double savingBalance;
    ReflectionChild(double value, double saving) { super(value); savingBalance = saving; }
    final boolean unchanged(double ordinary, double saving) {
        return ordinaryUnchanged(ordinary) &&
            Double.doubleToRawLongBits(savingBalance) == Double.doubleToRawLongBits(saving);
    }
}
class UnplannedChild extends ReflectionChild {
    UnplannedChild() { super(800.0, 200.0); }
}
class WrongTypeFixture { private int balance = 7; }
class StaticFixture { private static double balance = 11.0; }
class PublicFixture { public double balance = 17.0; }
"""


def _synthetic_adapter_source(adapter, class_name, *, declaring="ReflectionFixture",
        runtime="ReflectionChild", same_class=False):
    """Fixture-only class literal mapping; never change or compile BANK source."""
    source = adapter.source.replace("ExactReadOnlyReflectionAdapter", class_name)
    source = source.replace("BankAccount.class", declaring + ".class")
    source = source.replace("SavingAccount.class", runtime + ".class")
    if same_class:
        source = source.replace("EXPECTED_RUNTIME_CLASS.getSuperclass() == DECLARING_CLASS",
            "EXPECTED_RUNTIME_CLASS == DECLARING_CLASS")
    assert "BankAccount.class" not in source and "SavingAccount.class" not in source
    return source


def _probe_statement(label, adapter, expression):
    return """{
        var observed = %s.readExactBoundField(%s);
        emit("%s", observed.requestFingerprint, observed.runtimeClassIdentity,
            observed.declaringClassIdentity, observed.measuredFieldType,
            observed.canonicalValueBits, observed.status, observed.failureCode,
            observed.adapterVersion, observed.targetValidationNanos,
            observed.reflectionReadNanos, observed.valueNormalizationNanos,
            observed.totalDiagnosticNanos, observed.mutationAuthority);
    }
    """ % (adapter, expression, label)


@pytest.fixture(scope="module")
def synthetic_java_probe(compatibility, request):
    javac = resolve_javac(excluded_root=ROOT)
    if javac is None:
        pytest.skip("trusted javac unavailable; no JDK installation is attempted")
    java = Path(javac).with_name("java.exe" if os.name == "nt" else "java")
    if not java.is_file():
        pytest.skip("matching trusted Java runtime unavailable")
    fixture, plan, requests = compatibility
    ordinary = next(r for r in requests if r.observation_role == "ordinary_balance_before")
    savings = next(r for r in requests if r.observation_role == "savings_balance_before")
    with no_execution_planning_effects():
        ordinary_adapter = rendered_adapter(ordinary, fixture, plan)
        savings_adapter = rendered_adapter(savings, fixture, plan)
    sources = {
        "ReflectionFixture.java": SYNTHETIC_FIXTURES,
        "OrdinaryAdapter.java": _synthetic_adapter_source(ordinary_adapter, "OrdinaryAdapter"),
        "SavingsAdapter.java": _synthetic_adapter_source(savings_adapter, "SavingsAdapter"),
    }
    for name in ("WrongTypeFixture", "StaticFixture", "PublicFixture"):
        sources[name + "Adapter.java"] = _synthetic_adapter_source(ordinary_adapter,
            name + "Adapter", declaring=name, runtime=name, same_class=True)
    statements = [_probe_statement("ordinary_" + str(i), "OrdinaryAdapter", "child") for i in range(5)]
    statements += [_probe_statement("savings_" + str(i), "SavingsAdapter", "child") for i in range(5)]
    statements += [
        _probe_statement("negative_zero", "OrdinaryAdapter", "new ReflectionChild(-0.0, 0.0)"),
        _probe_statement("wrong_runtime", "OrdinaryAdapter", "new ReflectionFixture(800.0)"),
        _probe_statement("unplanned_subclass", "OrdinaryAdapter", "new UnplannedChild()"),
        _probe_statement("null_runtime", "OrdinaryAdapter", "null"),
        _probe_statement("wrong_type", "WrongTypeFixtureAdapter", "new WrongTypeFixture()"),
        _probe_statement("static_field", "StaticFixtureAdapter", "new StaticFixture()"),
        _probe_statement("public_field", "PublicFixtureAdapter", "new PublicFixture()"),
    ]
    for label, expression in (("nan", "Double.NaN"), ("infinity", "Double.POSITIVE_INFINITY"),
            ("negative_infinity", "Double.NEGATIVE_INFINITY")):
        statements.append(_probe_statement(label, "OrdinaryAdapter",
            "new ReflectionChild(" + expression + ", 200.0)"))
    sources["SyntheticReflectionProbe.java"] = """public class SyntheticReflectionProbe {
    private static void emit(String label, String request, String runtime, String declaring,
            String type, String bits, String status, String failure, String adapter,
            long validation, long read, long normalization, long total, boolean mutation) {
        System.out.println(String.join("|", label, request, runtime, declaring, type, bits,
            status, failure, adapter, Long.toString(validation), Long.toString(read),
            Long.toString(normalization), Long.toString(total), Boolean.toString(mutation)));
    }
    public static void main(String[] args) {
        ReflectionChild child = new ReflectionChild(800.0, 200.0);
        %s
        if (!child.unchanged(800.0, 200.0)) throw new AssertionError("reflection changed private state");
        System.out.println("JVM|" + System.getProperty("java.runtime.version"));
        System.out.println("COUNTERS|1|0");
    }
}
""" % "".join(statements)
    workspace_handle = tempfile.TemporaryDirectory(prefix="cattus-reflect1-")
    request.addfinalizer(workspace_handle.cleanup)
    workspace = Path(workspace_handle.name)
    assert not workspace.is_relative_to(ROOT)
    empty, classes = workspace / "empty", workspace / "classes"
    empty.mkdir()
    classes.mkdir()
    for name, source in sources.items():
        (workspace / name).write_text(source, encoding="utf-8")
    environment = {name: os.environ[name] for name in ("SYSTEMROOT", "WINDIR", "PATH")
        if name in os.environ}
    environment.update({"TEMP": str(workspace), "TMP": str(workspace), "TMPDIR": str(workspace)})
    compile_started = time.perf_counter()
    compiled = subprocess.run([javac, "-encoding", "UTF-8", "-proc:none", "-implicit:none",
        "-sourcepath", str(empty), "-classpath", str(empty), "-d", str(classes),
        *[str(workspace / name) for name in sources]], cwd=workspace,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=environment)
    compile_seconds = time.perf_counter() - compile_started
    assert compiled.returncode == 0, compiled.stderr
    runtime_started = time.perf_counter()
    executed = subprocess.run([str(java), "-cp", str(classes), "SyntheticReflectionProbe"],
        cwd=workspace, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=30, env=environment)
    runtime_seconds = time.perf_counter() - runtime_started
    assert executed.returncode == 0, executed.stderr
    rows, runtime_identity = {}, ""
    columns = ("request_fingerprint", "runtime_class_identity", "declaring_class_identity",
        "measured_field_type", "canonical_value_bits", "status", "failure_code", "adapter_version",
        "target_validation_nanos", "reflection_read_nanos", "value_normalization_nanos",
        "total_diagnostic_nanos", "mutation_authority")
    for line in executed.stdout.splitlines():
        parts = line.split("|")
        if parts[0] == "JVM":
            runtime_identity = parts[1]
        elif parts[0] == "COUNTERS":
            assert parts[1:] == ["1", "0"]
        else:
            assert len(parts) == 14, parts
            row = dict(zip(columns, parts[1:]))
            for key in columns[8:12]:
                row[key] = int(row[key])
            row["mutation_authority"] = row["mutation_authority"] == "true"
            rows[parts[0]] = row
    assert runtime_identity and len(rows) == 20
    metrics_path = ROOT / ".tmp/reflect1-synthetic-probe.json"
    metrics_path.parent.mkdir(exist_ok=True)
    metrics_path.write_text(json.dumps({
        "evidence_kind": "synthetic_capability_fixture", "product_runtime_observed": False,
        "infrastructure_java_execution_count": 1, "BANK_behavioral_java_execution_count": 0,
        "fixture_javac_invocation_count": 1, "runtime_identity": runtime_identity,
        "compile_seconds": compile_seconds, "runtime_process_seconds": runtime_seconds,
        "source_hashes": {name: sha256(source.encode("utf-8")).hexdigest()
            for name, source in sources.items()}, "observations": rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"rows": rows, "runtime_identity": runtime_identity, "sources": sources,
        "workspace": workspace, "ordinary_request": ordinary, "savings_request": savings,
        "compile_seconds": compile_seconds, "runtime_process_seconds": runtime_seconds,
        "infrastructure_java_execution_count": 1, "BANK_behavioral_java_execution_count": 0}


def test_synthetic_exact_private_inherited_and_two_independently_bound_reads(synthetic_java_probe):
    rows = synthetic_java_probe["rows"]
    for prefix, value, declaring, request_key in (
            ("ordinary", 800.0, "ReflectionFixture", "ordinary_request"),
            ("savings", 200.0, "ReflectionChild", "savings_request")):
        values = []
        for index in range(5):
            row = rows[prefix + "_" + str(index)]
            assert row["status"] == "success" and row["failure_code"] == ""
            assert row["request_fingerprint"] == synthetic_java_probe[request_key].fingerprint
            assert row["runtime_class_identity"] == "ReflectionChild"
            assert row["declaring_class_identity"] == declaring
            assert row["measured_field_type"] == "double"
            assert row["canonical_value_bits"] == struct.pack(">d", value).hex()
            assert row["mutation_authority"] is False
            values.append(row["canonical_value_bits"])
        assert len(set(values)) == 1
    assert rows["negative_zero"]["canonical_value_bits"] == "8000000000000000"
    assert synthetic_java_probe["infrastructure_java_execution_count"] == 1
    assert synthetic_java_probe["BANK_behavioral_java_execution_count"] == 0


@pytest.mark.parametrize("label,code", (
    ("wrong_runtime", "reflection_runtime_class_mismatch"),
    ("unplanned_subclass", "reflection_runtime_class_mismatch"),
    ("null_runtime", "reflection_runtime_class_mismatch"),
    ("wrong_type", "reflection_target_mismatch"),
    ("static_field", "reflection_target_mismatch"),
    ("public_field", "reflection_target_mismatch"),
    ("nan", "reflection_nonfinite_value"),
    ("infinity", "reflection_nonfinite_value"),
    ("negative_infinity", "reflection_nonfinite_value"),
))
def test_synthetic_negative_runtime_type_static_and_nonfinite_reads(synthetic_java_probe, label, code):
    row = synthetic_java_probe["rows"][label]
    assert row["status"] == "failure" and row["failure_code"] == code
    assert row["canonical_value_bits"] == "" and row["mutation_authority"] is False


def test_read_latency_is_separate_from_fixture_compile_and_jvm_startup(synthetic_java_probe):
    assert synthetic_java_probe["compile_seconds"] > 0
    assert synthetic_java_probe["runtime_process_seconds"] > 0
    row = synthetic_java_probe["rows"]["ordinary_4"]
    assert row["target_validation_nanos"] > 0
    assert row["reflection_read_nanos"] > 0
    assert row["value_normalization_nanos"] > 0
    assert row["total_diagnostic_nanos"] >= sum(row[k] for k in (
        "target_validation_nanos", "reflection_read_nanos", "value_normalization_nanos"))
    assert row["total_diagnostic_nanos"] / 1e9 < synthetic_java_probe["runtime_process_seconds"]


@pytest.fixture(scope="module")
def synthetic_observation(synthetic_java_probe):
    """Issue receipt only after checked output from the real synthetic Java read."""
    probe = synthetic_java_probe
    row = probe["rows"]["ordinary_0"]
    assert row["status"] == "success" and not row["failure_code"]
    assert row["request_fingerprint"] == probe["ordinary_request"].fingerprint
    assert row["measured_field_type"] == "double" and row["mutation_authority"] is False
    observation, receipt = owner._issue_adapter_observation(probe["ordinary_request"],
        runtime_class_identity=row["runtime_class_identity"],
        declaring_class_identity=row["declaring_class_identity"],
        canonical_value=row["canonical_value_bits"], runtime_identity=probe["runtime_identity"],
        source_fingerprint=sha256(probe["sources"]["ReflectionFixture.java"].encode("utf-8")).hexdigest(),
        adapter_source_fingerprint=sha256(probe["sources"]["OrdinaryAdapter.java"].encode("utf-8")).hexdigest())
    return observation, receipt


def validate_observation(observation, receipt, compatibility, **changes):
    fixture, plan, requests = compatibility
    request = next(r for r in requests if r.observation_role == "ordinary_balance_before")
    return owner.validate_read_only_reflection_observation(observation,
        request=request, adapter_receipt=receipt, execution_plan=plan, **lineage(fixture, **changes))


def test_measured_observation_validator_preserves_synthetic_provenance(compatibility,
        synthetic_observation, synthetic_java_probe):
    observation, receipt = synthetic_observation
    with no_execution_planning_effects():
        assert validate_observation(observation.as_dict(), receipt, compatibility) == observation
    provenance = observation.diagnostic_provenance
    assert provenance.adapter_version == synthetic_java_probe["rows"]["ordinary_0"]["adapter_version"]
    assert provenance.runtime_identity == synthetic_java_probe["runtime_identity"]
    assert provenance.evidence_kind == "synthetic_capability_fixture"
    assert provenance.product_runtime_observed is False
    assert provenance.infrastructure_java_execution_count == 1
    assert provenance.BANK_behavioral_java_execution_count == 0
    assert observation.mutation_authority is False and observation.execution_authorized is False
    assert observation.canonical_value == struct.pack(">d", 800.0).hex()
    with pytest.raises(FrozenInstanceError):
        observation.canonical_value = struct.pack(">d", 1000.0).hex()
    with pytest.raises(FrozenInstanceError):
        receipt.observation = observation


def test_self_hashed_payload_and_serialized_receipt_do_not_prove_a_read(compatibility,
        synthetic_observation):
    observation, _ = synthetic_observation
    for receipt in (None, {"observation": observation.as_dict(), "issued_by": owner.ADAPTER_VERSION}):
        with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
            validate_observation(observation.as_dict(), receipt, compatibility)
        assert rejected.value.code == "reflection_observation_untrusted"


def test_rehashed_forged_value_is_rejected_against_actual_adapter_receipt(compatibility,
        synthetic_observation):
    observation, receipt = synthetic_observation
    forged = deepcopy(observation.as_dict())
    forged["canonical_value"] = struct.pack(">d", 1000.0).hex()
    forged.pop("observation_fingerprint")
    forged["observation_fingerprint"] = sha256(json.dumps(forged, sort_keys=True,
        ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_observation(forged, receipt, compatibility)
    assert rejected.value.code == "reflection_observation_untrusted"


def test_copying_receipt_with_a_different_observation_does_not_forge_origin(compatibility,
        synthetic_observation):
    observation, receipt = synthetic_observation
    forged = replace(observation, canonical_value=struct.pack(">d", 1000.0).hex())
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        fake_receipt = replace(receipt, observation=forged)
        validate_observation(forged, fake_receipt, compatibility)
    assert rejected.value.code == "reflection_observation_untrusted"


def test_receipt_issuance_remains_closed_to_candidate_runtime(synthetic_java_probe):
    probe = synthetic_java_probe
    with pytest.raises(ValueError) as rejected:
        owner._issue_adapter_observation(probe["ordinary_request"],
            runtime_class_identity="SavingAccount", declaring_class_identity="BankAccount",
            canonical_value=struct.pack(">d", 800.0).hex(), runtime_identity=probe["runtime_identity"],
            source_fingerprint=probe["ordinary_request"].target.source_sha256,
            adapter_source_fingerprint=sha256(probe["sources"]["OrdinaryAdapter.java"].encode()).hexdigest(),
            evidence_kind="candidate_runtime")
    assert rejected.value.code == "reflection_authority_escalation"


@pytest.mark.parametrize("key,value", (
    ("request_fingerprint", "b" * 64), ("runtime_class_identity", "java.lang.System"),
    ("declaring_class_identity", "ReflectionChild"), ("measured_field_type", "int"),
    ("canonical_value", "NaN"), ("canonical_value", "7ff0000000000000"),
    ("mutation_authority", True), ("reflection_write_authority", True),
    ("write_value", 7), ("operation", "invoke_private_method"),
))
def test_observation_tampering_cannot_change_binding_value_or_authority(compatibility,
        synthetic_observation, key, value):
    observation, receipt = synthetic_observation
    payload = deepcopy(observation.as_dict())
    payload[key] = value
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_observation(payload, receipt, compatibility)
    assert rejected.value.code in {"reflection_observation_untrusted", "reflection_authority_escalation",
        "reflection_observation_invalid", "reflection_nonfinite_value", "reflection_invalid"}


def test_synthetic_provenance_cannot_be_relabelled_as_bank_execution(compatibility,
        synthetic_observation):
    observation, receipt = synthetic_observation
    payload = deepcopy(observation.as_dict())
    payload["diagnostic_provenance"].update(product_runtime_observed=True,
        evidence_kind="candidate_runtime", infrastructure_java_execution_count=0,
        BANK_behavioral_java_execution_count=1)
    with no_execution_planning_effects(), pytest.raises(ValueError) as rejected:
        validate_observation(payload, receipt, compatibility)
    assert rejected.value.code == "reflection_observation_untrusted"


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_nonfinite_native_double_cannot_become_canonical_evidence(value):
    with pytest.raises(ValueError) as rejected:
        owner.canonical_double_value(value)
    assert rejected.value.code == "reflection_nonfinite_value"


@pytest.mark.parametrize("value", (800, True, "800.0", {"value": 800.0}))
def test_native_double_normalization_never_coerces_other_types(value):
    with pytest.raises(ValueError) as rejected:
        owner.canonical_double_value(value)
    assert rejected.value.code == "reflection_target_mismatch"


@pytest.mark.parametrize("value", (800.0, 200.0, -0.0, 0.0, 1.25))
def test_finite_double_bits_are_exact_and_deterministic(value):
    assert owner.canonical_double_value(value) == struct.pack(">d", value).hex()
    assert owner.canonical_double_value(value) == owner.canonical_double_value(value)
