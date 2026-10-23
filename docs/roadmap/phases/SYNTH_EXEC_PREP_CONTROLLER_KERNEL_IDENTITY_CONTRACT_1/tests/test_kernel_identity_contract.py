"""Static serialization fixtures only; never observe a kernel or issue an identity.

Test helpers evaluate proposed scalar grammars and byte preimages. Historical
Python is read or parsed as inert source. Reuse examples below are abstract
counterexamples to treating equal projections as a continuity proof, not claims
that a particular kernel lifecycle has been sampled.
"""
import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import stat

import pytest


PHASE = Path(__file__).resolve().parents[1]
ROOT = PHASE.parents[3]
ORDER = ("user", "mnt", "net", "pid", "ipc", "cgroup", "uts")
UNSIGNED_DECIMAL = r"(?:0|[1-9][0-9]*)"
NAMESPACE_DOMAIN = b"CATTUS:SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.1:namespace-tuple:v1\0"
CGROUP_DOMAIN = b"CATTUS:SYNTH.EXEC.PREP.CONTROLLER.KERNEL.IDENTITY.1:cgroup-raw:v1\0"
MAX_INTEGER = (1 << 63) - 1
HISTORY = ROOT / "docs/roadmap/phases"
SCHEMA_PATH = HISTORY / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def namespace_grammar(value, kind):
    """Lexical fact shape only; there is intentionally no inode digit bound."""
    return (kind in ORDER and type(value) is str and value.isascii()
            and re.fullmatch(re.escape(kind) + r":\[" + UNSIGNED_DECIMAL + r"\]", value) is not None)


def admitted_namespace(value, kind):
    return namespace_grammar(value, kind) and len(value.encode("ascii")) <= 256


def decimal_grammar(value):
    return (type(value) is str and value.isascii()
            and re.fullmatch(UNSIGNED_DECIMAL, value) is not None)


def namespace_digest_fixture(values):
    if (type(values) is not list or len(values) != len(ORDER)
            or any(not admitted_namespace(value, kind) for kind, value in zip(ORDER, values))):
        raise ValueError("fixed ordered seven namespace facts required")
    return sha256(NAMESPACE_DOMAIN + canonical_json(values)).hexdigest()


def cgroup_digest_fixture(raw):
    if type(raw) is not bytes or len(raw) >= (1 << 64):
        raise ValueError("exact raw bytes with representable eight-byte length required")
    return sha256(CGROUP_DOMAIN + len(raw).to_bytes(8, "big") + raw).hexdigest()


def integer_fixture(value, positive=False):
    if type(value) is not int or not (int(positive) <= value <= MAX_INTEGER):
        raise ValueError("exact in-range built-in integer required")
    return canonical_json(value)


def symbolic_leaves(value, path=""):
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            yield path, value
        else:
            for key, child in value.items():
                yield from symbolic_leaves(child, path + "/" + key)
    elif type(value) is list:
        for index, child in enumerate(value):
            yield from symbolic_leaves(child, path + "/" + str(index))


def symbolic_width(value, widths):
    """Read-only JSON byte arithmetic, without constructing any identity value."""
    if type(value) is dict:
        if "$unresolved_scalar_width" in value:
            return widths[value["$unresolved_scalar_width"]]
        return 2 + max(0, len(value) - 1) + sum(
            len(canonical_json(key)) + 1 + symbolic_width(child, widths)
            for key, child in value.items())
    if type(value) is list:
        return 2 + max(0, len(value) - 1) + sum(symbolic_width(child, widths) for child in value)
    return len(canonical_json(value))


class StringSubclass(str):
    pass


class IntegerSubclass(int):
    pass


NAMESPACE_VALUES = [kind + ":[4026531838]" for kind in ORDER]


@pytest.mark.parametrize("kind", ORDER)
@pytest.mark.parametrize("inode", ("0", "1", "4026531838", "18446744073709551615"))
def test_namespace_raw_fact_ascii_exact_spelling_and_json_width(kind, inode):
    value = kind + ":[" + inode + "]"
    assert admitted_namespace(value, kind)
    rule = read_json(PHASE / "contract.json")["namespaces"]["fields"][kind]
    assert re.fullmatch(rule["regex"], value)
    assert len(value.encode("ascii")) == len(kind) + 3 + len(inode)
    assert len(canonical_json(value)) == len(value) + 2
    assert json.loads(canonical_json(value)) == value


@pytest.mark.parametrize("value", (
    None, True, 1, b"mnt:[1]", StringSubclass("mnt:[1]"), "", "mnt:[]",
    "mnt:[01]", "mnt:[00]", "mnt:[+1]", "mnt:[-1]", "mnt:[1.0]",
    "mnt:[0x1]", "mnt:[1_0]", "mnt:[1e1]", "mnt:[ 1]", "mnt:[1 ]",
    " mnt:[1]", "mnt:[1] ", "mnt:[1]\n", "mnt:[1]\r", "mnt:[1]\x00",
    "MNT:[1]", "Mnt:[1]", "net:[1]", "mnt:(1)", "mnt:{1}", "mnt:[1",
    "mnt:1]", "mnt::[1]", "mnt:[1]]", "mnt:[\u0661]", "mnt:[\uff11]",
    "mnt\uff1a[1]", "mnt:\uff3b1\uff3d", "mnt:[1]\u200b",
))
def test_namespace_rejects_noncanonical_fixtures_without_normalization(value):
    assert not namespace_grammar(value, "mnt")
    if type(value) is str:
        rule = read_json(PHASE / "contract.json")["namespaces"]["fields"]["mnt"]
        assert re.fullmatch(rule["regex"], value) is None


def test_pid_namespace_fact_does_not_accept_pid_for_children_alias():
    assert namespace_grammar("pid:[1]", "pid")
    assert not namespace_grammar("pid_for_children:[1]", "pid")
    assert not namespace_grammar("pid_for_children:[1]", "pid_for_children")


def test_semantic_namespace_width_is_distinct_from_schema_admission():
    schema = read_json(SCHEMA_PATH)
    namespaces = read_json(PHASE / "contract.json")["namespaces"]
    assert namespaces["order"] == list(ORDER)
    assert set(namespaces["fields"]) == set(ORDER)
    assert schema["definitions"]["id"]["max_utf8_bytes"] == 256
    for kind in ORDER:
        largest_admitted_fixture = kind + ":[" + "9" * (256 - len(kind) - 3) + "]"
        too_wide_fixture = kind + ":[" + "9" * (257 - len(kind) - 3) + "]"
        assert admitted_namespace(largest_admitted_fixture, kind)
        assert namespace_grammar(too_wide_fixture, kind)
        assert not admitted_namespace(too_wide_fixture, kind)
        assert namespaces["fields"][kind]["maximum_semantic_inode_digits"] is None
        assert namespaces["fields"][kind]["maximum_admitted_inode_digits"] == 256 - len(kind) - 3
        assert namespaces["fields"][kind]["minimum_content_bytes"] == len(kind) + 4
        assert namespaces["fields"][kind]["minimum_canonical_json_bytes"] == len(kind) + 6
    # No inference here that a 252-digit inode is physically attainable in Linux.


def test_namespace_aggregate_preimage_has_fixed_order_and_distinct_role():
    expected_bytes = NAMESPACE_DOMAIN + b'["user:[4026531838]","mnt:[4026531838]","net:[4026531838]","pid:[4026531838]","ipc:[4026531838]","cgroup:[4026531838]","uts:[4026531838]"]'
    result = namespace_digest_fixture(NAMESPACE_VALUES)
    rule = read_json(PHASE / "contract.json")["namespace_identity"]
    assert rule["domain"].encode("ascii") + b"\0" == NAMESPACE_DOMAIN
    assert rule["algorithm"] == "SHA256"
    assert rule["role"] == "aggregate equality projection"
    assert result == sha256(expected_bytes).hexdigest()
    assert len(result) == 64 and re.fullmatch("[0-9a-f]{64}", result)
    assert len(canonical_json(result)) == 66
    assert result != sha256(canonical_json(NAMESPACE_VALUES)).hexdigest()
    assert result != sha256(CGROUP_DOMAIN + canonical_json(NAMESPACE_VALUES)).hexdigest()
    changed = NAMESPACE_VALUES.copy()
    changed[ORDER.index("mnt")] = "mnt:[4026531839]"
    assert namespace_digest_fixture(changed) != result


@pytest.mark.parametrize("values", (
    tuple(NAMESPACE_VALUES), [], NAMESPACE_VALUES[:-1], NAMESPACE_VALUES + ["uts:[1]"],
    list(reversed(NAMESPACE_VALUES)), {kind: value for kind, value in zip(ORDER, NAMESPACE_VALUES)},
    [True, *NAMESPACE_VALUES[1:]], [1, *NAMESPACE_VALUES[1:]],
    ["user:[01]", *NAMESPACE_VALUES[1:]],
))
def test_namespace_digest_rejects_type_order_missing_or_extra_facts(values):
    with pytest.raises(ValueError):
        namespace_digest_fixture(values)


def test_cgroup_digest_freezes_byte_length_and_raw_bytes_without_text_conversion():
    raw = b"0::/compiler\n"
    expected = CGROUP_DOMAIN + b"\0\0\0\0\0\0\0\x0d" + raw
    assert len(raw) == 13
    rule = read_json(PHASE / "contract.json")["cgroup_identity"]
    assert rule["domain"].encode("ascii") + b"\0" == CGROUP_DOMAIN
    assert rule["algorithm"] == "SHA256"
    assert rule["role"] == "membership observation equality projection"
    assert cgroup_digest_fixture(raw) == sha256(expected).hexdigest()
    assert re.fullmatch("[0-9a-f]{64}", cgroup_digest_fixture(raw))
    assert len(canonical_json(cgroup_digest_fixture(raw))) == 66
    variants = (raw, raw[:-1], raw + b"\n", b"0::/compiler\r\n",
                b"0::/compiler\r", b"0::/compiler \n", b"0::/Compiler\n",
                b"0::/compiler/\n", b"0::/compiler\xff\n")
    assert len({cgroup_digest_fixture(value) for value in variants}) == len(variants)
    assert cgroup_digest_fixture(raw) != sha256(CGROUP_DOMAIN + raw).hexdigest()
    assert cgroup_digest_fixture(raw) != sha256(CGROUP_DOMAIN + len(raw).to_bytes(8, "little") + raw).hexdigest()


def test_cgroup_record_order_and_final_newline_are_not_silently_normalized():
    first = b"5:cpu,cpuacct:/compile\n0::/compile\n"
    reordered = b"0::/compile\n5:cpu,cpuacct:/compile\n"
    assert cgroup_digest_fixture(first) != cgroup_digest_fixture(reordered)
    assert cgroup_digest_fixture(first) != cgroup_digest_fixture(first.strip())


@pytest.mark.parametrize("raw", (None, "0::/compiler\n", bytearray(b"0::/compiler\n"), 14, True))
def test_cgroup_digest_rejects_text_and_implicit_coercion(raw):
    with pytest.raises(ValueError):
        cgroup_digest_fixture(raw)


@pytest.mark.parametrize("value", ("0", "1", "99", "18446744073709551615", "9" * 257))
def test_start_tick_fact_grammar_does_not_invent_kernel_integer_width(value):
    assert decimal_grammar(value)
    assert canonical_json(value) == b'"' + value.encode("ascii") + b'"'
    if len(value) > 256:
        assert len(value) > read_json(SCHEMA_PATH)["definitions"]["id"]["max_utf8_bytes"]


@pytest.mark.parametrize("value", (
    None, 0, 1, False, b"1", StringSubclass("1"), "", "00", "01", "+1", "-0",
    "-1", "1.0", "1e1", "0x1", "1_000", " 1", "1 ", "1\n", "1\x00",
    "\u0661", "\uff11",
))
def test_start_tick_rejects_noncanonical_decimal_or_non_string_fixtures(value):
    assert not decimal_grammar(value)


@pytest.mark.parametrize("value", (0, 1, 2, 65534, 17407, MAX_INTEGER))
def test_numeric_metadata_is_exact_canonical_decimal_json(value):
    raw = integer_fixture(value)
    assert raw.decode("ascii") == str(value)
    assert not raw.startswith(b'"')
    assert json.loads(raw) == value
    assert len(raw) <= 19
    if value:
        assert integer_fixture(value, positive=True) == raw


@pytest.mark.parametrize("value", (None, True, False, 1.0, "1", IntegerSubclass(1), -1, MAX_INTEGER + 1))
def test_numeric_metadata_rejects_boolean_subclass_coercion_and_overflow(value):
    with pytest.raises(ValueError):
        integer_fixture(value)


def test_positive_pid_tid_child_pid_and_unsigned_parent_zero_are_distinct():
    assert integer_fixture(0) == b"0"
    with pytest.raises(ValueError):
        integer_fixture(0, positive=True)
    schema = read_json(SCHEMA_PATH)
    assert schema["definitions"]["uint"]["minimum"] == 0
    assert schema["definitions"]["positive_int"]["minimum"] == 1
    assert schema["definitions"]["uint"]["maximum"] == MAX_INTEGER
    assert schema["definitions"]["positive_int"]["maximum"] == MAX_INTEGER


def test_mode_fixture_preserves_file_type_and_permission_bits():
    full_mode = stat.S_IFDIR | 0o1777
    assert full_mode == 0o41777 == 17407
    assert integer_fixture(full_mode) == b"17407"
    assert stat.S_ISDIR(full_mode)
    assert stat.S_IMODE(full_mode) == 0o1777 == 1023
    assert integer_fixture(full_mode) != integer_fixture(stat.S_IMODE(full_mode))
    assert integer_fixture(stat.S_IFREG | 0o600) == b"33152"
    rule = next(row for row in read_json(PHASE / "contract.json")["numeric_metadata"] if row["field"] == "mode")
    assert "Full int(st_mode)" in rule["semantic_source"]
    assert "never stat.S_IMODE" in rule["semantic_source"]
    assert rule["minimum_json_bytes"] == 5
    assert rule["maximum_json_bytes"] == 19


def test_identical_fact_projections_do_not_prove_relation_continuity():
    # Abstract aliases show exactly what these serializations do not encode.
    old_process = ("first-lifetime", "pid:[11]", 7, "100")
    new_process = ("second-lifetime", "pid:[11]", 7, "100")
    assert old_process[1:] == new_process[1:] and old_process != new_process
    old_mount = ("first-mount-lifetime", "mnt:[12]", 21, 0, 42)
    new_mount = ("replacement-mount-lifetime", "mnt:[12]", 21, 0, 42)
    assert old_mount[1:] == new_mount[1:] and old_mount != new_mount
    old_fd = ("first-open-lifetime", 7, 3, "/work", 42, 1)
    reopened_fd = ("second-open-lifetime", 7, 3, "/work", 42, 1)
    assert old_fd[1:] == reopened_fd[1:] and old_fd != reopened_fd
    assert cgroup_digest_fixture(b"0::/compiler\n") == cgroup_digest_fixture(b"0::/compiler\n")


def test_contract_result_remains_unresolved_with_no_authority_or_effects():
    contract = read_json(PHASE / "contract.json")
    assert contract["typed_result"] == "KERNEL_IDENTITY_CONTRACT_UNRESOLVED"
    assert contract["contract_frozen"] is False
    assert all(value is False for value in contract["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in contract["operational_effects"].values())
    assert contract["schema_modified"] is False
    assert contract["historical_contracts_modified"] is False
    assert contract["requirement_evolution_required"] is False
    assert contract["candidate_A_selected"] is False
    assert contract["cap_bytes"] == 8192
    assert contract["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
    assert contract["descriptor_boundary"]["tagged_grammar_frozen"] is False
    assert contract["descriptor_boundary"]["selection"] is None
    assert contract["descriptor_boundary"]["records_per_writer_decided"] is False


def test_historical_sources_and_frozen_contract_hashes_are_unchanged():
    baseline = read_json(PHASE / "preservation_baseline.json")
    assert baseline["links_followed"] is False
    assert baseline["new_phase_excluded"] == PHASE.relative_to(ROOT).as_posix()
    sources = read_json(PHASE / "contract.json")["sources"]
    required = {"core/" + name for name in (
        "sandboxed_java_positive_probe.py", "sandbox_backend_provenance.py", "direct_read_receipt.py",
        "repository_inventory.py", "undo_backup.py", "failed_rollback_recovery.py")}
    required.update(row["path"] for row in sources.values())
    for relative in required:
        record = baseline["files"][relative]
        assert record["kind"] == "file"
        raw = (ROOT / relative).read_bytes()
        assert len(raw) == record["bytes"], relative
        assert sha256(raw).hexdigest() == record["sha256"], relative
    for record in sources.values():
        assert sha256((ROOT / record["path"]).read_bytes()).hexdigest() == record["sha256"]


def test_identity_matrix_covers_requested_fields_and_keeps_incarnation_gaps_explicit():
    contract = read_json(PHASE / "contract.json")
    rows = {field: row for row in contract["identity_matrix"] for field in row["fields"]}
    frozen = {"namespace_identity", "cgroup_identity", "process.start_identity", "task.start_identity",
              *("namespaces." + kind for kind in ORDER)}
    unresolved = {"mount_identity", "namespace_generation", "root_identity", "controller_process_identity",
                  "writer.process_identity", "writer.task_identity", "process_group_identity",
                  "writer_handle.descriptor_identity"}
    assert set(rows) == frozen | unresolved
    assert sum(len(row["fields"]) for row in contract["identity_matrix"]) == len(rows)
    for field in frozen:
        assert rows[field]["status"] == "OBSERVATION_PROJECTION_FROZEN"
        assert rows[field]["canonical_representation"] is not None
    for field in unresolved:
        assert rows[field]["status"] == "INCARNATION_ENCODING_UNRESOLVED"
        assert rows[field]["canonical_representation"] is None
        assert rows[field]["minimum_content_bytes"] is None
        assert rows[field]["maximum_semantic_content_bytes"] is None
        assert rows[field]["finite_semantic_width_guaranteed"] is False
    assert rows["controller_process_identity"] is rows["writer.process_identity"]
    assert rows["process.start_identity"] is not rows["writer.process_identity"]
    assert rows["task.start_identity"] is not rows["writer.task_identity"]


def test_numeric_metadata_keeps_existing_schema_ranges_and_fixed_zero_subordinate_count():
    rows = {row["field"]: row for row in read_json(PHASE / "contract.json")["numeric_metadata"]}
    assert set(rows) == {"mode", "uid", "gid", "link_count", "pid", "parent_pid", "tid", "child_pid", "subordinate_mount_count"}
    for field, row in rows.items():
        if field == "subordinate_mount_count":
            assert row["minimum_accepted"] == row["maximum_accepted"] == 0
            assert row["minimum_json_bytes"] == row["maximum_json_bytes"] == 1
        else:
            assert row["minimum_accepted"] == (1 if field in {"link_count", "pid", "tid", "child_pid"} else 0)
            assert row["maximum_accepted"] == MAX_INTEGER
            assert row["maximum_json_bytes"] == 19


def test_budget_partial_substitution_is_path_complete_and_preserves_frozen_layout():
    projection = read_json(PHASE / "budget_projection.json")
    history = read_json(HISTORY / "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1R/budget_witness.json")
    profile = next(row for row in history["profiles"] if row["name"] == projection["source_profile"])
    historical_responses = {row["operation"]: row for row in profile["messages"] if row["direction"] == "response"}
    assert len(historical_responses) == len(projection["responses"]) == 2
    expected_sizes = {"MATERIALIZE_EXACT_SCENARIO_SOURCE": 3567, "COMPILE_EXACT_SCENARIO": 5254}
    for response in projection["responses"]:
        original = historical_responses[response["operation"]]
        tree = original["annotated_symbolic_layout"]
        original_widths = original["width_assignment"]
        assert symbolic_width(tree, original_widths) == original["canonical_payload_bytes"]
        leaves = dict(symbolic_leaves(tree))
        selected = {row["path"]: row for row in response["selected_substitutions"]}
        assert len(selected) == len(response["selected_substitutions"])
        assert set(selected) <= set(leaves)
        widths = dict(original_widths)
        expected_paths = set()
        for path, leaf in leaves.items():
            symbol, family = leaf["$unresolved_scalar_width"], leaf["family"]
            expected = None
            if family == "future_owner":
                expected = 19
            elif symbol.startswith("namespace."):
                expected = len(symbol.split(".", 1)[1]) + 6
            elif symbol == "process_namespace_identity" or family == "kernel_cgroup":
                expected = 66
            elif family == "mode":
                expected = 5
            elif family == "kernel_start":
                expected = 3
            if expected is not None:
                expected_paths.add(path)
                row = selected[path]
                assert row["symbol"] == symbol and row["family"] == family
                assert row["historical_canonical_json_bytes"] == original_widths[symbol]
                assert row["partial_lower_canonical_json_bytes"] == expected
                assert row["delta_bytes"] == expected - original_widths[symbol]
                assert row["semantic_value_selected"] is False
                widths[symbol] = expected
        assert set(selected) == expected_paths
        assert symbolic_width(tree, widths) == expected_sizes[response["operation"]]
        assert response["partial_lower_payload_bytes"] == symbolic_width(tree, widths)
        assert response["partial_lower_payload_bytes"] == original["canonical_payload_bytes"] + sum(
            row["delta_bytes"] for row in selected.values())
        residuals = response["unresolved_residual_leaves"]
        assert len({row["path"] for row in residuals}) == len(residuals)
        assert set(row["path"] for row in residuals) <= set(leaves)
        counts = Counter(row["symbol"] for row in residuals)
        assert dict(counts) == response["unresolved_residual_width_terms"]
        for row in residuals:
            assert row["symbol"] == leaves[row["path"]]["$unresolved_scalar_width"]
            assert row["partial_lower_canonical_json_bytes"] == widths[row["symbol"]]
            assert row["width_not_an_execution_observation"] is True
        # A wider scalar costs its true path multiplicity, not one byte per name.
        widened = dict(widths)
        widened["controller_process_identity"] += 7
        assert symbolic_width(tree, widened) - symbolic_width(tree, widths) == 7 * counts["controller_process_identity"]
        assert counts["controller_process_identity"] == 2
        assert response["exact_full_projected_size_bytes"] is None
    assert profile["controller_writers"] == 1
    assert profile["potential_write_handles_per_writer"] == 2
    assert profile["class_size_decimal_width"] == 5
    assert profile["response_frame_overhead_bytes"] == 8
    assert profile["candidate_A_UNSELECTED"] is True


def test_budget_totals_remain_conditional_and_do_not_select_or_evolve_transport():
    projection = read_json(PHASE / "budget_projection.json")
    assert projection["frozen_owner_content_bytes"] == 17
    assert projection["frozen_owner_json_bytes"] == 19
    assert projection["namespace_minimum_json_widths"] == {kind: len(kind) + 6 for kind in ORDER}
    assert projection["namespace_set_minimum_json_bytes"] == sum(projection["namespace_minimum_json_widths"].values()) == 67
    assert projection["namespace_set_minimum_delta_bytes"] == 67 - 7 * 3 == 46
    materialize, compile_response = projection["responses"]
    assert projection["partial_lower_materialize_response_bytes"] == materialize["partial_lower_payload_bytes"] == 3567
    assert projection["partial_lower_compile_response_bytes"] == compile_response["partial_lower_payload_bytes"] == 5254
    semantic = sum(row["partial_lower_payload_bytes"] for row in projection["responses"])
    assert projection["partial_lower_semantic_total_bytes"] == semantic == 8821
    framed = semantic + projection["conditional_candidate_A_framing_bytes"]
    assert projection["conditional_candidate_A_framing_bytes"] == 8
    assert projection["conditional_candidate_A_partial_lower_framed_total_bytes"] == framed == 8829
    assert projection["cap_bytes"] == 8192
    assert projection["partial_lower_semantic_excess_bytes"] == semantic - 8192 == 629
    assert projection["partial_lower_semantic_margin_bytes"] == 8192 - semantic == -629
    assert projection["conditional_candidate_A_excess_bytes"] == framed - 8192 == 637
    assert projection["conditional_candidate_A_margin_bytes"] == 8192 - framed == -637
    for field in ("exact_full_projected_materialize_response_bytes", "exact_full_projected_compile_response_bytes",
                  "exact_full_projected_semantic_total_bytes", "exact_full_projected_candidate_A_framed_total_bytes"):
        assert projection[field] is None
    for field in ("candidate_A_selected", "transport_selected", "writer_topology_changed", "cap_changed",
                  "actual_class_size_selected", "attainable_execution_witness", "historical_proof_imported",
                  "historical_proof_rerun", "frozen_artifacts_modified", "universal_transport_impossibility_claimed"):
        assert projection[field] is False
    assert projection["writer_completeness"] == "WRITER_INVENTORY_COMPLETENESS_UNRESOLVED"
    assert projection["class_size_decimal_width"] == 5
    assert projection["class_size_occurrences_in_compile"] == 2
    assert projection["overall_budget_feasibility"] == projection["physical_transport_feasibility"] == "UNRESOLVED"
    assert all(value is False for value in projection["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in projection["operational_effects"].values())
    for source in projection["source_artifacts"]:
        assert sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]


def test_new_phase_python_has_no_owner_import_runtime_probe_or_process_launch():
    forbidden_imports = ("core", "subprocess", "socket", "requests", "urllib", "http", "importlib")
    forbidden_calls = {"exec", "eval", "__import__", "Popen", "run", "check_output",
                       "system", "fork", "spawn", "stat", "lstat", "readlink"}
    # Validation has explicit instrumentation and source readers; the contract
    # writer, arithmetic and this fixture file must remain inert source tools.
    for path in PHASE.rglob("*.py"):
        if path.name == "validate_pure.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.split(".")[0] in forbidden_imports for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden_imports, path
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else None)
                assert name not in forbidden_calls, (path, name)

