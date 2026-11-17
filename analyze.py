"""
analyze.py - computes every metric reported in README.md from the raw logs
saved in results/ by run_experiments.sh.

  T_seq  : mean execution time of the sequential baseline (runs 1..N)
  T_p    : mean total execution time of an MPI version with P processes
  S_p    : T_seq / T_p
  E_p    : S_p / P
  LI     : max(t_i) / mean(t_i)        (t_i = local processing time of rank i)
  spread : (max(t_i) - min(t_i)) / mean(t_i)

LI and spread are computed per run and then averaged over the valid runs.
Warm-up runs (*_warmup.log) are ignored.

Usage:  python3 analyze.py [results_dir]   (default results/; writes summary.md
        and summary.json inside that directory)
"""
import glob
import json
import os
import re
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_top10(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Top 10"):
            out = []
            for l in lines[i + 1:i + 11]:
                m = re.match(r"\s+(\S+): (\d+)$", l)
                if m:
                    out.append((m.group(1), int(m.group(2))))
            return out
    return []


def host_wall(text):
    m = re.search(r"HOST_WALL_SECONDS=([\d.]+)", text)
    return float(m.group(1)) if m else None


def run_logs(name):
    files = glob.glob(os.path.join(RES, f"{name}_run*.log"))
    return sorted(files, key=lambda p: int(re.search(r"run(\d+)\.log$", p).group(1)))


def parse_baseline():
    runs = []
    for p in run_logs("baseline"):
        text = read(p)
        t = float(re.search(r"Tiempo de ejecuci\S+n: ([\d.]+) segundos", text).group(1))
        runs.append({"file": os.path.basename(p), "time": t, "top10": parse_top10(text),
                     "host_wall": host_wall(text)})
    return runs


def parse_mpi(name):
    runs = []
    for p in run_logs(name):
        text = read(p)
        t = float(re.search(r"EXECUTION_TIME=([\d.]+)", text).group(1))
        procs = []
        for m in re.finditer(r"^PROC (.*)$", text, re.M):
            d = dict(kv.split("=") for kv in m.group(1).split())
            procs.append({
                "rank": int(d["rank"]), "files": int(d["files"]), "bytes": int(d["bytes"]),
                "tasks": int(d.get("tasks", 0)), "local_time": float(d["local_time"]),
                "wait_time": float(d.get("wait_time", "nan")),
            })
        procs.sort(key=lambda x: x["rank"])
        ts = [x["local_time"] for x in procs]
        mean_t = st.mean(ts)
        runs.append({
            "file": os.path.basename(p), "time": t, "P": len(procs), "procs": procs,
            "li": max(ts) / mean_t, "spread": (max(ts) - min(ts)) / mean_t,
            "tmax": max(ts), "tmin": min(ts), "tmean": mean_t,
            "top10": parse_top10(text), "host_wall": host_wall(text),
        })
    return runs


def sd(xs):
    return st.stdev(xs) if len(xs) > 1 else 0.0


def main():
    base = parse_baseline()
    v1 = parse_mpi("mpi1")
    v2 = parse_mpi("mpi2")
    if not base or not v1 or not v2:
        raise SystemExit("Missing logs in results/. Run run_experiments.sh first.")

    t_seq = st.mean(r["time"] for r in base)
    ref_top = base[0]["top10"]
    out = []
    w = out.append

    w("## Sequential baseline\n")
    w("| Run | Time (s) | Host wall incl. Docker start (s) |")
    w("|---|---|---|")
    for i, r in enumerate(base, 1):
        w(f"| {i} | {r['time']:.3f} | {r['host_wall']:.3f} |")
    w(f"| **Mean** | **{t_seq:.3f}** (sd {sd([r['time'] for r in base]):.3f}) | "
      f"{st.mean(r['host_wall'] for r in base):.3f} |\n")

    summary = {"T_seq": t_seq, "T_seq_sd": sd([r["time"] for r in base]),
               "baseline_runs": [r["time"] for r in base]}

    top_ok = all(r["top10"] == ref_top for r in base)
    for name, runs in (("mpi1", v1), ("mpi2", v2)):
        P = runs[0]["P"]
        t_p = st.mean(r["time"] for r in runs)
        s_p = t_seq / t_p
        e_p = s_p / P
        li = st.mean(r["li"] for r in runs)
        spread = st.mean(r["spread"] for r in runs)
        top_ok = top_ok and all(r["top10"] == ref_top for r in runs)
        summary[name] = {
            "P": P, "runs": [r["time"] for r in runs], "T_p": t_p,
            "T_p_sd": sd([r["time"] for r in runs]), "S_p": s_p, "E_p": e_p,
            "LI_mean": li, "LI_runs": [r["li"] for r in runs],
            "spread_mean": spread, "spread_runs": [r["spread"] for r in runs],
            "host_wall_mean": st.mean(r["host_wall"] for r in runs),
            "top10_identical_to_baseline": all(r["top10"] == ref_top for r in runs),
        }

        w(f"## {name} (P = {P})\n")
        w("| Run | T_p (s) | max t_i (s) | min t_i (s) | mean t_i (s) | LI | Spread | Host wall (s) |")
        w("|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(runs, 1):
            w(f"| {i} | {r['time']:.3f} | {r['tmax']:.3f} | {r['tmin']:.3f} | {r['tmean']:.3f} | "
              f"{r['li']:.3f} | {r['spread']:.3f} | {r['host_wall']:.3f} |")
        w(f"| **Mean** | **{t_p:.3f}** (sd {sd([r['time'] for r in runs]):.3f}) | "
          f"{st.mean(r['tmax'] for r in runs):.3f} | {st.mean(r['tmin'] for r in runs):.3f} | "
          f"{st.mean(r['tmean'] for r in runs):.3f} | **{li:.3f}** | **{spread:.3f}** | "
          f"{st.mean(r['host_wall'] for r in runs):.3f} |\n")

        # per-process table: one column per run + mean
        w(f"Per-process local time t_i (s), {name}:\n")
        hdr = "| Rank | Files (run 1) | MB (run 1) |" + "".join(
            f" t_i run {i} |" for i in range(1, len(runs) + 1)) + " Mean t_i |"
        if name == "mpi2":
            hdr += " Mean files | Mean wait (s) |"
        w(hdr)
        w("|" + "---|" * (hdr.count("|") - 1))
        for k in range(P):
            ts = [r["procs"][k]["local_time"] for r in runs]
            p1 = runs[0]["procs"][k]
            row = f"| {k} | {p1['files']} | {p1['bytes'] / 1e6:.2f} |" + "".join(
                f" {t:.3f} |" for t in ts) + f" {st.mean(ts):.3f} |"
            if name == "mpi2":
                row += (f" {st.mean(r['procs'][k]['files'] for r in runs):.1f} |"
                        f" {st.mean(r['procs'][k]['wait_time'] for r in runs):.3f} |")
            w(row)
        w("")

    w("## Comparison\n")
    w("| Metric | Sequential | MPI v1 (static) | MPI v2 (dynamic) |")
    w("|---|---|---|---|")
    a, b = summary["mpi1"], summary["mpi2"]
    w(f"| Processes | 1 | {a['P']} | {b['P']} |")
    w(f"| Mean execution time (s) | {t_seq:.3f} | {a['T_p']:.3f} | {b['T_p']:.3f} |")
    w(f"| Std. dev. of time (s) | {summary['T_seq_sd']:.3f} | {a['T_p_sd']:.3f} | {b['T_p_sd']:.3f} |")
    w(f"| Speedup S_p = T_seq/T_p | 1.00 | {a['S_p']:.2f} | {b['S_p']:.2f} |")
    w(f"| Efficiency E_p = S_p/P | 1.00 | {a['E_p']:.3f} | {b['E_p']:.3f} |")
    w(f"| Mean LI = max(t_i)/mean(t_i) | - | {a['LI_mean']:.3f} | {b['LI_mean']:.3f} |")
    w(f"| Mean relative spread | - | {a['spread_mean']:.3f} | {b['spread_mean']:.3f} |")
    w(f"| Mean host wall time incl. Docker start (s) | "
      f"{st.mean(r['host_wall'] for r in base):.3f} | {a['host_wall_mean']:.3f} | {b['host_wall_mean']:.3f} |")
    gain = (a["T_p"] - b["T_p"]) / a["T_p"] * 100
    summary["v2_vs_v1_time_reduction_pct"] = gain
    summary["v2_vs_v1_speedup"] = a["T_p"] / b["T_p"]
    w(f"\nv2 vs v1: T_v1/T_v2 = {a['T_p'] / b['T_p']:.3f} "
      f"({gain:+.1f}% time reduction; negative means v2 is slower).")
    summary["top10_all_identical"] = top_ok
    w(f"\nTop 10 identical to the sequential baseline in every run: {'YES' if top_ok else 'NO'}")
    corr = os.path.join(RES, "correctness.txt")
    if os.path.exists(corr):
        w("Full 200-word count comparison (results/correctness.txt):")
        for line in read(corr).splitlines():
            w(f"- {line}")

    # ---- derived metrics used in the Analysis section ----
    w("\n## Derived metrics (where does the time go?)\n")
    w("| Metric | MPI v1 | MPI v2 |")
    w("|---|---|---|")
    rows = {}
    for name, runs in (("mpi1", v1), ("mpi2", v2)):
        P = runs[0]["P"]
        sum_t = st.mean(sum(x["local_time"] for x in r["procs"]) for r in runs)
        d = {
            "ideal_T": t_seq / P,
            "mean_tmax": st.mean(r["tmax"] for r in runs),
            "mean_tmean": st.mean(r["tmean"] for r in runs),
            "imbalance_cost": st.mean(r["tmax"] - r["tmean"] for r in runs),
            "outside_counting": st.mean(r["time"] - r["tmax"] for r in runs),
            "sum_ti": sum_t,
            "inflation": sum_t / t_seq,
            "corr_mb_time": st.correlation([x["bytes"] for r in runs for x in r["procs"]],
                                           [x["local_time"] for r in runs for x in r["procs"]])
            if hasattr(st, "correlation") else float("nan"),
        }
        rows[name] = d
        summary[name]["derived"] = d
    a, b = rows["mpi1"], rows["mpi2"]
    w(f"| Ideal time T_seq/P (s) | {a['ideal_T']:.3f} | {b['ideal_T']:.3f} |")
    w(f"| Mean max t_i (s) | {a['mean_tmax']:.3f} | {b['mean_tmax']:.3f} |")
    w(f"| Mean of mean t_i (s) | {a['mean_tmean']:.3f} | {b['mean_tmean']:.3f} |")
    w(f"| Imbalance cost: mean(max t_i - mean t_i) (s) | {a['imbalance_cost']:.3f} | {b['imbalance_cost']:.3f} |")
    w(f"| Time outside counting: mean(T_p - max t_i) (s) | {a['outside_counting']:.3f} | {b['outside_counting']:.3f} |")
    w(f"| Sum of t_i over processes (s) | {a['sum_ti']:.3f} | {b['sum_ti']:.3f} |")
    w(f"| Work inflation: sum(t_i) / T_seq | {a['inflation']:.2f} | {b['inflation']:.2f} |")
    w(f"| Pearson corr(MB assigned, t_i), all runs | {a['corr_mb_time']:.2f} | {b['corr_mb_time']:.2f} |")

    for name, d in rows.items():
        T = summary[name]["T_p"]
        w(f"- {name}: imbalance cost = {d['imbalance_cost'] / T * 100:.1f}% of T_p; "
          f"outside counting = {d['outside_counting'] / T * 100:.1f}% of T_p; "
          f"runs range {min(summary[name]['runs']):.3f}-{max(summary[name]['runs']):.3f} s")
    diff = summary["mpi1"]["T_p"] - summary["mpi2"]["T_p"]
    w(f"- T_v1 - T_v2 = {diff:.3f} s = {diff / summary['mpi1']['T_p_sd']:.1f} x sd(v1) = "
      f"{diff / summary['mpi2']['T_p_sd']:.1f} x sd(v2); spread ratio v1/v2 = "
      f"{summary['mpi1']['spread_mean'] / summary['mpi2']['spread_mean']:.1f}")

    # LI including the time each process spent waiting for messages (v2 only:
    # v1 has no message waits inside its counting phase)
    li_w = [max(x["local_time"] + x["wait_time"] for x in r["procs"]) /
            st.mean(x["local_time"] + x["wait_time"] for x in r["procs"]) for r in v2]
    summary["mpi2"]["LI_with_wait_runs"] = li_w
    summary["mpi2"]["LI_with_wait_mean"] = st.mean(li_w)
    w(f"- mpi2: LI computed on (t_i + wait_i) = {st.mean(li_w):.3f} "
      f"(runs: {', '.join(f'{x:.3f}' for x in li_w)})")

    # design check of mpi2 (results/design_variants/, run_design_check.sh)
    dv = os.path.join(RES, "design_variants")
    if os.path.isdir(dv):
        w("\n## MPI v2 design check: PREFETCH (requests in flight per worker)\n")
        w("| Variant | Runs T_p (s) | Mean T_p (s) | sd (s) | S_p | Mean LI | Mean worker wait (s) | Counts identical |")
        w("|---|---|---|---|---|---|---|---|")
        summary["design_variants"] = {}
        for pf in (1, 2):
            files = sorted(glob.glob(os.path.join(dv, f"mpi2_prefetch{pf}_run*.log")))
            if not files:
                continue
            ts, lis, waits, ok = [], [], [], True
            for p in files:
                text = read(p)
                ts.append(float(re.search(r"EXECUTION_TIME=([\d.]+)", text).group(1)))
                procs = [dict(kv.split("=") for kv in m.group(1).split())
                         for m in re.finditer(r"^PROC (.*)$", text, re.M)]
                lt = [float(d["local_time"]) for d in procs]
                lis.append(max(lt) / st.mean(lt))
                waits.append(st.mean(float(d["wait_time"]) for d in procs if d["role"] == "worker"))
                ok = ok and "COUNTS_IDENTICAL_TO_BASELINE=yes" in text and parse_top10(text) == ref_top
            d = {"runs": ts, "T_p": st.mean(ts), "sd": sd(ts), "S_p": t_seq / st.mean(ts),
                 "LI_mean": st.mean(lis), "worker_wait_mean": st.mean(waits), "correct": ok}
            summary["design_variants"][f"prefetch{pf}"] = d
            w(f"| PREFETCH={pf}{' (default)' if pf == 2 else ''} | {', '.join(f'{x:.3f}' for x in ts)} | "
              f"{d['T_p']:.3f} | {d['sd']:.3f} | {d['S_p']:.2f} | {d['LI_mean']:.3f} | "
              f"{d['worker_wait_mean']:.3f} | {'yes' if ok else 'NO'} |")
        dvs = summary["design_variants"]
        if "prefetch1" in dvs and "prefetch2" in dvs:
            g = (dvs["prefetch1"]["T_p"] - dvs["prefetch2"]["T_p"]) / dvs["prefetch1"]["T_p"] * 100
            dvs["prefetch2_vs_1_time_reduction_pct"] = g
            w(f"\nPREFETCH=2 vs PREFETCH=1: {g:+.1f}% time reduction (S_p uses T_seq = {t_seq:.3f} s).")

    # hardware reference: Detectar_procesos_mpi (CPU-bound prime counting)
    det = os.path.join(HERE, "results", "detectar_procesos_mpi.log")
    if os.path.exists(det):
        med = {int(n): float(t) for n, t in re.findall(r"N=(\d+), mediana: ([\d.]+) s", read(det))}
        rec = int(re.search(r"N RECOMENDADO: (\d+)", read(det)).group(1))
        ref = med[1] / med[rec]
        summary["detector"] = {"medians": med, "recommended_P": rec, "speedup_at_P": ref}
        w(f"\nDetectar_procesos_mpi (results/detectar_procesos_mpi.log): recommended P = {rec}; "
          f"median time N=1: {med[1]:.3f} s, N={rec}: {med[rec]:.3f} s -> "
          f"CPU-bound reference speedup at P={rec}: {ref:.2f} (efficiency {ref / rec:.3f}).")
        for name in ("mpi1", "mpi2"):
            frac = summary[name]["S_p"] / ref
            summary[name]["fraction_of_reference_speedup"] = frac
            w(f"- {name}: S_p / reference speedup = {frac:.2f}")

    # ---- dataset description (deterministic: generator.py uses seed 42) ----
    ds = os.path.join(HERE, "dataset")
    if os.path.isdir(ds):
        names = sorted(n for n in os.listdir(ds) if n.startswith("file_") and n.endswith(".txt"))
        sizes = [os.path.getsize(os.path.join(ds, n)) for n in names]
        words = []
        for n in names:
            with open(os.path.join(ds, n), encoding="utf-8") as f:
                words.append(len(f.read().split()))
        with open(os.path.join(ds, "consulta.txt"), encoding="utf-8") as f:
            nq = sum(1 for l in f if l.strip())
        small = sum(x <= 5000 for x in words)
        medium = sum(10000 <= x <= 20000 for x in words)
        large = sum(x >= 50000 for x in words)
        summary["dataset"] = {"files": len(names), "query_words": nq,
                              "total_bytes": sum(sizes), "min_bytes": min(sizes),
                              "max_bytes": max(sizes), "total_words": sum(words),
                              "min_words": min(words), "max_words": max(words),
                              "small_2k_5k": small, "medium_10k_20k": medium,
                              "large_50k_100k": large}
        w("\n## Dataset\n")
        w(f"- Files: {len(names)}, query words: {nq}")
        w(f"- Total size: {sum(sizes) / 1e6:.1f} MB, total words: {sum(words)}")
        w(f"- Words per file: min {min(words)}, max {max(words)} "
          f"(ratio {max(words) / min(words):.1f}x); bytes per file: min {min(sizes)}, max {max(sizes)}")
        w(f"- Small (2k-5k words): {small}, medium (10k-20k): {medium}, large (50k-100k): {large}")
        w(f"- Large files hold {sum(x for x in words if x >= 50000) / sum(words) * 100:.1f}% of all words")

    text = "\n".join(out) + "\n"
    print(text)
    with open(os.path.join(RES, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(RES, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
