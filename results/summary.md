## Sequential baseline

| Run | Time (s) | Host wall incl. Docker start (s) |
|---|---|---|
| 1 | 4.386 | 4.588 |
| 2 | 4.493 | 4.788 |
| 3 | 4.365 | 4.629 |
| **Mean** | **4.415** (sd 0.068) | 4.668 |

## mpi1 (P = 8)

| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | 1.253 | 1.244 | 0.941 | 1.094 | 1.137 | 0.277 | 1.545 |
| 2 | 1.224 | 1.205 | 0.924 | 1.107 | 1.088 | 0.253 | 1.556 |
| 3 | 1.212 | 1.200 | 0.883 | 1.088 | 1.103 | 0.291 | 1.564 |
| **Mean** | **1.230** (sd 0.021) | 1.216 | 0.916 | 1.096 | **1.110** | **0.274** | 1.555 |

Per-process local time t_i (s), mpi1:

| Rank | Files (run 1) | MB (run 1) | t_i run 1 | t_i run 2 | t_i run 3 | Mean t_i |
|---|---|---|---|---|---|---|
| 0 | 375 | 36.73 | 1.122 | 1.158 | 1.186 | 1.155 |
| 1 | 375 | 29.37 | 0.941 | 0.924 | 0.883 | 0.916 |
| 2 | 375 | 37.82 | 1.244 | 1.205 | 1.193 | 1.214 |
| 3 | 375 | 36.57 | 1.132 | 1.119 | 1.169 | 1.140 |
| 4 | 375 | 32.32 | 1.009 | 1.043 | 1.026 | 1.026 |
| 5 | 375 | 33.86 | 1.029 | 1.143 | 1.057 | 1.076 |
| 6 | 375 | 33.10 | 1.070 | 1.092 | 0.988 | 1.050 |
| 7 | 375 | 35.28 | 1.204 | 1.173 | 1.200 | 1.192 |

## mpi2 (P = 8)

| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | 1.147 | 1.109 | 1.064 | 1.089 | 1.018 | 0.042 | 1.432 |
| 2 | 1.119 | 1.102 | 1.043 | 1.069 | 1.030 | 0.055 | 1.463 |
| 3 | 1.103 | 1.079 | 1.034 | 1.056 | 1.022 | 0.043 | 1.392 |
| **Mean** | **1.123** (sd 0.022) | 1.097 | 1.047 | 1.072 | **1.024** | **0.046** | 1.429 |

Per-process local time t_i (s), mpi2:

| Rank | Files (run 1) | MB (run 1) | t_i run 1 | t_i run 2 | t_i run 3 | Mean t_i | Mean files | Mean wait (s) |
|---|---|---|---|---|---|---|---|---|
| 0 | 360 | 37.29 | 1.091 | 1.045 | 1.036 | 1.058 | 397.3 | 0.032 |
| 1 | 376 | 33.27 | 1.064 | 1.102 | 1.034 | 1.067 | 376.0 | 0.032 |
| 2 | 368 | 33.89 | 1.095 | 1.099 | 1.055 | 1.083 | 365.3 | 0.020 |
| 3 | 380 | 35.20 | 1.089 | 1.043 | 1.071 | 1.067 | 373.3 | 0.037 |
| 4 | 360 | 35.39 | 1.109 | 1.064 | 1.079 | 1.084 | 382.7 | 0.023 |
| 5 | 376 | 33.31 | 1.093 | 1.062 | 1.039 | 1.065 | 368.0 | 0.031 |
| 6 | 424 | 33.80 | 1.091 | 1.064 | 1.071 | 1.076 | 389.3 | 0.029 |
| 7 | 356 | 32.91 | 1.082 | 1.077 | 1.062 | 1.074 | 348.0 | 0.038 |

## Comparison

| Metric | Sequential | MPI v1 (static) | MPI v2 (dynamic) |
|---|---|---|---|
| Processes | 1 | 8 | 8 |
| Mean execution time (s) | 4.415 | 1.230 | 1.123 |
| Std. dev. of time (s) | 0.068 | 0.021 | 0.022 |
| Speedup S_p = T_seq/T_p | 1.00 | 3.59 | 3.93 |
| Efficiency E_p = S_p/P | 1.00 | 0.449 | 0.491 |
| Mean LI = max(t_i)/mean(t_i) | - | 1.110 | 1.024 |
| Mean relative spread | - | 0.274 | 0.046 |
| Mean host wall time incl. Docker start (s) | 4.668 | 1.555 | 1.429 |

v2 vs v1: T_v1/T_v2 = 1.095 (+8.7% time reduction; negative means v2 is slower).

Top 10 identical to the sequential baseline in every run: YES
Full 200-word count comparison (results/correctness.txt):
- mpi1 full counts (200 query words) IDENTICAL to baseline
- mpi2 full counts (200 query words) IDENTICAL to baseline

## Derived metrics (where does the time go?)

| Metric | MPI v1 | MPI v2 |
|---|---|---|
| Ideal time T_seq/P (s) | 0.552 | 0.552 |
| Mean max t_i (s) | 1.216 | 1.097 |
| Mean of mean t_i (s) | 1.096 | 1.072 |
| Imbalance cost: mean(max t_i - mean t_i) (s) | 0.120 | 0.025 |
| Time outside counting: mean(T_p - max t_i) (s) | 0.013 | 0.026 |
| Sum of t_i over processes (s) | 8.770 | 8.573 |
| Work inflation: sum(t_i) / T_seq | 1.99 | 1.94 |
| Pearson corr(MB assigned, t_i), all runs | 0.91 | 0.32 |
- mpi1: imbalance cost = 9.8% of T_p; outside counting = 1.1% of T_p; runs range 1.212-1.253 s
- mpi2: imbalance cost = 2.2% of T_p; outside counting = 2.3% of T_p; runs range 1.103-1.147 s
- T_v1 - T_v2 = 0.107 s = 5.0 x sd(v1) = 4.8 x sd(v2); spread ratio v1/v2 = 5.9

Detectar_procesos_mpi (results/detectar_procesos_mpi.log): recommended P = 8; median time N=1: 3.869 s, N=8: 0.925 s -> CPU-bound reference speedup at P=8: 4.18 (efficiency 0.523).
- mpi1: S_p / reference speedup = 0.86
- mpi2: S_p / reference speedup = 0.94

## Dataset

- Files: 3000, query words: 200
- Total size: 275.1 MB, total words: 44951458
- Words per file: min 2000, max 99859 (ratio 49.9x); bytes per file: min 12071, max 609318
- Small (2k-5k words): 1755, medium (10k-20k): 908, large (50k-100k): 337
- Large files hold 56.4% of all words
