##!/usr/bin/env bash
# setup_test_env.sh
#
# Usage:
#   source setup_test_env.sh
#   spyre_pytest test_binary_ufuncs.py -v

set -eo pipefail

# ---------------------------------------------------------------------------
# 1. Set HOME to the login working directory of the pod
# ---------------------------------------------------------------------------
export HOME="$(pwd)"
echo "[setup_test_env] HOME set to: $HOME"

# ---------------------------------------------------------------------------
# 2. Find pytorch source root — walk up from torch.__file__ only,
#    no broad filesystem search
# ---------------------------------------------------------------------------
_find_pytorch_root() {
    local torch_location
    torch_location=$(python3 -c "import torch; print(torch.__file__)" 2>/dev/null) || {
        echo "ERROR: could not import torch. Is your virtualenv active?" >&2
        return 1
    }

    # Walk up from torch.__file__ looking for test/test_binary_ufuncs.py
    local dir
    dir=$(dirname "$(dirname "$torch_location")")
    for _ in 1 2 3 4 5 6 7 8; do
        dir=$(dirname "$dir")
        if [ -f "$dir/test/test_binary_ufuncs.py" ]; then
            echo "$dir"
            return 0
        fi
        # Stop at filesystem root
        [ "$dir" = "/" ] && break
    done

    # Targeted search under HOME only, max depth 4, with timeout
    local found
    found=$(find "$HOME" -maxdepth 4 -name "test_binary_ufuncs.py" 2>/dev/null | head -1)
    if [ -n "$found" ]; then
        echo "$(dirname "$(dirname "$found")")"
        return 0
    fi

    echo "ERROR: could not find pytorch source root under HOME=$HOME" >&2
    return 1
}

# ---------------------------------------------------------------------------
# 3. Find torch-spyre source root — importlib first, then targeted search
# ---------------------------------------------------------------------------
_find_torch_spyre_root() {
    # First try: already importable
    local found_via_python
    found_via_python=$(python3 -c "
import importlib.util, os
spec = importlib.util.find_spec('spyre_test_base_common')
if spec:
    print(os.path.dirname(os.path.dirname(spec.origin)))
" 2>/dev/null) || true

    if [ -n "$found_via_python" ]; then
        echo "$found_via_python"
        return 0
    fi

    # Targeted search under HOME only, max depth 5
    local found
    found=$(find "$HOME" -maxdepth 5 -name "spyre_test_base_common.py" 2>/dev/null | head -1)
    if [ -n "$found" ]; then
        echo "$(dirname "$(dirname "$found")")"
        return 0
    fi

    echo "ERROR: could not find torch-spyre source root under HOME=$HOME" >&2
    return 1
}

# ---------------------------------------------------------------------------
# 4. Discover paths
# ---------------------------------------------------------------------------
echo "[setup_test_env] Discovering pytorch root..."
PYTORCH_ROOT=$(_find_pytorch_root)
echo "[setup_test_env]   PYTORCH_ROOT=$PYTORCH_ROOT"

echo "[setup_test_env] Discovering torch-spyre root..."
TORCH_SPYRE_ROOT=$(_find_torch_spyre_root)
echo "[setup_test_env]   TORCH_SPYRE_ROOT=$TORCH_SPYRE_ROOT"

# ---------------------------------------------------------------------------
# 5. Validate
# ---------------------------------------------------------------------------
_check() {
    local path="$1" label="$2"
    if [ ! -e "$path" ]; then
        echo "ERROR: $label not found at: $path" >&2
        return 1
    fi
}

_check "$PYTORCH_ROOT/test/test_binary_ufuncs.py"          "pytorch test dir"
_check "$TORCH_SPYRE_ROOT/tests/spyre_test_base_common.py" "spyre_test_base_common.py"
_check "$TORCH_SPYRE_ROOT/tests/test_suite_config.yaml"    "test_suite_config.yaml"

# ---------------------------------------------------------------------------
# 6. Export environment variables
# ---------------------------------------------------------------------------
export PYTORCH_ROOT
export TORCH_SPYRE_ROOT
export PYTORCH_TESTING_DEVICE_ONLY_FOR="privateuse1"
export TORCH_TEST_DEVICES="$TORCH_SPYRE_ROOT/tests/spyre_test_base_common.py"
export PYTORCH_TEST_CONFIG="$TORCH_SPYRE_ROOT/tests/test_suite_config.yaml"

_spyre_tests_path="$TORCH_SPYRE_ROOT/tests"
case ":${PYTHONPATH:-}:" in
    *":$_spyre_tests_path:"*) ;;
    *) export PYTHONPATH="$_spyre_tests_path:${PYTHONPATH:-}" ;;
esac

# ---------------------------------------------------------------------------
# 7. Pytest wrapper
# ---------------------------------------------------------------------------
spyre_pytest() {
    cd "$PYTORCH_ROOT/test"
    python3 -m pytest "$@" || true
}
export -f spyre_pytest

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------
echo ""
echo "[setup_test_env] Environment ready:"
echo "  HOME                            = $HOME"
echo "  PYTORCH_ROOT                    = $PYTORCH_ROOT"
echo "  TORCH_SPYRE_ROOT                = $TORCH_SPYRE_ROOT"
echo "  PYTORCH_TESTING_DEVICE_ONLY_FOR = $PYTORCH_TESTING_DEVICE_ONLY_FOR"
echo "  TORCH_TEST_DEVICES              = $TORCH_TEST_DEVICES"
echo "  PYTORCH_TEST_CONFIG             = $PYTORCH_TEST_CONFIG"
echo "  PYTHONPATH                      = $PYTHONPATH"
echo ""
echo "[setup_test_env] Run tests using:"
echo "  spyre_pytest test_binary_ufuncs.py -v"
echo "  spyre_pytest test_view_ops.py -v"
echo "  spyre_pytest test_view_ops.py::TestOldViewOpsPRIVATEUSE1::test_expand_spyre -v"