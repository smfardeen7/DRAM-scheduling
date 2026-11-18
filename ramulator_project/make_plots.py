"""Graphs from results/*.csv -> results/fig_*.png  (Ramulator results)"""
import csv, os
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.join(HERE, "results")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                     "grid.alpha": .25, "axes.axisbelow": True})
rd = lambda n: list(csv.DictReader(open(os.path.join(RES, n))))
m = rd("mixes.csv")
POL = list(dict.fromkeys(r["policy"] for r in m))                 # FIFO, FR-FCFS, Fair-W (T=..), Fair-P (T=..)
COL = dict(zip(POL, ["#8E9AAF", "#1F4E79", "#E07A1F", "#2A9D8F"]))
FAIRW, FAIRP = POL[2], POL[3]
PROG = {"stream": "Streaming", "random": "Random\naccess", "matmul": "Matrix\nmultiply", "linkedlist": "Linked\nlist", "mixed": "Mixed"}
save = lambda name: (plt.tight_layout(), plt.savefig(os.path.join(RES, name), dpi=200), plt.close())

# 1. single programs: FIFO vs FR-FCFS
s = rd("single_programs.csv"); progs = ["stream", "mixed", "matmul", "random", "linkedlist"]
names = {"stream": "Array sum\n(streaming)", "mixed": "Mixed\n(stream+random)", "matmul": "Matrix\nmultiply", "random": "Random\naccess", "linkedlist": "Linked\nlist"}
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
for k, (met, title, fmt) in enumerate([("hit_rate", "Row-buffer hit rate", "{:.0%}"), ("avg_wait", "Average wait in queue (memory cycles)", "{:.0f}")]):
    x = np.arange(len(progs))
    for j, pol in enumerate(POL[:2]):
        v = [float([r for r in s if r["program"] == p and r["policy"] == pol][0][met]) for p in progs]
        b = ax[k].bar(x + (j - .5) * .38, v, .38, label=pol, color=COL[pol])
        for rect, val in zip(b, v): ax[k].text(rect.get_x() + rect.get_width() / 2, val, fmt.format(val), ha="center", va="bottom", fontsize=9)
    ax[k].set_xticks(x); ax[k].set_xticklabels([names[p] for p in progs]); ax[k].set_title(title)
ax[0].legend(frameon=False, loc="upper right"); save("fig_single.png")

# 2. per-program slowdown: stream + random, and the 4-program mix (FR-FCFS and the fair policies; FIFO is off the scale)
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [2, 4]})
for k, mix in enumerate(["mix_stream_random", "mix4"]):
    rows = {r["policy"]: r for r in m if r["mix"] == mix}
    progs = rows[POL[0]]["programs"].split("+"); x = np.arange(len(progs))
    for j, pol in enumerate(POL[1:]):
        v = [float(t) for t in rows[pol]["slowdowns"].split(";")]
        b = ax[k].bar(x + (j - 1) * .27, v, .27, label=f"{pol}: unfairness {float(rows[pol]['unfairness']):.2f}", color=COL[pol])
        for rect, val in zip(b, v): ax[k].text(rect.get_x() + rect.get_width() / 2, val, f"{val:.2f}", ha="center", va="bottom", fontsize=8)
    fifo = [float(t) for t in rows[POL[0]]["slowdowns"].split(";")]
    ax[k].set_xticks(x); ax[k].set_xticklabels([PROG[p] for p in progs]); ax[k].set_ylabel("Slowdown vs. running alone")
    ax[k].set_title(("Streaming + random access" if k == 0 else "4-program mix") + f"\n(FIFO not drawn: worst slowdown {max(fifo):.1f})", fontsize=11)
    ax[k].legend(frameon=False, fontsize=9)
save("fig_slowdown.png")

# 3. waiting-time limit T
t = rd("T_sweep.csv")
fig, ax = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
for k, mix in enumerate(["mix_stream_random", "mix4"]):
    rows = [r for r in t if r["mix"] == mix]
    for i, (met, yl) in enumerate([("unfairness", "unfairness (max / min slowdown)"), ("weighted_speedup", "weighted speedup")]):
        a = ax[i][k]
        for tag, pol in (("Fair-W", FAIRW), ("Fair-P", FAIRP)):
            sw = [r for r in rows if r["policy"] == tag]
            a.plot([int(r["T"]) for r in sw], [float(r[met]) for r in sw], "o-", color=COL[pol], label=tag)
        a.axhline(float([r for r in rows if r["policy"] == "FR-FCFS"][0][met]), color=COL["FR-FCFS"], ls="--", label="FR-FCFS")
        if met == "weighted_speedup":
            a.axhline(float([r for r in rows if r["policy"] == "FIFO"][0][met]), color=COL["FIFO"], ls=":", label="FIFO")
        a.set_xscale("log"); a.set_ylabel(yl)
        if i == 0: a.set_title(("Streaming + random access" if k == 0 else "4-program mix") + ("" if met != "unfairness" else f"  (FIFO: {float([r for r in rows if r['policy'] == 'FIFO'][0][met]):.1f}, not drawn)"), fontsize=11)
        if i == 1: a.set_xlabel("waiting-time limit T (memory cycles)")
        a.legend(frameon=False, fontsize=9)
save("fig_T_sweep.png")

# 4. number of banks (queue = 32)
sw = rd("sweeps.csv"); banks = sorted({int(r["banks"]) for r in sw})
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
for k, (met, yl) in enumerate([("unfairness", "unfairness (max / min slowdown)"), ("throughput", "throughput (requests / memory cycle)"), ("hit_rate", "row-buffer hit rate")]):
    for pol in POL:
        ax[k].plot(banks, [float([r for r in sw if r["banks"] == str(b) and r["queue"] == "32" and r["policy"] == pol][0][met]) for b in banks], "o-", color=COL[pol], label=pol)
    ax[k].set_xscale("log", base=2); ax[k].set_xticks(banks); ax[k].set_xticklabels(banks); ax[k].set_xlabel("number of banks (queue = 32)"); ax[k].set_ylabel(yl)
ax[0].set_yscale("log"); ax[0].set_yticks([1, 2, 5, 10, 20, 40]); ax[0].set_yticklabels([1, 2, 5, 10, 20, 40])
ax[1].legend(frameon=False, fontsize=9); fig.suptitle("Streaming + random access", fontsize=11); save("fig_banks.png")

# 5. queue size (8 banks)
queues = sorted({int(r["queue"]) for r in sw})
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
for k, (met, yl) in enumerate([("unfairness", "unfairness (max / min slowdown)"), ("throughput", "throughput (requests / memory cycle)")]):
    for pol in POL:
        ax[k].plot(queues, [float([r for r in sw if r["banks"] == "8" and r["queue"] == str(q) and r["policy"] == pol][0][met]) for q in queues], "o-", color=COL[pol], label=pol)
    ax[k].set_xscale("log", base=2); ax[k].set_xticks(queues); ax[k].set_xticklabels(queues); ax[k].set_xlabel("request-queue size (8 banks)"); ax[k].set_ylabel(yl)
ax[0].set_yscale("log"); ax[0].set_yticks([1, 2, 5, 10, 20]); ax[0].set_yticklabels([1, 2, 5, 10, 20])
ax[1].legend(frameon=False, fontsize=9); fig.suptitle("Streaming + random access", fontsize=11); save("fig_queue.png")
print("ok")
