"""Runs every scheduler on every workload with the modified Ramulator and writes results/*.csv.

slowdown(p) = CPU cycles p needs for its first 1,000,000 instructions when sharing the channel
              / the same when running alone (same scheduler, banks and queue size)
unfairness  = max slowdown / min slowdown over the programs in the mix
Policies    : FIFO    = Ramulator FCFS
              FR-FCFS = Ramulator FRFCFS_PriorHit (row hits first, then oldest)
              Fair-W  = our FAIR scheduler: FR-FCFS + waiting-time limit T (memory cycles)
              Fair-P  = our FAIR_PROG scheduler: Fair-W + the program with the fewest waiting requests goes first
"""
import csv, os, sys
from concurrent.futures import ThreadPoolExecutor
import ramsim

RES = os.path.join(ramsim.HERE, "results")
os.makedirs(RES, exist_ok=True)

T_DEFAULT = int(sys.argv[1]) if len(sys.argv) > 1 else 500
POL = [("FCFS", "FIFO"), ("FRFCFS_PriorHit", "FR-FCFS"), ("FAIR", f"Fair-W (T={T_DEFAULT})"), ("FAIR_PROG", f"Fair-P (T={T_DEFAULT})")]
SINGLE = ["stream", "mixed", "matmul", "random", "linkedlist"]
MIXES = {
    "mix_stream_random": ["stream", "random"],
    "mix_stream_linkedlist": ["stream", "linkedlist"],
    "mix_two_stream": ["stream", "stream"],
    "mix_matmul_random": ["matmul", "random"],
    "mix_matmul_linkedlist": ["matmul", "linkedlist"],
    "mix4": ["stream", "random", "matmul", "linkedlist"],
}
T_VALUES = [20, 50, 100, 200, 300, 500, 750, 1000, 2000, 5000]
BANKS = [1, 2, 4, 8, 16]
QUEUES = [8, 16, 32, 64]


def jobs():
    """Every (programs, scheduler, T, banks, queue) the tables below need (shared runs and alone runs)."""
    out = set()
    def add_mix(progs, sched, T=T_DEFAULT, banks=8, queue=32):
        slots = tuple((p, i) for i, p in enumerate(progs))
        out.add((slots, sched, T, banks, queue))
        for ps in slots:
            out.add(((ps,), sched, T, banks, queue))
    for p in SINGLE:
        for sched, _ in POL:
            out.add((((p, 0),), sched, T_DEFAULT, 8, 32))
    for progs in MIXES.values():
        for sched, _ in POL:
            add_mix(progs, sched)
    for name in ("mix_stream_random", "mix4"):
        for sched in ("FAIR", "FAIR_PROG"):
            for T in T_VALUES:
                add_mix(MIXES[name], sched, T)
    for b in BANKS:
        for q in QUEUES:
            for sched, _ in POL:
                add_mix(MIXES["mix_stream_random"], sched, banks=b, queue=q)
    return sorted(out)


def write_csv(name, header, rows):
    with open(os.path.join(RES, name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


def main():
    todo = jobs()
    print(f"{len(todo)} Ramulator runs (cached runs are skipped)")
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
        list(ex.map(lambda j: ramsim.run([list(p) for p in j[0]], j[1], j[2], j[3], j[4]), todo))

    # 1. single programs
    rows = []
    for p in SINGLE:
        for sched, label in POL[:2]:
            r = ramsim.run([[p, 0]], sched)
            rows.append([p, label, r["hit_rate"], r["avg_wait"], r["read_latency"], r["throughput"], r["cycles"][0]])
    write_csv("single_programs.csv", ["program", "policy", "hit_rate", "avg_wait", "avg_latency", "throughput", "cpu_cycles_per_1M_instr"], rows)

    # 2. mixes x policies
    rows = []
    for name, progs in MIXES.items():
        for sched, label in POL:
            m = ramsim.mix(progs, sched, T_DEFAULT)
            rows.append([name, "+".join(progs), label, m["hit_rate"], m["avg_wait"], m["throughput"],
                         ";".join(f"{s:.3f}" for s in m["slowdowns"]), m["max_slowdown"], m["unfairness"], m["weighted_speedup"]])
    write_csv("mixes.csv", ["mix", "programs", "policy", "hit_rate", "avg_wait", "throughput", "slowdowns", "max_slowdown", "unfairness", "weighted_speedup"], rows)

    # 3. waiting-time limit sweep
    rows = []
    for name in ("mix_stream_random", "mix4"):
        for sched, tag in (("FAIR", "Fair-W"), ("FAIR_PROG", "Fair-P")):
            for T in T_VALUES:
                m = ramsim.mix(MIXES[name], sched, T)
                rows.append([name, tag, T, m["hit_rate"], m["throughput"], ";".join(f"{s:.3f}" for s in m["slowdowns"]), m["max_slowdown"], m["unfairness"], m["weighted_speedup"]])
        for sched, tag in (("FCFS", "FIFO"), ("FRFCFS_PriorHit", "FR-FCFS")):
            m = ramsim.mix(MIXES[name], sched)
            rows.append([name, tag, "", m["hit_rate"], m["throughput"], ";".join(f"{s:.3f}" for s in m["slowdowns"]), m["max_slowdown"], m["unfairness"], m["weighted_speedup"]])
    write_csv("T_sweep.csv", ["mix", "policy", "T", "hit_rate", "throughput", "slowdowns", "max_slowdown", "unfairness", "weighted_speedup"], rows)

    # 4. banks x queue size (stream + random)
    rows = []
    for b in BANKS:
        for q in QUEUES:
            for sched, label in POL:
                m = ramsim.mix(MIXES["mix_stream_random"], sched, T_DEFAULT, banks=b, queue=q)
                rows.append([b, q, label, m["hit_rate"], m["throughput"], ";".join(f"{s:.3f}" for s in m["slowdowns"]), m["max_slowdown"], m["unfairness"], m["weighted_speedup"]])
    write_csv("sweeps.csv", ["banks", "queue", "policy", "hit_rate", "throughput", "slowdowns", "max_slowdown", "unfairness", "weighted_speedup"], rows)
    print("results written to", RES)


if __name__ == "__main__":
    main()
