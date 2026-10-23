"""Pure declarative schema sizing; these invented records are not live evidence.

No controller, wire parser, process, capability or semantic validator is built.
One-character kernel identifiers make these optimistic size lower bounds.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCHEMA_PATH = "docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json"
DEFINITIONS = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))["definitions"]


def illustrative_minimum(spec):
    if type(spec) is str:
        return illustrative_minimum(DEFINITIONS[spec])
    kind = spec["type"]
    if kind == "record":
        return {key: illustrative_minimum(value) for key, value in spec["fields"].items()}
    if kind == "enum":
        return min(spec["values"], key=lambda value: len(json.dumps(value, separators=(",", ":"))))
    if kind == "fixed_list":
        return list(spec["values"])
    if kind == "nullable":
        return None
    if kind == "list":
        return []
    if kind == "str":
        return "0" * 64 if "pattern" in spec else "x" * spec.get("min_utf8_bytes", 0)
    if kind == "int":
        return max(spec.get("minimum", 0), 0)
    if kind == "bool":
        return True
    raise ValueError(kind)


def illustrative_state(stage, include_writers):
    value = illustrative_minimum("workspace_state")
    value.update(container_identity="c" * 64, workspace_generation="0" * 64,
        controller_generation="1" * 64, stage=stage, observation_challenge="0" * 64)
    for path, options in (("/tmp", "rw,nosuid,nodev,noexec,size=16m,mode=1777"),
            ("/work", "rw,nosuid,nodev,size=32m,mode=1777")):
        mount = illustrative_minimum("mount")
        mount.update(path=path, options=options)
        mount["root_metadata"].update(mode=17407, link_count=2)
        value["mounts"].append(mount)
    process = illustrative_minimum("process")
    process.update(role="controller", uid=65534, gid=65534,
        tasks=[illustrative_minimum("task")])
    exclusivity = value["process_exclusivity_observation"]
    exclusivity.update(processes=[process], controller_generation="1" * 64)
    if include_writers:
        writer = illustrative_minimum("writer")
        writer["accounted_original_relation_id"] = "x"
        for path in ("/tmp", "/work"):
            handle = illustrative_minimum("writer_handle")
            handle.update(path=path, access_kind="potential_write_access")
            writer["handles"].append(handle)
        exclusivity["writers"] = [writer]
    paths = ["/work/SyntheticStateBox.java", "/work/classes"]
    if stage == "prepared":
        paths.append("/work/classes/SyntheticStateBox.class")
    for path in paths:
        directory = path == "/work/classes"
        entry = illustrative_minimum("manifest_entry")
        entry.update(path=path, kind="directory" if directory else "file",
            mode=16384 if directory else 32768, uid=65534, gid=65534,
            link_count=2 if directory else 1)
        if not directory:
            entry.update(size_bytes=239 if path.endswith(".java") else 1, sha256="0" * 64)
        value["work_manifest"].append(entry)
    return value


def illustrative_response(operation, result_type, stage, include_writers):
    value = illustrative_minimum("response")
    value.update(operation=operation, purpose=operation, status="COMPLETE",
        container_identity="c" * 64, workspace_generation="0" * 64,
        controller_generation="1" * 64)
    if operation.startswith("OBSERVE"):
        value["challenge"] = "0" * 64
    value["result"] = illustrative_minimum(result_type)
    value["result"]["workspace_state"] = illustrative_state(stage, include_writers)
    if result_type == "result_compile":
        capture = value["result"]["capture_and_reap"]
        capture["timed_out"] = False
        for name in ("stdout", "stderr"):
            capture[name]["overflow"] = False
    return value


operations = (("MATERIALIZE_EXACT_SCENARIO_SOURCE", "result_materialize", "materialized"),
    ("COMPILE_EXACT_SCENARIO", "result_compile", "prepared"),
    ("OBSERVE_PREPARED_ARTIFACTS", "result_observation", "prepared"))
cases = []
for include_writers in (False, True):
    records = [illustrative_response(*operation, include_writers) for operation in operations]
    lengths = [len(json.dumps(record, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("utf-8")) + 4 for record in records]
    cases.append({"one_controller_writer_two_root_handles": include_writers,
        "operations": [operation[0] for operation in operations],
        "payload_plus_four_header_bytes": lengths,
        "materialize_compile_total": sum(lengths[:2]),
        "materialize_compile_fresh_observation_total": sum(lengths),
        "illustrative_records": records})

report = {
    "kind": "pure_declarative_schema_sizing_lower_bound",
    "source_schema": SCHEMA_PATH,
    "live_observations": False,
    "controller_or_protocol_implementation": False,
    "limitations": [
        "All kernel, descriptor and relationship identifiers optimistically use one character.",
        "File mode integers include only mandatory type bits, not actual observed permission bits.",
        "Class length is one byte; hashes/challenges are invented sizing strings, never evidence.",
        "No claim these illustrative records satisfy every authenticated runtime cross-field predicate.",
        "Writer-free case is strictly a smaller structural lower bound; writer case includes only one controller and two potential-write root handles.",
        "No initial empty observation, error, cleanup or additional current observation is counted.",
        "Short labels do not prove a truthful complete kernel inventory can fit the remaining bytes."
    ],
    "frozen_attempt_outer_stdout_limit": 8192,
    "preliminary_structural_count": {
        "payload_plus_four_header_bytes": [3256, 4803, 3405],
        "materialize_compile_total": 8059,
        "materialize_compile_fresh_observation_total": 11464,
        "description": "Earlier direct schema-default count with one writer/two handles and UID65534, but zero mode fields, default boolean values and null writer-accounting reference. This is byte arithmetic only, not a semantically valid successful witness. The main cases below correct mandatory mode type bits, success booleans and the writer reference."
    },
    "attempt_boundary_source": [
        "PREP closure contract.json:521 describes one fixed materialize-then-compile attempt.",
        "PREP closure contract.json:219-220 also describes receipt revalidation during one live attempt.",
        "Controller schema cross_field_rules requires a fresh OBSERVE before readiness/handoff and preserves whole-attempt8192 capture.",
        "Excluding postcompile readiness observation from this cap requires an explicit, faithful distinction between preparation-operation interval and retained lifecycle; these sizes do not authorize redefining the frozen attempt."
    ],
    "cases": cases
}
(HERE / "sizing_witness.json").write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
print(json.dumps([{key: value for key, value in case.items() if key != "illustrative_records"}
    for case in cases], sort_keys=True))
