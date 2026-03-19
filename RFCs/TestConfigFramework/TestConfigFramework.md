# RFC: Test Suite Configuration for running upstream pytorch tests from  OOT devices

**Authors:**

- Anubhav Jana (IBM Research, India)
- Ashok Pon Kumar Sree Prakash (IBM Research, India)

*Reference implementation: IBM Spyre*

---

## 1. Motivation

PyTorch provides a large suite of upstream tests that validate operator correctness across devices. For out-of-tree (OOT) device backends registered via `privateuse1`, reusing these upstream tests is preferable to writing new ones — it ensures the same correctness bar and reduces maintenance burden.

However, OOT devices typically support a subset of ops and dtypes, and some tests may be known to fail, crash, or require special tolerance settings. Running the full upstream suite without filtering would result in thousands of failures and crashes that obscure real signal. While the upstream test refactoring is happening, we want to enable a way to selectively enable or edit the tests out of tree even before refactoring of all tests are complete.

This RFC defines a YAML-based configuration schema that allows an OOT device team to:

- Declare which ops and dtypes their device supports
- Select which upstream tests to run, skip, or mark as expected failures
- Allow the same framework to control, parameterise device specific custom tests 
- Express per-op and per-test tolerance overrides
- Tag tests with model names and other metadata for traceability
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

The Spyre framework hooks into this mechanism via `SpyreTestBase` (which can eventually be contributed back to `PrivateUse1TestBase`) which:

1. Loads the YAML config on first `instantiate_test` call
2. Patches `@ops.op_list` directly to restrict which ops generate variants (`_SpyreOpListPatcher`)
3. Patches `@onlyOn` to allow the `spyre` device type (`_SpyreOnlyOnPatcher`)
4. Injects extra dtypes into `@ops.allowed_dtypes` (`_SpyreDtypePatcher`)
5. Applies skip, xfail, or mandatory_success to each generated variant
6. Adds custom markers to tests for provenance. 

---

## 3. Configuration File

The configuration is a YAML file pointed to by the `PYTORCH_TEST_CONFIG` environment variable. The downstream can have multiple
such config files. `PYTORCH_TEST_CONFIG` will govern which config needs to be used by upstream.

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
| `files` | Yes | List of test file entries |
| `global` | No | Device-wide capability declaration |

---

## 4. File Entry

Each entry under `files` corresponds to one test file.

```yaml
- path: ${PYTORCH}/test/test_binary_ufuncs.py
  unlisted_test_mode: skip
  tests:
    - ...
```

| Field | Required | Default | Description |
|---|---|---|---|
| `path` | Yes | — | Path to the test file. Supports `${PYTORCH}` and `${TORCH_SPYRE}` tokens resolved from env vars `PYTORCH_ROOT` and `TORCH_SPYRE_ROOT` || `unlisted_test_mode` | No | `skip` | Mode applied to tests not listed under `tests`, or listed without an explicit `mode` |
| `tests` | No | `[]` | List of test entries with explicit configuration |

### 4.1 `unlisted_test_mode`

Controls the behaviour for tests that are **not explicitly listed** in `tests`.

| Value | Behaviour |
|---|---|
| `skip` | Skip entirely (**Default**). Use when the file is under active development and most tests are not yet ready |
| `xfail` | Run but mark as expected failure. Use when the device broadly supports the op set but individual tests may still fail |
| `xfail_strict` | Run and mark as `xfail(strict=True)`. Fails the suite if the test unexpectedly passes — use when you want to be notified of unexpected improvements |
| `mandatory_success` | Must pass. Use with caution — any new test added to the test file will immediately break the suite |

**When to use each:**

```
New device, early stage:
  unlisted_test_mode: skip             <- only run what you explicitly list and skip the unlisted tests

Device broadly working, tracking regressions:
  unlisted_test_mode: xfail             <- run everything, failures expected

Stable device, enforcing correctness:
  unlisted_test_mode: mandatory_success  <- everything must pass
```

---

## 5. Test Entry

Each entry under `tests` configures a specific upstream test method. The same test can have multiple entires to define different combinations of behaviour if relevant. The final set will be the union of all tests.

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
| `mode` | No | `mandatory_success` | How to treat this test's variants |
| `tags` | No | `[]` | Pytest mark labels applied to all variants of this test |
| `edits` | No | — | Per-test overrides for ops and dtypes |

### 5.1 Test `mode`

Applied at the **variant level** — each `(test, op, dtype)` combination is treated independently.

| Value | Behaviour |
|---|---|
| `mandatory_success` | Variant must pass. Fails the suite if it does not |
| `xfail` | Variant is expected to fail. Passes the suite either way |
| `xfail_strict` | Variant must fail. Fails the suite if it unexpectedly passes |
| `skip` | Variant is skipped entirely with a skip message |

**`mode` vs `unlisted_test_mode` precedence:**

```
test listed with explicit mode    → test mode governs
test listed without mode          → mandatory_success
test not listed at all            → unlisted_test_mode governs
```

### 5.2 Markers

Markers are registered as pytest marks on every variant of the test. This enables test selection based on various filters like model:

```bash
pytest test_binary_ufuncs.py -m model_name_depending_on_this_test_1
pytest test_binary_ufuncs.py -m "model_a or model_b"
pytest test_binary_ufuncs.py -m "not model_a"
```

Markers must be valid Python identifiers (no spaces or special characters).

### 5.3 Edits


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
| `include` | The test uses a pre-filtered op list (e.g. `binary_ufuncs_with_references`) that excludes an op you want to test or a particular op is not in global supported_ops, but anyway you want to override and test it. Injects the op into `@ops.op_list` at instantiation time |
| `exclude` | The op is in `supported_ops` and in the test's `@ops.op_list`, but you want to suppress it for this specific test only |

> **Note on `include`:** This is only needed when the test uses a filtered list that excludes your op or the op is not in globally supported ops like and you want to selectively enable for this test alone. For example, `binary_ufuncs_with_references = [op for op in binary_ufuncs if op.ref is not None]` excludes ops without a reference implementation. If `gcd` has no `ref`, you cannot test it via `test_scalar_support` without injecting it via `include`.

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
    + edits.dtypes.include <- injected dtypes
    - edits.dtypes.exclude                                          <- removed dtypes
```

Where:

- `global.supported_dtypes` — hardware capability. 
- `op.dtypes` — op-level dtype override from `global.supported_ops[op].dtypes`. If not specified, defaults to `global.supported_dtypes`.
- `test.allowed_dtypes` — upstream `@ops(allowed_dtypes=(...))` constraint from the test source code.
- `edits.dtypes.include` — can be mutually exclusive to `global.supported_dtypes`, not necessarily a subset. It can be an additional dtype to 
test for a particular op without affecting other tests.
- `edits.dtypes.exclude` — applied last, after all inclusions.

---

## 6. Global Configuration

Declares the device-wide capability.

```yaml
global:
  supported_dtypes:
    - name: float16
    - name: int64
  supported_ops:
    - name: add
      dtypes:
        - name: float16
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
| `supported_dtypes` | Yes | Device-wide supported dtypes. |
| `supported_ops` | Yes | List of ops the device supports. Only ops listed here generate test variants |

### 6.1 `supported_dtypes`

The complete set of dtypes the device hardware supports. No test variant will run with a dtype outside this list will run, unless in the test specific config, it is explicitly set to include.

If omitted, no dtype filtering is applied at the global level.

### 6.2 `supported_ops`

Each entry declares one op the device supports and configures how tests exercising that op behave.

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | Yes | — | Op name matching `OpInfo.name` in upstream `op_db` |
| `force_xfail` | No | `false` | If `true`, flips any `mandatory_success` variant for this op to `xfail`. Has no effect on variants already marked `xfail` or `xfail_strict` |
| `dtypes` | No | `global.supported_dtypes` | Op-level dtype override. |

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

`force_xfail` only flips `mandatory_success` -> `xfail`. It never changes `xfail`, `xfail_strict`, or `skip`.

> **When to use `force_xfail: true`:** When an op is in `supported_ops` (so variants are generated) but is not yet stable enough to require passing. This allows tracking which tests exercise the op without committing to a correctness guarantee.

#### 6.2.2 Op-level `dtypes`

Narrows the dtype variants generated for this op across all tests. 

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
    - path: ${PYTORCH}/test/test_binary_ufuncs.py
      unlisted_test_mode: skip
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
    - path: ${PYTORCH}/test/test_binary_ufuncs.py
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
  mode: skip
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
| `path` | string | Yes | — |
| `unlisted_test_mode` | enum | No | `skip` |
| `tests` | list | No | `[]` |

### Test entry

| Field | Type | Required | Default |
|---|---|---|---|
| `test` | string (`ClassName::method_name`) | Yes | — |
| `mode` | enum | No | `mandatory_success` |
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
| `dtypes` | list of `{name, precision}` | No | `supported_dtypes` |

### Precision

| Field | Type | Required | Default |
|---|---|---|---|
| `atol` | float | No | framework default |
| `rtol` | float | No | framework default |

---

## 9. Validation Rules

1. `test` must match `ClassName::method_name` pattern
2. `mode` and `unlisted_test_mode` must be one of `mandatory_success`, `xfail`, `xfail_strict`, `skip`
3. All dtype strings must be valid PyTorch dtype names
4. `edits.dtypes.include` may be subset of `global.supported_dtypes` or mutually exclusive to `global.supported_dtypes` 
5. `supported_ops[*].dtypes` must be a subset of `global.supported_dtypes`
6. If `supported_ops[*].dtypes` ∩ `global.supported_dtypes` is empty, a warning is emitted
7. `tags` must be valid Python identifiers (used as pytest mark names)
8. `path` tokens (`${PYTORCH}`, `${TORCH_SPYRE}`) must resolve via environment variables at load time

---

## 10. Environment Variables

| Variable | Description |
|---|---|
| `PYTORCH_TEST_CONFIG` | Path to the YAML config file |
| `PYTORCH_ROOT` | Resolves `${PYTORCH}` token in `path` |
| `TORCH_SPYRE_ROOT` | Resolves `${TORCH_SPYRE}` token in `path` |
| `PYTORCH_TESTING_DEVICE_ONLY_FOR` | Must be set to `privateuse1` |
| `TORCH_TEST_DEVICES` | Must point to `spyre_test_base_common.py` |
| `PYTORCH_TEST_WITH_SLOW` | Must be set to `1` to enable slow tests like `test_compare_cpu` |
