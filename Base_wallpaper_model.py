"""
Base_wallpaper_model.py
=======================
MIS41160 Optimisation in Business - Job Shop Scheduling (base model)

Gueret, Prins and Sevaux (1999), Applications of Optimization with
Xpress-MP, Section 7.3 "Job shop scheduling" (wallpaper printing),
written with the FICO Xpress Python API. The maths is the book's [BASE].

    Variables  start[o] >= 0        start time of operation o
               y[a,b]  in {0,1}     1 if op a goes before op b on a machine
               Cmax >= 0            makespan
    Objective  min Cmax
    (P) start[next op of job] >= start[op] + p[op]          route order
    (D) start[b] >= start[a] + p[a] - M*(1 - y[a,b])        a before b
        start[a] >= start[b] + p[b] - M*y[a,b]              b before a
    (C) Cmax >= start[last op of job] + p[last op]

Run:  python Base_wallpaper_model.py        (no other files needed)
"""

import warnings
from itertools import combinations

import xpress as xp

warnings.filterwarnings("ignore", message=r".*license file found.*")

# ----------------------------------------------------------------------
# Data: {job: [(machine, minutes), ...] in route order}
# ----------------------------------------------------------------------
DATASETS = {
    # D1 - book case: 3 papers x 3 machines, optimum makespan 97
    "D1": {
        1: [("Blue", 45), ("Yellow", 10)],
        2: [("Green", 10), ("Blue", 20), ("Yellow", 34)],
        3: [("Yellow", 28), ("Blue", 12), ("Green", 17)],
    },
    # D3 - ft06 benchmark (Fisher & Thompson 1963), optimum makespan 55
    "D3": {
        1: [("M3", 1), ("M1", 3), ("M2", 6), ("M4", 7), ("M6", 3), ("M5", 6)],
        2: [("M2", 8), ("M3", 5), ("M5", 10), ("M6", 10), ("M1", 10), ("M4", 4)],
        3: [("M3", 5), ("M4", 4), ("M6", 8), ("M1", 9), ("M2", 1), ("M5", 7)],
        4: [("M2", 5), ("M1", 5), ("M3", 5), ("M4", 3), ("M5", 8), ("M6", 9)],
        5: [("M3", 9), ("M2", 3), ("M5", 5), ("M6", 4), ("M1", 3), ("M4", 1)],
        6: [("M2", 3), ("M4", 3), ("M6", 9), ("M1", 10), ("M5", 4), ("M3", 1)],
    },
}
EXPECTED = {"D1": 97, "D3": 55}


def operations(routes):
    """Flatten routes into a list of ops: {id, job, machine, p}."""
    return [{"id": f"J{j}_O{k + 1}", "job": j, "machine": m, "p": p}
            for j, route in routes.items() for k, (m, p) in enumerate(route)]


def solve_base(routes, time_limit=60):
    ops = operations(routes)
    by_job = {j: [o for o in ops if o["job"] == j] for j in routes}
    pairs = [(a, b) for a, b in combinations(ops, 2) if a["machine"] == b["machine"]]
    big_m = sum(o["p"] for o in ops)                       # book's Big-M

    prob = xp.problem(name="Base_JobShop")
    start = {o["id"]: prob.addVariable(lb=0, name=f"start_{o['id']}") for o in ops}
    y = {(a["id"], b["id"]): prob.addVariable(vartype=xp.binary) for a, b in pairs}
    cmax = prob.addVariable(lb=0, name="Cmax")

    for route in by_job.values():                          # (P) route order
        for a, b in zip(route, route[1:]):
            prob.addConstraint(start[b["id"]] >= start[a["id"]] + a["p"])
    for a, b in pairs:                                     # (D) no overlap
        ya = y[(a["id"], b["id"])]
        prob.addConstraint(start[b["id"]] >= start[a["id"]] + a["p"] - big_m * (1 - ya))
        prob.addConstraint(start[a["id"]] >= start[b["id"]] + b["p"] - big_m * ya)
    for route in by_job.values():                          # (C) makespan
        prob.addConstraint(cmax >= start[route[-1]["id"]] + route[-1]["p"])

    prob.setObjective(cmax, sense=xp.minimize)
    prob.controls.outputlog = 0
    prob.controls.timelimit = time_limit
    _, status = prob.optimize()
    if status not in (xp.SolStatus.OPTIMAL, xp.SolStatus.FEASIBLE):
        return {"status": str(status)}

    sched = [{**o, "start": round(prob.getSolution(start[o["id"]]), 2)} for o in ops]
    for s in sched:
        s["end"] = s["start"] + s["p"]
    return {"status": "Optimal" if status == xp.SolStatus.OPTIMAL else "Feasible (time limit)",
            "makespan": round(prob.getSolution(cmax), 2), "schedule": sched}


def print_schedule(sched):
    for m in sorted({s["machine"] for s in sched}):
        row = sorted((s for s in sched if s["machine"] == m), key=lambda s: s["start"])
        print(f"  {m:<7}" + "  ".join(f"{s['id']} {s['start']:.0f}-{s['end']:.0f}" for s in row))


if __name__ == "__main__":
    for name, routes in DATASETS.items():
        r = solve_base(routes)
        print(f"\n{name}: {r['status']}, makespan = {r.get('makespan')} (expected {EXPECTED[name]})")
        if "schedule" in r:
            print_schedule(r["schedule"])
