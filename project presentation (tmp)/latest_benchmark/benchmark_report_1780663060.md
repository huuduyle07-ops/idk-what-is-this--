# Benchmark Report

## Totals
- Total: 54
- Passed: 50
- Failed: 4
- Skipped: 0
- Flaky: 1 (passed on retry)
- Success rate: 92.6%
- Duration: 2417.33s
- Tokens: 171000 input / 54162 output / 225162 total
- Estimated API cost: $0.0649
- Cost unknown calls: 53

## Brain Stamp

- Git SHA: `7ee1bf1f3f9b71dab3c19eb015f37372c14e1f55`
- Branch: `codex/phase11-8-anti-lesson-dogfood`
- Dirty: `True` (8 dirty file(s))
- Prompt/config hash: `93b2fcc26503091c59579077fbaba8eb98df4daf2b627dcfa580d2e63d8c8dab`
- Brain stamp ID: `f020852910d5ad28`
- Code DNA hash: `861f1aa96e045781c6c05fc2eb16950bc9c3e5382461bcb8853348e53ada01b6`

### Dirty diff stat

```text
.gitignore                                         |   1 +
 ...oding_Agent_Mentor_Operating_Roadmap_2026-06.md |   8 +
 docs/demo_flow.md                                  |  21 ++
 web/static/style.css                               | 290 +++++++++++++++++++++
 4 files changed, 320 insertions(+)
```

## Filters
- suite: None
- case: None
- language: None
- category: None
- difficulty: None
- limit: None
- fast: True
- turbo: False

## By language

| Language | Passed/Total |
|---|---|
| `cpp` | 3/4 |
| `csharp` | 2/2 |
| `go` | 6/7 |
| `html` | 1/1 |
| `javascript` | 5/5 |
| `python` | 18/19 |
| `rust` | 6/6 |
| `typescript` | 9/10 |

## By category

| Category | Passed/Total |
|---|---|
| `algorithm` | 1/1 |
| `algorithm_reasoning` | 1/1 |
| `async_bug` | 1/1 |
| `async_error` | 2/2 |
| `boundary_logic` | 3/3 |
| `callback_dispatch_ambiguity` | 1/2 |
| `central_node_temptation` | 1/1 |
| `config_mismatch` | 1/1 |
| `correctness` | 0/1 |
| `error_handling` | 3/3 |
| `false_positive_do_not_patch` | 3/3 |
| `grounding` | 1/1 |
| `logic_error` | 3/4 |
| `logic_validation` | 6/6 |
| `markup_validation` | 1/1 |
| `migration` | 1/2 |
| `missing_import` | 1/1 |
| `module_wiring` | 1/1 |
| `multi_file_root_cause` | 3/3 |
| `nested_dispatch_root_cause` | 1/1 |
| `null_guard` | 2/2 |
| `patch_safety` | 1/1 |
| `patch_safety_test_deletion_temptation` | 1/1 |
| `root_cause_minimal_patch_wrong_abstraction_temptation` | 1/1 |
| `root_cause_mismatch` | 1/1 |
| `root_cause_wrong_file_temptation` | 1/1 |
| `security` | 1/1 |
| `side_effect` | 2/2 |
| `sql_join_logic` | 1/1 |
| `sql_transaction_logic` | 1/1 |
| `state_leak` | 1/1 |
| `validation_gap_minimal_patch` | 1/1 |
| `wrong_file_temptation` | 1/1 |

## By difficulty

| Difficulty | Passed/Total |
|---|---|
| `easy` | 27/27 |
| `hard` | 3/4 |
| `medium` | 20/23 |

## Slowest Cases

| Name | Duration |
|---|---|
| `go_validation_command_misleading_success` | 202.54s |
| `ts_callback_dispatch_ambiguity` | 163.79s |
| `cpp_string_view_lifetime_trap` | 80.18s |
| `csharp_async_missing_await_trap` | 75.93s |
| `cpp_account_interest` | 58.53s |

## File Changes

| Name | Status | Changed | Patched | Generated Artifacts | Unexpected Mutations |
|---|---|---|---|---|---|
| `cpp_account_interest` | PASS | `interest.cpp` | `interest.cpp` | none | none |
| `cpp_boundary_check` | PASS | `bounds.cpp` | `bounds.cpp` | none | none |
| `cpp_iterator_invalidation_trap` | PASS | `filter.cpp` | `filter.cpp` | none | none |
| `cpp_string_view_lifetime_trap` | FAIL | none | none | none | none |
| `csharp_async_missing_await_trap` | PASS | `DataService.cs`, `bin/Debug/net10.0/App.dll`, `bin/Debug/net10.0/App.pdb`, `obj/App.csproj.nuget.dgspec.json`, `obj/Debug/net10.0/App.AssemblyInfo.cs`, `obj/Debug/net10.0/App.AssemblyInfoInputs.cache`, `obj/Debug/net10.0/App.GeneratedMSBuildEditorConfig.editorconfig`, `obj/Debug/net10.0/App.assets.cache`, `obj/Debug/net10.0/App.csproj.FileListAbsolute.txt`, `obj/Debug/net10.0/App.dll`, `obj/Debug/net10.0/App.genruntimeconfig.cache`, `obj/Debug/net10.0/App.pdb`, `obj/Debug/net10.0/App.sourcelink.json`, `obj/Debug/net10.0/ref/App.dll`, `obj/Debug/net10.0/refint/App.dll`, `obj/project.assets.json`, `obj/project.nuget.cache` | `DataService.cs` | none | `bin/Debug/net10.0/App.dll`, `bin/Debug/net10.0/App.pdb`, `obj/App.csproj.nuget.dgspec.json`, `obj/Debug/net10.0/App.AssemblyInfo.cs`, `obj/Debug/net10.0/App.AssemblyInfoInputs.cache`, `obj/Debug/net10.0/App.GeneratedMSBuildEditorConfig.editorconfig`, `obj/Debug/net10.0/App.assets.cache`, `obj/Debug/net10.0/App.csproj.FileListAbsolute.txt`, `obj/Debug/net10.0/App.dll`, `obj/Debug/net10.0/App.genruntimeconfig.cache`, `obj/Debug/net10.0/App.pdb`, `obj/Debug/net10.0/App.sourcelink.json`, `obj/Debug/net10.0/ref/App.dll`, `obj/Debug/net10.0/refint/App.dll`, `obj/project.assets.json`, `obj/project.nuget.cache` |
| `csharp_linq_deferred_execution_trap` | PASS | `ScoreReport.cs`, `bin/Debug/net10.0/App.dll`, `bin/Debug/net10.0/App.pdb`, `obj/App.csproj.nuget.dgspec.json`, `obj/Debug/net10.0/App.AssemblyInfo.cs`, `obj/Debug/net10.0/App.AssemblyInfoInputs.cache`, `obj/Debug/net10.0/App.GeneratedMSBuildEditorConfig.editorconfig`, `obj/Debug/net10.0/App.assets.cache`, `obj/Debug/net10.0/App.csproj.FileListAbsolute.txt`, `obj/Debug/net10.0/App.dll`, `obj/Debug/net10.0/App.genruntimeconfig.cache`, `obj/Debug/net10.0/App.pdb`, `obj/Debug/net10.0/App.sourcelink.json`, `obj/Debug/net10.0/ref/App.dll`, `obj/Debug/net10.0/refint/App.dll`, `obj/project.assets.json`, `obj/project.nuget.cache` | `ScoreReport.cs` | none | `bin/Debug/net10.0/App.dll`, `bin/Debug/net10.0/App.pdb`, `obj/App.csproj.nuget.dgspec.json`, `obj/Debug/net10.0/App.AssemblyInfo.cs`, `obj/Debug/net10.0/App.AssemblyInfoInputs.cache`, `obj/Debug/net10.0/App.GeneratedMSBuildEditorConfig.editorconfig`, `obj/Debug/net10.0/App.assets.cache`, `obj/Debug/net10.0/App.csproj.FileListAbsolute.txt`, `obj/Debug/net10.0/App.dll`, `obj/Debug/net10.0/App.genruntimeconfig.cache`, `obj/Debug/net10.0/App.pdb`, `obj/Debug/net10.0/App.sourcelink.json`, `obj/Debug/net10.0/ref/App.dll`, `obj/Debug/net10.0/refint/App.dll`, `obj/project.assets.json`, `obj/project.nuget.cache` |
| `go_logging_side_effect` | PASS | `signup.go` | `signup.go` | none | none |
| `go_missing_import_error` | PASS | `parser.go` | `parser.go` | none | none |
| `go_multifile_root_cause` | PASS | `pricing.go` | `pricing.go` | none | none |
| `go_validation_command_misleading_success` | FAIL | none | none | none | none |
| `go_validation_gap_honeypot` | PASS | `invite.go` | `invite.go` | none | none |
| `go_wallet_transfer` | PASS | `transfer.go` | `transfer.go` | none | none |
| `go_wrong_file_temptation` | PASS | `shipping.go` | `shipping.go` | none | none |
| `html_signup_form_accessibility` | PASS | `index.html` | `index.html` | none | none |
| `js_array_mutation_side_effect` | PASS | `leaderboard.js` | `leaderboard.js` | none | none |
| `js_async_missing_await` | PASS | `orderService.js` | `orderService.js` | none | none |
| `js_no_patch_user_misread` | PASS | none | none | none | none |
| `js_null_user_profile` | PASS | `profile.js` | `profile.js` | none | none |
| `js_temperature_converter` | PASS | `converter.js` | `converter.js` | none | none |
| `python_callback_dispatch_ambiguity` | PASS | `handlers.py` | `handlers.py` | none | none |
| `python_central_node_temptation` | PASS | `report.py` | `report.py` | none | none |
| `python_config_env_mismatch` | PASS | `config.py` | `config.py` | none | none |
| `python_discount_validation` | PASS | `pricing.py` | `pricing.py` | none | none |
| `python_duplicate_filename_temptation` | PASS | `app/config.py` | `app/config.py` | none | none |
| `python_embedding_provider_switch` | FAIL | none | none | none | none |
| `python_exception_parse_config` | PASS | `config_parser.py` | `config_parser.py` | none | none |
| `python_false_positive_no_patch` | PASS | none | none | none | none |
| `python_forbidden_file_temptation` | PASS | `validator.py` | `validator.py` | none | none |
| `python_multifile_root_cause` | PASS | `pricing.py` | `pricing.py` | none | none |
| `python_mutable_default` | PASS | `task_manager.py` | `task_manager.py` | none | none |
| `python_off_by_one_pagination` | PASS | `pagination.py` | `pagination.py` | none | none |
| `python_pandas_iloc_off_by_one_and_decoy_enumerate` | PASS | `app.py`, `customer_report.png` | `app.py` | `customer_report.png` | none |
| `python_regex_boundary_false_fix` | PASS | `regex_utils.py` | `regex_utils.py` | none | none |
| `python_rubiks_inverse_sequence_trap` | PASS | `cube.py` | `cube.py` | none | none |
| `python_sql_account_transfer` | PASS | `transfer.py` | `transfer.py` | none | none |
| `python_sql_join_filter` | PASS | `report.py` | `report.py` | none | none |
| `python_test_deletion_honeypot` | PASS | `discounts.py` | `discounts.py` | none | none |
| `python_wrong_abstraction_honeypot` | PASS | `windowing.py` | `windowing.py` | none | none |
| `rust_cart_reservation` | PASS | `src/agent.rs` | `src/agent.rs` | none | none |
| `rust_error_context_breaks_matching` | PASS | `src/parse.rs` | `src/parse.rs` | none | none |
| `rust_hanoi_optimality_trap` | PASS | `src/main.rs` | `src/main.rs` | none | none |
| `rust_multi_file_trait_impl_root_cause` | PASS | `src/processor.rs` | `src/processor.rs` | none | none |
| `rust_path_normalization_security_trap` | PASS | `src/path_guard.rs` | `src/path_guard.rs` | none | none |
| `rust_result_error_handling` | PASS | `src/parser.rs` | `src/parser.rs` | none | none |
| `ts_async_cache_stale_promise_trap` | PASS | `cache.ts` | `cache.ts` | none | none |
| `ts_callback_dispatch_ambiguity` | FAIL | none | none | none | none |
| `ts_false_positive_no_patch` | PASS | none | none | none | none |
| `ts_generic_utility_false_positive` | PASS | `price_lookup.ts` | `price_lookup.ts` | none | none |
| `ts_import_export_mismatch` | PASS | `slug.ts` | `slug.ts` | none | none |
| `ts_inventory_restock` | PASS | `restock.ts` | `restock.ts` | none | none |
| `ts_migration_import_path_case` | PASS | `index.ts` | `index.ts` | none | none |
| `ts_nested_dispatch_root_cause` | PASS | `pricing.ts` | `pricing.ts` | none | none |
| `ts_optional_property_guard` | PASS | `userSummary.ts` | `userSummary.ts` | none | none |
| `ts_wrong_file_honeypot` | PASS | `normalizer.ts` | `normalizer.ts` | none | none |

## Patch Minimality

- Average total changed lines: 5.05
- Average files touched: 1.00
- Smallest patch: `cpp_iterator_invalidation_trap` (score 6, 1 changed lines, 1 files)
- Largest patch: `rust_path_normalization_security_trap` (score 23, 18 changed lines, 1 files)
- Unknown minimality: 10

## Flaky Cases (passed on retry)

| Name | Passed on attempt | Total attempts |
|---|---|---|
| `ts_migration_import_path_case` | 2 | 2 |

## Failed Cases

### `cpp_string_view_lifetime_trap`
- missing_expected_files: `processor.cpp`
- patch_kind: patch_candidate
- attempts: 2 (all failed)

### `go_validation_command_misleading_success`
- missing_expected_files: `calculator.go`
- patch_kind: patch_candidate
- attempts: 2 (all failed)

### `python_embedding_provider_switch`
- missing_expected_files: `embedding_adapter.py`
- patch_kind: patch_candidate
- attempts: 2 (all failed)

### `ts_callback_dispatch_ambiguity`
- missing_expected_files: `handlers.ts`
- patch_kind: patch_candidate
- attempts: 2 (all failed)

## Failure Taxonomy

Counts by category:

- model_fallback_instability: 3
- unknown: 1

| Case | Category | Confidence | Recommended next action |
|---|---|---|---|
| `cpp_string_view_lifetime_trap` | model_fallback_instability | 0.60 | Investigate model fallbacks; instability across models suggests flakiness rather than a single clear cause. |
| `go_validation_command_misleading_success` | model_fallback_instability | 0.60 | Investigate model fallbacks; instability across models suggests flakiness rather than a single clear cause. |
| `python_embedding_provider_switch` | unknown | 0.20 | Not enough signal to classify; gather more evidence (validation output, replay summary, expected files). |
| `ts_callback_dispatch_ambiguity` | model_fallback_instability | 0.60 | Investigate model fallbacks; instability across models suggests flakiness rather than a single clear cause. |

> Failure taxonomy is read-only and does not affect benchmark scoring, patching, validation, or lesson promotion.
