"""Baseline solution, comparison with an equal-split plan, and sensitivity sweeps.
Run from the repository root:  python src/run_analysis.py
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import model

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)
SKILLS = ["Skill 1", "Skill 2", "Skill 3", "Skill 4"]


def row(label, value, r):
    return dict(parameter=label, value=value, status=r["status"],
                total_cost=round(r["total_cost"]), project_days=r["project_days"],
                days_late=round(r["delay_days"]), overtime_hours=round(r["overtime_hours"]),
                workers_used=r["workers_used"])


# ---------------------------------------------------------------- baseline
base = model.solve()
ref = model.equal_split_cost()
with open(OUT / "baseline_results.txt", "w") as f:
    f.write("BASELINE (deadline 20 working days, lateness $1,000/day, overtime x1.5)\n")
    f.write(f"Status:                 {base['status']}\n")
    f.write(f"Total cost:             ${base['total_cost']:,.0f}\n")
    f.write(f"  Labour cost:          ${base['labour_cost']:,.0f}\n")
    f.write(f"  Lateness penalty:     ${base['total_cost'] - base['labour_cost']:,.0f}\n")
    f.write(f"Project length:         {base['project_days']} working days ({base['delay_days']:.0f} late)\n")
    f.write(f"Stage lengths (days):   {base['stage_days']}\n")
    f.write(f"Total hours worked:     {base['total_hours']:,.0f} (overtime {base['overtime_hours']:,.0f})\n")
    f.write(f"Workers used:           {base['workers_used']} of 10\n\n")
    f.write("EQUAL-SPLIT REFERENCE (every worker does an equal share of each skill's output)\n")
    f.write(f"Labour cost:            ${ref['labour_cost']:,.0f}\n")
    f.write(f"Project length:         {ref['project_days']} working days ({ref['delay_days']} late, "
            f"lateness penalty ${ref['total_cost'] - ref['labour_cost']:,.0f})\n")
    f.write(f"Total cost:             ${ref['total_cost']:,.0f}\n")
    f.write(f"Optimised plan saves:   ${ref['labour_cost'] - base['labour_cost']:,.0f} of labour cost "
            f"({(1 - base['labour_cost'] / ref['labour_cost']) * 100:.0f}%) and finishes "
            f"{ref['project_days'] - base['project_days']} days sooner\n")

with open(OUT / "baseline_hours_by_worker_skill.csv", "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["worker", "hourly_wage"] + [f"{s} hours" for s in SKILLS] + ["total_hours"])
    for w in model.DEFAULTS["workers"]:
        hrs = [base["hours_by_worker_skill"][(w, s)] for s in range(model.NUM_SKILLS)]
        wr.writerow([f"W{w + 1}", model.WAGES[w]] + [round(h, 1) + 0.0 for h in hrs] + [round(sum(hrs), 1)])

# ---------------------------------------------------------------- sensitivity
sweeps = {
    "deadline_days": ("deadline (working days)", [12, 14, 16, 18, 20, 24, 28, 32, 40]),
    "tardiness_per_day": ("lateness penalty ($ per day)", [100, 200, 300, 500, 1000, 2000]),
    "workload_scale": ("workload (share of baseline hours)", [0.8, 0.9, 1.0, 1.1, 1.2]),
    "efficiency_scale": ("worker efficiency (share of baseline)", [0.8, 0.9, 1.0, 1.1]),
    "overtime_multiplier": ("overtime pay multiplier", [1.0, 1.25, 1.5, 2.0, 3.0]),
    "crew_size": ("workers available (first n)", [10, 9, 8, 7, 6, 5]),
}
results = {}
for key, (label, values) in sweeps.items():
    rows = []
    for v in values:
        kwargs = {"workers": list(range(v))} if key == "crew_size" else {key: v}
        r = model.solve(**kwargs)
        rows.append(row(key, v, r) if r["status"] == "OPTIMAL"
                    else dict(parameter=key, value=v, status=r["status"]))
    results[key] = rows

fields = ["parameter", "value", "status", "total_cost", "project_days", "days_late", "overtime_hours", "workers_used"]
with open(OUT / "sensitivity_results.csv", "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=fields)
    wr.writeheader()
    for rows in results.values():
        wr.writerows(rows)

# ---------------------------------------------------------------- charts
INK, LINE, GRID = "#1f2933", "#2a6f97", "#d9dee3"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK, "ytick.color": INK})
panels = [("deadline_days", "total_cost", "Total cost ($)", "Cost falls as the deadline loosens"),
          ("deadline_days", "overtime_hours", "Overtime hours", "Tight deadlines are met with overtime"),
          ("tardiness_per_day", "project_days", "Project length (days)", "Cheap lateness gets tolerated"),
          ("workload_scale", "total_cost", "Total cost ($)", "Cost grows with the amount of work"),
          ("overtime_multiplier", "total_cost", "Total cost ($)", "Overtime premium raises cost"),
          ("crew_size", "total_cost", "Total cost ($)", "Smaller crews cost more")]
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for ax, (key, metric, ylabel, title) in zip(axes.flat, panels):
    rows = [r for r in results[key] if r["status"] == "OPTIMAL"]
    xs, ys = [r["value"] for r in rows], [r[metric] for r in rows]
    ax.plot(xs, ys, color=LINE, lw=2, marker="o", ms=6)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    ax.set_xlabel(sweeps[key][0]); ax.set_ylabel(ylabel)
    ax.grid(True, color=GRID, lw=0.8); ax.spines[["top", "right"]].set_visible(False)
    if key == "crew_size":
        ax.invert_xaxis()
fig.suptitle("Sensitivity analysis: multi-skilled project scheduling", fontsize=13, fontweight="bold")
fig.tight_layout()
fig.savefig(OUT / "sensitivity_charts.png", dpi=150)

print(open(OUT / "baseline_results.txt").read())
for key, rows in results.items():
    print(key)
    for r in rows:
        print("  ", {k: r[k] for k in r if k != "parameter"})
