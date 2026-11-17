# 1. Title

**LAB 2 – Parallel Word Counting in a Text Corpus with MPI**
(sequential baseline, MPI version 1 with static distribution, MPI version 2 with dynamic master-worker distribution)

- **Author:** Sebastián Viloria
- **Submission date:** 2026-11-16

Every number in this document comes from the raw logs in `results/` and is computed by `analyze.py`
(`python3 analyze.py` prints and writes `results/summary.md` / `results/summary.json`; its *Dataset* section is only produced when `dataset/` has been regenerated).

---

# 2. Problem Description

`generator.py` creates `dataset/` with:

- `consulta.txt`: the query, one word per line;
- `file_0001.txt … file_3000.txt`: the corpus.

The task is to count how many times each query word appears in the whole corpus and print the 10 most frequent query words.
Tokens are obtained exactly as in `baseline_secuencial.py`: each line is split on whitespace and lower-cased.

The dataset is deliberately heterogeneous, which is what makes load balancing relevant (values from `analyze.py`, section *Dataset*):

| Property | Value |
|---|---|
| Files | 3000 |
| Query words | 200 |
| Total size / total words | 275.1 MB / 44,951,458 words |
| Words per file | min 2,000, max 99,859 (49.9x ratio) |
| Small files (2k–5k words) | 1,755 |
| Medium files (10k–20k words) | 908 |
| Large files (50k–100k words) | 337, holding 56.4% of all words |

The generator uses a fixed seed (42), so the dataset is identical on every run.

---

# 3. Environment and Execution Instructions

**Environment** (recorded in `results/environment.txt`):

| Item | Value |
|---|---|
| Host | MacBook Air, Apple M5 (4 performance + 6 efficiency cores, 10 logical CPUs, fanless) |
| Container runtime | Docker Desktop, Docker Engine 29.8.2 (Linux VM with 10 CPUs, 8319504384 bytes of RAM) |
| Image | `augustosalazar/slim-mpi:2`, architecture `arm64/linux` (native on Apple Silicon, no emulation) |
| Software in the image | Python 3.8.20, Open MPI (OpenRTE) 4.1.4, mpi4py 4.1.1 |
| Process count | **P = 8**, the value recommended by `Detectar_procesos_mpi` (see 3.a) |

**Files in this repository**

| File | Role |
|---|---|
| `generator.py`, `baseline_secuencial.py`, `run_all.sh` | Provided by the course, **unchanged** |
| `mpi1.py` | MPI version 1: broadcast plus static distribution |
| `mpi2.py` | MPI version 2: dynamic master-worker distribution |
| `run_experiments.sh` | Runs the experimental plan of this report and stores every raw log in `results/` |
| `run_design_check.sh` | Design check of `mpi2.py`: PREFETCH = 1 versus 2, same protocol, logs in `results/design_variants/` |
| `analyze.py` | Computes T_seq, T_p, S_p, E_p, LI and spread from `results/` |

**How to run** (from the repository root; on Windows `cmd` use `"%cd%:/app"` instead of `"$(pwd)":/app`):

> **The `dataset/` folder is not included in this repository** (275 MB). Regenerate it with step 0 below before running anything else.
> `generator.py` uses a fixed seed (42), so it recreates exactly the same 3000 files and `consulta.txt` used for the results in `results/`.

```bash
# 0) regenerate the dataset (creates dataset/ and spanish_words.info)
docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 python /app/generator.py
# 1) sequential baseline
docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 python /app/baseline_secuencial.py
# 2) MPI version 1 and version 2 with P = 8
docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root -n 8 python /app/mpi1.py
docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 mpiexec --allow-run-as-root -n 8 python /app/mpi2.py
# 3) full experimental plan of this report (host side, ~15-30 min) and analysis
bash run_experiments.sh
python3 analyze.py
# 4) course batch script (NP = 2, 4, 8; WARNING: it deletes results/ first)
docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 sh /app/run_all.sh
```

Both MPI programs print `EXECUTION_TIME=<seconds>`, so `run_all.sh` collects their times in `results/times_summary.csv`.

## a. Experimental Plan

| Aspect | Decision |
|---|---|
| Question 1 | Does MPI v1 improve the sequential baseline, and how close is S_p to P? |
| Question 2 | How much load imbalance does static distribution produce, and does dynamic distribution (v2) reduce it enough to lower the total time? |
| Process count | One value, P = 8, from `Detectar_procesos_mpi` (`results/detectar_procesos_mpi.log`). It times a CPU-bound MPI task for N = 1…10 (`nproc` = 10 in the container) and picked N = 8 (median 0.925 s, versus 3.869 s for N = 1). |
| Programs | `baseline_secuencial.py`, `mpi1.py`, `mpi2.py`, all on the same dataset |
| Repetitions | 1 warm-up run per program (discarded: it fills the file cache), then **3 valid runs** per program |
| Order | Interleaved rounds (baseline → mpi1 → mpi2, three times), so slow changes of the machine affect all programs equally |
| Cool-down | 30 s pause between consecutive runs (fanless laptop) |
| Quiet machine | Before each run the script waits until the host 1-minute load average is < 2.5 (see 5.c). Load average and thermal state are stored in every log. |
| Time measured | Sequential: the program's own timer (counting phase). MPI: `MPI.Wtime()` on rank 0, from a `Barrier` before reading the query until the global result is merged. Both exclude interpreter, container and `mpiexec` start-up. The host wall time including Docker start-up is also stored (`HOST_WALL_SECONDS`). |
| Local time t_i | Time each rank spends counting words in its files (I/O plus counting), measured with `MPI.Wtime()` |
| Metrics | T_seq = mean of 3 runs; T_p = mean of 3 runs; S_p = T_seq / T_p; E_p = S_p / P; LI = max(t_i) / mean(t_i) and spread = (max t_i − min t_i) / mean t_i, computed per run and averaged |
| Correctness | Top 10 of every run compared with the baseline, and the full 200-word count tables compared (`results/correctness.txt`) |

## b. Sequential baseline (what it does and how)

`baseline_secuencial.py` (provided, unchanged) reads `consulta.txt` into a set and then goes through every `file_*.txt` in `os.listdir` order.
For each line it splits on whitespace, lower-cases the tokens and increments a `Counter` for every token in the query set.
It prints its execution time (the counting phase), the number of files and tokens, and `Counter.most_common(10)`, and writes all 200 counts to `dataset/baseline_results.csv`.
It runs in one process, so it uses one core.

## c. MPI version 1 (what it does and how)

`mpi1.py` follows the steps required in Part 1:

1. **rank 0** reads `consulta.txt` and **broadcasts** the query set (`comm.bcast`).
2. **rank 0** lists the `file_*.txt` files (sorted by name, so the split is reproducible).
3. **Static distribution:** the list is cut into P contiguous blocks with the same number of files (3000 / 8 = 375 files per rank) and sent with `comm.scatter`.
4. Every rank counts the query words in its own files with the same counting rule as the baseline, and measures its local time t_i.
5. Partial `Counter`s and per-rank statistics (files, bytes, tokens, t_i) are **gathered** on rank 0 (`comm.gather`), which merges them, prints the per-process report, LI and the **top 10**, and writes `dataset/mpi1_results.csv`.

The split is balanced in *number of files*, not in *amount of work*: the file sizes vary 49.9x, and the cores are not all equally fast.

**MPI version 2** (`mpi2.py`, results in 4.d) keeps steps 1, 2 and 5. It replaces steps 3–4 with a dynamic master-worker scheme:

- The file list is cut into small **tasks** of 4 consecutive files (750 tasks).
- **Workers** (ranks 1…7) ask rank 0 for a task, count it, and ask again. Each worker keeps **2 requests in flight** (prefetch): when a task arrives it immediately asks for the next one and then starts counting. So the next task is usually already waiting when the current one ends.
- **Rank 0 is a working master:** it takes tasks from the same queue for itself and, between two files, answers pending requests (`comm.Iprobe`). When the queue is empty it answers every outstanding request with `STOP`. MPI keeps message order per sender, so a worker never receives a task after a `STOP`.
- All 8 processes count words, so the comparison with v1, which also has 8 counting processes, is fair.

Design decisions made during development:

- A first version used a **dedicated (idle) master**, which left only 7 counting processes. Rank 0 now also counts words.
- The master used to `stat` every file to sort tasks by size. Through the Docker bind mount this added serial time before the first task, so both programs now list files with `os.scandir` (no per-file `stat`).
- **Requests in flight (`PREFETCH`).** This one was measured with the same protocol (`run_design_check.sh`, logs in `results/design_variants/`). With 1 request in flight, workers waited 0.132 s on average for the master and LI was 1.082. With 2 requests, the wait dropped to 0.031 s and LI to 1.024, so 2 is the default. The mean times (1.226 s versus 1.211 s) are not conclusive because of one slow run (1.431 s), although the other two PREFETCH=2 runs (1.090 s, 1.112 s) were faster than every PREFETCH=1 run.

## d. Test procedure

1. Generate the dataset (`results/generator.log`) and run `Detectar_procesos_mpi` ([detectar_procesos_mpi.py](https://github.com/augustosalazar/mpi_taller_sudoku/blob/main/detectar_procesos_mpi.py), linked in the lab statement) to choose P (`results/detectar_procesos_mpi.log`).
2. Smoke tests: `mpi1.py` and `mpi2.py` with P = 1 and 8 (P = 2 and 4 through `run_all.sh`); compare the output with the baseline.
3. Run `bash run_experiments.sh`. It stores the environment and, per run, `results/<program>_<warmup|runK>.log` (full program output, `HOST_WALL_SECONDS`, load average, thermal state), and copies the three result CSVs to `results/`.
4. Correctness: `run_experiments.sh` compares the full 200-word tables (`results/correctness.txt`), and `analyze.py` checks that the top 10 of every run equals the baseline's top 10.
5. `bash run_design_check.sh` measures the PREFETCH design choice of v2 (section 3.c).
6. `python3 analyze.py` produces every table of sections 3.c and 4.
7. `run_all.sh` was also executed, on a copy of the folder because it deletes `results/`. It completed successfully for NP = 2, 4 and 8, with a correct top 10 for both versions. Its output is kept in `results/run_all_check/`. It runs without pauses or load control, so it is not used for the analysis.

---

# 4. Experimental Plan Execution

Campaign used for the analysis: `results/*.log` (interleaved, with pauses and load control).

## a. Sequential baseline timing

| Run | Time (s) | Host wall incl. Docker start (s) |
|---|---|---|
| 1 | 4.386 | 4.588 |
| 2 | 4.493 | 4.788 |
| 3 | 4.365 | 4.629 |
| **Mean T_seq** | **4.415** (sd 0.068) | 4.668 |

Global output (identical in every run and identical to the sample in the course README):

| # | Word | Count |
|---|---|---|
| 1 | a | 785774 |
| 2 | para | 392156 |
| 3 | sus | 228913 |
| 4 | otros | 105530 |
| 5 | ante | 99832 |
| 6 | unos | 88794 |
| 7 | otra | 83901 |
| 8 | vosotros | 61617 |
| 9 | mios | 58420 |
| 10 | tuya | 56635 |

Totals: 3000 files, 44,951,458 tokens, 3,631,778 occurrences.

## b. MPI version 1 timing results

| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | 1.253 | 1.244 | 0.941 | 1.094 | 1.137 | 0.277 | 1.545 |
| 2 | 1.224 | 1.205 | 0.924 | 1.107 | 1.088 | 0.253 | 1.556 |
| 3 | 1.212 | 1.200 | 0.883 | 1.088 | 1.103 | 0.291 | 1.564 |
| **Mean** | **1.230** (sd 0.021) | 1.216 | 0.916 | 1.096 | **1.110** | **0.274** | 1.555 |

**S_p = 4.415 / 1.230 = 3.59; E_p = 3.59 / 8 = 0.449.**
In all 3 runs the top 10 equals the baseline's, and the complete table of the 200 counts is identical to `baseline_results.csv`.

## c. Load imbalance evidence (per-process local times and LI)

Per-process report of MPI v1 (every rank always receives the same 375 files, so MB is the same in every run):

| Rank | Files | MB | t_i run 1 (s) | t_i run 2 (s) | t_i run 3 (s) | Mean t_i (s) |
|---|---|---|---|---|---|---|
| 0 | 375 | 36.73 | 1.122 | 1.158 | 1.186 | 1.155 |
| 1 | 375 | 29.37 | 0.941 | 0.924 | 0.883 | **0.916** |
| 2 | 375 | 37.82 | 1.244 | 1.205 | 1.193 | **1.214** |
| 3 | 375 | 36.57 | 1.132 | 1.119 | 1.169 | 1.140 |
| 4 | 375 | 32.32 | 1.009 | 1.043 | 1.026 | 1.026 |
| 5 | 375 | 33.86 | 1.029 | 1.143 | 1.057 | 1.076 |
| 6 | 375 | 33.10 | 1.070 | 1.092 | 0.988 | 1.050 |
| 7 | 375 | 35.28 | 1.204 | 1.173 | 1.200 | 1.192 |

Evidence:

- **LI** is 1.137, 1.088 and 1.103 in the three runs (mean **1.110**). The slowest rank is about 11% slower than the average, and the spread is 0.274 (about 27% of the mean between the fastest and slowest rank).
- **Same file count, very different work:** the ranks receive between 29.37 MB (rank 1) and 37.82 MB (rank 2). Rank 1 is always the fastest and rank 2 is almost always the slowest. The Pearson correlation between MB assigned and t_i over all runs is **0.91**, so file size explains most of the imbalance.
- **Cost:** on average all ranks wait for the slowest one for max t_i − mean t_i = **0.120 s**, which is 9.8% of T_p.

## d. MPI version 2: how it corrects the imbalance, and its results (total execution time, speedup, efficiency, LI)

**How it corrects the imbalance.** v1 decides the assignment before knowing how long each file will take.
v2 assigns work *when a process becomes free*. A process that got large files or runs on a slow (efficiency) core simply asks for fewer tasks, and a fast one asks for more.
Tasks are small (4 files), so at the end every process finishes within roughly one task of the others. Prefetching keeps the extra communication from becoming idle time.

| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | 1.147 | 1.109 | 1.064 | 1.089 | 1.018 | 0.042 | 1.432 |
| 2 | 1.119 | 1.102 | 1.043 | 1.069 | 1.030 | 0.055 | 1.463 |
| 3 | 1.103 | 1.079 | 1.034 | 1.056 | 1.022 | 0.043 | 1.392 |
| **Mean** | **1.123** (sd 0.022) | 1.097 | 1.047 | 1.072 | **1.024** | **0.046** | 1.429 |

Per-process report of MPI v2 (files and MB differ in each run because the assignment is dynamic; columns 2–3 are run 1):

| Rank | Files (run 1) | MB (run 1) | t_i run 1 (s) | t_i run 2 (s) | t_i run 3 (s) | Mean t_i (s) | Mean files | Mean wait (s) |
|---|---|---|---|---|---|---|---|---|
| 0 (master) | 360 | 37.29 | 1.091 | 1.045 | 1.036 | 1.058 | 397.3 | 0.032 |
| 1 | 376 | 33.27 | 1.064 | 1.102 | 1.034 | 1.067 | 376.0 | 0.032 |
| 2 | 368 | 33.89 | 1.095 | 1.099 | 1.055 | 1.083 | 365.3 | 0.020 |
| 3 | 380 | 35.20 | 1.089 | 1.043 | 1.071 | 1.067 | 373.3 | 0.037 |
| 4 | 360 | 35.39 | 1.109 | 1.064 | 1.079 | 1.084 | 382.7 | 0.023 |
| 5 | 376 | 33.31 | 1.093 | 1.062 | 1.039 | 1.065 | 368.0 | 0.031 |
| 6 | 424 | 33.80 | 1.091 | 1.064 | 1.071 | 1.076 | 389.3 | 0.029 |
| 7 | 356 | 32.91 | 1.082 | 1.077 | 1.062 | 1.074 | 348.0 | 0.038 |

Here t_i is the time spent counting, the same definition as in v1. Waiting for the master is reported separately (column *Mean wait*). If the wait is added to t_i, LI is 1.016, so including it does not change the conclusion.

The number of files per rank now varies (from 348.0 to 397.3 on average), while the local times are nearly equal (mean t_i from 1.058 to 1.084 s).
The correlation between MB and t_i drops to **0.32**: the work is no longer fixed in advance, so file sizes no longer drive the imbalance.

**Comparison of both versions** (P = 8, T_seq = 4.415 s):

| Metric | Sequential | MPI v1 (static) | MPI v2 (dynamic) |
|---|---|---|---|
| Mean execution time (s) | 4.415 | 1.230 | **1.123** |
| Std. dev. of time (s) | 0.068 | 0.021 | 0.022 |
| Speedup S_p | 1.00 | 3.59 | **3.93** |
| Efficiency E_p | 1.00 | 0.449 | **0.491** |
| Mean LI | – | 1.110 | **1.024** |
| Mean relative spread | – | 0.274 | **0.046** |
| Host wall time incl. Docker start (s) | 4.668 | 1.555 | 1.429 |

v2 is **8.7% faster** than v1 (T_v1 / T_v2 = 1.095). The difference (0.107 s) is 5.0 times the standard deviation of v1 and 4.8 times that of v2, and every v2 run (1.103–1.147 s) is faster than every v1 run (1.212–1.253 s). In all 3 runs the top 10 equals the baseline's, and the full table of counts is identical.

---

# 5. Analysis

## a. Parallel performance

**Yes, MPI v1 improved the baseline:** 4.415 s → 1.230 s, **S_p = 3.59**, **E_p = 0.449** (v2: S_p = 3.93, E_p = 0.491). This is far from the ideal S_p = 8, which would mean 0.552 s.

| Where the time goes (from `analyze.py`) | MPI v1 | MPI v2 |
|---|---|---|
| Outside counting (start-up, bcast, scatter/messages, gather, merge): T_p − max t_i (s) | 0.013 (1.1% of T_p) | 0.026 (2.3% of T_p) |
| Imbalance: max t_i − mean t_i (s) | 0.120 | 0.025 |
| Work inflation: Σ t_i / T_seq | 1.99 | 1.94 |

**What explains the gap:** communication is negligible and imbalance is a minor part. The main cause is that **every process counts about 2x slower than the sequential program alone** (Σ t_i = 1.99 × T_seq). With 8 processes and only 4 performance cores, at least 4 processes run on efficiency cores. All of them also share memory bandwidth, caches and the Docker file system.
The `Detectar_procesos_mpi` measurements confirm this ceiling: on the same container a pure CPU-bound task reaches only **4.18** at N = 8 (3.869 s → 0.925 s). v1 reaches 0.86 and v2 **0.94** of that reference.

## b. Load balance

- **Evidence in v1:** LI = **1.110** (1.137 / 1.088 / 1.103) and spread 0.274. Each rank gets 375 files but between 29.37 and 37.82 MB, and t_i follows the MB assigned (correlation **0.91**). Rank 1 is always the fastest and rank 2 is the slowest in 2 of 3 runs. The imbalance costs 0.120 s per run.
- **v2 reduced it:** LI = **1.024**, spread 0.046 (5.9x smaller), correlation with MB 0.32, imbalance cost 0.025 s.
- **Real improvement? Yes, but moderate and reliable only within one session:** T_p 1.230 → 1.123 s (**−8.7%**), and v2 won 3 of 3 interleaved rounds. Between sessions, however, the same v2 configuration varied by +7.8% (see 5.c), a similar magnitude. The robust evidence is the LI reduction (1.110 → 1.024): v2's LI stayed between 1.014 and 1.024 in every session. Balancing can only recover the 0.120 s of imbalance; the 2x per-process slowdown remains.

## c. Limitations

| Limitation | How much it weakens the conclusions |
|---|---|
| **Docker inside a Linux VM on macOS**, with files read through a bind mount | Absolute times differ from a native Linux node, and file-system calls are slower. Both versions ran in the same environment, so the v1 versus v2 comparison is less affected. |
| **4 performance + 6 efficiency cores**, processes not pinned | Main cause of E_p = 0.449–0.491. The share of the imbalance caused by core speed cannot be separated from the share caused by file size. |
| **Fanless MacBook Air (thermal throttling)** | Mitigated with a warm-up run, 30 s pauses and interleaved order. `pmset -g therm` recorded no warnings, but small clock reductions cannot be ruled out. |
| **Background load on the host** | A first campaign (`results/campaign1_background_load/`) ran while macOS daemons used several cores: T_seq = 9.006 s, T_v1 = 2.262 s (S_p 3.98, LI 1.083), T_v2 = 2.282 s (S_p 3.95, LI 1.014). There v2 balanced better but was not faster. The final campaign waited for load < 2.5, and the slow PREFETCH=2 run in the design check (1.431 s) shows that noise still appears occasionally. The absolute S_p depends on the state of the host. In the final logs only the load average documents that state: the stored top-CPU field is empty, because the first sample of macOS `top` reports 0% (`run_experiments.sh` was then fixed to take two samples). |
| **Variation between sessions** | The same v2 configuration took 1.123 s (main campaign) and 1.211 s (design check), +7.8%, close to the 8.7% gain of v2 over v1. LI was 1.024 in both. Time differences are only reliable within one interleaved session. |
| **3 valid runs per program** | Enough to separate v1 from v2 within one session (difference 0.107 s, sd ≈ 0.02 s), not enough for confidence intervals. |
| **Small dataset (275 MB)** | With T_p ≈ 1.1–1.2 s, fixed costs weigh more, and a few hundredths of a second change S_p visibly. |
| **One P (8), one machine, image `arm64/linux`** | Native on Apple Silicon (no emulation). No information on scaling with P, on multi-node clusters or on `amd64`. |

**Overall:** the direction of the results is solid (MPI is clearly faster; v2 balances better and is moderately faster), and so is the explanation of the gap. The exact S_p and E_p values are specific to this laptop and its state at measurement time.

---

# 6. Conclusions

For this problem I recommend the **dynamic master-worker distribution (MPI version 2)**.
The recommendation rests mainly on load balance, which was stable: with P = 8, v2 reduced the load imbalance from LI = 1.110 to **LI = 1.024** (spread from 0.274 to 0.046), and its LI stayed between 1.014 and 1.024 in every measurement session.
In the interleaved campaign it also cut the mean execution time from 1.230 s to **1.123 s** (−8.7%, faster in 3 of 3 rounds). This raised the speedup over the 4.415 s sequential baseline from 3.59 to **3.93**, and the efficiency from 0.449 to **0.491**, while producing exactly the same top 10 and the same 200 counts as the baseline.
That time gain is reliable only as a comparison within the same session: the same v2 configuration varied by 7.8% between sessions, a magnitude similar to the gain itself.
The static split is simpler but blind to the 49.9x variation in file size and to the different core speeds: its local times followed the megabytes assigned (correlation 0.91), and everyone waited for the slowest rank.
The dynamic scheme adapts to both, with time outside the counting phase of only 2.3% of the runtime.
Its benefit is bounded, however: the remaining distance to the ideal speedup of 8 comes from the hardware (4 performance and 6 efficiency cores, shared memory and file system inside a Docker VM), which limits even a pure CPU-bound task to a speedup of 4.18 on this machine. v2 already reaches 0.94 of that limit.
