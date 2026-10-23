"""Summarize pure checks and compare all preexisting bytes without repinning."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
BASELINE = json.loads((PHASE/'preservation_baseline.json').read_text(encoding='utf-8'))
NEW_PATHS = {'core/runtime_java_pinned_requirement.py','tests/test_runtime_java_requirement_pinned1.py'}

def load(name):
    path = PHASE/name
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else None

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

changed, missing = [], []
for rel, expected in BASELINE['files'].items():
    path = ROOT/rel
    if not path.is_file():
        missing.append(rel)
    elif digest(path) != expected['sha256']:
        changed.append({'path':rel,'before_sha256':expected['sha256'],'after_sha256':digest(path)})
excluded_dirs = {'.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.aws'}
excluded_top = {'.tmp','tmp_tests','tmp','temp'}
new_paths = []
for base, dirs, names in os.walk(ROOT):
    relbase = Path(base).relative_to(ROOT)
    dirs[:] = [d for d in dirs if d not in excluded_dirs and not (len((relbase/d).parts)==1 and d in excluded_top)]
    if Path(base)==PHASE:
        dirs[:] = []
        continue
    for name in names:
        path = Path(base)/name
        rel = path.relative_to(ROOT).as_posix()
        if name == '.env' or name.startswith('.env.') and name != '.env.example' or name.endswith('.log'):
            continue
        if rel not in BASELINE['files']:
            new_paths.append(rel)

# Observe prior historical expectations as recorded, including existing drift.
# Their files and expected digests remain untouched; this phase does not repin.
prior = []
for rel in BASELINE['files']:
    if not rel.startswith('docs/') or not rel.endswith('_PRESERVATION.json'):
        continue
    if not any(s in rel for s in ('RUNTIME_JAVA','RUNTIME_SANDBOX','SYNTH_AUTH','SYNTH_REFLECT','PATCH_CANDIDATE_BEHAVIOR_EXECUTOR')):
        continue
    try:
        manifest = json.loads((ROOT/rel).read_text(encoding='utf-8-sig'))
    except (ValueError,OSError):
        continue
    expectations = manifest.get('baseline_sha256',{})
    before_drift, after_drift, excluded_expectations = [], [], []
    for expected_rel, expected_digest in expectations.items():
        if not isinstance(expected_digest,str):
            continue
        excluded = next((row for row in BASELINE['excluded'] if expected_rel == row['path'] or expected_rel.startswith(row['path'].rstrip('/')+'/')), None)
        if excluded is not None:
            excluded_expectations.append({'path':expected_rel,'reason':excluded['reason']})
            continue
        before = BASELINE['files'].get(expected_rel,{}).get('sha256')
        path = ROOT/expected_rel
        after = digest(path) if path.is_file() else None
        if before != expected_digest:
            before_drift.append({'path':expected_rel,'expected_sha256':expected_digest,'actual_sha256':before})
        if after != expected_digest:
            after_drift.append({'path':expected_rel,'expected_sha256':expected_digest,'actual_sha256':after})
    already_missing = manifest.get('already_missing_paths',manifest.get('preexisting_missing_paths',[]))
    if not isinstance(already_missing, list):
        already_missing = []
    prior.append({'manifest':rel,'expectations_checked':len(expectations)-len(excluded_expectations),'excluded_expectations':excluded_expectations,'preexisting_drift':before_drift,'after_drift':after_drift,'drift_state_unchanged':before_drift==after_drift,'prior_recorded_missing_paths':already_missing,'prior_missing_paths_still_absent':[p for p in already_missing if not (ROOT/p).exists()]})

preservation = {
    'phase_id':'RUNTIME.JAVA.REQUIREMENT.PINNED.1',
    'baseline_manifest':'preservation_baseline.json',
    'existing_files_checked':len(BASELINE['files']),
    'baseline_bytes':BASELINE['total_bytes'],
    'existing_files_changed':changed,
    'existing_files_missing':missing,
    'additive_source_paths':sorted(p for p in new_paths if p in NEW_PATHS),
    'unexpected_new_paths':sorted(p for p in new_paths if p not in NEW_PATHS),
    'new_phase_artifacts_allowed_under':'docs/roadmap/phases/RUNTIME_JAVA_REQUIREMENT_PINNED_1/',
    'frozen_core_scripts_tests_docs_registry_reversal_receipts_unchanged':not changed and not missing,
    'historical_repins':False,
    'prior_historical_expectation_observations':prior,
    'prior_historical_drift_retained':all(p['drift_state_unchanged'] for p in prior),
    'note':'All baseline bytes, including preexisting working-tree edits and historical manifests, are preserved. Missing or mismatched older expectations are observations only and are never rewritten.',
}
(PHASE/'preservation.json').write_text(json.dumps(preservation,indent=2)+'\n',encoding='utf-8')

frozen_baseline = load('frozen_baseline.json')
frozen_after = load('frozen_after.json')
registry_baseline = load('registry_baseline.json')
registry_after = load('registry_after.json')
new_requirement = load('new_requirement.json')
benchmark = load('benchmark_check.json')

def failure_ids(report):
    return sorted(f['nodeid'] for f in report['failures']) if report else None

compile_paths = set(NEW_PATHS)
if frozen_after:
    compile_paths.update(frozen_after['test_files'])
compile_paths.update(p for p in BASELINE['files'] if p.startswith(('core/sandboxed_java','core/java_','core/thread_compatible_runtime_sandbox','core/sandbox_backend_binding','core/synthetic_runtime_authorization','core/behavioral_diagnostic_executor')) and p.endswith('.py'))
compile_paths.update(['scripts/measure_runtime_java_discovery_diag1.py','benchmarks/run_benchmarks.py'])
compile_paths.update(p.relative_to(ROOT).as_posix() for p in PHASE.glob('*.py'))
compilation_errors = []
for rel in sorted(compile_paths):
    try:
        compile((ROOT/rel).read_bytes(),str(ROOT/rel),'exec')
    except Exception as error:
        compilation_errors.append({'path':rel,'error':str(error)})

authored = [ROOT/p for p in sorted(NEW_PATHS)] + [p for p in PHASE.iterdir() if p.is_file() and p.suffix in {'.py','.md','.json'}]
whitespace = []
for path in authored:
    raw = path.read_bytes()
    content = raw.decode('utf-8-sig')
    if raw and not raw.endswith(b'\n'):
        whitespace.append({'path':path.relative_to(ROOT).as_posix(),'issue':'missing final newline'})
    for number,line in enumerate(content.splitlines(),1):
        if line.rstrip(' \t') != line:
            whitespace.append({'path':path.relative_to(ROOT).as_posix(),'line':number,'issue':'trailing whitespace'})
json_errors = []
for path in PHASE.glob('*.json'):
    try:
        json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as error:
        json_errors.append({'path':path.name,'error':str(error)})

validation = {
    'phase_id':'RUNTIME.JAVA.REQUIREMENT.PINNED.1',
    'focused_new_requirement_tests':new_requirement,
    'frozen_pure_baseline':frozen_baseline,
    'frozen_pure_after':frozen_after,
    'registry_picker_baseline':registry_baseline,
    'registry_picker_after':registry_after,
    'baseline_vs_after':{
        'registry_picker_failure_ids_unchanged':failure_ids(registry_baseline)==failure_ids(registry_after),
        'registry_picker_new_failures':sorted(set(failure_ids(registry_after) or [])-set(failure_ids(registry_baseline) or [])),
        'frozen_pure_failure_ids_unchanged':failure_ids(frozen_baseline)==failure_ids(frozen_after),
        'frozen_pure_new_failures':sorted(set(failure_ids(frozen_after) or [])-set(failure_ids(frozen_baseline) or [])),
        'historical_sources_rewritten':bool(changed or missing),
        'historical_repins':False,
    },
    'benchmark_structure_check':benchmark,
    'benchmark_bootstrap_observations':load('benchmark_bootstrap.json'),
    'in_memory_python_compilation':{'files':sorted(compile_paths),'errors':compilation_errors,'passed':not compilation_errors,'code_executed':False},
    'git_diff_check':load('git_diff_check.json'),
    'authored_artifact_whitespace':{'checked_files':[p.relative_to(ROOT).as_posix() for p in authored],'issues':whitespace,'passed':not whitespace,'raw_diagnostic_logs_reformatted':False},
    'authored_json_parse':{'errors':json_errors,'passed':not json_errors},
    'historical_preservation':{'artifact':'preservation.json','files_checked':preservation['existing_files_checked'],'changed':changed,'missing':missing,'unexpected_new_paths':preservation['unexpected_new_paths'],'historical_repins':False,'prior_drift_retained':preservation['prior_historical_drift_retained']},
    'denied_dependency_bootstrap_attempts':{name:{'audit_denied':r.get('real_effect_attempts',[]),'guard_denied':r.get('denied_attempts',{})} for name,r in [('frozen_baseline',frozen_baseline),('frozen_after',frozen_after),('registry_baseline',registry_baseline),('registry_after',registry_after),('new_requirement',new_requirement),('benchmark_check',benchmark)] if r},
    'successful_operational_effect_counts':dict.fromkeys(['Docker','containers','exports','Java','javac','compile','network','shell','host mounts','source projection','runtime lease consumption','reflection lease consumption','BANK','EXECUTOR.1R','Apply'],0),
    'effect_scope':'Operational runtime effects are zero. Host repository reads, Python/pytest validation and artifact/temp writes are maintenance. Frozen regression fixtures fabricate development-only in-memory authority records; they issue no operational capability. Attempted dependency bootstrap process/network probes were denied before any successful effect and are recorded separately.',
}
(PHASE/'validation.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'preserved_existing_files':preservation['existing_files_checked'],'changed_count':len(changed),'missing_count':len(missing),'unexpected_new_paths':preservation['unexpected_new_paths'],'prior_manifests_observed':len(prior),'prior_drift_retained':preservation['prior_historical_drift_retained'],'compilation_files':len(compile_paths),'compilation_errors':compilation_errors,'whitespace_issues':whitespace,'json_errors':json_errors,'baseline_vs_after':validation['baseline_vs_after']}))
