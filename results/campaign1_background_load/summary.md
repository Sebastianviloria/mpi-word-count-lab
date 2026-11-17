## Sequential baseline

| Run | Time (s) | Host wall incl. Docker start (s) |
|---|---|---|
| 1 | 9.167 | 9.425 |
| 2 | 8.934 | 9.187 |
| 3 | 8.917 | 9.179 |
| **Mean** | **9.006** (sd 0.140) | 9.264 |

## mpi1 (P = 8)

| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | 2.248 | 2.235 | 1.813 | 2.077 | 1.076 | 0.203 | 2.627 |
| 2 | 2.302 | 2.289 | 1.860 | 2.094 | 1.093 | 0.205 | 2.673 |
| 3 | 2.236 | 2.223 | 1.792 | 2.058 | 1.080 | 0.209 | 2.599 |
| **Mean** | **2.262** (sd 0.035) | 2.249 | 1.822 | 2.077 | **1.083** | **0.206** | 2.633 |

Per-process local time t_i (s), mpi1:

| Rank | Files (run 1) | MB (run 1) | t_i run 1 | t_i run 2 | t_i run 3 | Mean t_i |
|---|---|---|---|---|---|---|
| 0 | 375 | 36.73 | 2.223 | 2.185 | 2.115 | 2.174 |
| 1 | 375 | 29.37 | 1.813 | 1.860 | 1.792 | 1.822 |
| 2 | 375 | 37.82 | 2.235 | 2.289 | 2.223 | 2.249 |
| 3 | 375 | 36.57 | 2.165 | 2.147 | 2.139 | 2.150 |
| 4 | 375 | 32.32 | 1.998 | 2.057 | 1.991 | 2.015 |
| 5 | 375 | 33.86 | 2.066 | 2.140 | 2.044 | 2.083 |
| 6 | 375 | 33.10 | 1.940 | 1.942 | 1.994 | 1.959 |
| 7 | 375 | 35.28 | 2.178 | 2.133 | 2.170 | 2.160 |

## mpi2 (P = 8)

| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | 2.430 | 2.353 | 2.282 | 2.324 | 1.012 | 0.030 | 2.901 |
| 2 | 2.155 | 2.103 | 2.036 | 2.073 | 1.014 | 0.032 | 2.555 |
| 3 | 2.262 | 2.149 | 2.091 | 2.119 | 1.014 | 0.028 | 2.744 |
| **Mean** | **2.282** (sd 0.138) | 2.202 | 2.136 | 2.172 | **1.014** | **0.030** | 2.734 |

Per-process local time t_i (s), mpi2:

| Rank | Files (run 1) | MB (run 1) | t_i run 1 | t_i run 2 | t_i run 3 | Mean t_i | Mean files | Mean wait (s) |
|---|---|---|---|---|---|---|---|---|
| 0 | 352 | 33.42 | 2.282 | 2.047 | 2.138 | 2.156 | 349.3 | 0.062 |
| 1 | 408 | 33.91 | 2.333 | 2.036 | 2.104 | 2.158 | 388.0 | 0.081 |
| 2 | 376 | 35.82 | 2.326 | 2.063 | 2.131 | 2.173 | 368.0 | 0.069 |
| 3 | 368 | 34.55 | 2.328 | 2.068 | 2.149 | 2.182 | 365.3 | 0.084 |
| 4 | 344 | 34.73 | 2.350 | 2.075 | 2.115 | 2.180 | 368.0 | 0.059 |
| 5 | 400 | 34.79 | 2.303 | 2.101 | 2.127 | 2.177 | 390.7 | 0.076 |
| 6 | 380 | 32.87 | 2.317 | 2.103 | 2.097 | 2.173 | 377.3 | 0.080 |
| 7 | 372 | 34.96 | 2.353 | 2.090 | 2.091 | 2.178 | 393.3 | 0.070 |

## Comparison

| Metric | Sequential | MPI v1 (static) | MPI v2 (dynamic) |
|---|---|---|---|
| Processes | 1 | 8 | 8 |
| Mean execution time (s) | 9.006 | 2.262 | 2.282 |
| Std. dev. of time (s) | 0.140 | 0.035 | 0.138 |
| Speedup S_p = T_seq/T_p | 1.00 | 3.98 | 3.95 |
| Efficiency E_p = S_p/P | 1.00 | 0.498 | 0.493 |
| Mean LI = max(t_i)/mean(t_i) | - | 1.083 | 1.014 |
| Mean relative spread | - | 0.206 | 0.030 |
| Mean host wall time incl. Docker start (s) | 9.264 | 2.633 | 2.734 |

v2 vs v1: T_v1/T_v2 = 0.991 (-0.9% time reduction; negative means v2 is slower).

Top 10 identical to the sequential baseline in every run: YES
Full 200-word count comparison (results/correctness.txt):
- mpi1 full counts (200 query words) IDENTICAL to baseline
- mpi2 full counts (200 query words) IDENTICAL to baseline

## Derived metrics (where does the time go?)

| Metric | MPI v1 | MPI v2 |
|---|---|---|
| Ideal time T_seq/P (s) | 1.126 | 1.126 |
| Mean max t_i (s) | 2.249 | 2.202 |
| Mean of mean t_i (s) | 2.077 | 2.172 |
| Imbalance cost: mean(max t_i - mean t_i) (s) | 0.172 | 0.030 |
| Time outside counting: mean(T_p - max t_i) (s) | 0.013 | 0.081 |
| Sum of t_i over processes (s) | 16.613 | 17.377 |
| Work inflation: sum(t_i) / T_seq | 1.84 | 1.93 |
| Pearson corr(MB assigned, t_i), all runs | 0.94 | 0.06 |
- mpi1: imbalance cost = 7.6% of T_p; outside counting = 0.6% of T_p; runs range 2.236-2.302 s
- mpi2: imbalance cost = 1.3% of T_p; outside counting = 3.5% of T_p; runs range 2.155-2.430 s
- T_v1 - T_v2 = -0.020 s = -0.6 x sd(v1) = -0.1 x sd(v2); spread ratio v1/v2 = 6.8

Detectar_procesos_mpi (results/detectar_procesos_mpi.log): recommended P = 8; median time N=1: 3.869 s, N=8: 0.925 s -> CPU-bound reference speedup at P=8: 4.18 (efficiency 0.523).
- mpi1: S_p / reference speedup = 0.95
- mpi2: S_p / reference speedup = 0.94

## Dataset

- Files: 3000, query words: 200
- Total size: 275.1 MB, total words: 44951458
- Words per file: min 2000, max 99859 (ratio 49.9x); bytes per file: min 12071, max 609318
- Small (2k-5k words): 1755, medium (10k-20k): 908, large (50k-100k): 337
- Large files hold 56.4% of all words
