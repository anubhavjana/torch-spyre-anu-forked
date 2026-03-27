#!/usr/bin/env bash
# run_test.sh -- Single-entry-point test runner for torch-spyre OOT tests.
#
# Usage:
#   bash run_test.sh /path/to/test_suite_config.yaml [extra pytest args...]
#


set -euo pipefail


if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <path/to/test_suite_config.yaml> [extra pytest args...]" >&2
    exit 1
fi

YAML_CONFIG="$(realpath "$1")"
shift
EXTRA_PYTEST_ARGS=("$@")

if [[ ! -f "$YAML_CONFIG" ]]; then
    echo "ERROR: YAML config not found: $YAML_CONFIG" >&2
    exit 1
fi

echo "[spyre_run] Using YAML config: $YAML_CONFIG"
YAML_DIR="$(dirname "$YAML_CONFIG")"

# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

# Walk upward from a dir checking each ancestor for a sentinel relative path.
_walk_up_for_sentinel() {
    local dir sentinel
    dir="$(realpath "$1")"
    sentinel="$2"
    for _ in $(seq 1 12); do
        if [[ -e "$dir/$sentinel" ]]; then
            echo "$dir"
            return 0
        fi
        [[ "$dir" == "/" ]] && break
        dir="$(dirname "$dir")"
    done
    return 1
}

# Walk upward from a dir; at each ancestor level check every sibling subdir
# for a sentinel relative path. Finds e.g. pytorch/ as a sibling of torch-spyre/.
_find_sibling_with_sentinel() {
    local dir sentinel
    dir="$(realpath "$1")"
    sentinel="$2"
    for _ in $(seq 1 6); do
        dir="$(dirname "$dir")"
        [[ "$dir" == "/" ]] && break
        for sibling in "$dir"/*/; do
            [[ -f "${sibling}${sentinel}" ]] && { echo "${sibling%/}"; return 0; }
        done
    done
    return 1
}

# ---------------------------------------------------------------------------
# 2. Resolve and export TORCH_ROOT
# ---------------------------------------------------------------------------
echo "[spyre_run] Resolving TORCH_ROOT..."
if [[ -n "${TORCH_ROOT:-}" && -d "$TORCH_ROOT" ]]; then
    echo "[spyre_run]   already set: $TORCH_ROOT"
else
    TORCH_ROOT=""

    # Editable install: torch.__file__ is inside the source tree
    # (works if torch was installed with pip install -e .)
    _found=$(python3 -c "
import torch, os
candidate = os.path.dirname(os.path.dirname(os.path.abspath(torch.__file__)))
if os.path.isfile(os.path.join(candidate, 'test', 'test_binary_ufuncs.py')):
    print(candidate)
" 2>/dev/null) || true
    [[ -n "$_found" ]] && TORCH_ROOT="$_found"

    # Sibling search: pytorch/ sits next to torch-spyre/ under a common parent
    if [[ -z "$TORCH_ROOT" ]]; then
        TORCH_ROOT=$(_find_sibling_with_sentinel "$YAML_DIR" "test/test_binary_ufuncs.py" 2>/dev/null) || true
    fi

    if [[ -z "$TORCH_ROOT" ]]; then
        echo "ERROR: Could not locate PyTorch source root." >&2
        echo "       Expected pytorch/ as a sibling of your torch-spyre repo, or" >&2
        echo "       an editable install (pip install -e .)." >&2
        echo "       Set TORCH_ROOT explicitly if the layout differs." >&2
        exit 1
    fi
fi
export TORCH_ROOT
# Also export as PYTORCH_ROOT for backward compat with upstream test framework
export PYTORCH_ROOT="$TORCH_ROOT"
echo "[spyre_run]   TORCH_ROOT=$TORCH_ROOT"

# ---------------------------------------------------------------------------
# 3. Resolve and export TORCH_DEVICE_ROOT
# ---------------------------------------------------------------------------
echo "[spyre_run] Resolving TORCH_DEVICE_ROOT..."
if [[ -n "${TORCH_DEVICE_ROOT:-}" && -d "$TORCH_DEVICE_ROOT" ]]; then
    echo "[spyre_run]   already set: $TORCH_DEVICE_ROOT"
else
    TORCH_DEVICE_ROOT=""

    # Primary: read source path from torch_spyre editable install metadata
    _found=$(python3 -c "
import importlib.metadata, json, os
try:
    dist = importlib.metadata.distribution('torch_spyre')
    direct_url = os.path.join(str(dist._path), 'direct_url.json')
    if os.path.isfile(direct_url):
        data = json.load(open(direct_url))
        url = data.get('url', '')
        if url.startswith('file://'):
            candidate = url[len('file://'):]
            if os.path.isfile(os.path.join(candidate, 'tests', 'spyre_test_base_common.py')):
                print(candidate)
except Exception:
    pass
" 2>/dev/null) || true
    [[ -n "$_found" ]] && TORCH_DEVICE_ROOT="$_found"

    # Fallback: already importable via PYTHONPATH
    if [[ -z "$TORCH_DEVICE_ROOT" ]]; then
        _found=$(python3 -c "
import importlib.util, os
spec = importlib.util.find_spec('spyre_test_base_common')
if spec:
    print(os.path.dirname(os.path.dirname(os.path.abspath(spec.origin))))
" 2>/dev/null) || true
        [[ -n "$_found" ]] && TORCH_DEVICE_ROOT="$_found"
    fi

    # Fallback: walk upward from YAML dir (YAML lives inside tests/)
    if [[ -z "$TORCH_DEVICE_ROOT" ]]; then
        TORCH_DEVICE_ROOT=$(_walk_up_for_sentinel "$YAML_DIR" "tests/spyre_test_base_common.py" 2>/dev/null) || true
    fi

    if [[ -z "$TORCH_DEVICE_ROOT" ]]; then
        echo "ERROR: Could not locate torch-spyre source root." >&2
        echo "       Expected torch_spyre to be installed as an editable install" >&2
        echo "       (pip install -e .), or the repo adjacent to your YAML." >&2
        echo "       Set TORCH_DEVICE_ROOT explicitly if the layout differs." >&2
        exit 1
    fi
fi
export TORCH_DEVICE_ROOT
# Also export as TORCH_SPYRE_ROOT for backward compat
export TORCH_SPYRE_ROOT="$TORCH_DEVICE_ROOT"
echo "[spyre_run]   TORCH_DEVICE_ROOT=$TORCH_DEVICE_ROOT"

# ---------------------------------------------------------------------------
# 4. Export all framework environment variables
# ---------------------------------------------------------------------------
export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
export TORCH_TEST_DEVICES="${TORCH_DEVICE_ROOT}/tests/spyre_test_base_common.py"
export PYTORCH_TEST_CONFIG="$YAML_CONFIG"

_spyre_tests_path="${TORCH_DEVICE_ROOT}/tests"
case ":${PYTHONPATH:-}:" in
    *":$_spyre_tests_path:"*) ;;
    *) export PYTHONPATH="$_spyre_tests_path:${PYTHONPATH:-}" ;;
esac

echo ""
echo "[spyre_run] Environment set:"
echo "  TORCH_ROOT                      = $TORCH_ROOT"
echo "  TORCH_DEVICE_ROOT               = $TORCH_DEVICE_ROOT"
echo "  PYTORCH_TESTING_DEVICE_ONLY_FOR = $PYTORCH_TESTING_DEVICE_ONLY_FOR"
echo "  TORCH_TEST_DEVICES              = $TORCH_TEST_DEVICES"
echo "  PYTORCH_TEST_CONFIG             = $PYTORCH_TEST_CONFIG"
echo "  PYTHONPATH                      = $PYTHONPATH"
echo ""

# ---------------------------------------------------------------------------
# 5. Extract raw file paths from YAML
# ---------------------------------------------------------------------------
_extract_file_paths_from_yaml() {
    awk '
        /^[[:space:]]*-[[:space:]]*path:[[:space:]]/ {
            match($0, /path:[[:space:]]+(.+)/, arr)
            if (arr[1] != "") print arr[1]
            next
        }
        /^[[:space:]]*path:[[:space:]]/ {
            match($0, /path:[[:space:]]+(.+)/, arr)
            if (arr[1] != "") print arr[1]
        }
    ' "$1" | sed 's/[[:space:]]*#.*//' | sed '/^[[:space:]]*$/d'
}

echo "[spyre_run] Parsing YAML for test file paths..."
RAW_PATHS=()
while IFS= read -r line; do
    RAW_PATHS+=("$line")
done < <(_extract_file_paths_from_yaml "$YAML_CONFIG")

if [[ ${#RAW_PATHS[@]} -eq 0 ]]; then
    echo "ERROR: No file paths found in YAML config." >&2
    exit 1
fi

echo "[spyre_run] Found ${#RAW_PATHS[@]} path entry(s):"
for p in "${RAW_PATHS[@]}"; do
    echo "  $p"
done

# ---------------------------------------------------------------------------
# 6. Token expansion
# ---------------------------------------------------------------------------
_expand_path() {
    local p="$1"
    p="${p//\$\{TORCH_ROOT\}/$TORCH_ROOT}"
    p="${p//\$\{TORCH_DEVICE_ROOT\}/$TORCH_DEVICE_ROOT}"
    if command -v envsubst &>/dev/null; then
        p=$(echo "$p" | envsubst)
    fi
    echo "$p"
}

# ---------------------------------------------------------------------------
# 7. Expand globs and collect resolved test files
# ---------------------------------------------------------------------------
shopt -s globstar nullglob 2>/dev/null || true

TEST_FILES=()
for raw in "${RAW_PATHS[@]}"; do
    expanded=$(_expand_path "$raw")
    if [[ "$expanded" == *'*'* || "$expanded" == *'?'* ]]; then
        matched=( $expanded )
        if [[ ${#matched[@]} -eq 0 ]]; then
            echo "WARNING: Glob pattern matched no files: $expanded" >&2
        fi
        for f in "${matched[@]}"; do
            [[ -f "$f" ]] && TEST_FILES+=("$f")
        done
    else
        if [[ -f "$expanded" ]]; then
            TEST_FILES+=("$expanded")
        else
            echo "WARNING: Resolved path does not exist, skipping: $expanded" >&2
        fi
    fi
done

if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
    echo "ERROR: No test files resolved from YAML paths." >&2
    exit 1
fi

echo ""
echo "[spyre_run] Resolved test file(s):"
for f in "${TEST_FILES[@]}"; do
    echo "  $f"
done
echo ""

# ---------------------------------------------------------------------------
# 8. Run pytest for each resolved test file
# ---------------------------------------------------------------------------
OVERALL_EXIT=0

for test_file in "${TEST_FILES[@]}"; do
    test_dir="$(dirname "$test_file")"
    test_basename="$(basename "$test_file")"

    echo "========================================================================"
    echo "[spyre_run] Running: $test_file"
    echo "========================================================================"

    (
        cd "$test_dir"
        python3 -m pytest "$test_basename" "${EXTRA_PYTEST_ARGS[@]}" || true
    )
    _exit=$?
    if [[ $_exit -ne 0 ]]; then
        echo "[spyre_run] WARNING: pytest exited with code $_exit for $test_file" >&2
        OVERALL_EXIT=$_exit
    fi
done

echo ""
echo "[spyre_run] Done. Overall exit code: $OVERALL_EXIT"
exit $OVERALL_EXIT