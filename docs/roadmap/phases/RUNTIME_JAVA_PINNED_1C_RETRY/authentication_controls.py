"""Additive retry observation and reversible authentication controls.

The observer recognizes only the frozen private-prefix generator and bounded
process code objects. It retains their exact original strings, authenticates
absence before a control can run, and restores instrumentation on every exit.
Neither reports nor reconstructed paths can supply observation provenance.
"""
from copy import copy, deepcopy
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading

from core import runtime_java_pinned_provider as owner
from core import runtime_java_pinned_target_inspection as target


def _absent(path):
    candidate = Path(path)
    return not candidate.exists() and not candidate.is_symlink()


def _instrumentation_present():
    checks = {"sys_profile": sys.getprofile(), "sys_trace": sys.gettrace(),
        "thread_profile": threading.getprofile(), "thread_trace": threading.gettrace()}
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is not None:
        for tool_id in range(6):
            checks["monitoring_" + str(tool_id)] = monitoring.get_tool(tool_id)
    return [name for name, value in checks.items() if value is not None]


class PrivateConfigObserver:
    """Read-only observation around exactly one independently gated owner call."""
    def __init__(self):
        self.records = []
        self._origins = {}
        self._canonical = None
        self._installed = False
        self.instrumentation_restored = False

    def __enter__(self):
        present = _instrumentation_present()
        if present:
            raise owner.PinnedProviderBlocked(owner.UNRESOLVED,
                "retry_instrumentation_already_owned:" + ",".join(present))
        self._prefix_code = owner.sandbox._docker_prefix.__code__
        self._control_code = owner.sandbox._bounded_process.__code__
        self._previous_trace = sys.gettrace()
        self._temp_root = Path(tempfile.gettempdir()).resolve()
        self._installed = True
        sys.settrace(self._entry_trace)
        return self

    def _entry_trace(self, frame, event, result):
        if event == "call" and frame.f_code in (self._prefix_code, self._control_code):
            if frame.f_code is self._control_code:
                self._before_control(frame)
            return self._exact_frame_trace
        return None

    def _exact_frame_trace(self, frame, event, result):
        if event == "return" and frame.f_code is self._prefix_code and result:
            self._generated_prefix(frame, result)
        return self._exact_frame_trace

    def _scope(self, frame):
        codes = []
        while frame is not None:
            codes.append(frame.f_code)
            frame = frame.f_back
        sandbox_codes = (owner.sandbox2.invoke.__code__, owner.sandbox2.replay.__code__)
        if owner.runtime._invoke.__code__ in codes:
            return "JAVA1C_fixed_controller"
        if owner.runtime.verify.__code__ in codes:
            return ("JAVA1C_SANDBOX2_infrastructure" if any(code in codes for code in sandbox_codes)
                else "JAVA1C_controls")
        if owner.backend._run.__code__ in codes:
            return ("BIND_SANDBOX2_infrastructure" if any(code in codes for code in sandbox_codes)
                else "BIND_controls")
        if target.inspect_target.__code__ in codes:
            return "PINNED1A_stopped_inspection"
        if owner._measure_backend.__code__ in codes or owner._fixed_route.__code__ in codes:
            return "runtime_backend_bracket"
        return "pure_observer_control"

    def _generated_prefix(self, frame, prefix):
        endpoint = owner.sandbox._local_endpoint()
        if (type(prefix) is not tuple or len(prefix) != 5 or prefix[1] != "--config"
                or prefix[3:] != ("--host", endpoint) or type(prefix[2]) is not str):
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_exact_generated_private_prefix_required")
        path = prefix[2]
        candidate = Path(path)
        if (candidate.parent.resolve() != self._temp_root
                or re.fullmatch(r"runtime-sandbox1-no-config-[0-9a-f]{32}", candidate.name) is None
                or any(path == original[2] for original in self._origins.values())):
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_phase_generated_config_namespace_required")
        if not _absent(path):
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_private_config_not_absent_at_generation")
        record = {"owner_scope": self._scope(frame), "path": path,
            "generated_by_exact_owner_code": True, "caller_supplied": False,
            "issuing_pid": os.getpid(), "absent_at_generation": True,
            "absence_before_every_control": True, "control_calls": 0,
            "absent_after_use": None}
        self.records.append(record)
        self._origins[id(path)] = prefix

    def _before_control(self, frame):
        argv = frame.f_locals.get("argv")
        if type(argv) is not tuple or len(argv) < 5:
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_exact_private_control_argv_required")
        prefix = self._origins.get(id(argv[2]))
        if prefix is None or argv[:5] != prefix or argv[2] is not prefix[2]:
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_private_config_original_generator_provenance_required")
        if not _absent(argv[2]):
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_private_config_not_absent_before_control")
        record = next(row for row in self.records if row["path"] is argv[2])
        record["control_calls"] += 1

    def __exit__(self, exc_type, exc, traceback):
        if self._installed:
            sys.settrace(self._previous_trace)
            self._installed = False
        self.instrumentation_restored = not _instrumentation_present()
        for record in self.records:
            record["absent_after_use"] = _absent(record["path"])
        self._canonical = owner._canonical(self.records)
        if not self.instrumentation_restored:
            raise owner.PinnedProviderBlocked(owner.CLEANUP_FAILURE,
                "retry_observer_instrumentation_cleanup_unproven")
        if any(record["absent_after_use"] is not True for record in self.records):
            raise owner.PinnedProviderBlocked(owner.CLEANUP_FAILURE,
                "retry_private_config_absence_after_use_unproven")
        return False

    def authenticate(self, records=None):
        """Authenticate retained original observation rows, never report imports."""
        supplied = self.records if records is None else records
        if (supplied is not self.records or self._canonical is None
                or owner._canonical(supplied) != self._canonical
                or not self.instrumentation_restored):
            raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                "retry_original_private_config_observation_required")
        for row in supplied:
            prefix = self._origins.get(id(row["path"]))
            if (prefix is None or row["path"] is not prefix[2]
                    or row["issuing_pid"] != os.getpid()
                    or row["generated_by_exact_owner_code"] is not True
                    or row["caller_supplied"] is not False
                    or any(row[key] is not True for key in ("absent_at_generation",
                        "absence_before_every_control", "absent_after_use"))
                    or not _absent(row["path"])):
                raise owner.PinnedProviderBlocked(owner.BACKEND_MISMATCH,
                    "retry_private_config_isolation_authentication_failed")
        return True

    def as_dict(self):
        authenticated, blocker = False, None
        try:
            authenticated = self.authenticate()
        except (ValueError, OSError, KeyError, TypeError) as error:
            blocker = {"status": getattr(error, "status", owner.UNRESOLVED),
                "reason": getattr(error, "reason", str(error))}
        return {"method": "read_only_exact_owner_code_trace_original_prefix_retention",
            "report_only": True, "observation_authenticated": authenticated,
            "cleanup_verified": authenticated, "authentication_blocker": blocker,
            "instrumentation_restored": self.instrumentation_restored,
            "generated_config_paths": deepcopy(self.records),
            "control_calls_authenticated": sum(row["control_calls"] for row in self.records),
            "config_paths_compared_as_backend_identity": False}

    @property
    def cleanup_verified(self):
        try:
            return self.authenticate()
        except ValueError:
            return False


def config_observation():
    return PrivateConfigObserver()


def authenticate_all_originals(outcome):
    values = owner._outcome_objects(outcome)
    owner.validate_pinned_java_exact_provider(outcome.receipt, *values)
    owner.validate_runtime_attachment(values[9], *values[:9])
    owner.pinned.validate_pinned_backend_target_binding(*values[:5])
    owner.backend.validate_sandbox_backend_binding(*values[1:4])
    target.validate_target_inspection_receipt(values[4])
    owner.runtime.validate_descriptor(*values[5:7])
    owner.runtime.authenticate_sandbox2(*values[7:9])
    return {"final_provider_root": True, "runtime_attachment": True,
        "PINNED1B": True, "BIND_attachment_and_pair": True,
        "PINNED1A_target": True, "JAVA1C_pair": True, "actual_runtime_SANDBOX2_pair": True}


def reauthenticate_originals(outcome):
    return authenticate_all_originals(outcome)


def retry_negative_authentication_matrix(outcome, config_observer=None):
    """Use retained fresh originals only; never issue another live graph.

Fresh-identity candidates below are distinct copies of this fresh graph with a
new candidate identity. They are deliberately unauthenticated substitutions,
not a claim that another authentic graph was operationally issued.
"""
    values = owner._outcome_objects(outcome)
    results = owner.negative_authentication_matrix(outcome)

    def reject(objects=values):
        try:
            owner.validate_pinned_java_exact_provider(outcome.receipt, *objects)
        except (ValueError, TypeError, AttributeError, KeyError):
            return True
        return False

    for index, label in ((0, "PINNED1B"), (1, "BIND_attachment"),
            (4, "target_inspection"), (5, "JAVA1C_descriptor"),
            (6, "JAVA1C_receipt"), (7, "actual_runtime_SANDBOX2_descriptor"),
            (8, "actual_runtime_SANDBOX2_receipt")):
        candidate = copy(values[index])
        key = "attachment_id" if index == 1 else "receipt_id" if hasattr(candidate, "receipt_id") else None
        if key is not None:
            object.__setattr__(candidate, key, secrets.token_hex(32))
        swapped = list(values)
        swapped[index] = candidate
        results["different_fresh_identity_candidate_" + label] = reject(tuple(swapped))

    # The two actual sandbox pairs already have separate authenticated origins.
    swapped = list(values)
    swapped[7:9] = values[2:4]
    results["different_authenticated_actual_runtime_SANDBOX2_pair"] = reject(tuple(swapped))

    for index, key, changed, label in (
            (0, "canonical_backend_route_identity", "local-docker:caller-alias", "changed_route"),
            (0, "canonical_backend_server_version", "different", "changed_Server.Version"),
            (6, "image_identity", "sha256:" + "0" * 64, "changed_image"),
            (6, "java_sha256", "0" * 64, "changed_java_identity"),
            (6, "javac_sha256", "0" * 64, "changed_javac_identity"),
            (4, "controller_source_identity", (), "changed_controller_source_identity"),
            (4, "cleanup_evidence", (), "changed_cleanup_evidence")):
        original = getattr(values[index], key)
        try:
            object.__setattr__(values[index], key, changed)
            results[label] = reject()
        finally:
            object.__setattr__(values[index], key, original)
    controller = values[4].archive.controller
    original = controller.sha256
    try:
        object.__setattr__(controller, "sha256", "0" * 64)
        results["changed_controller_identity"] = reject()
    finally:
        object.__setattr__(controller, "sha256", original)

    record = owner._ATTACHMENTS[outcome.attachment.receipt_id]
    retained = record["measurement"]

    def change_measurement(label, mutate):
        candidate = deepcopy(retained)
        mutate(candidate)
        try:
            record["measurement"] = candidate
            results[label] = reject()
        finally:
            record["measurement"] = retained

    change_measurement("chronology_only_fake", lambda m: m.update(controls=[]))
    change_measurement("changed_runtime_traversal_fact", lambda m:
        m["facts"]["controller_before"].update(uid=0))
    change_measurement("changed_runtime_cleanup_evidence", lambda m:
        m["runtime_report"].update(temporary_workspace_removed=False))
    change_measurement("failed_config_path_absence_isolation", lambda m:
        m["config_paths"][0].update(absent=False))
    change_measurement("caller_config_path_alias", lambda m:
        m["runtime_prefix"].__setitem__(2, "caller-supplied-config"))

    def equal_paths_changed_route(measurement):
        path = measurement["prefix"][2]
        measurement["runtime_prefix"][2] = measurement["invoke_prefix"][2] = path
        for row in measurement["controls"]:
            row["argv"][2] = path
        measurement["config_paths"] = [{"path": path, "absent": True}]
        measurement["pre"][0] = measurement["post"][0] = "local-docker:caller-alias"
    change_measurement("config_path_equality_cannot_masquerade_as_backend_identity", equal_paths_changed_route)

    swapped = list(values)
    swapped[4] = json.loads(json.dumps(values[4].as_dict()))
    results["matching_hashes_without_original_owner_authentication"] = reject(tuple(swapped))
    if config_observer is not None:
        for label, candidate in (("reconstructed_config_path_observation",
                json.loads(json.dumps(config_observer.records))),
                ("caller_alias_private_config_observation", copy(config_observer.records))):
            try:
                config_observer.authenticate(candidate)
            except ValueError:
                results[label] = True
            else:
                results[label] = False
        config_observer.authenticate()
    else:
        # Owner-authenticated config evidence cannot be imported as an attachment.
        swapped = list(values)
        swapped[9] = json.loads(json.dumps(values[9].as_dict()))
        results["reconstructed_config_path_attachment"] = reject(tuple(swapped))
    authentication = authenticate_all_originals(outcome)
    return {"controls": results, "all_controls_rejected": bool(results) and all(results.values()),
        "originals_reauthenticated_after_controls": authentication,
        "additional_live_owner_issuances": 0,
        "different_fresh_candidate_semantics":
            "distinct unauthenticated candidates derived from this fresh graph; no second live graph claim",
        "two_authentic_graph_substitution_coverage": "pure original-owner fixtures only"}


def negative_authentication_matrix(outcome, config_observer=None):
    return retry_negative_authentication_matrix(outcome, config_observer)["controls"]
