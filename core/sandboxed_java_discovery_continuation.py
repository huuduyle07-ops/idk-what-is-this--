"""Additive JAVA.1D retry: original discovery plus live BIND.1 and JAVA.1C.

Only verify() performs infrastructure effects, with no caller inputs. Receipt
validation is pure, process-local, and grants no execution or compatibility
authority. The first JAVA.1D blocked attempt remains a separate frozen artifact.
"""
from dataclasses import asdict, dataclass, field, replace
import hmac
import os
import secrets
import subprocess
from unittest.mock import patch

from core import candidate_runtime_sandbox as sandbox
from core import sandbox_backend_binding as binding
from core import sandboxed_java_positive_continuation as java1c
from core import sandboxed_java_toolchain_discovery as discovery

PHASE_ID = 'RUNTIME.JAVA.1D'
SCHEMA_VERSION = 'runtime_java_1d_v1'
COMPLETE = 'RUNTIME_JAVA_1D_COMPLETE_WITH_WARNINGS'
DISCOVERY_INCOMPLETE = 'RUNTIME_JAVA_1D_BLOCKED_DISCOVERY_INCOMPLETE'
BACKEND_BINDING = 'RUNTIME_JAVA_1D_BLOCKED_BACKEND_BINDING'
ARTIFACT_MISSING = 'RUNTIME_JAVA_1D_BLOCKED_ARTIFACT_MISSING'
JAVA_AUTHENTICATION = 'RUNTIME_JAVA_1D_BLOCKED_JAVA1C_AUTHENTICATION'
PROVIDER_COHERENCE = 'RUNTIME_JAVA_1D_BLOCKED_PROVIDER_COHERENCE'
CLEANUP = 'RUNTIME_JAVA_1D_BLOCKED_CLEANUP'
UNRESOLVED = 'RUNTIME_JAVA_1D_BLOCKED_UNRESOLVED'
IMAGE = 'sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a'
POLICY_SHA256 = '5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75'
JAVA_PATH = '/opt/temurin-26.0.2.1/bin/java'
JAVA_SHA256 = 'a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2'
JAVAC_PATH = '/opt/temurin-26.0.2.1/bin/javac'
JAVAC_SHA256 = 'e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023'
AUTHORITIES = binding.AUTHORITIES
_SECRET = secrets.token_bytes(32)
_LIVE = {}


class ContinuationBlocked(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


def _payload(value):
    result = asdict(value)
    result.pop('_signature')
    return result


def _sign(value):
    return hmac.new(_SECRET, sandbox._json(_payload(value)).encode(), 'sha256').hexdigest()


def _canonical_inventory(inventory):
    """Sort full owner records only; retain every record and inner distinction."""
    artifacts = tuple(sorted(inventory.artifacts,
        key=lambda a: (a.image_identity, sandbox._json(asdict(a)))))
    return artifacts, sandbox._hash([asdict(a) for a in artifacts])


def _discovery_gates(attachment, inventory):
    if type(inventory) is not discovery.LocalJavaDiscovery:
        raise ContinuationBlocked(DISCOVERY_INCOMPLETE, 'original_discovery_owner_record_required')
    if inventory.cleanup_verified is not True:
        raise ContinuationBlocked(CLEANUP, 'original_discovery_cleanup_not_verified')
    if inventory.complete_inventory is not True:
        raise ContinuationBlocked(DISCOVERY_INCOMPLETE, inventory.reason)
    if not binding.sandbox_backend_binding_satisfies_java1_discovery(
            attachment, inventory.backend_identity, inventory.backend_version):
        raise ContinuationBlocked(BACKEND_BINDING, 'original_discovery_route_or_server_version_mismatch')
    matches = tuple(a for a in inventory.artifacts if a.image_identity == IMAGE)
    if not matches:
        raise ContinuationBlocked(ARTIFACT_MISSING, 'exact_pinned_image_absent_from_complete_inventory')
    if len(matches) != 1:
        raise ContinuationBlocked(PROVIDER_COHERENCE, 'ambiguous_exact_image_records_preserved')
    artifact = matches[0]
    if artifact.os != 'linux' or artifact.architecture != 'amd64' or artifact.image_declared_volumes:
        raise ContinuationBlocked(PROVIDER_COHERENCE, 'exact_image_discovery_classification_ineligible')
    pairs = tuple(p for a, p in inventory.available_toolchains if a is artifact
        and (p.java_path, p.java_sha256, p.javac_path, p.javac_sha256)
        == (JAVA_PATH, JAVA_SHA256, JAVAC_PATH, JAVAC_SHA256)
        and p.controller_path == '/usr/local/bin/python'
        and len(p.controller_sha256) == 64
        and all(c in '0123456789abcdef' for c in p.controller_sha256))
    if len(pairs) != 1:
        raise ContinuationBlocked(PROVIDER_COHERENCE, 'exact_discovered_java_toolchain_missing_or_ambiguous')
    return artifact, pairs[0]


def _authenticate_java(descriptor, receipt):
    try:
        java1c.validate_descriptor(descriptor, receipt)
    except (ValueError, TypeError, AttributeError) as error:
        raise ContinuationBlocked(JAVA_AUTHENTICATION, 'fresh_java1c_owner_authentication_failed') from error
    if (any(v.phase_id != 'RUNTIME.JAVA.1C' or v.schema_version != 'runtime_java_1c_v1'
            or v.status != java1c.COMPLETE for v in (descriptor, receipt))
            or descriptor.available is not True or descriptor.verified is not True
            or receipt.cleanup_verified is not True
            or receipt.seccomp_policy_sha256 != POLICY_SHA256
            or any(getattr(v, k) is not False for v in (descriptor, receipt)
                for k in java1c.sandbox2.AUTHORITIES)):
        raise ContinuationBlocked(JAVA_AUTHENTICATION, 'fresh_java1c_exact_contract_required')
    if ((receipt.image_identity, receipt.java_path, receipt.java_sha256,
            receipt.javac_path, receipt.javac_sha256)
            != (IMAGE, JAVA_PATH, JAVA_SHA256, JAVAC_PATH, JAVAC_SHA256)):
        raise ContinuationBlocked(PROVIDER_COHERENCE, 'fresh_java1c_image_or_toolchain_disagrees_with_inventory')


@dataclass(frozen=True, slots=True)
class JavaDiscoveryCompleteContinuationReceipt:
    binding_attachment_id: str
    binding_attachment_fingerprint: str
    sandbox_descriptor_fingerprint: str
    sandbox_receipt_fingerprint: str
    sandbox_receipt_evidence_sha256: str
    canonical_backend_identity: str
    canonical_backend_version: str
    discovery_backend_identity: str
    discovery_backend_version: str
    artifact_inventory: tuple[discovery.LocalJavaArtifact, ...]
    discovery_sources: tuple[str, ...]
    discovery_reason: str
    inventory_count: int
    inventory_sha256: str
    java1c_descriptor_fingerprint: str
    java1c_receipt_fingerprint: str
    java1c_evidence_sha256: str
    java1c_sandbox_descriptor_fingerprint: str
    java1c_sandbox_receipt_fingerprint: str
    cleanup_evidence_json: str
    effect_accounting: tuple[tuple[str, str], ...]
    issuing_pid: int
    receipt_id: str
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    sandbox_policy_sha256: str = field(default=POLICY_SHA256, init=False)
    binding_semantics: str = field(default='original_java1_route_and_server_version_v1', init=False)
    backend_binding_result: bool = field(default=True, init=False)
    complete_inventory: bool = field(default=True, init=False)
    exact_pinned_image_membership: bool = field(default=True, init=False)
    selected_image_identity: str = field(default=IMAGE, init=False)
    java_path: str = field(default=JAVA_PATH, init=False)
    java_sha256: str = field(default=JAVA_SHA256, init=False)
    javac_path: str = field(default=JAVAC_PATH, init=False)
    javac_sha256: str = field(default=JAVAC_SHA256, init=False)
    inventory_to_java1c_image_coherence: bool = field(default=True, init=False)
    toolchain_coherence: bool = field(default=True, init=False)
    cleanup_verified: bool = field(default=True, init=False)
    daemon_continuity_proven: bool = field(default=False, init=False)
    aba_resistance_proven: bool = field(default=False, init=False)
    runtime_java_1_v1_identity_asserted: bool = field(default=False, init=False)
    compatibility_asserted: bool = field(default=False, init=False)
    synth_auth_requirement_satisfied: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)
    daemon_continuity_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        return sandbox._hash(_payload(self))

    def as_dict(self):
        return {**_payload(self), 'verification_receipt_fingerprint': self.fingerprint}


def validate_provider_continuation_receipt(receipt):
    """Pure authentication of this live receipt and retained original owners."""
    if type(receipt) is not JavaDiscoveryCompleteContinuationReceipt:
        raise ValueError('java1d_live_receipt_required')
    record = _LIVE.get(receipt.receipt_id)
    if (record is None or record[0] is not receipt or receipt.issuing_pid != os.getpid()
            or type(receipt._signature) is not str
            or not hmac.compare_digest(receipt._signature, _sign(receipt))
            or sandbox._json(_payload(receipt)) != record[1]):
        raise ValueError('java1d_receipt_unauthenticated')
    _, _, attachment, sd, sr, jd, jr = record
    binding.validate_sandbox_backend_binding(attachment, sd, sr)
    _authenticate_java(jd, jr)
    return receipt


def _metrics(calls):
    def count(command, operation=None):
        return sum(r['command'] == command and (operation is None or r['operation'] == operation) for r in calls)
    return {'docker_calls': len(calls), 'version_calls': count('version'),
        'inventory_calls': count('image', 'ls'), 'image_inspections': count('image', 'inspect'),
        'container_inspections': count('inspect'), 'container_create_attempts': count('create'),
        'containers_created': sum(r['command'] == 'create' and r.get('exit_code') == 0 for r in calls),
        'container_starts': count('start'), 'image_exports': count('export'),
        'image_pulls': count('pull') + count('image', 'pull'),
        'image_builds': count('build') + count('image', 'build')}


def verify():
    """Issue exactly one BIND.1, use original discovery once, then JAVA.1C once."""
    report = {'phase_id': PHASE_ID, 'schema_version': SCHEMA_VERSION, 'attempt': 'additive_retry',
        'status': UNRESOLVED, 'reason': 'not_verified', 'exported_json_is_report_only': True,
        'binding_attachment_authenticated': False, 'fresh_java1c_authenticated': False,
        'complete_inventory': None, 'inventory_count': None, 'inventory_sha256': None,
        'exact_pinned_image_membership': None, 'backend_binding_result': None,
        'inventory_to_java1c_image_coherence': False, 'toolchain_coherence': False,
        'positive_receipt_issued': False, 'java1d_receipt_fingerprint': None,
        'runtime_java_1_v1_identity_asserted': False, 'compatibility_asserted': False,
        'daemon_continuity_proven': False, 'aba_resistance_proven': False,
        **dict.fromkeys(AUTHORITIES, False),
        'binding_issuance_attempts': 0, 'discovery_invocations': 0, 'java1c_invocations': 0}
    calls, processes, stack = [], [], []
    scope, version_index = ['binding'], [0]
    invoke, launch = sandbox._bounded_process, subprocess.Popen

    def command(argv):
        return (argv[5] if len(argv) > 5 else '', argv[6] if len(argv) > 6 and argv[5] == 'image' else None)

    def observed(argv, **kwargs):
        cmd, operation = command(argv)
        label = scope[0]
        if label == 'binding':
            if cmd == 'version':
                version_index[0] += 1
                label = 'bind1_pre' if version_index[0] == 1 else 'bind1_post'
            else:
                label = 'bind1_sandbox2'
        row = {'scope': label, 'command': cmd, 'operation': operation, 'exit_code': None}
        calls.append(row)
        stack.append(label)
        try:
            captured = invoke(argv, **kwargs)
            row.update(status=captured.status, exit_code=captured.exit_code)
            return captured
        finally:
            stack.pop()

    def observed_process(argv, *args, **kwargs):
        child = launch(argv, *args, **kwargs)
        cmd, operation = command(argv)
        label = stack[-1] if stack else scope[0]
        processes.append((child, label))
        if not stack:  # Original discovery export bypasses _bounded_process.
            calls.append({'scope': label, 'command': cmd, 'operation': operation,
                'export_process': child, 'exit_code': None})
        return child

    attachment = sd = sr = jd = jr = inventory = None
    java_report = {}
    pending_status = BACKEND_BINDING
    with patch.object(sandbox, '_bounded_process', observed), patch.object(subprocess, 'Popen', observed_process):
        try:
            report['binding_issuance_attempts'] = 1
            attachment, sd, sr = binding.issue_sandbox_backend_binding()
            binding.validate_sandbox_backend_binding(attachment, sd, sr)
            report.update(binding_attachment_authenticated=True, binding_attachment=attachment.as_dict(),
                bound_sandbox_descriptor=sd.as_dict(), bound_sandbox_receipt=sr.as_dict())
            scope[0], pending_status = 'discovery', DISCOVERY_INCOMPLETE
            report['discovery_invocations'] = 1
            inventory = discovery.discover_local_java_artifacts()
            artifacts, digest = _canonical_inventory(inventory)
            report.update(discovery=asdict(inventory), complete_inventory=inventory.complete_inventory,
                artifact_inventory=[asdict(a) for a in artifacts], inventory_count=len(artifacts),
                inventory_sha256=digest, discovery_backend_identity=inventory.backend_identity,
                discovery_backend_version=inventory.backend_version)
            artifact, pair = _discovery_gates(attachment, inventory)
            report.update(backend_binding_result=True, exact_pinned_image_membership=True,
                selected_image_identity=artifact.image_identity, selected_toolchain=asdict(pair))
            scope[0], pending_status = 'java1c', JAVA_AUTHENTICATION
            report['java1c_invocations'] = 1
            jd, jr, java_report = java1c.verify()
            report['fresh_java1c'] = java_report
            if java_report.get('cleanup_verified') is not True:
                raise ContinuationBlocked(CLEANUP, 'fresh_java1c_cleanup_not_verified')
            _authenticate_java(jd, jr)
            report.update(fresh_java1c_authenticated=True, java1c_descriptor=jd.as_dict(),
                java1c_receipt=jr.as_dict(), inventory_to_java1c_image_coherence=True, toolchain_coherence=True)
            # Repeat only pure owner validation, with discovery's original values.
            binding.validate_sandbox_backend_binding(attachment, sd, sr)
            _discovery_gates(attachment, inventory)
            report.update(status=COMPLETE, reason='original_discovery_binding_and_fresh_java1c_cohere')
        except ContinuationBlocked as error:
            report.update(status=error.status, reason=str(error))
            if error.status == BACKEND_BINDING:
                report['backend_binding_result'] = False
            if error.status == ARTIFACT_MISSING:
                report['exact_pinned_image_membership'] = False
        except binding.BindingBlocked as error:
            report.update(status=CLEANUP if error.status == binding.CLEANUP else BACKEND_BINDING,
                reason=str(error), binding_status=error.status)
        except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.SubprocessError) as error:
            report.update(status=pending_status, reason=type(error).__name__ + ': ' + str(error)[:250])
        finally:
            scope[0] = 'cleanup'
            try:
                prefix = sandbox._docker_prefix()
                capture = sandbox._bounded_process((*prefix, 'ps', '-a', '--format', '{{.Names}}',
                    '--filter', 'name=runtime-sandbox2-', '--filter', 'name=runtime-java1c-',
                    '--filter', 'name=runtime-java1-discovery-'), timeout_ms=8000, stdout_limit=65536) if prefix else None
                remaining = len(capture.stdout.splitlines()) if (capture is not None
                    and capture.status == 'sandbox_completed' and capture.exit_code == 0) else None
            except (OSError, ValueError, subprocess.SubprocessError):
                remaining = None
    for row in calls:
        child = row.pop('export_process', None)
        if child is not None:
            row.update(exit_code=child.poll(), status='export_completed' if child.poll() == 0 else 'export_failed')
    controls_clean = all(p.poll() is not None and all(stream is None or stream.closed
        for stream in (p.stdin, p.stdout, p.stderr)) for p, _ in processes)
    bind_clean = attachment.sandbox_cleanup_verified if report['binding_attachment_authenticated'] else None
    discovery_clean = getattr(inventory, 'cleanup_verified', None)
    cleanup = {'remaining_phase_containers': remaining, 'controls_reaped_and_pipes_closed': controls_clean,
        'bind1_cleanup_verified': bind_clean,
        'discovery_cleanup_verified': discovery_clean,
        'java1c_cleanup_verified': java_report.get('cleanup_verified'),
        'java1c_descendants_and_capture_cleanup': java_report.get('child_and_capture_cleanup_verified'),
        'java1c_temporary_workspace_removed': java_report.get('temporary_workspace_removed')}
    report.update(cleanup=cleanup, remaining_phase_containers=remaining,
        cleanup_verified=remaining == 0 and controls_clean
            and report.get('binding_status') != binding.CLEANUP
            and (not report['binding_attachment_authenticated'] or bind_clean is True)
            and discovery_clean is not False
            and (not java_report or java_report.get('cleanup_verified') is True))
    effects = {label: _metrics([r for r in calls if r['scope'] == label]) for label in (
        'bind1_pre', 'bind1_sandbox2', 'bind1_post', 'discovery', 'java1c', 'cleanup')}
    effects['total'] = _metrics(calls)
    live_java = java_report.get('live_sandbox2', {})
    effects['execution'] = {
        'bind1_javac_version': int(report['binding_attachment_authenticated']),
        'bind1_java_version': int(report['binding_attachment_authenticated']),
        'java1c_sandbox_javac_version': live_java.get('javac_version_count', 0),
        'java1c_sandbox_java_version': live_java.get('java_version_count', 0),
        'javac_compilations': java_report.get('compile_count', 0),
        'java_fixture_executions': java_report.get('jvm_fixture_count', 0),
        'host_child_processes': len(processes), 'source_projections': int(java_report.get('java_workload_attempted') is True),
        **dict.fromkeys(('network_calls', 'shell_calls', 'host_mounts', 'runtime_lease_consumptions',
            'reflection_lease_consumptions', 'bank_executions', 'executor1r_retries', 'apply_actions',
            'repository_runtime_writes'), 0)}
    report.update(effects=effects, docker_control_calls=calls)
    if report['cleanup_verified'] is not True:
        report['preceding_gate_status'] = report['status']
        report.update(status=CLEANUP, reason='phase_cleanup_not_verified')
    if report['status'] != COMPLETE:
        return None, report
    # Positive evidence exists only after every owner gate and final cleanup.
    receipt = JavaDiscoveryCompleteContinuationReceipt(
        attachment.attachment_id, attachment.fingerprint, sd.fingerprint, sr.fingerprint, sr.evidence_sha256,
        attachment.canonical_backend_identity, attachment.canonical_backend_version,
        inventory.backend_identity, inventory.backend_version, artifacts, inventory.discovery_sources,
        inventory.reason, len(artifacts), digest, jd.fingerprint, jr.fingerprint, jr.evidence_sha256,
        jr.sandbox_descriptor_fingerprint, jr.sandbox_receipt_fingerprint, sandbox._json(cleanup),
        tuple((label, sandbox._json(value)) for label, value in sorted(effects.items())), os.getpid(), secrets.token_hex(32))
    receipt = replace(receipt, _signature=_sign(receipt))
    _LIVE[receipt.receipt_id] = (receipt, sandbox._json(_payload(receipt)), attachment, sd, sr, jd, jr)
    validate_provider_continuation_receipt(receipt)
    report.update(positive_receipt_issued=True, java1d_receipt_fingerprint=receipt.fingerprint,
        provider_receipt=receipt.as_dict(), receipt_authenticated_in_issuing_process=True)
    return receipt, report
