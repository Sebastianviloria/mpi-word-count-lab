#!/bin/bash
# Design check for MPI version 2: number of requests each worker keeps in
# flight (PREFETCH = 1 vs PREFETCH = 2, the default used in mpi2.py).
# Same protocol as run_experiments.sh: 1 warm-up per variant (not counted),
# RUNS interleaved rounds, PAUSE seconds between runs, and wait until the host
# 1-minute load average is below MAX_LOAD before each run.
# Raw logs go to results/design_variants/. Analyze with: python3 analyze.py
#
# Usage:  bash run_design_check.sh   (P=8 RUNS=3 PAUSE=30 MAX_LOAD=2.5 MAX_WAIT=900)
set -euo pipefail

cd "$(dirname "$0")"
P="${P:-8}"
RUNS="${RUNS:-3}"
PAUSE="${PAUSE:-30}"
MAX_LOAD="${MAX_LOAD:-2.5}"
MAX_WAIT="${MAX_WAIT:-900}"
IMAGE="augustosalazar/slim-mpi:2"
OUT="results/design_variants"
mkdir -p "$OUT"

load1() { sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}' || awk '{print $1}' /proc/loadavg; }

wait_quiet() {
  local waited=0
  while awk -v l="$(load1)" -v m="$MAX_LOAD" 'BEGIN{exit !(l>=m)}' && [ "$waited" -lt "$MAX_WAIT" ]; do
    sleep 10; waited=$((waited + 10))
  done
  echo "$waited"
}

# run_variant <prefetch> <label>
run_variant() {
  local pf="$1" label="$2"
  local log="$OUT/mpi2_prefetch${pf}_${label}.log"
  local waited before
  waited=$(wait_quiet)
  before=$(load1)
  echo ">>> mpi2 PREFETCH=$pf $label (waited ${waited}s, load1=$before)"
  docker run --rm -e PREFETCH="$pf" -v "$PWD":/app "$IMAGE" \
    mpiexec --allow-run-as-root -x PREFETCH -n "$P" python /app/mpi2.py > "$log" 2>&1
  echo "THERMAL: $(pmset -g therm 2>/dev/null | tr '\n' ' ' | tr -s ' ')" >> "$log"
  echo "HOST_LOAD1_BEFORE=$before" >> "$log"
  echo "HOST_WAITED_FOR_QUIET_SECONDS=$waited" >> "$log"
  grep -E "EXECUTION_TIME" "$log"
  cmp -s dataset/baseline_results.csv dataset/mpi2_results.csv \
    && echo "COUNTS_IDENTICAL_TO_BASELINE=yes" >> "$log" \
    || echo "COUNTS_IDENTICAL_TO_BASELINE=no" >> "$log"
}

# baseline counts for the correctness check (not timed here)
docker run --rm -v "$PWD":/app "$IMAGE" python /app/baseline_secuencial.py > /dev/null

run_variant 1 warmup; sleep "$PAUSE"
run_variant 2 warmup
for r in $(seq 1 "$RUNS"); do
  sleep "$PAUSE"; run_variant 1 "run$r"
  sleep "$PAUSE"; run_variant 2 "run$r"
done
echo "Done. Now run: python3 analyze.py"
