#!/usr/bin/env bash
# scripts/check_test_coverage.sh
#
# Enforces that every test_*.py under tests/ is referenced by at least one
# config YAML anywhere under tests/configs/, AND that config is referenced
# in at least one GitHub Actions workflow under .github/workflows/.
#
# Design notes
# ────────────
# 1. Scans ALL of tests/configs/ (not just torch_spyre_tests/) because some
#    test files — like test_modules_custom.py — appear as secondary entries
#    inside model configs under tests/configs/module_tests/.
#
# 2. Extracts EVERY `path:` line from each YAML (not just the first) because
#    model configs list multiple test files in a single YAML, e.g.:
#      - path: .../test_modules.py        <- primary
#      - path: .../test_modules_custom.py <- secondary, same file
#
# 3. Checks all workflow YAMLs under .github/workflows/ so that model configs
#    registered in a different workflow (e.g. module-tests.yml) are accepted.
#
# Exit code: 0 = all tests covered, 1 = gaps found
#
# Usage (run from repo root):
#   bash scripts/check_test_coverage.sh
#
# Overrides (for local testing):
#   --workflows-dir  path/to/.github/workflows/
#   --configs-root   path/to/tests/configs/
#   --tests          path/to/tests/

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
WORKFLOWS_DIR="${REPO_ROOT}/.github/workflows"
CONFIGS_ROOT="${REPO_ROOT}/tests/configs"      # scan everything underneath
TESTS_DIR="${REPO_ROOT}/tests"

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
error()  { echo -e "  ${RED}✘${RST}  $*"; }
info()   { echo -e "  ${CYN}·${RST}  $*"; }
warn()   { echo -e "  ${YEL}!${RST}  $*"; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
fail=0
[[ -d "$WORKFLOWS_DIR" ]] || { echo -e "${RED}ERROR${RST}: workflows dir not found: $WORKFLOWS_DIR"; fail=1; }
[[ -d "$CONFIGS_ROOT"  ]] || { echo -e "${RED}ERROR${RST}: configs root not found: $CONFIGS_ROOT";   fail=1; }
[[ -d "$TESTS_DIR"     ]] || { echo -e "${RED}ERROR${RST}: tests dir not found: $TESTS_DIR";         fail=1; }
[[ $fail -eq 0 ]] || { echo "Aborting."; exit 1; }

# ----- Step 1: Build map  test_rel_path -> config_rel_path  -----
#
# Read ALL `path:` lines from every YAML under tests/configs/ (not just the
# first), because a single model config can reference multiple test files.
#
# path: lines look like either:
#   - path: ${TORCH_DEVICE_ROOT}/tests/test_modules_custom.py
#   - path: ${TORCH_ROOT}/test/test_modules.py
#
# We extract the basename-anchor "/tests/" segment to normalise both forms.
# Paths that don't contain "/tests/" (e.g. upstream test paths like
# ${TORCH_ROOT}/test/) are tracked separately — they're expected and fine.

header "Reading all config YAMLs under tests/configs/"

declare -A TEST_TO_CONFIG     # test_rel_path -> config_rel_path (rel to tests/configs/)
declare -A UPSTREAM_COVERED   # records test paths outside our tests/ tree (informational)

while IFS= read -r -d '' config_abs; do
  config_rel="${config_abs#${CONFIGS_ROOT}/}"

  # Extract every line that contains "path:" — skips comment lines (#)
  mapfile -t path_lines < <(grep 'path:' "$config_abs" 2>/dev/null | grep -v '^\s*#' || true)

  if [[ ${#path_lines[@]} -eq 0 ]]; then
    warn "$config_rel — no 'path:' fields, skipping"
    continue
  fi

  for path_line in "${path_lines[@]}"; do
    # Pull out the value after "path:" and trim whitespace
    raw_value="${path_line#*path:}"
    raw_value="${raw_value#"${raw_value%%[![:space:]]*}"}"  # ltrim
    raw_value="${raw_value%%[[:space:]]*}"                  # rtrim (remove trailing spaces/comments)

    if [[ -z "$raw_value" ]]; then
      continue
    fi

    if [[ "$raw_value" == *"/tests/"* ]]; then
      # Strip everything up to and including the last "/tests/" occurrence
      # to get the path relative to a tests/ root
      declared_path="${raw_value##*/tests/}"

      # Only track paths that look like our test_*.py files
      if [[ "$declared_path" == test_*.py || "$declared_path" == */test_*.py ]]; then
        # If this path was already claimed by another config, keep the first
        # (multiple model configs can cover the same test file — that's fine)
        if [[ ! -v TEST_TO_CONFIG["$declared_path"] ]]; then
          TEST_TO_CONFIG["$declared_path"]="$config_rel"
          info "$declared_path  ←  $config_rel"
        else
          info "$declared_path  ←  $config_rel  (also covered by ${TEST_TO_CONFIG[$declared_path]})"
        fi
      fi
    else
      # Path outside our tests/ tree (e.g. ${TORCH_ROOT}/test/test_modules.py)
      # Record it as informational — not our responsibility to gate on
      UPSTREAM_COVERED["$raw_value"]="$config_rel"
    fi
  done

done < <(find "$CONFIGS_ROOT" -name "*.yaml" -print0 | sort -z)

echo ""
info "Mapped ${#TEST_TO_CONFIG[@]} test file(s) from configs."

# ----- Step 2: Build set of config paths referenced across ALL workflows -----
header "Reading all workflow YAMLs under .github/workflows/"

# We grep every workflow file for config: entries and collect all mentioned
# config paths into a single lookup string (WORKFLOW_CONTENTS).
# Using grep -h to suppress filenames and concatenate all matches.

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

# ----- Step 3: Walk every test_*.py and check coverage -----
header "Checking every test_*.py"

SCAN_DIRS=(
  "$TESTS_DIR"
  "$TESTS_DIR/inductor"
  "$TESTS_DIR/tensor"
  "$TESTS_DIR/models"
)

missing_config=()
missing_workflow=()

while IFS= read -r -d '' test_abs; do
  test_rel="${test_abs#${TESTS_DIR}/}"

  if [[ -v TEST_TO_CONFIG["$test_rel"] ]]; then
    config_rel="${TEST_TO_CONFIG[$test_rel]}"

    # Check if this config's path appears anywhere in any workflow file
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

done < <(
  for d in "${SCAN_DIRS[@]}"; do
    [[ -d "$d" ]] && find "$d" -maxdepth 1 -name "test_*.py" -print0
  done | sort -z
)

# ----- Step 4: Summary and actionable output -----

n_no_config=${#missing_config[@]}
n_no_workflow=${#missing_workflow[@]}
n_bad=$(( n_no_config + n_no_workflow ))
n_covered=$(( ${#TEST_TO_CONFIG[@]} - n_no_workflow ))

echo "  Config YAMLs scanned : all files under tests/configs/"
echo "  Test files mapped    : ${#TEST_TO_CONFIG[@]}"
echo -e "  ${GRN}Fully covered${RST}        : $n_covered"
echo -e "  ${RED}No config at all${RST}     : $n_no_config"
echo -e "  ${RED}Config not in any workflow${RST}: $n_no_workflow"

if [[ $n_bad -eq 0 ]]; then
  echo ""
  echo -e "${GRN}${BLD}All test files are covered — CI is up to date.${RST}"
  exit 0
fi

# ── Fix instructions ──────────────────────────────────────────────────────────
echo ""
echo -e "${RED}${BLD}ACTION REQUIRED — $n_bad test file(s) not fully wired into CI.${RST}"

if [[ ${#missing_config[@]} -gt 0 ]]; then
  echo ""
  echo -e "${BLD}Files not referenced by any config YAML:${RST}"
  for f in "${missing_config[@]}"; do echo "  • $f"; done
  echo ""
  echo "  These files need a config entry somewhere under tests/configs/."
  echo "  For a standalone test, create tests/configs/torch_spyre_tests[/subdir]/test_<name>_config.yaml:"
  echo ""
  echo "    test_suite_config:"
  echo "      files:"
  echo "        - path: \${TORCH_DEVICE_ROOT}/tests/<path/to/test_file.py>"
  echo "          unlisted_test_mode: mandatory_success"
  echo ""
  echo "  Or add the file as a secondary entry inside an existing model config"
  echo "  under tests/configs/module_tests/ if it belongs to a model test suite."
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