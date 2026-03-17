# RFC: PyTorch Test Suite Configuration for OOT Device

**Authors:**

- Anubhav Jana (IBM Research, India)
- Ashok Pon Kumar Sree Prakash (IBM Research, India)

*Reference implementation: IBM Spyre*

---

## 1. Motivation

PyTorch provides a large suite of upstream tests that validate operator correctness across devices. For out-of-tree (OOT) device backends registered via `privateuse1`, reusing these upstream tests is preferable to writing new ones — it ensures the same correctness bar and reduces maintenance burden.

However, OOT devices typically support a subset of ops and dtypes, and some tests may be known to fail, crash, or require special tolerance settings. Running the full upstream suite without filtering would result in thousands of failures and crashes that obscure real signal.

This RFC defines a YAML-based configuration schema that allows an OOT device team to:

- Declare which ops and dtypes their device supports
- Select which upstream tests to run, skip, or mark as expected failures
- Express per-op and per-test tolerance overrides
- Tag tests with model names for traceability
- Gradually expand test coverage as the device matures

---

## 2. Background

### 2.1 How upstream PyTorch tests work

Upstream PyTorch tests use the `@ops` decorator to parametrize test methods across all ops in `op_db` and all dtypes supported by those ops:

```python
@ops(binary_ufuncs, allowed_dtypes=(torch.float32, torch.float16))
def test_scalar_support(self, device, dtype, op):
    ...
```

At collection time, `@ops` generates one test variant per `(op, dtype)` combination. For a device to participate, it must register a `TestBase` subclass via `TORCH_TEST_DEVICES` and implement `instantiate_test`.

### 2.2 The Spyre test framework

The Spyre framework hooks into this mechanism via `SpyreTestBase` which:

1. Loads the YAML config on first `instantiate_test` call
2. Patches `@ops.op_list` directly to restrict which ops generate variants (`_SpyreOpListPatcher`)
3. Patches `@onlyOn` to allow the `spyre` device type (`_SpyreOnlyOnPatcher`)
4. Injects extra dtypes into `@ops.allowed_dtypes` (`_SpyreDtypePatcher`)
5. Applies skip, xfail, or mandatory_success to each generated variant

---

## 3. Configuration File

The configuration is a YAML file pointed to by the `SPYRE_PYTORCH_TEST_CONFIG` environment variable.

### 3.1 Top-level structure

```yaml
test_suite_config:
  files:
    - ...   # one entry per upstream test file
  global:
    supported_dtypes: [...]
    supported_ops:
      - ...
```

| Field | Required | Description |
|---|---|---|
| `test_suite_config` | Yes | Root key |
| `files` | Yes | List of upstream test file entries |
| `global` | No | Device-wide capability declaration |

---

## 4. File Entry

Each entry under `files` corresponds to one upstream test file.

```yaml
- rel_path: ${PYTORCH}/test/test_binary_ufuncs.py
  unlisted_test_mode: xfail
  tests:
    - ...
```

| Field | Required | Default | Description |
|---|---|---|---|
| `rel_path` | Yes | — | Path to the upstream test file. Supports `${PYTORCH}` and `${TORCH_SPYRE}` tokens resolved from env vars `SPYRE_PYTORCH_ROOT` and `SPYRE_TORCH_SPYRE_ROOT` |
| `unlisted_test_mode` | No | `xfail` | Mode applied to tests not listed under `tests`, or listed without an explicit `mode` |
| `tests` | No | `[]` | List of test entries with explicit configuration |

### 4.1 `unlisted_test_mode`

Controls the behaviour for tests that are **not explicitly listed** in `tests`, or are listed but have **no `mode` field**.

| Value | Behaviour |
|---|---|
| `block` | Skip entirely. Use when the file is under active development and most tests are not yet ready |
| `xfail` | Run but mark as expected failure. **Default.** Use when the device broadly supports the op set but individual tests may still fail |
| `xfail_strict` | Run and mark as `xfail(strict=True)`. Fails the suite if the test unexpectedly passes — use when you want to be notified of unexpected improvements |
| `mandatory_success` | Must pass. Use with caution — any new upstream test added to the file will immediately break the suite |

**When to use each:**

```
New device, early stage:
  unlisted_test_mode: block             <- only run what you explicitly list

Device broadly working, tracking regressions:
  unlisted_test_mode: xfail             <- run everything, failures expected

Stable device, enforcing correctness:
  unlisted_test_mode: mandatory_success  <- everything must pass
```

---

## 5. Test Entry

Each entry under `tests` configures a specific upstream test method.

```yaml
- test: TestBinaryUfuncs::test_scalar_support
  mode: xfail
  tags:
    - model_name_depending_on_this_test_1
  edits:
    ops:
      include:
        - name: add
      exclude:
        - name: gcd
    dtypes:
      include:
        - name: float16
        - name: int64
      exclude:
        - name: bfloat16
```

| Field | Required | Default | Description |
|---|---|---|---|
| `test` | Yes | — | `ClassName::method_name` identifying the upstream test |
| `mode` | No | `unlisted_test_mode` | How to treat this test's variants |
| `tags` | No | `[]` | Pytest mark labels applied to all variants of this test |
| `edits` | No | — | Per-test overrides for ops and dtypes |

### 5.1 Test `mode`

Applied at the **variant level** — each `(test, op, dtype)` combination is treated independently.

| Value | Behaviour |
|---|---|
| `mandatory_success` | Variant must pass. Fails the suite if it does not |
| `xfail` | Variant is expected to fail. Passes the suite either way |
| `xfail_strict` | Variant must fail. Fails the suite if it unexpectedly passes |
| `block` | Variant is skipped entirely with a skip message |

**`mode` vs `unlisted_test_mode` precedence:**

```
test listed with explicit mode    → test mode governs
test listed without mode          → unlisted_test_mode governs
test not listed at all            → unlisted_test_mode governs
```

### 5.2 Tags

Tags are registered as pytest marks on every variant of the test. This enables test selection by model name:

```bash
pytest test_binary_ufuncs.py -m model_name_depending_on_this_test_1
pytest test_binary_ufuncs.py -m "model_a or model_b"
pytest test_binary_ufuncs.py -m "not model_a"
```

Tags must be valid Python identifiers (no spaces or special characters).

### 5.3 Edits

`edits` allows per-test overrides on top of the global configuration. All edits are scoped to the specific test — they do not affect other tests.

#### 5.3.1 `edits.ops`

Controls which ops are included in `@ops.op_list` for this specific test.

```yaml
edits:
  ops:
    include:
      - name: add    # inject add into @ops.op_list for this test
    exclude:
      - name: gcd    # remove gcd from @ops.op_list for this test
```

| Field | When to use |
|---|---|
| `include` | The test uses a pre-filtered op list (e.g. `binary_ufuncs_with_references`) that excludes an op you want to test. Injects the op into `@ops.op_list` at instantiation time |
| `exclude` | The op is in `supported_ops` and in the test's `@ops.op_list`, but you want to suppress it for this specific test only |

> **Note on `include`:** This is only needed when the upstream test uses a filtered list that excludes your op. For example, `binary_ufuncs_with_references = [op for op in binary_ufuncs if op.ref is not None]` excludes ops without a reference implementation. If `gcd` has no `ref`, you cannot test it via `test_scalar_support` without injecting it via `include`.

Both `include` and `exclude` are lists of dicts with a `name` field, kept consistent for future extensibility (e.g. adding per-op precision overrides at the test level).

#### 5.3.2 `edits.dtypes`

Controls which dtype variants are generated for this test.

```yaml
edits:
  dtypes:
    include:
      - name: float16
      - name: int64
    exclude:
      - name: bfloat16
```

| Field | When to use |
|---|---|
| `include` | Inject a dtype that the upstream `@ops(allowed_dtypes=(...))` does not include. Without this, the variant is never generated and cannot be tested |
| `exclude` | Suppress a dtype variant for this test only. Useful when a specific `(test, dtype)` combination is known to crash or produce incorrect results |

**Dtype precedence chain:**

The effective dtypes for a given test variant are computed as:

```
effective_dtypes =
    (global.supported_dtypes ∩ op.dtypes ∩ test.allowed_dtypes)     <- base intersection
    + (global.supported_dtypes ∩ op.dtypes ∩ edits.dtypes.include)  <- injected dtypes
    - edits.dtypes.exclude                                          <- removed dtypes
```

Where:

- `global.supported_dtypes` — hardware capability ceiling. Acts as a hard cap. Cannot be overridden.
- `op.dtypes` — op-level dtype override from `global.supported_ops[op].dtypes`. If not specified, defaults to `global.supported_dtypes`.
- `test.allowed_dtypes` — upstream `@ops(allowed_dtypes=(...))` constraint from the test source code.
- `edits.dtypes.include` — must be a subset of `global.supported_dtypes`. A validation error is raised otherwise.
- `edits.dtypes.exclude` — applied last, after all inclusions.

**Validation rule:** If `edits.dtypes.include` contains a dtype not in `global.supported_dtypes`, the config is rejected at load time:

```
ValidationError: edits.dtypes.include contains 'float32' which is not in
global.supported_dtypes [float16, int64].
edits.dtypes.include must be a subset of global.supported_dtypes.
```

---

## 6. Global Configuration

Declares the device-wide capability baseline. All file and test entries operate within these bounds.

```yaml
global:
  supported_dtypes:
    - float16
    - int64
  supported_ops:
    - name: add
      force_xfail: false
      dtypes:
        - name: float16
          precision:
            atol: 1e-3
            rtol: 1e-3
        - name: int64
    - name: mul
    - name: sub
    - name: gcd
      force_xfail: true
```

| Field | Required | Description |
|---|---|---|
| `supported_dtypes` | Yes | Device-wide supported dtypes. Acts as a hard ceiling for all dtype filtering |
| `supported_ops` | Yes | List of ops the device supports. Only ops listed here generate test variants |

### 6.1 `supported_dtypes`

The complete set of dtypes the device hardware supports. This is the outermost constraint — no test variant will run with a dtype outside this list regardless of any other configuration.

If omitted, no dtype filtering is applied at the global level.

### 6.2 `supported_ops`

Each entry declares one op the device supports and configures how tests exercising that op behave.

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | Yes | — | Op name matching `OpInfo.name` in upstream `op_db` |
| `force_xfail` | No | `false` | If `true`, flips any `mandatory_success` variant for this op to `xfail`. Has no effect on variants already marked `xfail` or `xfail_strict` |
| `dtypes` | No | `global.supported_dtypes` | Op-level dtype override. Must be a subset of `global.supported_dtypes` |

#### 6.2.1 `force_xfail` behaviour

`force_xfail` operates at the **variant level**, not the test level. Since `@ops` generates one variant per `(op, dtype)` combination, `force_xfail` on an op affects only variants for that specific op:

```
test_scalar_support_add_float16:
  test mode: mandatory_success, add.force_xfail: false  ->  mandatory_success

test_scalar_support_gcd_float16:
  test mode: mandatory_success, gcd.force_xfail: true   ->  xfail (flipped)

test_scalar_support_gcd_float16:
  test mode: xfail,             gcd.force_xfail: true   ->  xfail (unchanged)

test_scalar_support_gcd_float16:
  test mode: xfail_strict,      gcd.force_xfail: true   ->  xfail_strict (unchanged)
```

`force_xfail` only flips `mandatory_success` → `xfail`. It never changes `xfail`, `xfail_strict`, or `block`.

> **When to use `force_xfail: true`:** When an op is in `supported_ops` (so variants are generated) but is not yet stable enough to require passing. This allows tracking which tests exercise the op without committing to a correctness guarantee.

#### 6.2.2 Op-level `dtypes`

Narrows the dtype variants generated for this op across all tests. Must be a subset of `global.supported_dtypes`. If op-level `dtypes` contains a dtype not in `global.supported_dtypes`, a validation error is raised.

Each dtype entry can optionally specify tolerance overrides:

```yaml
dtypes:
  - name: float16
    precision:
      atol: 1e-3
      rtol: 1e-3
  - name: int64       # no precision override, uses framework default
```

Precision overrides apply to all test variants for this `(op, dtype)` combination.

---

## 7. Scenarios

### 7.1 New model to be supported

A model depends on `add` and `mul`. You want to run the tests that exercise these ops and verify they pass.

```yaml
test_suite_config:
  files:
    - rel_path: ${PYTORCH}/test/test_binary_ufuncs.py
      unlisted_test_mode: block       # only run what is listed
      tests:
        - test: TestBinaryUfuncs::test_scalar_support
          mode: mandatory_success
          tags:
            - my_model
        - test: TestBinaryUfuncs::test_contig_vs_transposed
          mode: mandatory_success
          tags:
            - my_model

  global:
    supported_dtypes: [float16, int64]
    supported_ops:
      - name: add
      - name: mul
```

Another model team wants to reuse the same op tests — they add their tag without changing anything else:

```yaml
- test: TestBinaryUfuncs::test_scalar_support
  mode: mandatory_success
  tags:
    - my_model
    - another_model    # <- added, no other change needed
```

### 7.2 New op supported by device

`gcd` is newly supported. You want to run all upstream tests that exercise `gcd`, with failures expected while it stabilises.

```yaml
test_suite_config:
  files:
    - rel_path: ${PYTORCH}/test/test_binary_ufuncs.py
      unlisted_test_mode: xfail       # run everything, failures expected
      tests:
        - test: ....
          mode: mandatory_success

  global:
    supported_dtypes: [float16, int64]
    supported_ops:
      - name: gcd
        force_xfail: true             # all variants expected to fail initially
```

As `gcd` stabilises, flip `force_xfail: false` and move specific tests to `mandatory_success`.

### 7.3 Known crash — suppress a specific test

`test_add` causes a segfault. Block it entirely:

```yaml
- test: TestBinaryUfuncs::test_add
  mode: block
  # Signal 11 - Segmentation fault
```

### 7.4 Tolerance override for a specific op

`add` passes on `float16` but requires looser tolerance:

```yaml
global:
  supported_ops:
    - name: add
      dtypes:
        - name: float16
          precision:
            atol: 1e-3
            rtol: 1e-3
```

### 7.5 Test uses a filtered op list — inject an op

`test_scalar_support` uses `binary_ufuncs_with_references` which only includes ops with a `ref`. If `gcd` has no `ref`, it is excluded from that list. To test it anyway:

```yaml
- test: TestBinaryUfuncs::test_scalar_support
  mode: xfail
  edits:
    ops:
      include:
        - name: gcd     # gcd has no ref so binary_ufuncs_with_references excludes it
                        # include injects it into @ops.op_list for this test only
```

---

## 8. Field Reference Summary

### File entry

| Field | Type | Required | Default |
|---|---|---|---|
| `rel_path` | string | Yes | — |
| `unlisted_test_mode` | enum | No | `xfail` |
| `tests` | list | No | `[]` |

### Test entry

| Field | Type | Required | Default |
|---|---|---|---|
| `test` | string (`ClassName::method_name`) | Yes | — |
| `mode` | enum | No | `unlisted_test_mode` |
| `tags` | list of strings | No | `[]` |
| `edits.ops.include` | list of `{name}` | No | `[]` |
| `edits.ops.exclude` | list of `{name}` | No | `[]` |
| `edits.dtypes.include` | list of `{name}` | No | `[]` |
| `edits.dtypes.exclude` | list of `{name}` | No | `[]` |

### Global

| Field | Type | Required | Default |
|---|---|---|---|
| `supported_dtypes` | list of dtype strings | Yes | no filtering |
| `supported_ops` | list of op entries | Yes | no filtering |

### Supported op entry

| Field | Type | Required | Default |
|---|---|---|---|
| `name` | string | Yes | — |
| `force_xfail` | bool | No | `false` |
| `dtypes` | list of `{name, precision?}` | No | `supported_dtypes` |

### Precision

| Field | Type | Required | Default |
|---|---|---|---|
| `atol` | float | No | framework default |
| `rtol` | float | No | framework default |

---

## 9. Validation Rules

1. `test` must match `ClassName::method_name` pattern
2. `mode` and `unlisted_test_mode` must be one of `mandatory_success`, `xfail`, `xfail_strict`, `block`
3. All dtype strings must be valid PyTorch dtype names
4. `edits.dtypes.include` must be a subset of `global.supported_dtypes`
5. `supported_ops[*].dtypes` must be a subset of `global.supported_dtypes`
6. If `supported_ops[*].dtypes` ∩ `global.supported_dtypes` is empty, a warning is emitted
7. `tags` must be valid Python identifiers (used as pytest mark names)
8. `rel_path` tokens (`${PYTORCH}`, `${TORCH_SPYRE}`) must resolve via environment variables at load time

---

## 10. Environment Variables

| Variable | Description |
|---|---|
| `SPYRE_PYTORCH_TEST_CONFIG` | Path to the YAML config file |
| `SPYRE_PYTORCH_ROOT` | Resolves `${PYTORCH}` token in `rel_path` |
| `SPYRE_TORCH_SPYRE_ROOT` | Resolves `${TORCH_SPYRE}` token in `rel_path` |
| `PYTORCH_TESTING_DEVICE_ONLY_FOR` | Must be set to `privateuse1` |
| `TORCH_TEST_DEVICES` | Must point to `spyre_test_base_common.py` |
| `PYTORCH_TEST_WITH_SLOW` | Must be set to `1` to enable slow tests like `test_compare_cpu` |
