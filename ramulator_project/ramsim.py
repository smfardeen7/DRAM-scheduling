"""Runs our modified Ramulator once and returns the numbers we need."""
import os, subprocess, tempfile, hashlib, json

HERE = os.path.dirname(os.path.abspath(__file__))
RAMULATOR = os.path.join(HERE, "..", "ramulator", "ramulator")
TRACES = os.path.join(HERE, "traces")
CACHE = os.path.join(HERE, "cache")
VERSION = 2       # bump when the simulator changes, so old cached runs are not reused
LIMIT = 1000000   # every program is measured over its first 1,000,000 instructions

CFG = """standard = DDR3
channels = 1
ranks = 1
speed = DDR3_1600K
org = DDR3_2Gb_x8
cpu_tick = 4
mem_tick = 1
early_exit = off
expected_limit_insts = {limit}
warmup_insts = 0
cache = no
translation = {translation}
scheduler = {scheduler}
fair_T = {T}
queue_size = {queue}
banks = {banks}
print_cmd_trace = {print_cmd}
"""


def parse_stats(path):
    """name -> value.  Per-core values are printed as "[i] value" under their stat and become name_i."""
    d, last = {}, None
    for line in open(path):
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            if parts[0].startswith("ramulator."):
                last = parts[0][len("ramulator."):]
                d[last] = float(parts[1])
            elif parts[0].startswith("[") and last:
                d[f"{last}_{parts[0][1:-1]}"] = float(parts[1])
        except ValueError:
            pass
    return d


def run(programs, scheduler, T=500, banks=8, queue=32, limit=LIMIT, translation="Random"):
    """programs = list of (name, slot).  Core i runs programs[i].  Results are cached on disk."""
    if not scheduler.startswith("FAIR"):
        T = 0
    key = json.dumps([VERSION, programs, scheduler, T, banks, queue, limit, translation])
    os.makedirs(CACHE, exist_ok=True)
    cpath = os.path.join(CACHE, hashlib.md5(key.encode()).hexdigest() + ".json")
    if os.path.exists(cpath):
        return json.load(open(cpath))
    with tempfile.TemporaryDirectory() as tmp:
        cfg, stats = os.path.join(tmp, "run.cfg"), os.path.join(tmp, "run.stats")
        open(cfg, "w").write(CFG.format(limit=limit, scheduler=scheduler, T=T, queue=queue, banks=banks, print_cmd="off", translation=translation))
        files = [os.path.join(TRACES, f"{p}_s{s}.trace") for p, s in programs]
        subprocess.run([RAMULATOR, cfg, "--mode=cpu", "--stats", stats] + files,
                       check=True, capture_output=True, cwd=tmp)
        st = parse_stats(stats)
    n = len(programs)
    hits, misses, conf = st["row_hits_channel_0_core"], st["row_misses_channel_0_core"], st["row_conflicts_channel_0_core"]
    wait_sum = sum(st[f"queue_wait_sum_channel_0_core_{i}"] for i in range(n))
    wait_n = sum(st[f"queue_wait_reqs_channel_0_core_{i}"] for i in range(n))
    res = {
        "hit_rate": hits / (hits + misses + conf),
        "avg_wait": wait_sum / wait_n,                                   # memory cycles in the queue
        "avg_wait_core": [st[f"queue_wait_sum_channel_0_core_{i}"] / st[f"queue_wait_reqs_channel_0_core_{i}"] for i in range(n)],
        "read_latency": st["read_latency_avg_0"],                        # memory cycles, arrival -> data
        "throughput": st["incoming_requests"] / st["dram_cycles"],       # requests per memory cycle
        "cycles": [st[f"record_cycs_core_{i}"] for i in range(n)],       # CPU cycles to reach the limit
        "insts": [st[f"record_insts_core_{i}"] for i in range(n)],
    }
    json.dump(res, open(cpath, "w"))
    return res


def mix(programs, scheduler, T=500, banks=8, queue=32, translation="Random"):
    """programs = list of names.  Adds slowdown (shared time / alone time) and unfairness."""
    progs = [(p, i) for i, p in enumerate(programs)]
    res = dict(run(progs, scheduler, T, banks, queue, translation=translation))
    alone = [run([ps], scheduler, T, banks, queue, translation=translation)["cycles"][0] for ps in progs]
    sd = [c / a for c, a in zip(res["cycles"], alone)]
    res["slowdowns"] = sd
    res["max_slowdown"] = max(sd)
    res["unfairness"] = max(sd) / min(sd)
    res["weighted_speedup"] = sum(1 / s for s in sd)
    return res
