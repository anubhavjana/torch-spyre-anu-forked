#!/usr/bin/env bash
# tests/scripts/check_test_coverage.sh
#
# Enforces that every test_*.py under tests/ is referenced by at least one
# config YAML anywhere under tests/configs/, AND that config is referenced
# in at least one GitHub Actions workflow under .github/workflows/.
#
# Design notes
# ────────────
# 1. Scans ALL of tests/configs/ (not just torch_spyre_tests/) because some
#    test files appear as secondary entries inside model configs under
#    tests/configs/module_tests/ or tests/configs/model_ops_tests/.
#
# 2. Extracts EVERY `path:` line from each YAML (not just the first) because
#    a single model config can reference multiple test files.
#
# 3. Handles both path prefixes used in configs:
#      ${TORCH_DEVICE_ROOT}/tests/...  (this repo's tests)
#      ${TORCH_ROOT}/test/...          (upstream PyTorch tests — singular "test")
#    Anchors on the filename (test_*.py) and verifies existence on disk to
#    distinguish our files from upstream ones.
#
# 4. Checks all workflow YAMLs under .github/workflows/ so configs registered
#    in different workflows (e.g. module-tests.yml) are also accepted.
#
# 5. Supports an ignore list (IGNORED_TEST_FILES) for test files that are
#    intentionally not wired into CI (e.g. test harness helpers).
#
# Exit code: 0 = all tests covered, 1 = gaps found
#
# Usage (run from repo root):
#   bash tests/scripts/check_test_coverage.sh
#
# Overrides (for local testing):
#   --workflows-dir  path/to/.github/workflows/
#   --configs-root   path/to/tests/configs/
#   --tests          path/to/tests/

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
WORKFLOWS_DIR="${REPO_ROOT}/.github/workflows"
CONFIGS_ROOT="${REPO_ROOT}/tests/configs"
TESTS_DIR="${REPO_ROOT}/tests"

# ── Ignore list ───────────────────────────────────────────────────────────────
# Paths relative to TESTS_DIR. These files are intentionally excluded from CI
# (e.g. shared test harness helpers, not standalone test suites).
# Add new entries here when a test_*.py file should never be gated on.
IGNORED_TEST_FILES=(
  "models/test_model_ops.py"   # base class / helper — not a standalone test suite
)

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workflows-dir) WORKFLOWS_DIR="$2"; shift 2 ;;
    --configs-root)  CONFIGS_ROOT="$2";  shift 2 ;;
    --tests)         TESTS_DIR="$2";     shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'
CYN='\033[0;36m'; BLD='\033[1m';    RST='\033[0m'

header() { echo -e "\n${BLD}── $* ──${RST}"; }
ok()     { echo -e "  ${GRN}✔${RST}  $*"; }
skip()   { echo -e "  ${YEL}–${RST}  $* (ignored)"; }
error()  { echo -e "  ${RED}✘${RST}  $*"; }
info()   { echo -e "  ${CYN}·${RST}  $*"; }
warn()   { echo -e "  ${YEL}!${RST}  $*"; }

# Build a fast lookup set from the ignore list
declare -A IGNORED
for f in "${IGNORED_TEST_FILES[@]}"; do
  IGNORED["$f"]=1
done

# ── Sanity checks ─────────────────────────────────────────────────────────────
fail=0
[[ -d "$WORKFLOWS_DIR" ]] || { echo -e "${RED}ERROR${RST}: workflows dir not found: $WORKFLOWS_DIR"; fail=1; }
[[ -d "$CONFIGS_ROOT"  ]] || { echo -e "${RED}ERROR${RST}: configs root not found: $CONFIGS_ROOT";   fail=1; }
[[ -d "$TESTS_DIR"     ]] || { echo -e "${RED}ERROR${RST}: tests dir not found: $TESTS_DIR";         fail=1; }
[[ $fail -eq 0 ]] || { echo "Aborting."; exit 1; }

# ── Step 1: Build map  test_rel_path -> config_rel_path ───────────────────────
#
# For each config YAML, grep every line containing "path:" and extract the
# file path value. Two path prefix conventions exist in the configs:
#
#   ${TORCH_DEVICE_ROOT}/tests/models/test_foo.py   <- this repo, /tests/ (plural)
#   ${TORCH_ROOT}/test/test_modules.py              <- upstream PyTorch, /test/ (singular)
#
# We anchor on: (1) filename is test_*.py, (2) file exists on disk under
# TESTS_DIR. If it doesn't exist, it's an upstream file — skipped silently.

header "Reading all config YAMLs under tests/configs/"

declare -A TEST_TO_CONFIG   # test_rel_path -> config_rel_path (rel to tests/configs/)

while IFS= read -r -d '' config_abs; do
  config_rel="${config_abs#${CONFIGS_ROOT}/}"

  # Collect every line containing "path:", excluding comment lines.
  # This also matches "module_path:" lines in model configs, but those are
  # filtered out below by the test_*.py filename check.
  mapfile -t path_lines < <(grep 'path:' "$config_abs" 2>/dev/null | grep -v '^\s*#' || true)

  if [[ ${#path_lines[@]} -eq 0 ]]; then
    warn "$config_rel — no 'path:' fields, skipping"
    continue
  fi

  for path_line in "${path_lines[@]}"; do
    # Extract the value after "path:" and trim surrounding whitespace
    raw_value="${path_line#*path:}"
    raw_value="${raw_value#"${raw_value%%[![:space:]]*}"}"  # ltrim
    raw_value="${raw_value%%[[:space:]]*}"                  # rtrim

    [[ -z "$raw_value" ]] && continue

    # Only care about test_*.py filenames — filters out module_path:, etc.
    filename="${raw_value##*/}"
    [[ "$filename" == test_*.py ]] || continue

    # Resolve repo-relative path by stripping up to /tests/ or /test/
    if [[ "$raw_value" == *"/tests/"* ]]; then
      declared_path="${raw_value##*/tests/}"
    elif [[ "$raw_value" == *"/test/"* ]]; then
      declared_path="${raw_value##*/test/}"
    else
      continue
    fi

    # If the file doesn't exist under our TESTS_DIR, it's upstream — skip
    if [[ ! -f "${TESTS_DIR}/${declared_path}" ]]; then
      info "(upstream, skipping) $declared_path  ←  $config_rel"
      continue
    fi

    # Record mapping (first config to claim a file wins; duplicates are fine)
    if [[ ! -v TEST_TO_CONFIG["$declared_path"] ]]; then
      TEST_TO_CONFIG["$declared_path"]="$config_rel"
      info "$declared_path  ←  $config_rel"
    else
      info "$declared_path  ←  $config_rel  (also covered by ${TEST_TO_CONFIG[$declared_path]})"
    fi
  done

done < <(find "$CONFIGS_ROOT" -name "*.yaml" -print0 | sort -z)

echo ""
info "Mapped ${#TEST_TO_CONFIG[@]} test file(s) from configs."

# ── Step 2: Collect contents of all workflow YAMLs ────────────────────────────
header "Reading all workflow YAMLs under .github/workflows/"

WORKFLOW_CONTENTS=""
while IFS= read -r -d '' wf; do
  wf_rel="${wf#${REPO_ROOT}/}"
  count=$(grep -c 'config:' "$wf" 2>/dev/null || true)
  if [[ $count -gt 0 ]]; then
    info "$wf_rel ($count config: entries)"
    WORKFLOW_CONTENTS+=$'\n'"$(cat "$wf")"
  fi
done < <(find "$WORKFLOWS_DIR" \( -name "*.yml" -o -name "*.yaml" \) -print0 2>/dev/null | sort -z)

echo ""

# ── Step 3: Walk every test_*.py and check coverage ───────────────────────────
header "Checking every test_*.py"

if [[ ${#IGNORED_TEST_FILES[@]} -gt 0 ]]; then
  echo -e "  ${YEL}Ignored files (intentionally excluded from CI):${RST}"
  for f in "${IGNORED_TEST_FILES[@]}"; do echo "    – tests/$f"; done
  echo ""
fi

mapfile -d '' ALL_TEST_FILES < <(
  find "$TESTS_DIR" -maxdepth 2 -name "test_*.py" -print0 | sort -z
)

missing_config=()
missing_workflow=()

for test_abs in "${ALL_TEST_FILES[@]}"; do
  test_rel="${test_abs#${TESTS_DIR}/}"

  # Skip explicitly ignored files
  if [[ -v IGNORED["$test_rel"] ]]; then
    skip "tests/${test_rel}"
    continue
  fi

  if [[ -v TEST_TO_CONFIG["$test_rel"] ]]; then
    config_rel="${TEST_TO_CONFIG[$test_rel]}"
    if echo "$WORKFLOW_CONTENTS" | grep -qF "$config_rel" 2>/dev/null; then
      ok "tests/${test_rel}"
    else
      error "tests/${test_rel}"
      echo "       Config found  : tests/configs/${config_rel}"
      echo -e "       ${RED}NOT in any workflow${RST} under .github/workflows/"
      missing_workflow+=("tests/${test_rel}  [config: tests/configs/${config_rel}]")
    fi
  else
    error "tests/${test_rel}"
    echo "       No config YAML references this file anywhere under tests/configs/"
    missing_config+=("tests/${test_rel}")
  fi
done

# ── Step 4: Summary and actionable output ─────────────────────────────────────
header "Summary"

n_ignored=${#IGNORED_TEST_FILES[@]}
n_no_config=${#missing_config[@]}
n_no_workflow=${#missing_workflow[@]}
n_bad=$(( n_no_config + n_no_workflow ))
n_covered=$(( ${#TEST_TO_CONFIG[@]} - n_no_workflow ))

echo "  Config YAMLs scanned      : all files under tests/configs/"
echo "  Test files mapped         : ${#TEST_TO_CONFIG[@]}"
echo -e "  ${YEL}Intentionally ignored${RST}     : $n_ignored"
echo -e "  ${GRN}Fully covered${RST}             : $n_covered"
echo -e "  ${RED}No config at all${RST}          : $n_no_config"
echo -e "  ${RED}Config not in any workflow${RST} : $n_no_workflow"

if [[ $n_bad -eq 0 ]]; then
  echo ""
  echo -e "${GRN}${BLD}All test files are covered — CI is up to date.${RST}"
  exit 0
fi

# ── Fix instructions ──────────────────────────────────────────────────────────
echo ""
echo -e "${RED}${BLD}ACTION REQUIRED — $n_bad test file(s) not fully wired into CI.${RST}"
echo ""
echo "If a file should never be in CI, add it to IGNORED_TEST_FILES"
echo "at the top of tests/scripts/check_test_coverage.sh."

if [[ ${#missing_config[@]} -gt 0 ]]; then
  echo ""
  echo -e "${BLD}Files not referenced by any config YAML:${RST}"
  for f in "${missing_config[@]}"; do echo "  • $f"; done
  echo ""
  echo "  For a standalone test, create tests/configs/torch_spyre_tests[/subdir]/test_<name>_config.yaml:"
  echo ""
  echo "    test_suite_config:"
  echo "      files:"
  echo "        - path: \${TORCH_DEVICE_ROOT}/tests/<path/to/test_file.py>"
  echo "          unlisted_test_mode: mandatory_success"
  echo ""
  echo "  Or add as a secondary path: entry inside an existing model config"
  echo "  under tests/configs/module_tests/ or tests/configs/model_ops_tests/."
fi

if [[ ${#missing_workflow[@]} -gt 0 ]]; then
  echo ""
  echo -e "${BLD}Files whose config is not referenced in any workflow:${RST}"
  for f in "${missing_workflow[@]}"; do echo "  • $f"; done
  echo ""
  echo "  Add the config to the appropriate workflow matrix, e.g.:"
  echo "    - name: <Human Readable Name>"
  echo "      config: <config path relative to tests/configs/>"
fi

echo ""
echo "Full guide: tests/docs/enabling_torch_spyre_cicd_tests.md"
exit 1