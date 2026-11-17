"""
MPI version 1 - static file distribution.

Counts how many times each word of dataset/consulta.txt appears in the
corpus dataset/file_*.txt and prints the global top 10.

Scheme:
  1. rank 0 reads consulta.txt and broadcasts the query words (comm.bcast).
  2. rank 0 lists the file_*.txt files and splits them STATICALLY into
     `size` contiguous blocks with (almost) the same number of files.
     The blocks are sent with comm.scatter.
  3. every process counts the query words in its own files (same counting
     rule as baseline_secuencial.py: split on whitespace, lowercase).
  4. partial Counters and per-process stats are gathered on rank 0
     (comm.gather), which merges them and prints the top 10.

Run (Docker):
  docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 \
      mpiexec --allow-run-as-root -n 8 python /app/mpi1.py
"""
import os
from collections import Counter

from mpi4py import MPI

TOP_N = 10
QUERY_NAME = "consulta.txt"
RESULTS_CSV = "mpi1_results.csv"


def load_query(path):
    """Read consulta.txt -> set of lowercase query words (same as baseline)."""
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if line.strip())


def list_corpus_files(dataset_dir):
    """Sorted list of file_*.txt names (sorted so the split is reproducible).
    os.scandir + is_file() uses the directory entry type, so it avoids one
    stat() per file, which is slow through the Docker bind mount."""
    with os.scandir(dataset_dir) as entries:
        return sorted(
            e.name for e in entries
            if e.name.startswith("file_") and e.name.endswith(".txt") and e.is_file()
        )


def count_file(path, query, counter):
    """Count query words in one file. Returns the number of tokens read."""
    tokens = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            words = [w.lower() for w in line.split()]
            tokens += len(words)
            for w in words:
                if w in query:
                    counter[w] += 1
    return tokens


def static_blocks(items, parts):
    """Split `items` into `parts` contiguous blocks whose lengths differ by <= 1."""
    base, extra = divmod(len(items), parts)
    blocks, start = [], 0
    for i in range(parts):
        end = start + base + (1 if i < extra else 0)
        blocks.append(items[start:end])
        start = end
    return blocks


def save_csv(path, counter):
    with open(path, "w", encoding="utf-8") as f:
        f.write("palabra,conteo\n")
        for word in sorted(counter):
            f.write(f"{word},{counter[word]}\n")


def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(script_dir, "dataset")

    comm.Barrier()
    t0 = MPI.Wtime()

    # 1) rank 0 reads the query and broadcasts it
    query = load_query(os.path.join(dataset_dir, QUERY_NAME)) if rank == 0 else None
    query = comm.bcast(query, root=0)

    # 2) rank 0 lists the files and builds the static assignment
    blocks = static_blocks(list_corpus_files(dataset_dir), size) if rank == 0 else None
    my_files = comm.scatter(blocks, root=0)

    # 3) local counting
    t_local0 = MPI.Wtime()
    local_counter = Counter()
    local_tokens = 0
    local_bytes = 0
    for name in my_files:
        path = os.path.join(dataset_dir, name)
        local_bytes += os.path.getsize(path)
        local_tokens += count_file(path, query, local_counter)
    local_time = MPI.Wtime() - t_local0

    stats = {
        "rank": rank,
        "files": len(my_files),
        "bytes": local_bytes,
        "tokens": local_tokens,
        "local_time": local_time,
    }

    # 4) gather partial results on rank 0
    gathered = comm.gather((local_counter, stats), root=0)

    if rank == 0:
        global_counter = Counter()
        for partial, _ in gathered:
            global_counter.update(partial)
        total_time = MPI.Wtime() - t0

        all_stats = [s for _, s in gathered]
        times = [s["local_time"] for s in all_stats]
        mean_t = sum(times) / len(times)

        print(f"MPI version 1 (static distribution), processes: {size}")
        print(f"Execution time: {total_time:.6f} seconds\n")
        print("Per-process report:")
        print(f"  {'rank':>4} {'files':>6} {'MB':>8} {'tokens':>10} {'local_time_s':>13}")
        for s in all_stats:
            print(f"  {s['rank']:>4} {s['files']:>6} {s['bytes'] / 1e6:>8.2f} "
                  f"{s['tokens']:>10} {s['local_time']:>13.6f}")
        print(f"\nLoad imbalance LI = max/mean = {max(times) / mean_t:.4f}")
        print(f"Relative spread (max-min)/mean = {(max(times) - min(times)) / mean_t:.4f}\n")

        print(f"Files processed: {sum(s['files'] for s in all_stats)}")
        print(f"Total tokens read: {sum(s['tokens'] for s in all_stats)}")
        print(f"Total occurrences found: {sum(global_counter.values())}\n")
        print(f"Top {TOP_N} query words in the corpus:")
        for word, count in global_counter.most_common(TOP_N):
            print(f"  {word}: {count}")

        # Machine-readable lines (parsed by analyze.py and run_all.sh)
        for s in all_stats:
            print(f"PROC rank={s['rank']} files={s['files']} bytes={s['bytes']} "
                  f"tokens={s['tokens']} local_time={s['local_time']:.6f}")
        print(f"EXECUTION_TIME={total_time:.6f}")

        # Full result table (outside the timed region), for correctness checks
        save_csv(os.path.join(dataset_dir, RESULTS_CSV), global_counter)


if __name__ == "__main__":
    main()
