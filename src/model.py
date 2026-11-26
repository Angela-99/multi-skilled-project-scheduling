"""Multi-skilled project scheduling as a mixed-integer program (Google OR-Tools).

The project is 10 tasks with precedence. Tasks that can run in parallel are grouped into
sequential stages, so the project is a chain of 8 stages. For each stage the model chooses:
  - how many working days it lasts (integer),
  - how many regular and overtime hours each worker spends on each skill of each task.

Rules:
  - every task needs a set number of hours of each skill; a worker's hour produces
    (efficiency of that worker in that skill) hours of skill output
  - per day a worker has 8 regular hours and up to 2 overtime hours, shared across all tasks
    in the stage (so a stage lasting m days gives each worker 8m regular and 2m overtime hours)
  - overtime costs a premium; each working day after the deadline costs a lateness penalty

Cost = wages for regular hours + premium wages for overtime hours + lateness penalty.
"""
from ortools.linear_solver import pywraplp

NUM_SKILLS = 4

# Tasks 0..9 grouped into sequential stages (tasks inside a stage have no precedence between them)
STAGES = [[0], [1, 2], [3], [4, 5], [6], [7], [8], [9]]

# Hours of each skill needed per task (rows: task, columns: skill)
SKILL_HOURS = [
    [40, 30, 20, 25], [35, 40, 25, 30], [30, 25, 40, 20], [45, 35, 30, 40], [40, 30, 35, 25],
    [35, 40, 30, 35], [40, 35, 40, 30], [30, 40, 25, 40], [40, 30, 40, 35], [35, 40, 30, 40],
]

# Output per hour worked (rows: worker, columns: skill)
EFFICIENCY = [
    [0.9, 0.7, 0.8, 0.6], [0.8, 0.9, 0.7, 0.8], [0.7, 0.8, 0.9, 0.7], [0.6, 0.7, 0.8, 0.9],
    [0.8, 0.6, 0.7, 0.8], [0.7, 0.8, 0.6, 0.9], [0.9, 0.7, 0.8, 0.7], [0.8, 0.9, 0.7, 0.6],
    [0.6, 0.8, 0.9, 0.8], [0.7, 0.6, 0.8, 0.9],
]

# Synthetic hourly wages in dollars, one per worker (assumed values, not from a source)
WAGES = [32, 28, 35, 30, 26, 38, 29, 33, 27, 36]

DEFAULTS = dict(
    deadline_days=20,
    regular_daily_hours=8,
    overtime_daily_hours=2,
    overtime_multiplier=1.5,
    tardiness_per_day=1000.0,  # dollars per working day finished after the deadline
    max_stage_days=40,
    workload_scale=1.0,
    efficiency_scale=1.0,
    wage_scale=1.0,
    workers=list(range(len(WAGES))),
)


def solve(**overrides):
    p = {**DEFAULTS, **overrides}
    workers = p["workers"]
    eff = lambda w, s: min(EFFICIENCY[w][s] * p["efficiency_scale"], 1.0)
    need = lambda t, s: SKILL_HOURS[t][s] * p["workload_scale"]
    wage = lambda w: WAGES[w] * p["wage_scale"]

    solver = pywraplp.Solver.CreateSolver("SCIP")
    days = [solver.IntVar(1, p["max_stage_days"], f"days_{k}") for k in range(len(STAGES))]
    reg = {(w, t, s): solver.NumVar(0, solver.infinity(), "")
           for k, tasks in enumerate(STAGES) for t in tasks for w in workers for s in range(NUM_SKILLS)}
    ot = {key: solver.NumVar(0, solver.infinity(), "") for key in reg}
    delay = solver.NumVar(0, solver.infinity(), "delay")

    for k, tasks in enumerate(STAGES):
        for t in tasks:
            for s in range(NUM_SKILLS):   # skill requirement is met
                solver.Add(sum(eff(w, s) * (reg[(w, t, s)] + ot[(w, t, s)]) for w in workers) >= need(t, s))
        for w in workers:                  # daily hour limits, shared across the stage's tasks
            solver.Add(sum(reg[(w, t, s)] for t in tasks for s in range(NUM_SKILLS))
                       <= p["regular_daily_hours"] * days[k])
            solver.Add(sum(ot[(w, t, s)] for t in tasks for s in range(NUM_SKILLS))
                       <= p["overtime_daily_hours"] * days[k])
    solver.Add(delay >= sum(days) - p["deadline_days"])

    labour = sum(wage(w) * (reg[(w, t, s)] + p["overtime_multiplier"] * ot[(w, t, s)])
                 for (w, t, s) in reg)
    solver.Minimize(labour + p["tardiness_per_day"] * delay)

    params = pywraplp.MPSolverParameters()
    params.SetDoubleParam(pywraplp.MPSolverParameters.RELATIVE_MIP_GAP, 0.0)   # solve to proven optimality
    status = solver.Solve(params)
    if status != pywraplp.Solver.OPTIMAL:
        return {"status": "INFEASIBLE" if status == pywraplp.Solver.INFEASIBLE else f"status {status}"}

    reg_h = {k: v.solution_value() for k, v in reg.items()}
    ot_h = {k: v.solution_value() for k, v in ot.items()}
    worker_hours = {w: sum(reg_h[k] + ot_h[k] for k in reg_h if k[0] == w) for w in workers}
    return dict(
        status="OPTIMAL",
        total_cost=solver.Objective().Value(),
        labour_cost=sum(wage(w) * (reg_h[(w, t, s)] + p["overtime_multiplier"] * ot_h[(w, t, s)])
                        for (w, t, s) in reg_h),
        project_days=int(round(sum(d.solution_value() for d in days))),
        delay_days=delay.solution_value(),
        stage_days=[int(round(d.solution_value())) for d in days],
        total_hours=sum(worker_hours.values()),
        overtime_hours=sum(ot_h.values()),
        workers_used=sum(1 for v in worker_hours.values() if v > 1e-6),
        worker_hours=worker_hours,
        hours_by_worker_skill={(w, s): sum(reg_h[(w, t, s)] + ot_h[(w, t, s)]
                                           for t in range(len(SKILL_HOURS)))
                               for w in workers for s in range(NUM_SKILLS)},
    )


def equal_split_cost(**overrides):
    """Reference case: every worker does an equal share of each skill's output, all at regular
    pay if the stage is long enough. Stage length is the smallest that fits the hours."""
    p = {**DEFAULTS, **overrides}
    workers = p["workers"]
    eff = lambda w, s: min(EFFICIENCY[w][s] * p["efficiency_scale"], 1.0)
    share = 1.0 / len(workers)
    cost, days = 0.0, 0
    for tasks in STAGES:
        per_worker_hours = {w: 0.0 for w in workers}
        for t in tasks:
            for s in range(NUM_SKILLS):
                for w in workers:   # each worker produces an equal share of the output
                    per_worker_hours[w] += SKILL_HOURS[t][s] * p["workload_scale"] * share / eff(w, s)
        cap = p["regular_daily_hours"] + p["overtime_daily_hours"]
        m = max(1, -(-max(per_worker_hours.values()) // cap))
        days += int(m)
        for w in workers:
            h = per_worker_hours[w]
            reg_h = min(h, p["regular_daily_hours"] * m)
            cost += p["wage_scale"] * WAGES[w] * (reg_h + p["overtime_multiplier"] * (h - reg_h))
    late = max(0, days - p["deadline_days"])
    return dict(labour_cost=cost, total_cost=cost + p["tardiness_per_day"] * late,
                project_days=int(days), delay_days=late)


if __name__ == "__main__":
    r = solve()
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()
           if k not in ("worker_hours", "hours_by_worker_skill")})
    print("equal split:", equal_split_cost())
