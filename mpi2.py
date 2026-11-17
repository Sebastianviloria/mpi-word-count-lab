"""
MPI version 2 - dynamic master-worker distribution (working master + prefetch).

Same problem as mpi1.py, but files are handed out ON DEMAND to reduce the
load imbalance caused by (a) files of very different sizes and (b) cores of
different speed (Apple performance/efficiency cores, shared VM).

Scheme:
  1. rank 0 (master) reads consulta.txt and broadcasts the query (comm.bcast).
  2. rank 0 lists file_*.txt and cuts the list into small TASKS of
     FILES_PER_TASK consecutive files (default 4 -> 750 tasks).
  3. workers (ranks 1..P-1) ask the master for a task, count the query words
     in it and ask again. To hide the master's response latency each worker
     keeps PREFETCH requests in flight (default 2): when a task arrives it
     immediately asks for another one and then processes the task.
  4. the master is also a worker: it takes tasks from the same queue for
     itself and, between two files, answers any pending request (Iprobe).
     When the queue is empty it answers each request with STOP (one STOP
     per outstanding request, MPI keeps message order per sender).
  5. partial Counters and per-process stats are gathered on rank 0
     (comm.gather), which merges them and prints the top 10.

All P processes count words, so the comparison with mpi1.py (P counting
processes) is fair.

Run (Docker):
  docker run --rm -v "$(pwd)":/app augustosalazar/slim-mpi:2 \
      mpiexec --allow-run-as-root -n 8 python /app/mpi2.py
"""
import os
from collections import Counter

from mpi4py import MPI

TOP_N = 10
QUERY_NAME = "consulta.txt"
RESULTS_CSV = "mpi2_results.csv"
FILES_PER_TASK = int(os.environ.get("FILES_PER_TASK", 4))  # small tasks -> fine-grained balance
PREFETCH = int(os.environ.get("PREFETCH", 2))  # requests each worker keeps in flight

TAG_REQUEST = 1
TAG_TASK = 2
TAG_STOP = 3


def load_query(path):
    """Read consulta.txt -> set of lowercase query words (same as baseline)."""
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if line.strip())


def list_corpus_files(dataset_dir):
    """Sorted list of file_*.txt names.
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


def build_tasks(dataset_dir, files_per_task):
    """Cut the sorted file list into tasks of `files_per_task` file names."""
    names = list_corpus_files(dataset_dir)
    return [names[i:i + files_per_task] for i in range(0, len(names), files_per_task)]


class Stats:
    def __init__(self):
        self.files = self.tasks = self.tokens = self.bytes = 0
        self.busy = 0.0  # time spent counting = local processing time t_i
        self.wait = 0.0  # time blocked waiting for messages

    def process(self, dataset_dir, name, query, counter):
        t = MPI.Wtime()
        path = os.path.join(dataset_dir, name)
        self.bytes += os.path.getsize(path)
        self.tokens += count_file(path, query, counter)
        self.files += 1
        self.busy += MPI.Wtime() - t


def master(comm, tasks, dataset_dir, query, counter):
    """Hand out tasks on demand and process tasks itself between requests."""
    status = MPI.Status()
    st = Stats()
    stops_left = (comm.Get_size() - 1) * PREFETCH  # one STOP per outstanding request
    next_task = 0
    served = 0

    def answer(source):
        nonlocal next_task, stops_left, served
        comm.recv(source=source, tag=TAG_REQUEST)
        if next_task < len(tasks):
            comm.send(tasks[next_task], dest=source, tag=TAG_TASK)
            next_task += 1
            served += 1
        else:
            comm.send(None, dest=source, tag=TAG_STOP)
            stops_left -= 1

    def serve_pending():
        while comm.Iprobe(source=MPI.ANY_SOURCE, tag=TAG_REQUEST, status=status):
            answer(status.Get_source())

    # Phase A: there is work left -> serve pending requests, then work a bit
    while next_task < len(tasks):
        serve_pending()
        if next_task >= len(tasks):
            break
        my_task = tasks[next_task]
        next_task += 1
        st.tasks += 1
        for name in my_task:
            st.process(dataset_dir, name, query, counter)
            serve_pending()  # answer requests between two files

    # Phase B: queue empty -> answer every outstanding request with STOP
    while stops_left > 0:
        t = MPI.Wtime()
        comm.Probe(source=MPI.ANY_SOURCE, tag=TAG_REQUEST, status=status)
        st.wait += MPI.Wtime() - t
        answer(status.Get_source())
    return st, served


def worker(comm, dataset_dir, query, counter):
    """Keep PREFETCH requests in flight; stop when all of them got STOP."""
    status = MPI.Status()
    st = Stats()

    def receive():
        t = MPI.Wtime()
        msg = comm.recv(source=0, tag=MPI.ANY_TAG, status=status)
        st.wait += MPI.Wtime() - t
        return msg, status.Get_tag()

    for _ in range(PREFETCH):
        comm.send(None, dest=0, tag=TAG_REQUEST)
    outstanding = PREFETCH
    while outstanding > 0:
        task, tag = receive()
        if tag == TAG_STOP:  # after the first STOP only STOPs can follow
            outstanding -= 1
            continue
        comm.send(None, dest=0, tag=TAG_REQUEST)  # ask for the next task first
        for name in task:
            st.process(dataset_dir, name, query, counter)
        st.tasks += 1
    return st


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

    # 2-4) dynamic distribution
    local_counter = Counter()
    n_tasks = None
    if rank == 0:
        tasks = build_tasks(dataset_dir, FILES_PER_TASK)
        n_tasks = len(tasks)
        st, _ = master(comm, tasks, dataset_dir, query, local_counter)
    else:
        st = worker(comm, dataset_dir, query, local_counter)
    stats = {"rank": rank, "files": st.files, "tasks": st.tasks, "bytes": st.bytes,
             "tokens": st.tokens, "local_time": st.busy, "wait_time": st.wait}

    # 5) gather partial results on rank 0
    gathered = comm.gather((local_counter, stats), root=0)

    if rank == 0:
        global_counter = Counter()
        for partial, _ in gathered:
            global_counter.update(partial)
        total_time = MPI.Wtime() - t0

        all_stats = [s for _, s in gathered]
        times = [s["local_time"] for s in all_stats]
        mean_t = sum(times) / len(times)

        print(f"MPI version 2 (dynamic master-worker), processes: {size}, "
              f"tasks: {n_tasks}, files per task: {FILES_PER_TASK}, prefetch: {PREFETCH}")
        print(f"Execution time: {total_time:.6f} seconds\n")
        print("Per-process report (rank 0 = master, it also counts words):")
        print(f"  {'rank':>4} {'files':>6} {'tasks':>6} {'MB':>8} {'tokens':>10} "
              f"{'local_time_s':>13} {'wait_s':>9}")
        for s in all_stats:
            print(f"  {s['rank']:>4} {s['files']:>6} {s['tasks']:>6} {s['bytes'] / 1e6:>8.2f} "
                  f"{s['tokens']:>10} {s['local_time']:>13.6f} {s['wait_time']:>9.4f}")
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
            role = "master" if s["rank"] == 0 else "worker"
            print(f"PROC rank={s['rank']} role={role} files={s['files']} tasks={s['tasks']} "
                  f"bytes={s['bytes']} tokens={s['tokens']} "
                  f"local_time={s['local_time']:.6f} wait_time={s['wait_time']:.6f}")
        print(f"EXECUTION_TIME={total_time:.6f}")

        save_csv(os.path.join(dataset_dir, RESULTS_CSV), global_counter)


if __name__ == "__main__":
    main()
