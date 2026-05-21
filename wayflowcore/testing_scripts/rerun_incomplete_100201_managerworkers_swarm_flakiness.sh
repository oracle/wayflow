#!/usr/bin/env bash

set -uo pipefail

repeat_count="${FLAKY_REPEAT_COUNT:-50}"
mode="serial"
pytest_bin="${PYTEST_BIN:-pytest}"
output_dir="${FLAKY_OUTPUT_DIR:-.flaky_results_$(date +%Y%m%d_%H%M%S)_managerworkers_swarm_incomplete_100201}"
tmux_session="${FLAKY_TMUX_SESSION:-wayflow-flaky-rerun-100201}"
run_in_tmux=false
stop_tmux=false
attach_tmux=false
check_collection=false
runner_args=()
child_pids=()

usage() {
  cat <<'EOF'
Usage:
  wayflowcore/testing_scripts/rerun_incomplete_100201_managerworkers_swarm_flakiness.sh [--repeat N] [--output-dir DIR]
  wayflowcore/testing_scripts/rerun_incomplete_100201_managerworkers_swarm_flakiness.sh --parallel [--repeat N] [--output-dir DIR]
  wayflowcore/testing_scripts/rerun_incomplete_100201_managerworkers_swarm_flakiness.sh --tmux [--repeat N] [--output-dir DIR]
  wayflowcore/testing_scripts/rerun_incomplete_100201_managerworkers_swarm_flakiness.sh --stop
  wayflowcore/testing_scripts/rerun_incomplete_100201_managerworkers_swarm_flakiness.sh --attach
  wayflowcore/testing_scripts/rerun_incomplete_100201_managerworkers_swarm_flakiness.sh --check-collection

Environment:
  FLAKY_REPEAT_COUNT  Default repeat count when --repeat is omitted. Defaults to 50.
  FLAKY_OUTPUT_DIR    Default output directory when --output-dir is omitted.
  FLAKY_TMUX_SESSION  Default tmux session name. Defaults to wayflow-flaky-rerun-100201.
  PYTEST_BIN          pytest executable. Defaults to pytest.

Notes:
  This reruns only tests that measured fewer than 50 attempts in:
    .flaky_results_20260515_100201_managerworkers_swarm

  The retry_test decorator intentionally exits non-zero in FLAKY_TEST_EVALUATION_MODE.
  Serial mode is the default to reduce model-server contention and help slow tests reach 50
  attempts before the decorator's per-test cap.
EOF
}

tests=(
  "swarm_always_handoff|wayflowcore/tests/test_swarm.py::test_swarm_uses_handoff_tool_in_always_handoff_mode"
  "mw_three_level|wayflowcore/tests/test_managerworkers.py::test_three_level_managerworkers_with_llms"
  "mw_linear_chain|wayflowcore/tests/test_managerworkers.py::test_linear_chain_managerworkers_with_llms"
  "mw_two_level|wayflowcore/tests/test_managerworkers.py::test_two_level_managerworkers_with_llms"
  "swarm_routing_with_handoff|wayflowcore/tests/test_swarm.py::test_swarm_can_complete_routing_task[with_handoff]"
  "mw_without_user_input|wayflowcore/tests/test_managerworkers.py::test_managerworkers_without_user_input_can_execute_as_expected"
  "swarm_without_user_input|wayflowcore/tests/test_swarm.py::test_swarm_without_user_input_can_execute_as_expected"
  "mw_exception_does_not_raise|wayflowcore/tests/test_managerworkers.py::test_managerworkers_can_do_multiple_tool_calling_with_tool_raising_exception_does_not_raise_error"
  "mw_multiple_tool_calling|wayflowcore/tests/test_managerworkers.py::test_managerworkers_can_do_multiple_tool_calling_when_appropriate"
  "swarm_exception_does_not_raise|wayflowcore/tests/test_swarm.py::test_swarm_can_do_multiple_tool_calling_with_tool_raising_exception_does_not_raise_error"
  "swarm_multiple_tool_calling|wayflowcore/tests/test_swarm.py::test_swarm_can_do_multiple_tool_calling_when_appropriate"
  "mw_multi_managers|wayflowcore/tests/test_managerworkers.py::test_multi_managers_with_llms"
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repeat)
      repeat_count="$2"
      runner_args+=("--repeat" "$2")
      shift 2
      ;;
    --parallel)
      mode="parallel"
      runner_args+=("--parallel")
      shift
      ;;
    --output-dir)
      output_dir="$2"
      runner_args+=("--output-dir" "$2")
      shift 2
      ;;
    --check-collection)
      check_collection=true
      runner_args+=("--check-collection")
      shift
      ;;
    --tmux)
      run_in_tmux=true
      shift
      ;;
    --tmux-session)
      tmux_session="$2"
      shift 2
      ;;
    --stop)
      stop_tmux=true
      shift
      ;;
    --attach)
      attach_tmux=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_path="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

if [[ "$stop_tmux" == true ]]; then
  if tmux has-session -t "$tmux_session" 2>/dev/null; then
    tmux kill-session -t "$tmux_session"
    echo "Stopped tmux session: $tmux_session"
  else
    echo "No tmux session found: $tmux_session"
  fi
  exit 0
fi

if [[ "$attach_tmux" == true ]]; then
  tmux attach-session -t "$tmux_session"
  exit $?
fi

if [[ "$run_in_tmux" == true ]]; then
  if ! command -v tmux >/dev/null 2>&1; then
    echo "tmux is not installed or not on PATH." >&2
    exit 127
  fi
  if tmux has-session -t "$tmux_session" 2>/dev/null; then
    echo "tmux session already exists: $tmux_session" >&2
    echo "Attach with: $script_path --attach --tmux-session $tmux_session" >&2
    echo "Stop with:   $script_path --stop --tmux-session $tmux_session" >&2
    exit 1
  fi
  tmux_command="cd $(printf '%q' "$PWD") && exec $(printf '%q' "$script_path")"
  if [[ ${#runner_args[@]} -gt 0 ]]; then
    for arg in "${runner_args[@]}"; do
      tmux_command+=" $(printf '%q' "$arg")"
    done
  fi
  tmux new-session -d -s "$tmux_session" "$tmux_command"
  echo "Started tmux session: $tmux_session"
  echo "Attach with: $script_path --attach --tmux-session $tmux_session"
  echo "Stop with:   $script_path --stop --tmux-session $tmux_session"
  echo "Or directly: tmux kill-session -t $tmux_session"
  exit 0
fi

cleanup_children() {
  trap - INT TERM HUP
  if [[ ${#child_pids[@]} -eq 0 ]]; then
    return
  fi
  echo
  echo "Stopping ${#child_pids[@]} running measurement process(es)..."
  for pid in "${child_pids[@]}"; do
    pkill -TERM -P "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
  done
  sleep 2
  for pid in "${child_pids[@]}"; do
    pkill -KILL -P "$pid" 2>/dev/null || true
    kill -KILL "$pid" 2>/dev/null || true
  done
}

trap 'cleanup_children; exit 130' INT TERM HUP

if [[ "$check_collection" == true ]]; then
  for entry in "${tests[@]}"; do
    name="${entry%%|*}"
    test_id="${entry#*|}"
    echo "Checking $name"
    "$pytest_bin" --collect-only -q "$test_id" >/dev/null || exit $?
  done
  echo "All incomplete test ids collected successfully."
  exit 0
fi

mkdir -p "$output_dir"
status_file="$output_dir/status.tsv"
printf "name\ttest\texit_code\tlog\n" > "$status_file"

run_one() {
  local entry="$1"
  local name="${entry%%|*}"
  local test_id="${entry#*|}"
  local log_file="$output_dir/${name}.log"
  local exit_code
  local pytest_pid

  echo "[$(date '+%H:%M:%S')] Measuring $name"
  echo "  $test_id"
  FLAKY_TEST_EVALUATION_MODE="$repeat_count" "$pytest_bin" -q "$test_id" -q --tb=short --show-capture=no > >(tee "$log_file") 2>&1 &
  pytest_pid="$!"
  child_pids+=("$pytest_pid")
  wait "$pytest_pid"
  exit_code="$?"
  printf "%s\t%s\t%s\t%s\n" "$name" "$test_id" "$exit_code" "$log_file" >> "$status_file"
}

if [[ "$mode" == "parallel" ]]; then
  echo "Running ${#tests[@]} incomplete measurements in parallel."
  echo "Parallel mode may increase per-attempt latency and hit the decorator time cap again."
  for entry in "${tests[@]}"; do
    run_one "$entry" &
    child_pids+=("$!")
  done
  wait
else
  echo "Running ${#tests[@]} incomplete measurements serially."
  for entry in "${tests[@]}"; do
    run_one "$entry"
  done
fi

echo
echo "Logs written to: $output_dir"
echo "Status written to: $status_file"
echo
echo "Suggested docstring blocks:"
if command -v rg >/dev/null 2>&1; then
  rg -n "Failure rate:|Observed on:|Average success time:|Average failure time:|Max attempt:|Justification:" "$output_dir" || true
else
  grep -R -n -E "Failure rate:|Observed on:|Average success time:|Average failure time:|Max attempt:|Justification:" "$output_dir" || true
fi
