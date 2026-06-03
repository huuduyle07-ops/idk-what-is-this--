# Phase 11-prep / 11c-b: 50-Case Adversarial Benchmark Expansion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 new adversarial benchmark cases, growing the suite from 42 to 50 cases.

**Architecture:** Each case follows the existing pattern: `benchmarks/cases/<lang>/<case_name>/case.json` + `buggy_repo/` with source files and a validation command. All 8 cases are added to `full_v1`. 4 go to `dev_v1`, 4 to `held_out_v1`. The stale test in `test_benchmark_suites.py` (expects 41, now 42) is updated to 50.

**Tech Stack:** C++ (g++, validate.py), C# (dotnet run), Rust (cargo), Python (python), TypeScript (node --experimental-strip-types)

---

## File Map

### New case directories (8 total)
- `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/case.json`
- `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/filter.h`
- `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/filter.cpp`
- `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/main.cpp`
- `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/validate.py`
- `benchmarks/cases/cpp/cpp_string_view_lifetime_trap/case.json`
- `benchmarks/cases/cpp/cpp_string_view_lifetime_trap/buggy_repo/processor.h`
- `benchmarks/cases/cpp/cpp_string_view_lifetime_trap/buggy_repo/processor.cpp`
- `benchmarks/cases/cpp/cpp_string_view_lifetime_trap/buggy_repo/main.cpp`
- `benchmarks/cases/cpp/cpp_string_view_lifetime_trap/buggy_repo/validate.py`
- `benchmarks/cases/csharp/csharp_async_missing_await_trap/case.json`
- `benchmarks/cases/csharp/csharp_async_missing_await_trap/buggy_repo/App.csproj`
- `benchmarks/cases/csharp/csharp_async_missing_await_trap/buggy_repo/DataService.cs`
- `benchmarks/cases/csharp/csharp_async_missing_await_trap/buggy_repo/Program.cs`
- `benchmarks/cases/csharp/csharp_linq_deferred_execution_trap/case.json`
- `benchmarks/cases/csharp/csharp_linq_deferred_execution_trap/buggy_repo/App.csproj`
- `benchmarks/cases/csharp/csharp_linq_deferred_execution_trap/buggy_repo/ScoreReport.cs`
- `benchmarks/cases/csharp/csharp_linq_deferred_execution_trap/buggy_repo/Program.cs`
- `benchmarks/cases/rust/rust_error_context_breaks_matching/case.json`
- `benchmarks/cases/rust/rust_error_context_breaks_matching/buggy_repo/Cargo.toml`
- `benchmarks/cases/rust/rust_error_context_breaks_matching/buggy_repo/src/parse.rs`
- `benchmarks/cases/rust/rust_error_context_breaks_matching/buggy_repo/src/main.rs`
- `benchmarks/cases/rust/rust_path_normalization_security_trap/case.json`
- `benchmarks/cases/rust/rust_path_normalization_security_trap/buggy_repo/Cargo.toml`
- `benchmarks/cases/rust/rust_path_normalization_security_trap/buggy_repo/src/path_guard.rs`
- `benchmarks/cases/rust/rust_path_normalization_security_trap/buggy_repo/src/main.rs`
- `benchmarks/cases/python/python_regex_boundary_false_fix/case.json`
- `benchmarks/cases/python/python_regex_boundary_false_fix/buggy_repo/regex_utils.py`
- `benchmarks/cases/python/python_regex_boundary_false_fix/buggy_repo/main.py`
- `benchmarks/cases/typescript/ts_async_cache_stale_promise_trap/case.json`
- `benchmarks/cases/typescript/ts_async_cache_stale_promise_trap/buggy_repo/cache.ts`
- `benchmarks/cases/typescript/ts_async_cache_stale_promise_trap/buggy_repo/main.ts`

### Modified files
- `benchmarks/suites/full_v1.json` — add 8 new case names, update description
- `benchmarks/suites/dev_v1.json` — add 4 new dev cases
- `benchmarks/suites/held_out_v1.json` — add 4 new held-out cases
- `tests/test_benchmark_suites.py` — update `41→50`, add new cases to HELD_OUT_CASES

---

## Suite Placement

**dev_v1** gets:
- `cpp_iterator_invalidation_trap`
- `csharp_async_missing_await_trap`
- `rust_error_context_breaks_matching`
- `python_regex_boundary_false_fix`

**held_out_v1** gets:
- `cpp_string_view_lifetime_trap`
- `csharp_linq_deferred_execution_trap`
- `rust_path_normalization_security_trap`
- `ts_async_cache_stale_promise_trap`

---

## Task 1: cpp_iterator_invalidation_trap

**Bug:** Index-based loop increments `i` after `erase()`, skipping elements when negatives are adjacent.

**Files:**
- Create: `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/case.json`
- Create: `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/filter.h`
- Create: `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/filter.cpp`
- Create: `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/main.cpp`
- Create: `benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo/validate.py`

- [ ] **Step 1: Create filter.h**

```cpp
#ifndef FILTER_H
#define FILTER_H
#include <vector>
int remove_negatives(std::vector<int>& v);
#endif
```

- [ ] **Step 2: Create filter.cpp (buggy)**

```cpp
#include "filter.h"
#include <cstddef>

int remove_negatives(std::vector<int>& v) {
    // BUG: increments i after erase(), skipping the element that shifted into position i
    int removed = 0;
    for (std::size_t i = 0; i < v.size(); ++i) {
        if (v[i] < 0) {
            v.erase(v.begin() + static_cast<std::ptrdiff_t>(i));
            ++removed;
        }
    }
    return removed;
}
```

Correct fix (only in `filter.cpp`):
```cpp
int remove_negatives(std::vector<int>& v) {
    int removed = 0;
    for (std::size_t i = 0; i < v.size(); ) {
        if (v[i] < 0) {
            v.erase(v.begin() + static_cast<std::ptrdiff_t>(i));
            ++removed;
        } else {
            ++i;
        }
    }
    return removed;
}
```

- [ ] **Step 3: Create main.cpp (test)**

```cpp
#include "filter.h"
#include <cstdlib>
#include <iostream>
#include <vector>

static void fail(const char* msg) {
    std::cerr << "FAIL: " << msg << "\n";
    std::exit(1);
}

int main() {
    // all negatives — buggy code skips alternating, leaves {-2}
    std::vector<int> v1 = {-3, -2, -1};
    int n1 = remove_negatives(v1);
    if (!v1.empty())   fail("all negatives: vector should be empty");
    if (n1 != 3)       fail("all negatives: should report 3 removed");

    // mixed
    std::vector<int> v2 = {-1, 2, -3, 4};
    int n2 = remove_negatives(v2);
    if (v2.size() != 2)               fail("mixed: two positives should remain");
    if (v2[0] != 2 || v2[1] != 4)    fail("mixed: positives should be 2 and 4");
    if (n2 != 2)                      fail("mixed: should report 2 removed");

    // no negatives
    std::vector<int> v3 = {1, 2, 3};
    int n3 = remove_negatives(v3);
    if (v3.size() != 3)  fail("no negatives: nothing should be removed");
    if (n3 != 0)         fail("no negatives: should report 0 removed");

    std::cout << "OK\n";
    return 0;
}
```

- [ ] **Step 4: Create validate.py** (copy from cpp_account_interest pattern with filenames adjusted)

Use the same validate.py as cpp_account_interest but compile `filter.cpp` and `main.cpp` instead of `interest.cpp`.

```python
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"
EXE = HERE / ("validation_test.exe" if IS_WINDOWS else "validation_test")
NTSTATUS_ERROR_THRESHOLD = 0xC0000000


def gxx_runtime_env():
    env = os.environ.copy()
    if not IS_WINDOWS:
        return env
    gxx = shutil.which("g++")
    if not gxx:
        return env
    gxx_dir = str(Path(gxx).resolve().parent)
    if env.get("PATH", "").split(os.pathsep)[0].lower() != gxx_dir.lower():
        env["PATH"] = gxx_dir + os.pathsep + env.get("PATH", "")
    return env


def run_and_forward(cmd, env=None):
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    if result.stdout: sys.stdout.write(result.stdout)
    if result.stderr: sys.stderr.write(result.stderr)
    sys.stdout.flush(); sys.stderr.flush()
    return result.returncode


def is_windows_av_crash(rc):
    if not IS_WINDOWS or rc <= 0: return False
    return (rc & 0xFFFFFFFF) >= NTSTATUS_ERROR_THRESHOLD


compile_cmd = [
    "g++", str(HERE / "main.cpp"), str(HERE / "filter.cpp"),
    "-std=c++17", "-o", str(EXE),
]

try:
    if EXE.exists(): EXE.unlink()
except OSError:
    pass

runtime_env = gxx_runtime_env()
exit_code = 0
try:
    rc = run_and_forward(compile_cmd, env=runtime_env)
    if rc != 0:
        print(f"compile failed (exit {rc})", file=sys.stderr)
        exit_code = rc
    else:
        rc = run_and_forward([str(EXE)], env=runtime_env)
        if is_windows_av_crash(rc):
            time.sleep(1.5)
            rc = run_and_forward([str(EXE)], env=runtime_env)
        if rc != 0:
            print(f"validation_test failed (exit {rc})", file=sys.stderr)
            exit_code = rc
        else:
            print("OK")
finally:
    try:
        if EXE.exists(): EXE.unlink()
    except OSError:
        pass

sys.exit(exit_code)
```

- [ ] **Step 5: Create case.json**

```json
{
  "name": "cpp_iterator_invalidation_trap",
  "language": "cpp",
  "category": "logic_error",
  "difficulty": "medium",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "python validate.py",
  "expected_changed_files": ["filter.cpp"],
  "forbidden_changed_files": ["main.cpp", "filter.h", "validate.py"],
  "allowed_generated_files": [],
  "prompt": "Fix the C++ iterator invalidation bug.\n\nRequirements:\n- Modify filter.cpp only.\n- remove_negatives must erase all negative elements from the vector.\n- remove_negatives must return the count of removed elements.\n- Elements at adjacent positions must all be removed (not skipped).\n- Positive elements must remain unchanged in their original order.\n- Do not modify main.cpp, filter.h, or validate.py.\n- Do not create new files.\n- Use patch_candidate if only remove_negatives changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: python validate.py"
}
```

- [ ] **Step 6: Verify pre-fix failure**

```
cd benchmarks/cases/cpp/cpp_iterator_invalidation_trap/buggy_repo
python validate.py
```
Expected: non-zero exit code with "FAIL: all negatives: vector should be empty"

- [ ] **Step 7: Temporarily apply fix, verify pass, restore buggy**

Apply the fix to `filter.cpp`, run `python validate.py`, expect "OK". Then restore.

- [ ] **Step 8: Commit**
```bash
git add benchmarks/cases/cpp/cpp_iterator_invalidation_trap/
```

---

## Task 2: cpp_string_view_lifetime_trap

**Bug:** Off-by-one in `substr` indices — `input.substr(open, close - open)` includes the `[` and excludes the content boundary. The "trap" is that reviewers focus on `string_view` lifetime instead of the offset arithmetic.

**Files:**
- Create: `benchmarks/cases/cpp/cpp_string_view_lifetime_trap/case.json`
- Create: buggy_repo with `processor.h`, `processor.cpp`, `main.cpp`, `validate.py`

- [ ] **Step 1: Create processor.h**
```cpp
#ifndef PROCESSOR_H
#define PROCESSOR_H
#include <string_view>
std::string_view extract_bracket_content(std::string_view input);
#endif
```

- [ ] **Step 2: Create processor.cpp (buggy)**
```cpp
#include "processor.h"

std::string_view extract_bracket_content(std::string_view input) {
    std::size_t open  = input.find('[');
    std::size_t close = input.rfind(']');
    if (open  == std::string_view::npos ||
        close == std::string_view::npos ||
        close <= open) {
        return {};
    }
    // BUG: off-by-one — includes '[' and excludes ']' content
    return input.substr(open, close - open);
}
```

Correct fix (`processor.cpp` only):
```cpp
    return input.substr(open + 1, close - open - 1);
```

- [ ] **Step 3: Create main.cpp (test)**
```cpp
#include "processor.h"
#include <cstdlib>
#include <iostream>
#include <string_view>

static void assert_sv(std::string_view actual, std::string_view expected, const char* msg) {
    if (actual != expected) {
        std::cerr << "FAIL: " << msg
                  << ": expected '" << expected << "', got '" << actual << "'\n";
        std::exit(1);
    }
}

int main() {
    assert_sv(extract_bracket_content("[hello]"),          "hello", "simple bracketed word");
    assert_sv(extract_bracket_content("prefix[world]end"), "world", "embedded brackets");
    assert_sv(extract_bracket_content("[x]"),              "x",     "single char");
    assert_sv(extract_bracket_content("no brackets"),      "",      "no brackets");
    assert_sv(extract_bracket_content("["),                "",      "unclosed bracket");
    std::cout << "OK\n";
    return 0;
}
```

- [ ] **Step 4: Create validate.py** (same pattern, compile `main.cpp processor.cpp`)

- [ ] **Step 5: Create case.json**
```json
{
  "name": "cpp_string_view_lifetime_trap",
  "language": "cpp",
  "category": "logic_error",
  "difficulty": "medium",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "python validate.py",
  "expected_changed_files": ["processor.cpp"],
  "forbidden_changed_files": ["main.cpp", "processor.h", "validate.py"],
  "allowed_generated_files": [],
  "prompt": "Fix the C++ string_view extraction bug.\n\nRequirements:\n- Modify processor.cpp only.\n- extract_bracket_content must return the content between the outermost '[' and ']' in input.\n- The '[' and ']' delimiters must NOT be included in the return value.\n- If no valid bracket pair exists, return an empty string_view.\n- Do not modify main.cpp, processor.h, or validate.py.\n- Do not create new files.\n- Use patch_candidate if only extract_bracket_content changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: python validate.py"
}
```

- [ ] **Step 6: Verify pre-fix failure and post-fix pass, restore**

---

## Task 3: csharp_async_missing_await_trap

**Bug:** `GetCountAsync()` is called without `await` in `SummarizeAsync()`, so `count` holds a `Task<int>` object and the interpolated string becomes `"Total: System.Threading.Tasks.Task`1[System.Int32]"`.

**Files:**
- Create: `benchmarks/cases/csharp/csharp_async_missing_await_trap/case.json`
- Create: buggy_repo with `App.csproj`, `DataService.cs`, `Program.cs`

- [ ] **Step 1: Create App.csproj**
```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
```

- [ ] **Step 2: Create DataService.cs (buggy)**
```csharp
namespace App;

public static class DataService
{
    public static Task<int> GetCountAsync() => Task.FromResult(42);

    public static async Task<string> SummarizeAsync()
    {
        // BUG: missing await — count is Task<int>, not int
        var count = GetCountAsync();
        return $"Total: {count}";
    }
}
```

Correct fix (`DataService.cs` only):
```csharp
        var count = await GetCountAsync();
```

- [ ] **Step 3: Create Program.cs (test harness)**
```csharp
namespace App;

class Program
{
    static async Task Main()
    {
        var result = await DataService.SummarizeAsync();
        if (result != "Total: 42")
        {
            Console.Error.WriteLine($"FAIL: expected 'Total: 42', got '{result}'");
            Environment.Exit(1);
        }
        Console.WriteLine("OK");
    }
}
```

- [ ] **Step 4: Create case.json**
```json
{
  "name": "csharp_async_missing_await_trap",
  "language": "csharp",
  "category": "async_error",
  "difficulty": "easy",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "dotnet run",
  "expected_changed_files": ["DataService.cs"],
  "forbidden_changed_files": ["Program.cs", "App.csproj"],
  "allowed_generated_files": [],
  "prompt": "Fix the C# async/await bug in DataService.cs.\n\nRequirements:\n- Modify DataService.cs only.\n- SummarizeAsync must return \"Total: 42\" (the integer value, not the Task object).\n- GetCountAsync must be awaited.\n- Do not modify Program.cs or App.csproj.\n- Do not create new files.\n- Use patch_candidate if only SummarizeAsync changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: dotnet run"
}
```

- [ ] **Step 5: Verify pre-fix failure (output contains Task typename, exit 1) and post-fix pass**

Note: requires `dotnet` on PATH. dotnet 10.0.203 is installed on this machine.

---

## Task 4: csharp_linq_deferred_execution_trap

**Bug:** `GetPassing` returns a deferred LINQ `IEnumerable<int>`. After the caller adds an element to `scores` and then iterates the returned enumerable, the count is 4 instead of the expected 3 (deferred execution reflects post-mutation state).

**Files:**
- Create: `benchmarks/cases/csharp/csharp_linq_deferred_execution_trap/case.json`
- Create: buggy_repo with `App.csproj`, `ScoreReport.cs`, `Program.cs`

- [ ] **Step 1: Create App.csproj** (identical to Task 3)

- [ ] **Step 2: Create ScoreReport.cs (buggy)**
```csharp
namespace App;

public static class ScoreReport
{
    // BUG: deferred LINQ query — reflects mutations to scores made after this call
    public static IEnumerable<int> GetPassing(List<int> scores, int threshold) =>
        scores.Where(s => s >= threshold);
}
```

Correct fix (`ScoreReport.cs` only):
```csharp
    public static IEnumerable<int> GetPassing(List<int> scores, int threshold) =>
        scores.Where(s => s >= threshold).ToList();
```

- [ ] **Step 3: Create Program.cs (test harness)**
```csharp
namespace App;

class Program
{
    static void Main()
    {
        var scores = new List<int> { 50, 60, 70, 80 };
        var passing = ScoreReport.GetPassing(scores, 60);

        // Mutate the source after calling GetPassing
        scores.Add(100);

        // Deferred execution: if not materialized, reflects the mutation → count = 4
        var count = passing.Count();
        if (count != 3)
        {
            Console.Error.WriteLine($"FAIL: expected 3 passing scores, got {count}");
            Environment.Exit(1);
        }
        Console.WriteLine("OK");
    }
}
```

- [ ] **Step 4: Create case.json**
```json
{
  "name": "csharp_linq_deferred_execution_trap",
  "language": "csharp",
  "category": "logic_error",
  "difficulty": "medium",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "dotnet run",
  "expected_changed_files": ["ScoreReport.cs"],
  "forbidden_changed_files": ["Program.cs", "App.csproj"],
  "allowed_generated_files": [],
  "prompt": "Fix the C# LINQ deferred execution bug in ScoreReport.cs.\n\nRequirements:\n- Modify ScoreReport.cs only.\n- GetPassing must return a snapshot of matching scores at the time of the call.\n- Subsequent mutations to the scores list must not affect the returned collection.\n- The return type must remain IEnumerable<int>.\n- Do not modify Program.cs or App.csproj.\n- Do not create new files.\n- Use patch_candidate if only GetPassing changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: dotnet run"
}
```

- [ ] **Step 5: Verify pre-fix failure and post-fix pass**

---

## Task 5: rust_error_context_breaks_matching

**Bug:** `parse_field("")` and `parse_field("  ")` return `Err(ParseError::Invalid)` instead of `Err(ParseError::Empty)`. The `match` in `main.rs` fails because it expects `ParseError::Empty`.

**Files:**
- Create: `benchmarks/cases/rust/rust_error_context_breaks_matching/case.json`
- Create: buggy_repo with `Cargo.toml`, `src/parse.rs`, `src/main.rs`

- [ ] **Step 1: Create Cargo.toml**
```toml
[package]
name = "rust_error_context_breaks_matching"
version = "0.1.0"
edition = "2021"

[dependencies]
```

- [ ] **Step 2: Create src/parse.rs (buggy)**
```rust
#[derive(Debug, PartialEq)]
pub enum ParseError {
    Empty,
    Invalid,
}

pub fn parse_field(s: &str) -> Result<i32, ParseError> {
    // BUG: maps all parse failures to ParseError::Invalid,
    // but empty/whitespace-only input should return ParseError::Empty
    s.trim()
        .parse::<i32>()
        .map_err(|_| ParseError::Invalid)
}
```

Correct fix (`src/parse.rs` only):
```rust
pub fn parse_field(s: &str) -> Result<i32, ParseError> {
    let trimmed = s.trim();
    if trimmed.is_empty() {
        return Err(ParseError::Empty);
    }
    trimmed.parse::<i32>().map_err(|_| ParseError::Invalid)
}
```

- [ ] **Step 3: Create src/main.rs (test)**
```rust
mod parse;
use parse::{parse_field, ParseError};

fn main() {
    // valid integer
    match parse_field("42") {
        Ok(42) => {}
        other => panic!("valid integer: expected Ok(42), got {:?}", other),
    }

    // empty string must return Empty variant, not Invalid
    match parse_field("") {
        Err(ParseError::Empty) => {}
        other => panic!("empty string: expected Err(Empty), got {:?}", other),
    }

    // whitespace-only must return Empty variant
    match parse_field("   ") {
        Err(ParseError::Empty) => {}
        other => panic!("whitespace: expected Err(Empty), got {:?}", other),
    }

    // non-numeric must return Invalid
    match parse_field("abc") {
        Err(ParseError::Invalid) => {}
        other => panic!("non-numeric: expected Err(Invalid), got {:?}", other),
    }

    println!("OK");
}
```

- [ ] **Step 4: Create case.json**
```json
{
  "name": "rust_error_context_breaks_matching",
  "language": "rust",
  "category": "error_handling",
  "difficulty": "easy",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "cargo run",
  "expected_changed_files": ["src/parse.rs"],
  "forbidden_changed_files": ["src/main.rs", "Cargo.toml"],
  "allowed_generated_files": [],
  "prompt": "Fix the Rust error variant bug in src/parse.rs.\n\nRequirements:\n- Modify src/parse.rs only.\n- parse_field must return Err(ParseError::Empty) for empty and whitespace-only input.\n- parse_field must return Err(ParseError::Invalid) for non-numeric input.\n- parse_field must return Ok(value) for valid integer strings (with optional whitespace).\n- Do not modify src/main.rs or Cargo.toml.\n- Do not create new files.\n- Use patch_candidate if only parse_field changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: cargo run"
}
```

- [ ] **Step 5: Verify pre-fix failure and post-fix pass**

---

## Task 6: rust_path_normalization_security_trap

**Bug:** `safe_resolve` joins `base` and `user_input` without normalizing `..` components, allowing path traversal outside the base directory.

**Files:**
- Create: `benchmarks/cases/rust/rust_path_normalization_security_trap/case.json`
- Create: buggy_repo with `Cargo.toml`, `src/path_guard.rs`, `src/main.rs`

- [ ] **Step 1: Create Cargo.toml**
```toml
[package]
name = "rust_path_normalization_security_trap"
version = "0.1.0"
edition = "2021"

[dependencies]
```

- [ ] **Step 2: Create src/path_guard.rs (buggy)**
```rust
use std::path::{Path, PathBuf};

/// Returns the resolved path if it is safely within `base`, otherwise None.
pub fn safe_resolve(base: &Path, user_input: &str) -> Option<PathBuf> {
    // BUG: joins without normalising '..' components — allows path traversal
    Some(base.join(user_input))
}
```

Correct fix (`src/path_guard.rs` only):
```rust
use std::path::{Component, Path, PathBuf};

fn normalize(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for c in path.components() {
        match c {
            Component::ParentDir => { out.pop(); }
            Component::CurDir    => {}
            other                => out.push(other),
        }
    }
    out
}

pub fn safe_resolve(base: &Path, user_input: &str) -> Option<PathBuf> {
    let joined   = base.join(user_input);
    let resolved = normalize(&joined);
    let base_n   = normalize(base);
    if resolved.starts_with(&base_n) { Some(resolved) } else { None }
}
```

- [ ] **Step 3: Create src/main.rs (test)**
```rust
mod path_guard;
use path_guard::safe_resolve;
use std::path::Path;

fn main() {
    let base = Path::new("files");

    // safe path should resolve and remain under base
    let r = safe_resolve(base, "readme.txt");
    assert!(r.is_some(), "safe path: expected Some, got None");
    assert!(r.unwrap().starts_with(base), "safe path: must be under base");

    // direct traversal must be rejected
    let r = safe_resolve(base, "../secret.txt");
    assert!(r.is_none(), "traversal '../secret.txt': expected None");

    // nested traversal that escapes base must be rejected
    let r = safe_resolve(base, "sub/../../etc/passwd");
    assert!(r.is_none(), "traversal 'sub/../../etc/passwd': expected None");

    // subdirectory should resolve
    let r = safe_resolve(base, "sub/data.txt");
    assert!(r.is_some(), "subdirectory path: expected Some, got None");
    assert!(r.unwrap().starts_with(base), "subdirectory path: must be under base");

    println!("OK");
}
```

- [ ] **Step 4: Create case.json**
```json
{
  "name": "rust_path_normalization_security_trap",
  "language": "rust",
  "category": "security",
  "difficulty": "medium",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "cargo run",
  "expected_changed_files": ["src/path_guard.rs"],
  "forbidden_changed_files": ["src/main.rs", "Cargo.toml"],
  "allowed_generated_files": [],
  "prompt": "Fix the Rust path traversal security bug in src/path_guard.rs.\n\nRequirements:\n- Modify src/path_guard.rs only.\n- safe_resolve must return None for any user_input that resolves to a path outside base after normalising '..' components.\n- safe_resolve must return Some(resolved_path) for inputs that stay within base.\n- Do not use std::fs::canonicalize (filesystem access not required).\n- Do not modify src/main.rs or Cargo.toml.\n- Do not create new files.\n- Use patch_candidate if only safe_resolve changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: cargo run"
}
```

- [ ] **Step 5: Verify pre-fix failure and post-fix pass**

---

## Task 7: python_regex_boundary_false_fix

**Bug:** `count_word` uses `re.escape(word)` without `\b` word-boundary anchors, so it matches substrings within larger words (e.g., "cat" matches inside "catfish" and "concatenate").

**Files:**
- Create: `benchmarks/cases/python/python_regex_boundary_false_fix/case.json`
- Create: buggy_repo with `regex_utils.py`, `main.py`

- [ ] **Step 1: Create regex_utils.py (buggy)**
```python
import re


def count_word(text: str, word: str) -> int:
    """Count occurrences of word as a standalone word in text."""
    # BUG: no word boundaries; matches substrings inside larger words
    pattern = re.escape(word)
    return len(re.findall(pattern, text, re.IGNORECASE))
```

Correct fix (`regex_utils.py` only):
```python
    pattern = r'\b' + re.escape(word) + r'\b'
```

- [ ] **Step 2: Create main.py (test)**
```python
import sys
from regex_utils import count_word


def check(actual: int, expected: int, message: str) -> None:
    if actual != expected:
        print(f"FAIL: {message}: expected {expected}, got {actual}", file=sys.stderr)
        sys.exit(1)


# "cat" must not match inside "catfish" or "concatenate"
check(count_word("cat catfish concatenate", "cat"), 1, "cat as standalone only")
# "cat" standalone in a sentence
check(count_word("the cat sat on the mat", "cat"), 1, "cat in sentence")
# plural and related words must not count
check(count_word("cats cat category", "cat"), 1, "cats and category should not count")
# multiple standalone occurrences
check(count_word("hello world hello", "hello"), 2, "hello twice")
# no match
check(count_word("no match here", "xyz"), 0, "no match")
print("OK")
```

- [ ] **Step 3: Create case.json**
```json
{
  "name": "python_regex_boundary_false_fix",
  "language": "python",
  "category": "logic_error",
  "difficulty": "easy",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "python main.py",
  "expected_changed_files": ["regex_utils.py"],
  "forbidden_changed_files": ["main.py"],
  "allowed_generated_files": [],
  "prompt": "Fix the Python regex word-boundary bug in regex_utils.py.\n\nRequirements:\n- Modify regex_utils.py only.\n- count_word must count occurrences of word only when it appears as a standalone word (not as a substring of a larger word).\n- The match must be case-insensitive.\n- Do not modify main.py.\n- Do not create new files.\n- Use patch_candidate if only count_word changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: python main.py"
}
```

- [ ] **Step 4: Verify pre-fix failure and post-fix pass**

---

## Task 8: ts_async_cache_stale_promise_trap

**Bug:** `cachedFetch` stores resolved values under `key.toUpperCase()` but looks them up under the original `key`, so the cache never hits and `fetcher` is always called again.

**Files:**
- Create: `benchmarks/cases/typescript/ts_async_cache_stale_promise_trap/case.json`
- Create: buggy_repo with `cache.ts`, `main.ts`

- [ ] **Step 1: Create cache.ts (buggy)**
```typescript
const store = new Map<string, string>();

export async function cachedFetch(
    key: string,
    fetcher: (k: string) => Promise<string>,
): Promise<string> {
    const hit = store.get(key);
    if (hit !== undefined) return hit;
    const result = await fetcher(key);
    // BUG: stores under wrong key — cache lookup uses `key` but storage uses `key.toUpperCase()`
    store.set(key.toUpperCase(), result);
    return result;
}

export function clearCache(): void {
    store.clear();
}
```

Correct fix (`cache.ts` only):
```typescript
    store.set(key, result);
```

- [ ] **Step 2: Create main.ts (test)**
```typescript
import { cachedFetch, clearCache } from "./cache.ts";

async function main(): Promise<void> {
    let callCount = 0;
    const fetcher = async (k: string): Promise<string> => {
        callCount++;
        return `value_${k}`;
    };

    clearCache();
    callCount = 0;

    // first call: must fetch
    const r1 = await cachedFetch("foo", fetcher);
    if (r1 !== "value_foo") throw new Error(`r1: expected 'value_foo', got '${r1}'`);
    if (callCount !== 1) throw new Error(`after first call: expected 1 fetch, got ${callCount}`);

    // second call: must hit the cache, not call fetcher again
    const r2 = await cachedFetch("foo", fetcher);
    if (r2 !== "value_foo") throw new Error(`r2: expected 'value_foo', got '${r2}'`);
    if (callCount !== 1) throw new Error(`after second call: expected 1 fetch (cache hit), got ${callCount}`);

    // different key: must fetch again
    const r3 = await cachedFetch("bar", fetcher);
    if (r3 !== "value_bar") throw new Error(`r3: expected 'value_bar', got '${r3}'`);
    if (callCount !== 2) throw new Error(`after third call (new key): expected 2 fetches, got ${callCount}`);

    console.log("OK");
}

main().catch(err => {
    process.stderr.write(`FAIL: ${err.message}\n`);
    process.exit(1);
});
```

- [ ] **Step 3: Create case.json**
```json
{
  "name": "ts_async_cache_stale_promise_trap",
  "language": "typescript",
  "category": "async_error",
  "difficulty": "medium",
  "agent_mode": "reviewer",
  "patch_style": "balanced",
  "validation_command": "node --experimental-strip-types main.ts",
  "expected_changed_files": ["cache.ts"],
  "forbidden_changed_files": ["main.ts"],
  "allowed_generated_files": [],
  "prompt": "Fix the TypeScript async cache bug in cache.ts.\n\nRequirements:\n- Modify cache.ts only.\n- cachedFetch must return the same value for the same key without calling fetcher again.\n- The cache key must be consistent between storage and lookup.\n- Do not modify main.ts.\n- Do not create new files.\n- Use patch_candidate if only cachedFetch changes.\n- target_snippet must be copied verbatim from the actual file.\n\nValidation command: node --experimental-strip-types main.ts"
}
```

- [ ] **Step 4: Verify pre-fix failure and post-fix pass**

---

## Task 9: Update Suite Manifests

- [ ] **Step 1: Update full_v1.json** — add 8 new cases, update description to "50"

- [ ] **Step 2: Update dev_v1.json** — add 4 new dev cases

- [ ] **Step 3: Update held_out_v1.json** — add 4 new held-out cases

---

## Task 10: Update test_benchmark_suites.py

The test `test_full_discovery_matches_full_suite_manifest` currently says `len(discovered_names) == 41` (stale; currently 42 cases). Update to 50.

Add the 4 new held-out cases to the `HELD_OUT_CASES` list so `test_held_out_manifest_contains_suggested_cases` passes.

- [ ] **Step 1: Update `len(discovered_names) == 41` → `== 50`**

- [ ] **Step 2: Add new held-out cases to HELD_OUT_CASES**

```python
NEW_HELD_OUT_CASES_11PREP = [
    "cpp_string_view_lifetime_trap",
    "csharp_linq_deferred_execution_trap",
    "rust_path_normalization_security_trap",
    "ts_async_cache_stale_promise_trap",
]

HELD_OUT_CASES = [
    ...existing...,
    *NEW_HELD_OUT_CASES_11PREP,
]
```

---

## Task 11: Final Validation

- [ ] **Step 1: Run `python benchmarks/run_benchmarks.py --check`**

Expected: `Checked: 50 / Errors: 0`

- [ ] **Step 2: Run benchmark suite tests**

```
python -m pytest tests/test_benchmark_suites.py -v
```
Expected: all pass

- [ ] **Step 3: Run full pytest (optional, if feasible)**

```
python -m pytest tests/ -x -q
```

---

## C# Toolchain Note

C# cases require `dotnet` on PATH. This machine has dotnet 10.0.203. `--check` mode does not execute validation commands so these cases pass `--check` without dotnet. For full benchmark runs, `dotnet` must be available. The `csharp` language is not in `LANGUAGE_TOOLCHAINS` in `run_benchmarks.py`; `--skip-toolchain-failures` will not auto-skip C# cases if dotnet is absent.
