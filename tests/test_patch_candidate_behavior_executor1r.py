"""Pure exact-scope rejection; no synthetic source attestation is fabricated."""
from dataclasses import replace
from hashlib import sha256
import inspect

import pytest

from core import behavioral_diagnostic_executor_refresh as owner
from tests._preflight_runtime1_guard import no_runtime_effects


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=False) as evidence: yield evidence


def test_exact_fixture_is_independent_and_bound_to_its_field_definition():
    assert owner.SOURCE_SHA256 == sha256(owner.SOURCE).hexdigest()
    assert b'Bank' not in owner.SOURCE and b'Saving' not in owner.SOURCE
    assert b'private int value = 10;' in owner.SOURCE
    assert b'value -= amount;' in owner.SOURCE
    assert owner.requested_binding()['definition_sha256'] == sha256(b'private int value = 10;').hexdigest()


def test_existing_validators_reject_independent_scenario_and_field_without_aliasing_bank():
    findings = owner.compatibility_audit()
    assert tuple(row[0] for row in findings) == ('independent_scenario_family',
        'source_without_reconstructed_parents', 'integer_reflection_request', 'independent_owner_reflection')
    assert tuple(row[1] for row in findings) == ('execution_plan_oracle_drift',
        'authorization_invalid', 'reflection_invalid', 'reflection_target_mismatch')


def test_authorization_stop_precedes_every_runtime_effect_and_no_attempt_is_denied(guarded):
    before = dict(guarded.denied_attempts)
    receipt, report = owner.verify()
    assert receipt.status == owner.BLOCKED
    assert owner.validate_blocked_receipt(receipt) is receipt
    assert report['fresh_capabilities_obtained'] is False
    assert report['source_projected'] is report['harness_rendered'] is False
    assert report['positive_runtime_receipt'] is None
    assert report['measured_observations'] is None
    assert report['remaining_phase_containers'] is None
    assert report['phase_containers_created'] == 0
    assert dict(guarded.denied_attempts) == before


def test_blocked_evidence_has_zero_counts_and_no_real_or_synthetic_authority():
    receipt, report = owner.verify()
    for key,value in receipt.as_dict().items():
        if type(value) is bool: assert value is False
        if type(value) is int: assert value == 0
    assert report['synthetic_authorization'] is None
    assert report['allowed_runtime_operations'] == []


@pytest.mark.parametrize('field,value', [('status','COMPLETE'), ('execution_completed',True),
    ('synthetic_runtime_authorizations_consumed',1), ('source_sha256','0'*64),
    ('scenario_id','BANK.unsuccessful_debit'), ('positive_runtime_receipt_issued',True)])
def test_even_self_rehashed_altered_blocked_evidence_is_not_authenticated(field,value):
    receipt,_ = owner.verify()
    object.__setattr__(receipt, field, value)
    with pytest.raises(ValueError, match='unauthenticated'): owner.validate_blocked_receipt(receipt)


def test_json_and_unsigned_typed_receipt_cannot_establish_any_authority():
    receipt,_ = owner.verify()
    for value in (receipt.as_dict(), replace(receipt,_signature='')):
        with pytest.raises(ValueError, match='unauthenticated'): owner.validate_blocked_receipt(value)


def test_stop_is_deterministic_and_accepts_no_source_command_or_authority_input():
    first,_=owner.verify()
    second,_=owner.verify()
    assert first.fingerprint == second.fingerprint
    assert not inspect.signature(owner.verify).parameters
    assert '_signature' not in first.as_dict()
    source=inspect.getsource(owner)
    assert 'authorization._signature(' not in source
    assert 'object.__setattr__(source' not in source
    assert 'subprocess' not in source and 'getDeclaredFields' not in source
