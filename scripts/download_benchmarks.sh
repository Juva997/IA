#!/usr/bin/env bash
set -euo pipefail

WORKFLOW=${WORKFLOW:-benchmark-artifacts.yml}
NAME=${NAME:-benchmark-traces}
DEST=${DEST:-./benchmark_artifacts}
RUN_ID=""

usage() {
  cat <<EOF
Usage: $0 [-r run-id] [-d dest-dir] [-w workflow-file] [-n artifact-name]

Options:
  -r run-id         GitHub Actions run id to download (numeric). If omitted, the latest run of the workflow is used.
  -d dest-dir       Destination directory to extract artifact (default: ./benchmark_artifacts)
  -w workflow-file  Workflow file name to look for (default: ${WORKFLOW})
  -n artifact-name  Artifact name to download (default: ${NAME})
  -h                Show this help

Requires: gh CLI (https://cli.github.com/) authenticated with `gh auth login`.
EOF
  exit 1
}

while getopts ":r:d:w:n:h" opt; do
  case ${opt} in
    r) RUN_ID=${OPTARG} ;;
    d) DEST=${OPTARG} ;;
    w) WORKFLOW=${OPTARG} ;;
    n) NAME=${OPTARG} ;;
    h) usage ;;
    *) usage ;;
  esac
done

mkdir -p "${DEST}"

if [ -z "${RUN_ID}" ]; then
  # try to get the latest run id for the workflow
  echo "Fetching latest run for workflow: ${WORKFLOW}"
  # prefer JSON if available
  if command -v jq >/dev/null 2>&1; then
    RUN_ID=$(gh run list --workflow "${WORKFLOW}" --limit 1 --json id 2>/dev/null | jq -r '.[0].id')
  else
    # fallback parsing human-readable output
    RUN_ID=$(gh run list --workflow "${WORKFLOW}" --limit 1 2>/dev/null | awk 'NR==2{print $1}')
  fi
fi

if [ -z "${RUN_ID}" ] || [ "${RUN_ID}" = "null" ]; then
  echo "Could not determine run id for workflow ${WORKFLOW}." >&2
  echo "Run 'gh run list --workflow ${WORKFLOW}' to inspect available runs." >&2
  exit 2
fi

echo "Downloading artifact '${NAME}' from run ${RUN_ID} into ${DEST}"
gh run download "${RUN_ID}" --name "${NAME}" --dir "${DEST}"

echo "Done. Inspect ${DEST} for extracted artifacts (expecting benchmark/results)."
