"""Converts our address recordings (recorded/*.rec, made by record_traces.cpp from real running
programs) into Ramulator CPU traces.

Input line :  byte_offset,R|W,arrival_cycle      (cycle = memory-clock cycle, already cache-filtered)
Output line:  <bubbles> <read_address>           (Ramulator "filtered" CPU-trace format)

bubbles = non-memory instructions before the request.  Ramulator's core runs 4 instructions per CPU
cycle and 4 CPU cycles per memory cycle, so a gap of dt memory cycles becomes 16*dt instructions.

Every program gets one copy per 64 MB address region ("slot"), so that programs in a mix never
share rows and a program's alone-run uses exactly the addresses it uses in the mix.

Notes
- The recordings are misses of a write-allocate cache, so a W miss is also a line fill = a DRAM read
  (103 of the 100,000 recorded requests are W).  Writebacks are not modeled.
- Linked list: each load depends on the previous one.  Ramulator's core does not model dependences,
  so we put >= 128 instructions (the size of its instruction window) between two loads; then the
  window fills up behind an unfinished load and the next load cannot be issued early.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, "..", "recorded")
OUT = os.path.join(HERE, "traces")
REGION = 64 << 20            # 64 MB per program
SLOTS = 4
INSTR_PER_MEM_CYCLE = 16     # 4 CPU cycles per memory cycle x 4 instructions per CPU cycle
WINDOW = 128                 # Ramulator instruction window

# program name -> recording
PROGS = {"stream": "stream", "mixed": "chunks", "matmul": "matmul", "random": "random", "linkedlist": "linkedlist"}
DEPENDENT = {"linkedlist"}


def convert(prog, slot):
    last_t, n, instrs = 0, 0, 0
    path = os.path.join(OUT, f"{prog}_s{slot}.trace")
    with open(path, "w") as f:
        for line in open(os.path.join(REC, PROGS[prog] + ".rec")):
            off, _rw, t = line.strip().split(",")
            off, t = int(off), int(t)
            assert off < REGION
            bubbles = INSTR_PER_MEM_CYCLE * (t - last_t)
            if prog in DEPENDENT:
                bubbles = max(bubbles, WINDOW)
            last_t = t
            f.write(f"{bubbles} {slot * REGION + off}\n")
            n += 1
            instrs += bubbles + 1
    return n, instrs


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for prog in PROGS:
        for slot in range(SLOTS):
            n, instrs = convert(prog, slot)
        print(f"{prog:10s} {n} requests, {instrs} instructions per pass")
    print("traces written to", os.path.normpath(OUT))
