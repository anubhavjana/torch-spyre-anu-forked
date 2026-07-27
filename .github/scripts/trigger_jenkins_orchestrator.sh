#!/usr/bin/env bash
#
# Trigger the Spyre Jenkins orchestrator job directly (bypassing the
# label-filtered multibranch discovery) with PRESET=trigger-pr-validation and
# TRIGGER_PR set to this PR, then block until it completes.
#
# Why: torch_spyre_tests.yaml's normal `run-tests` job always tests against
# the STANDING image_spyre_backend runner image, which only picks up an
# upstream (flex/deeptools/spyre-comms/...) fix once Jenkins' separate
# main-push-build pipeline finishes and republishes :latest. The orchestrator,
# resolved via PRESET=trigger-pr-validation, re-walks every unpinned
# dependency at its own current main HEAD (see resolve_deps.py::resolve_graph
# pin_overrides), so it always builds against the LATEST upstream content,
# closing that lag. This script is the `run-tests-integration` job's only
# step in torch_spyre_tests.yaml.
#
# Required env:
#   JENKINS_URL     base URL, e.g. https://jenkins.example.com (no trailing slash needed)
#   JENKINS_USER    Jenkins username for the API token
#   JENKINS_TOKEN   Jenkins API token (not the account password)
#   TRIGGER_PR      host/owner/repo#pr, e.g. github.com/torch-spyre/torch-spyre#1234
#
# Optional env:
#   ORCHESTRATOR_JOB_PATH   Jenkins job path segments, default 'job/Spyre/job/orchestrator'
#   POLL_INTERVAL_SECONDS   default 30
#   QUEUE_TIMEOUT_SECONDS   how long to wait for the build to leave the Jenkins queue, default 600
#
# GITHUB_STEP_SUMMARY, if set (GitHub Actions), gets a one-line result summary.

set -euo pipefail

for v in JENKINS_URL JENKINS_USER JENKINS_TOKEN TRIGGER_PR; do
    if [[ -z "${!v:-}" ]]; then
        echo "ERROR: required environment variable ${v} is not set" >&2
        exit 1
    fi
done

JENKINS_URL="${JENKINS_URL%/}"
JOB_PATH="${ORCHESTRATOR_JOB_PATH:-job/Spyre/job/orchestrator}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-30}"
QUEUE_TIMEOUT_SECONDS="${QUEUE_TIMEOUT_SECONDS:-600}"

auth=(-u "${JENKINS_USER}:${JENKINS_TOKEN}")

echo "Fetching CSRF crumb from ${JENKINS_URL}..." >&2
crumb_header=()
crumb_json="$(curl -fsS "${auth[@]}" "${JENKINS_URL}/crumbIssuer/api/json" || true)"
if [[ -n "${crumb_json}" ]]; then
    crumb_field="$(echo "${crumb_json}" | jq -r '.crumbRequestField')"
    crumb_value="$(echo "${crumb_json}" | jq -r '.crumb')"
    if [[ -n "${crumb_field}" && -n "${crumb_value}" && "${crumb_field}" != "null" ]]; then
        crumb_header=(-H "${crumb_field}: ${crumb_value}")
    fi
else
    echo "no crumbIssuer response (CSRF protection may be disabled) — proceeding without a crumb" >&2
fi

echo "Dispatching orchestrator: PRESET=trigger-pr-validation TRIGGER_PR=${TRIGGER_PR}" >&2
queue_location="$(curl -fsS "${auth[@]}" "${crumb_header[@]}" -D - -o /dev/null \
    --data-urlencode "TRIGGER_PR=${TRIGGER_PR}" \
    --data-urlencode "PRESET=trigger-pr-validation" \
    --data-urlencode "MERGE_ON_GREEN=false" \
    "${JENKINS_URL}/${JOB_PATH}/buildWithParameters" \
    | grep -i '^Location:' | tr -d '\r\n' | awk '{print $2}')"

if [[ -z "${queue_location}" ]]; then
    echo "ERROR: Jenkins did not return a queue item Location header — dispatch failed" >&2
    exit 1
fi
echo "queued: ${queue_location}" >&2

build_url=""
elapsed=0
while (( elapsed < QUEUE_TIMEOUT_SECONDS )); do
    queue_json="$(curl -fsS "${auth[@]}" "${queue_location}api/json")"
    build_url="$(echo "${queue_json}" | jq -r '.executable.url // empty')"
    if [[ -n "${build_url}" ]]; then
        break
    fi
    cancelled="$(echo "${queue_json}" | jq -r '.cancelled // false')"
    if [[ "${cancelled}" == "true" ]]; then
        echo "ERROR: Jenkins cancelled the queued build before it started" >&2
        exit 1
    fi
    sleep "${POLL_INTERVAL_SECONDS}"
    elapsed=$(( elapsed + POLL_INTERVAL_SECONDS ))
done

if [[ -z "${build_url}" ]]; then
    echo "ERROR: build did not leave the Jenkins queue within ${QUEUE_TIMEOUT_SECONDS}s (executor capacity?)" >&2
    exit 1
fi
echo "Jenkins build: ${build_url}" >&2
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    {
        echo "## Jenkins orchestrator run"
        echo ""
        echo "[${build_url}](${build_url})"
    } >> "${GITHUB_STEP_SUMMARY}"
fi

result=""
while true; do
    build_json="$(curl -fsS "${auth[@]}" "${build_url}api/json")"
    building="$(echo "${build_json}" | jq -r '.building')"
    if [[ "${building}" == "false" ]]; then
        result="$(echo "${build_json}" | jq -r '.result')"
        break
    fi
    sleep "${POLL_INTERVAL_SECONDS}"
done

echo "Jenkins orchestrator result: ${result} (${build_url})" >&2
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    echo "Result: **${result}**" >> "${GITHUB_STEP_SUMMARY}"
fi

if [[ "${result}" != "SUCCESS" ]]; then
    echo "ERROR: Jenkins orchestrator run concluded '${result}' — see ${build_url}" >&2
    exit 1
fi

echo "Jenkins orchestrator run succeeded." >&2
