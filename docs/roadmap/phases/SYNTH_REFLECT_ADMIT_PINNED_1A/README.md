# SYNTH.REFLECT.ADMIT.PINNED.1A

Additive implementation of the admission owner declared by the frozen
[pinned reflection contract](../SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json).
The implementation phase is `SYNTH.REFLECT.ADMIT.PINNED.1`.

The owner is
[`core.synthetic_reflection_execution_admission_pinned`](../../../../core/synthetic_reflection_execution_admission_pinned.py),
with exact type `PinnedSyntheticReflectionExecutionAdmission`, schema
`synthetic_reflection_execution_admission_pinned_1_v1` and independent domain
`CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1`.

See the [implementation report](SYNTH_REFLECT_ADMIT_PINNED_1A_REPORT.md),
[safe historical validation](safe_validation_summary.json) and
[isolated admission validation](inert_admission_tests.json).
Test-local inert admissions are structural fixtures, never operational evidence.
No operational admission, reflection lease or reflection effect exists.

Focused validation from the repository root:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -B -m pytest -q -p no:cacheprovider tests/test_synthetic_reflection_execution_admission_pinned.py
```

The focused suite source-loads independent owner copies and constructs inert
upstream dataclasses. Only isolated public-validator seams accept those objects.
Production issuance, renderer, runtime transitions and provider validation are
denied, and production maps/stores and historical source bytes are compared.

Historical checks use source/AST extraction and file-only facades, never frozen
issuance-dependent suites:

```powershell
python -B docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode frozen
python -B docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode focused
python -B docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/validate_historical_pure.py --mode benchmark
python -B docs/roadmap/phases/SYNTH_REFLECT_ADMIT_PINNED_1A/finalize_safe_validation.py
```

`focused` in the historical harness means the frozen contract's source/AST tests;
it is separate from the isolated admission suite above. The original preservation
and registry baselines must remain untouched. Registry/picker comparison records
the same seven preexisting failures and unchanged public projections.

No registry/reversal slice was made. Historical owners, provider/executor history
and request bytes remain preserved. The future pinned reflection lifecycle,
source/compilation readiness and consumer remain unimplemented/unresolved.
Behavioral readiness remains false with `PROOF_UNRESOLVED`; compilation authority
is false. Stop after this admission implementation.
