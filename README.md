# Multi-Skilled Project Scheduling: Cost, Overtime and Deadline Trade-offs

A project has 10 tasks with precedence rules, each needing hours of four different skills. Ten workers differ in how fast they are at each skill and in what they are paid. This model decides who works on what, how long each stage lasts, and how much overtime to use, to minimise total cost. It is a mixed-integer program built with Google OR-Tools in Python, followed by a sensitivity analysis.

This started as a school project inspired by Karam, Attia and Duquenne (2017), "A MILP model for an integrated project scheduling and multi-skilled workforce allocation with flexible working hours" (20th IFAC World Congress). The model here is my own simplified formulation, not the paper's.

**What changed from the course version.** The course model computed cost as total work hours times one wage, so cost could not depend on who did the work, how long stages lasted, or the deadline. Its worker efficiency data was never used in the constraints. I rebuilt the model so that who works on which skill, overtime and lateness all affect cost, then re-ran the analysis. The results below come from this rebuilt model.

## The model

- Tasks that can run in parallel are grouped into 8 sequential stages (task 0; tasks 1 and 2; task 3; tasks 4 and 5; tasks 6, 7, 8 and 9 one by one).
- For each stage the model picks a length in whole working days, and the regular and overtime hours of each worker on each skill of each task.
- A worker's hour produces output equal to their efficiency in that skill (0.6 to 0.9). Each task must receive its required skill output.
- Each day a worker has 8 regular hours and up to 2 overtime hours, shared across the tasks in the stage.
- Cost = regular wages + overtime wages (1.5 times) + a penalty for each working day after the deadline.

Base case: 20 working day deadline, $1,000 per day late, 10 workers with hourly wages between $26 and $38.

## Results

| Measure | Optimised plan | Equal-split reference* |
|---|---|---|
| Labour cost | $47,668 | $58,088 |
| Project length | 20 working days | 24 working days (4 late, $4,000 penalty) |
| Overtime | 64 hours | n/a |

*Every worker does an equal share of each skill's output. The optimised plan saves $10,420 (18%) of labour cost and finishes 4 days sooner, by giving each skill to the workers who are cheapest per unit of output.

Sensitivity analysis (`outputs/sensitivity_charts.png`, full numbers in `outputs/sensitivity_results.csv`):

- **Deadline:** cost falls from $55,439 (deadline 12) to $43,213 (deadline 40). Overtime disappears once the deadline reaches 28 days, and the crew needed shrinks to 8 workers by day 32. The fastest possible finish is 19 working days, so deadlines of 12 to 18 days are always missed.
- **Lateness penalty:** at $100 per day the cheapest plan runs 42 days. At $500 per day or more it finishes in 20.
- **Workload:** 20% more work raises cost by 28% ($61,173), more than in proportion because overtime kicks in and the project runs a day late.
- **Worker efficiency:** 20% lower efficiency raises cost by 36% ($64,918) and makes the project 4 days late.
- **Overtime premium:** going from 1.0 to 3.0 times pay raises cost from $45,592 to $48,597. The plan uses 303 overtime hours when it is free and 22 when it is expensive.
- **Crew size:** with 8 workers instead of 10, cost rises to $53,279 and the project runs 4 days late. With 5 workers it takes 36 days.

## Limits to keep in mind

- **The inputs are assumed.** Wages, the $1,000 daily lateness penalty and the 1.5 times overtime rate are made-up values. Task hours and worker efficiencies are the course project's synthetic data. The results show how the model behaves, not what a real project would cost.
- **Simplifications.** Parallel tasks are grouped into stages, stage lengths are whole days, hours can be spread evenly across a stage, and cost counts wages only (no hiring, training or switching costs).
- **Crew-size results depend on which workers are removed.** The sweep drops workers from the end of the list, which is an arbitrary choice.
- **Equal-split is a simple reference, not a real company plan.**
- **Solver.** SCIP solves each case to proven optimality in a fraction of a second. I checked the results against an independent linear program (SciPy) for the chosen stage lengths and against 1,500 random alternative schedules per case, and none were cheaper. The HiGHS solver stopped about $2 above the optimum on one case, so the code uses SCIP.

## Run it

    pip install -r requirements.txt
    python src/run_analysis.py

Run from the repository root. Results are written to `outputs/`.

## Files

- `src/model.py`: the optimization model and the equal-split reference
- `src/run_analysis.py`: baseline, comparison and sensitivity sweeps, with charts
- `outputs/baseline_results.txt`: baseline and reference summary
- `outputs/baseline_hours_by_worker_skill.csv`: who works on which skill in the baseline plan
- `outputs/sensitivity_results.csv`: all sensitivity runs
- `outputs/sensitivity_charts.png`: sensitivity charts
