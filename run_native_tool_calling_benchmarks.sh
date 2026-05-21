#!/usr/bin/env bash

set -uo pipefail

REPEAT_COUNT="${1:-20}"
if [[ $# -gt 0 ]]; then
  shift
fi
PYTHON_BIN="${PYTHON:-python}"
WORKERS_PER_SUITE="${BENCHMARK_WORKERS_PER_SUITE:-2}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

RESULTS_DIR="${BENCHMARK_RESULTS_DIR:-wayflowcore/testing_scripts/benchmark_results/native_tool_calling_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$RESULTS_DIR"

echo "Running native tool-calling benchmark tests with FLAKY_TEST_EVALUATION_MODE=${REPEAT_COUNT}."
echo "These tests are parametrized over old_template and native_tool_calling_template."
echo "Running ${WORKERS_PER_SUITE} Swarm workers and ${WORKERS_PER_SUITE} ManagerWorkers workers."
echo "Raw pytest logs will be written to ${RESULTS_DIR}."

common_pytest_args=(
  -n "$WORKERS_PER_SUITE"
  --show-capture=no
  --tb=short
  --disable-warnings
  -o log_cli=false
  -o log_level=WARNING
  -o log_cli_level=WARNING
)

run_suite() {
  local suite_name="$1"
  local test_file="$2"
  local log_file="${RESULTS_DIR}/${suite_name}.log"
  local status_file="${RESULTS_DIR}/${suite_name}.status"
  shift 2

  echo "Starting ${suite_name}; raw output: ${log_file}"
  FLAKY_TEST_EVALUATION_MODE="$REPEAT_COUNT" "$PYTHON_BIN" -m pytest \
    "$test_file" \
    "${common_pytest_args[@]}" \
    "$@" \
    >"$log_file" 2>&1
  echo "$?" >"$status_file"
}

print_retry_results() {
  local suite_name="$1"
  local log_file="${RESULTS_DIR}/${suite_name}.log"

  echo
  echo "===== ${suite_name} retry_test results ====="
  awk '
    BEGIN {
      found = 0
    }
    /^_.*_$/ {
      current_test = $0
      sub(/^_+[[:space:]]*/, "", current_test)
      sub(/[[:space:]]*_+$/, "", current_test)
    }
    /ValueError: You ran the test with FLAKY_TEST_EVALUATION_MODE=/ {
      in_result = 1
      found = 1
      quote_count = 0
      print ""
      print "-----"
      if (current_test) {
        print current_test
      }
    }
    in_result {
      line = $0
      sub(/^E[[:space:]]*/, "", line)
      sub(/^ValueError: /, "", line)
      print line
      if (line ~ /^[[:space:]]*"""[[:space:]]*$/) {
        quote_count += 1
        if (quote_count == 2) {
          in_result = 0
        }
      }
    }
    END {
      if (!found) {
        print "No retry_test result blocks found. Inspect the raw log for details."
      }
    }
  ' "$log_file"

  echo
  echo "===== ${suite_name} non-docstring failures ====="
  awk '
    BEGIN {
      found = 0
    }
    /^_.*_$/ {
      current_test = $0
      sub(/^_+[[:space:]]*/, "", current_test)
      sub(/[[:space:]]*_+$/, "", current_test)
    }
    /E[[:space:]]+Failed:/ {
      found = 1
      line = $0
      sub(/^E[[:space:]]*/, "", line)
      print current_test " -> " line
    }
    END {
      if (!found) {
        print "None."
      }
    }
  ' "$log_file"
}

run_suite "swarm" "wayflowcore/tests/test_benchmark_swarm.py" "$@" &
swarm_pid=$!

run_suite "managerworkers" "wayflowcore/tests/test_benchmark_managerworkers.py" "$@" &
managerworkers_pid=$!

wait "$swarm_pid"
wait "$managerworkers_pid"

summary_file="${RESULTS_DIR}/summary.log"
{
  print_retry_results "swarm"
  print_retry_results "managerworkers"
} | tee "$summary_file"

swarm_status="$(cat "${RESULTS_DIR}/swarm.status")"
managerworkers_status="$(cat "${RESULTS_DIR}/managerworkers.status")"

echo
echo "Raw logs:"
echo "- ${RESULTS_DIR}/swarm.log"
echo "- ${RESULTS_DIR}/managerworkers.log"
echo "Clean summary:"
echo "- ${summary_file}"

if [[ "$swarm_status" != "0" && "$swarm_status" != "1" ]]; then
  echo "Swarm pytest exited with unexpected status ${swarm_status}."
  exit "$swarm_status"
fi

if [[ "$managerworkers_status" != "0" && "$managerworkers_status" != "1" ]]; then
  echo "ManagerWorkers pytest exited with unexpected status ${managerworkers_status}."
  exit "$managerworkers_status"
fi

echo "Done. Pytest status 1 is expected when tests execute in flaky evaluation mode."
