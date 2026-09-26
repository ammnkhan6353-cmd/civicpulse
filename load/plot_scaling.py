#!/usr/bin/env python3
"""Plot backend replicas against offered load (k6 virtual users) over time.

Inputs (produced during the load test - see docs/RUNBOOK.md "HPA load test"):
  load/replicas.csv     lines of  <unix_ts>,<replicas>        (from the watch loop)
  load/k6-results.csv   k6 --out csv=... output (we read the 'vus' metric)

Output:
  docs/evidence/scaling-chart.png

    pip install matplotlib
    python load/plot_scaling.py
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
replicas_file = ROOT / "load" / "replicas.csv"
k6_file = ROOT / "load" / "k6-results.csv"
out_file = ROOT / "docs" / "evidence" / "scaling-chart.png"

if not replicas_file.exists() or not k6_file.exists():
    sys.exit("Need load/replicas.csv and load/k6-results.csv - run the load test first.")

replicas: list[tuple[float, int]] = []
for row in csv.reader(replicas_file.open()):
    if len(row) >= 2 and row[0].strip().replace(".", "").isdigit():
        replicas.append((float(row[0]), int(row[1] or 0)))

vus: dict[int, float] = {}
with k6_file.open() as handle:
    for row in csv.DictReader(handle):
        if row.get("metric_name") == "vus":
            vus[int(float(row["timestamp"]))] = float(row["metric_value"])

if not replicas or not vus:
    sys.exit("One of the input files has no usable rows.")

t0 = min(min(t for t, _ in replicas), min(vus))
fig, ax_load = plt.subplots(figsize=(10, 5))
vu_times = sorted(vus)
ax_load.plot([t - t0 for t in vu_times], [vus[t] for t in vu_times],
             color="#2a6fdb", label="offered load (k6 virtual users)")
ax_load.set_xlabel("seconds since test start")
ax_load.set_ylabel("virtual users", color="#2a6fdb")

ax_rep = ax_load.twinx()
ax_rep.step([t - t0 for t, _ in replicas], [r for _, r in replicas], where="post",
            color="#0f6e5f", linewidth=2.5, label="backend replicas")
ax_rep.set_ylabel("backend replicas", color="#0f6e5f")
ax_rep.set_ylim(0, max(r for _, r in replicas) + 2)

fig.suptitle("CivicPulse HPA: backend replicas vs offered load")
fig.legend(loc="upper left", bbox_to_anchor=(0.08, 0.9))
fig.tight_layout()
out_file.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_file, dpi=150)
print(f"wrote {out_file}")
