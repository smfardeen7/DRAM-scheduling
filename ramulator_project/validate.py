"""Hand-checked tests on the modified Ramulator (DRAM-trace mode, commands printed).

Test 1.  Five reads to one bank arrive in the order A, B, A, A, B (A and B are two rows of bank 0).
  FCFS             serves A B A A B  -> 4 activations
  FRFCFS_PriorHit  serves A A A B B  -> 2 activations
  FAIR, T huge     nobody is over the limit -> must issue exactly the commands of FRFCFS_PriorHit
  FAIR, T = 0      everybody is over the limit -> must issue exactly the commands of Ramulator's FRFCFS
                   (oldest ready request first, row hits get no priority)

Test 2.  One read to row B arrives second, among 24 reads to row A (the waiting-time limit at work).
  FRFCFS_PriorHit  B is served last (all 24 row hits go first)
  FAIR, T = 40     B is served as soon as it has waited 40 cycles, before the remaining row hits
"""
import os, subprocess, sys, tempfile
from ramsim import RAMULATOR, CFG

A, B = 0x0, 0x10000          # 8 banks x 8 KB per row: row 0 and row 1 of bank 0


def run(trace, sched, T):
    with tempfile.TemporaryDirectory() as tmp:
        cfg, tr = os.path.join(tmp, "v.cfg"), os.path.join(tmp, "v.trace")
        open(cfg, "w").write(CFG.format(limit=0, scheduler=sched, T=T, queue=32, banks=8, print_cmd="on", translation="None"))
        open(tr, "w").write("".join(f"0x{a:x} R\n" for a in trace))
        out = subprocess.run([RAMULATOR, cfg, "--mode=dram", "--stats", os.path.join(tmp, "v.stats"), tr],
                             check=True, capture_output=True, text=True, cwd=tmp).stdout
    cmds = [l.split() for l in out.splitlines() if l.strip().startswith(("ACT", "RD", "PRE "))]
    return {"cmds": cmds,
            "acts": sum(1 for c in cmds if c[0] == "ACT"),
            "order": "".join("AB"[int(c[-2])] for c in cmds if c[0] == "RD"),     # row of each read, in service order
            "end": int(cmds[-1][1].rstrip(":"))}


ok = True
def check(label, cond, detail):
    global ok
    ok &= bool(cond)
    print(f"  {label:34s} {detail:48s} {'ok' if cond else 'FAIL'}")

print("Test 1: A B A A B on one bank")
t1 = [A, B, A + 0x40, A + 0x80, B + 0x40]
fcfs, hit, fr = run(t1, "FCFS", 0), run(t1, "FRFCFS_PriorHit", 0), run(t1, "FRFCFS", 0)
check("FCFS", fcfs["order"] == "ABAAB" and fcfs["acts"] == 4, f"order {fcfs['order']}, {fcfs['acts']} activations, done at {fcfs['end']}")
check("FRFCFS_PriorHit", hit["order"] == "AAABB" and hit["acts"] == 2, f"order {hit['order']}, {hit['acts']} activations, done at {hit['end']}")
for sched in ("FAIR", "FAIR_PROG"):
    big, zero = run(t1, sched, 10**6), run(t1, sched, 0)
    check(f"{sched}, T huge = FRFCFS_PriorHit", big["cmds"] == hit["cmds"], f"order {big['order']}, {big['acts']} activations")
    check(f"{sched}, T = 0 = FRFCFS", zero["cmds"] == fr["cmds"], f"order {zero['order']}, {zero['acts']} activations")

print("Test 2: one read to row B among 24 reads to row A")
t2 = [A, B] + [A + 0x40 * i for i in range(1, 24)]
hit, fair = run(t2, "FRFCFS_PriorHit", 0), run(t2, "FAIR", 40)
check("FRFCFS_PriorHit: B last", hit["order"].index("B") == 24, f"B is read number {hit['order'].index('B') + 1} of 25")
check("FAIR, T = 40: B earlier", fair["order"].index("B") < 24, f"B is read number {fair['order'].index('B') + 1} of 25")

print("VALIDATION PASS" if ok else "VALIDATION FAIL")
sys.exit(0 if ok else 1)
