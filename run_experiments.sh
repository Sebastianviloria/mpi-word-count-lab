#!/bin/bash
# Experimental plan used for the README (run on the HOST, macOS/Linux).
#  - 1 warm-up run of each program (baseline, mpi1, mpi2), not counted;
#  - RUNS rounds; each round runs baseline, mpi1 and mpi2 once (interleaved,
#    so slow drifts of the machine affect the three programs equally);
#  - PAUSE seconds between consecutive runs (fanless MacBook Air cool-down);
#  - before each run, wait (up to MAX_WAIT s) until the host 1-minute load
#    average is below MAX_LOAD, because macOS background daemons (Spotlight,
#    media analysis, iCloud...) were observed stealing several cores.
#    The load average and the top CPU consumers are stored in every log.
# Every raw output goes to results/.
#
# Usage:  bash run_experiments.sh   (P=8 RUNS=3 PAUSE=30 MAX_LOAD=2.5 MAX_WAIT=900)
set -euo pipefail

cd "$(dirname "$0")"
P="${P:-8}"
RUNS="${RUNS:-3}"
PAUSE="${PAUSE:-30}"
MAX_LOAD="${MAX_LOAD:-2.5}"
MAX_WAIT="${MAX_WAIT:-900}"
IMAGE="augustosalazar/slim-mpi:2"
OUT="results"
mkdir -p "$OUT"

load1() { sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}' || awk '{print $1}' /proc/loadavg; }

wait_quiet() {
  local waited=0
  while awk -v l="$(load1)" -v m="$MAX_LOAD" 'BEGIN{exit !(l>=m)}' && [ "$waited" -lt "$MAX_WAIT" ]; do
    sleep 10; waited=$((waited + 10))
  done
  echo "$waited"
}

now() { python3 -c 'import time; print(f"{time.time():.6f}")'; }

docker_run() { docker run --rm -v "$PWD":/app "$IMAGE" "$@"; }

{
  echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host_cpu=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -m)"
  echo "host_performance_cores=$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || echo NA)"
  echo "host_efficiency_cores=$(sysctl -n hw.perflevel1.physicalcpu 2>/dev/null || echo NA)"
  echo "host_logical_cpus=$(sysctl -n hw.ncpu 2>/dev/null || nproc)"
  echo "host_os=$(sw_vers -productVersion 2>/dev/null || uname -r)"
  echo "docker_server=$(docker info --format '{{.ServerVersion}}')"
  echo "docker_vm_cpus=$(docker info --format '{{.NCPU}}')"
  echo "docker_vm_mem_bytes=$(docker info --format '{{.MemTotal}}')"
  echo "image=$IMAGE"
  echo "image_architecture=$(docker image inspect "$IMAGE" --format '{{.Architecture}}/{{.Os}}')"
  echo "container_nproc=$(docker_run nproc)"
  echo "container_python=$(docker_run python --version 2>&1)"
  echo "container_mpi=$(docker_run mpiexec --version 2>&1 | head -n 1)"
  echo "container_mpi4py=$(docker_run python -c 'import mpi4py; print(mpi4py.__version__)')"
  echo "P=$P RUNS=$RUNS PAUSE=$PAUSE MAX_LOAD=$MAX_LOAD MAX_WAIT=$MAX_WAIT order=interleaved"
} > "$OUT/environment.txt"
cat "$OUT/environment.txt"

# run_one <name> <label> <command...>
run_one() {
  local name="$1" label="$2"; shift 2
  local log="$OUT/${name}_${label}.log"
  local waited before top
  waited=$(wait_quiet)
  before=$(load1)
  # 2 samples: the first sample of macOS top always reports 0% CPU
  top=$(top -l 2 -o cpu -n 5 -stats command,cpu 2>/dev/null | tail -5 | tr -s ' ' | paste -sd ';' - || true)
  echo ">>> $name $label (waited ${waited}s, load1=$before)"
  local t0 t1
  t0=$(now)
  docker_run "$@" > "$log" 2>&1
  t1=$(now)
  # wall time seen from the host (includes container + mpiexec start-up)
  python3 -c "print(f'HOST_WALL_SECONDS={$t1 - $t0:.6f}')" >> "$log"
  echo "THERMAL: $(pmset -g therm 2>/dev/null | tr '\n' ' ' | tr -s ' ')" >> "$log"
  echo "HOST_LOAD1_BEFORE=$before" >> "$log"
  echo "HOST_LOAD1_AFTER=$(load1)" >> "$log"
  echo "HOST_WAITED_FOR_QUIET_SECONDS=$waited" >> "$log"
  echo "HOST_TOP_CPU_BEFORE: $top" >> "$log"
  grep -E "Tiempo de ejecuc|EXECUTION_TIME|HOST_WALL" "$log" | tr '\n' ' '; echo
}

BASE_CMD="python /app/baseline_secuencial.py"
MPI1_CMD="mpiexec --allow-run-as-root -n $P python /app/mpi1.py"
MPI2_CMD="mpiexec --allow-run-as-root -n $P python /app/mpi2.py"

run_one baseline warmup $BASE_CMD; sleep "$PAUSE"
run_one mpi1 warmup $MPI1_CMD;     sleep "$PAUSE"
run_one mpi2 warmup $MPI2_CMD
for r in $(seq 1 "$RUNS"); do
  sleep "$PAUSE"; run_one baseline "run$r" $BASE_CMD
  sleep "$PAUSE"; run_one mpi1 "run$r" $MPI1_CMD
  sleep "$PAUSE"; run_one mpi2 "run$r" $MPI2_CMD
done
for v in baseline mpi1 mpi2; do cp "dataset/${v}_results.csv" "$OUT/${v}_results.csv"; done

{
  for v in mpi1 mpi2; do
    if cmp -s "$OUT/baseline_results.csv" "$OUT/${v}_results.csv"; then
      echo "$v full counts (200 query words) IDENTICAL to baseline"
    else
      echo "$v full counts DIFFER from baseline"
    fi
  done
} | tee "$OUT/correctness.txt"
echo "Done. Now run: python3 analyze.py"
