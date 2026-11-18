# Balancing Row-Buffer Locality and Fairness in Multi-Program DRAM Scheduling — Ramulator version

The experiments run on **Ramulator** (Kim, Yang, Mutlu, IEEE CAL 2015; `../ramulator/`, source from
https://github.com/CMU-SAFARI/ramulator), a cycle-accurate DRAM simulator. We added our scheduling
policies to its memory controller and drive it with traces recorded from our own programs.
(Our first, self-written simulator is still in the parent folder: `../dramsim.cpp`.)

## What we changed in Ramulator
Every change is marked `[project]` in the source.

| file | change |
|---|---|
| `src/Scheduler.h` | two new policies, `FAIR` and `FAIR_PROG`; the policy is chosen by name |
| `src/Controller.h` | reads `scheduler`, `fair_T`, `queue_size` from the config file; new per-program statistic: cycles a request waits in the queue before its first command |
| `src/Main.cpp` | `banks = N` in the config file overrides the number of banks (real DDR3 has 8) |

## Policies
| name in our graphs | Ramulator name | rule |
|---|---|---|
| FIFO | `FCFS` | oldest request only |
| FR-FCFS | `FRFCFS_PriorHit` | row hits first, then oldest; a row with waiting hits is not closed |
| Fair-W | `FAIR` (ours) | a request that has waited `T` memory cycles goes first, even over a row hit; otherwise FR-FCFS |
| Fair-P | `FAIR_PROG` (ours) | Fair-W, plus: a ready request of the program with the fewest waiting requests goes before the others |

Fair-W is the policy of our proposal. Fair-P is an extension we added after seeing the Fair-W results.

## Setup
- DDR3-1600 11-11-11 (`DDR3_1600K`), `DDR3_2Gb_x8`, 1 channel, 1 rank, 8 banks, 32-entry read and write queues.
- Ramulator CPU-trace mode: one core per program, 4-wide, 128-entry window, 4 CPU cycles per memory cycle,
  no cache model (the traces are already filtered by the recorder's 256 KB cache), random page mapping
  (`translation = Random`).
- Workloads: array sum (streaming), random access, chunked scan (mixed), 192x192 matrix multiply, linked list —
  recorded by `../record_traces.cpp`, converted by `gen_traces.py`.
- Each program is measured over its first 1,000,000 instructions; traces restart when they end, so every
  program keeps running until the slowest one is done.
- slowdown = CPU cycles when sharing / CPU cycles alone (same policy, banks, queue).
  unfairness = max slowdown / min slowdown. weighted speedup = sum of 1 / slowdown.

## Run
```
cd ../ramulator && make -j8 && cd ../ramulator_project
python3 gen_traces.py        # recorded/*.rec -> traces/*.trace
python3 validate.py          # hand-checked tests, must print VALIDATION PASS
python3 run_experiments.py   # 400 Ramulator runs (about 1 minute on 8 cores) -> results/*.csv
python3 make_plots.py        # results/fig_*.png  (needs matplotlib, numpy)
```

## Hand-checked tests (`validate.py`)
- Five reads to one bank in the order A, B, A, A, B: FIFO serves A B A A B with 4 activations (done at cycle 129);
  FR-FCFS serves A A A B B with 2 activations (done at cycle 55).
- `FAIR` and `FAIR_PROG` with a huge `T` issue exactly the commands of `FRFCFS_PriorHit`; with `T = 0` exactly
  the commands of Ramulator's plain `FRFCFS`.
- One read to row B among 24 reads to row A: FR-FCFS serves B last (25th); `FAIR` with `T = 40` serves it 9th.

## Results (8 banks, queue 32, T = 500)

Single programs, FIFO -> FR-FCFS: matrix multiply waits 68 -> 24 cycles, random access 229 -> 43 cycles.
Streaming (98% hits) and linked list (one request at a time) are the same under both.

| mix | policy | slowdown of each program | unfairness | weighted speedup |
|---|---|---|---|---|
| stream + random | FIFO | 17.56 ; 1.09 | 16.05 | 0.97 |
| | FR-FCFS | 3.63 ; 1.11 | 3.27 | 1.17 |
| | Fair-W | 3.63 ; 1.11 | 3.27 | 1.17 |
| | Fair-P | 1.89 ; 2.35 | 1.24 | 0.95 |
| matmul + random | FIFO | 2.86 ; 1.29 | 2.22 | 1.13 |
| | FR-FCFS | 1.64 ; 1.12 | 1.47 | 1.50 |
| | Fair-W | 1.64 ; 1.12 | 1.47 | 1.50 |
| | Fair-P | 1.23 ; 1.24 | 1.00 | 1.62 |
| stream + random + matmul + linked list | FIFO | 23.57 ; 1.46 ; 3.17 ; 10.44 | 16.19 | 1.14 |
| | FR-FCFS | 4.66 ; 1.32 ; 1.78 ; 2.61 | 3.53 | 1.92 |
| | Fair-W | 4.66 ; 1.32 ; 1.78 ; 2.61 | 3.53 | 1.92 |
| | Fair-P | 2.94 ; 2.12 ; 2.29 ; 1.23 | 2.40 | 2.07 |

All mixes are in `results/mixes.csv`; the T sweep in `results/T_sweep.csv`; banks x queue in `results/sweeps.csv`.

What the numbers say:
1. **FR-FCFS beats FIFO everywhere** in hit rate, throughput and fairness. FIFO is the least fair policy here,
   because it makes every request wait behind the random-access program's requests.
2. **The program that suffers is the streaming one, not the random-access one.** Alone, the streaming program
   gets 98% row hits. Next to the random-access program its rows are closed between two of its requests, so
   it pays a full precharge + activate each time and slows down 3.6x, while the random-access program
   (which never had row hits to lose) slows down only 1.1x. This is the opposite of what our proposal expected.
3. **A waiting-time limit alone (Fair-W) does not help.** With a large T it never triggers and equals FR-FCFS.
   With a small T it serves the oldest requests, which belong to the random-access program, and unfairness
   gets worse (3.3 -> 5.5-6.8 for T <= 100).
4. **Fair-P reduces unfairness**: 3.27 -> 1.24 (stream + random), 1.47 -> 1.00 (matmul + random),
   3.53 -> 2.40 (four programs). For stream + random it costs throughput (-20%) and weighted speedup
   (1.17 -> 0.95), because the random-access program is slowed 2.35x. For the other two mixes weighted
   speedup goes up.
5. **T is the balance knob of Fair-P** (stream + random): T = 300 gives the lowest unfairness (1.18);
   T >= 1000 lets the random-access program wait too long (slowdown 3.0, unfairness 1.9-2.0);
   T <= 100 turns the policy off (unfairness 5.5-6.5).
6. **Banks**: more banks reduce unfairness for every policy (FR-FCFS: 18.6 at 1 bank, 3.3 at 8, 2.3 at 16).
   Fair-P needs at least 2 banks; with 1 bank every request waits longer than T and it falls back to
   oldest-first.
7. **Queue size**: 16, 32 and 64 entries give the same results, because the two cores never have more than
   about 16 requests outstanding. Only the 8-entry queue changes the numbers.
8. Mixes with similar programs (stream + stream, matmul + linked list, stream + linked list) are already
   fair under FR-FCFS (unfairness 1.00-1.16) and the fair policies change little.

## Limitations
- One set of recorded traces (fixed seed), 20,000 requests each; shorter traces are repeated.
- The random-access program is very memory-intensive (about 8 instructions per miss).
- All requests are reads: the recordings are misses of a write-allocate cache, and writebacks are not modeled.
- Linked list: Ramulator's core does not model load-to-load dependences, so the trace has 128 instructions
  (one full window) between two loads to keep them one at a time.
- 1, 2, 4 and 16 banks are not real DDR3 parts; they use the `banks` override.
- Fair-P counts waiting requests per program inside the controller; this needs the core id of each request.
