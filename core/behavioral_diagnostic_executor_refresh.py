"""EXECUTOR.1R exact synthetic compatibility preflight, with a mandatory stop.

The existing authorization issuer requires reconstructed BANK-family plans and
REFLECT parents. This module cannot sign a substitute source, alias a BANK
grant, or launch a scenario without that source. Only blocked evidence is issued.
"""
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import secrets

from core import runtime_diagnostic_authorization as authorization
from core import behavioral_evidence_execution_plan as planner
from core import read_only_reflection as reflection

PHASE_ID = 'PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1R'
SCHEMA_VERSION = 'patch_candidate_behavior_executor_1r_v1'
BLOCKED = 'PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1R_BLOCKED_AUTHORIZATION'
SCENARIO_ID = 'synthetic.EXECUTOR.1R.decrement_3'
SOURCE = (b'final class SyntheticStateBox {\n'
    b'    private int value = 10;\n\n'
    b'    public boolean decrement(int amount) {\n'
    b'        if (amount <= 0 || amount > value) {\n'
    b'            return false;\n'
    b'        }\n'
    b'        value -= amount;\n'
    b'        return true;\n'
    b'    }\n'
    b'}\n')
SOURCE_SHA256 = sha256(SOURCE).hexdigest()
DEFINITION_SHA256 = sha256(b'private int value = 10;').hexdigest()
_SECRET = secrets.token_bytes(32)


def requested_binding():
    return {'phase_id': PHASE_ID, 'scenario_id': SCENARIO_ID,
        'source_sha256': SOURCE_SHA256, 'owner': 'SyntheticStateBox',
        'member': 'value', 'type': 'int', 'definition_sha256': DEFINITION_SHA256,
        'operation': 'read_exact_bound_field', 'public_invocation': 'decrement(3)',
        'requested_before': 10, 'requested_return': True, 'requested_after': 7}


def _target(declared_type='int'):
    return planner.ExactMemberBinding('SyntheticStateBox.java', 'SyntheticStateBox',
        'SyntheticStateBox', 'value', 'field', declared_type, (), DEFINITION_SHA256,
        SOURCE_SHA256, DEFINITION_SHA256, 'private', '')


def compatibility_audit():
    """Exercise actual closed validators, without constructing BANK parents."""
    findings = []
    def rejected(label, operation):
        try: operation()
        except ValueError as error:
            findings.append((label, getattr(error, 'code', type(error).__name__), str(error)))
        else: raise ValueError('existing_contract_changed_review_required:' + label)
    rejected('independent_scenario_family', lambda: planner.DiagnosticScenario(
        SCENARIO_ID, 'synthetic_decrement', None, (), (), None, (), (),
        ('direct_public_invocation', 'read_only_reflection'), (), planner.NumericComparisonPolicy()))
    # The public source issuer requires exact reconstructed typed parent objects;
    # phase ID/source hashes alone cannot create a synthetic attestation.
    rejected('source_without_reconstructed_parents', lambda:
        authorization.issue_synthetic_runtime_authorization_source(None,
            specification=None, compile_receipt=None, materialized=None,
            candidate=None, admitted_scope=None, scenario_ids=(SCENARIO_ID,),
            fixture_id='synthetic.EXECUTOR.1R.fixed'))
    binding = reflection.RuntimeClassBinding('SyntheticStateBox.java', 'SyntheticStateBox',
        'SyntheticStateBox', 'SyntheticStateBox', 'same_class', SOURCE_SHA256,
        sha256(SOURCE).hexdigest(), '', '')
    rejected('integer_reflection_request', lambda: reflection.ReadOnlyReflectionRequest(
        SOURCE_SHA256, SOURCE_SHA256, SOURCE_SHA256, SCENARIO_ID, (),
        SCENARIO_ID + '.before', 'ordinary_balance_before', _target(), binding,
        reflection.get_read_only_reflection_capability_descriptor().fingerprint))
    # Even changing the numeric type alone cannot bind a different owner/member.
    observation = planner.PlannedObservation(SCENARIO_ID + '.before', 'value', 'before',
        _target('double'), 'read_only_reflection', ('read_only_reflection',), 'read_exact_bound_field')
    rejected('independent_owner_reflection', lambda:
        reflection._target_and_runtime(observation, None, None, {}))
    return tuple(findings)


def _payload(value):
    result = asdict(value)
    result.pop('_signature')
    return result


def _sign(value):
    return hmac.new(_SECRET, authorization._json(_payload(value)).encode(), 'sha256').hexdigest()


@dataclass(frozen=True, slots=True)
class BlockedExecutorRefreshReceipt:
    compatibility_findings: tuple[tuple[str, str, str], ...]
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=BLOCKED, init=False)
    scenario_id: str = field(default=SCENARIO_ID, init=False)
    source_sha256: str = field(default=SOURCE_SHA256, init=False)
    execution_completed: bool = field(default=False, init=False)
    positive_runtime_receipt_issued: bool = field(default=False, init=False)
    synthetic_authorization_issued: bool = field(default=False, init=False)
    real_human_approval: bool = field(default=False, init=False)
    real_session_consumed: bool = field(default=False, init=False)
    operational_real_task_source: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    real_runtime_authorizations_consumed: int = field(default=0, init=False)
    synthetic_runtime_authorizations_consumed: int = field(default=0, init=False)
    bank_execution_count: int = field(default=0, init=False)
    real_behavioral_execution_count: int = field(default=0, init=False)
    synthetic_behavioral_execution_count: int = field(default=0, init=False)
    compile_count: int = field(default=0, init=False)
    jvm_execution_count: int = field(default=0, init=False)
    reflection_execution_count: int = field(default=0, init=False)
    console_count: int = field(default=0, init=False)
    repository_writes: int = field(default=0, init=False)
    apply_actions: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)

    @property
    def fingerprint(self): return authorization._hash(_payload(self))

    def as_dict(self): return {**_payload(self), 'blocked_receipt_fingerprint': self.fingerprint}


def validate_blocked_receipt(receipt):
    if (type(receipt) is not BlockedExecutorRefreshReceipt
            or type(receipt._signature) is not str
            or not hmac.compare_digest(receipt._signature, _sign(receipt))
            or receipt.compatibility_findings != compatibility_audit()
            or receipt.status != BLOCKED or receipt.execution_completed is not False
            or receipt.positive_runtime_receipt_issued is not False):
        raise ValueError('executor1r_blocked_receipt_unauthenticated')
    return receipt


def verify():
    """Stop before capability refresh or projection when exact authority is absent."""
    receipt = BlockedExecutorRefreshReceipt(compatibility_audit())
    receipt = replace(receipt, _signature=_sign(receipt))
    validate_blocked_receipt(receipt)
    return receipt, {'phase_id': PHASE_ID, 'status': receipt.status,
        'reason': 'existing_synthetic_issuer_cannot_reconstruct_independent_scenario',
        'requested_binding': requested_binding(), 'blocked_receipt': receipt.as_dict(),
        'blocked_receipt_authenticated_in_issuing_process': True,
        'exported_json_is_report_only': True, 'positive_runtime_receipt': None,
        'synthetic_authorization': None, 'harness_sha256': None,
        'sandbox2_authentication': 'not_attempted_authorization_gate_blocked',
        'java1_authentication': 'not_attempted_authorization_gate_blocked',
        'compile_stage': None, 'runtime_stage': None, 'measured_observations': None,
        'phase_containers_created': 0, 'remaining_phase_containers': None,
        'cleanup_outcome': 'not_required_no_runtime_resources_created',
        'host_java_artifacts_created': 0, 'source_projected': False,
        'harness_rendered': False, 'fresh_capabilities_obtained': False,
        'historical_executor_relabelled': False, 'bank_oracle_reduced': False,
        'allowed_runtime_operations': [], 'real_runtime_authority_available': False}
