"""
Extended_wallpaper_model.py
===========================
MIS41160 Optimisation in Business - Job Shop Scheduling (extended model)

The team's wallcovering plant: 8 jobs x 5 machines, built on the book's
job shop model and solved with the FICO Xpress Python API.
Labels: [BASE] from the book, [MOD] book element changed, [NEW] added.

  [BASE] start times, route order, makespan Cmax >= C_j
  [MOD]  M2 disjunctions include sequence-dependent setups s(a,b):
           start[b] >= start[a] + p_a + s(a,b) - M*(1 - y[a,b])
           start[a] >= start[b] + p_b + s(b,a) - M*y[a,b]
         Big-M enlarged to cover releases, setups and maintenance
  [NEW]  release dates     start[first op of j] >= r_j
         M4 maintenance    start + p <= ms + M*z   or   start >= me - M*(1 - z)
         completion        C_j = start[last op] + p[last op]
         tardiness         T_j >= C_j - d_j, T_j >= 0     (EUR w_j per minute)
         max lateness      Lmax >= C_j - d_j
         objectives        "makespan", "penalty" (sum w_j*T_j) or "lmax",
                           solved lexicographically: primary, fix it, secondary

Run:  python Extended_wallpaper_model.py        (no other files needed)
"""

import copy
from itertools import combinations

import xpress as xp


# ----------------------------------------------------------------------
# Data (D2)
# ----------------------------------------------------------------------
# job: (name, release, due, EUR per minute late, route [(machine, minutes)])
JOBS = {
    1: ("Royal Damask Gold",         0, 130, 35, [("M1", 25), ("M2", 30), ("M4", 20), ("M5", 15)]),
    2: ("Nordic Geometric Pastel",  10, 130, 20, [("M1", 20), ("M3", 25), ("M2", 15), ("M5", 20)]),
    3: ("Botanical Forest Mural",    0, 170, 50, [("M2", 35), ("M1", 20), ("M3", 30), ("M4", 25), ("M5", 20)]),
    4: ("Vintage Velvet Stripe",    15, 170, 15, [("M1", 15), ("M4", 35), ("M2", 20), ("M5", 25)]),
    5: ("Metallic Foil Abstract",   20, 160, 40, [("M3", 30), ("M2", 25), ("M4", 30), ("M5", 15)]),
    6: ("Kids Cartoon Playroom",     0, 150, 15, [("M1", 30), ("M2", 20), ("M3", 20), ("M5", 15)]),
    7: ("Textured Linen Neutral",   25, 160, 25, [("M1", 25), ("M4", 20), ("M3", 25), ("M5", 20)]),
    8: ("Industrial Urban Concrete", 30, 190, 20, [("M2", 25), ("M4", 30), ("M1", 20), ("M5", 25)]),
}
# Setup minutes on M2 when job `to` follows job `frm`: SETUP[frm][to-1]
SETUP_MACHINE = "M2"
SETUP = {
    1: [0, 15, 5, 10, 8, 12, 10, 8],
    2: [12, 0, 15, 8, 10, 6, 8, 12],
    3: [6, 18, 0, 12, 10, 14, 12, 6],
    4: [10, 12, 10, 0, 8, 10, 6, 8],
    5: [8, 14, 8, 10, 0, 12, 10, 8],
    6: [10, 8, 14, 8, 10, 0, 8, 10],
    7: [8, 10, 12, 6, 8, 8, 0, 8],
    8: [6, 14, 6, 10, 8, 12, 8, 0],
}
MAINT = {"M4": (100, 130)}  # roller calibration window

# Runs: (name, primary, secondary, scenario changes)
RUNS = [
    ("EXT_MAKESPAN",       "makespan", "penalty",  {}),
    ("EXT_PENALTY",        "penalty",  "makespan", {}),
    ("EXT_LMAX",           "lmax",     "penalty",  {}),
    ("SCEN_A_NO_MAINT",    "penalty",  "makespan", {"maint": {}}),
    ("SCEN_B2_MAINT_LATE", "penalty",  "makespan", {"maint": {"M4": (240, 270)}}),
    ("SCEN_C_RUSH_J3",     "penalty",  "makespan", {"due": {3: 130}}),
    ("SCEN_D_SETUP_HALF",  "penalty",  "makespan", {"setup_factor": 0.5}),
]


def setup(frm, to, factor):
    return SETUP[frm][to - 1] * factor


def solve_extended(primary, secondary=None, maint=None, due=None, setup_factor=1.0, time_limit=120):
    maint = MAINT if maint is None else maint
    jobs = copy.deepcopy(JOBS)
    for j, d in (due or {}).items():
        jobs[j] = jobs[j][:2] + (d,) + jobs[j][3:]

    ops = [{"id": f"J{j}_O{k + 1}", "job": j, "machine": m, "p": p}
           for j, job in jobs.items() for k, (m, p) in enumerate(job[4])]
    by_job = {j: [o for o in ops if o["job"] == j] for j in jobs}
    pairs = [(a, b) for a, b in combinations(ops, 2) if a["machine"] == b["machine"]]
    n_setup_ops = sum(o["machine"] == SETUP_MACHINE for o in ops)
    big_m = (sum(o["p"] for o in ops) + max(j[1] for j in jobs.values())          # [MOD]
             + max(max(r) for r in SETUP.values()) * setup_factor * n_setup_ops
             + sum(e - s for s, e in maint.values()))

    prob = xp.problem(name="Extended_JobShop")
    start = {o["id"]: prob.addVariable(lb=0, name=f"start_{o['id']}") for o in ops}
    y = {(a["id"], b["id"]): prob.addVariable(vartype=xp.binary) for a, b in pairs}
    cmax = prob.addVariable(lb=0, name="Cmax")
    C = {j: prob.addVariable(lb=0, name=f"C_{j}") for j in jobs}
    T = {j: prob.addVariable(lb=0, name=f"T_{j}") for j in jobs}
    lmax = prob.addVariable(lb=-xp.infinity, name="Lmax")
    maint_ops = [o for o in ops if o["machine"] in maint]
    z = {o["id"]: prob.addVariable(vartype=xp.binary) for o in maint_ops}

    for j, route in by_job.items():
        for a, b in zip(route, route[1:]):                                       # [BASE] route
            prob.addConstraint(start[b["id"]] >= start[a["id"]] + a["p"])
        prob.addConstraint(start[route[0]["id"]] >= jobs[j][1])                  # [NEW] release
        last = route[-1]
        prob.addConstraint(C[j] == start[last["id"]] + last["p"])                # [NEW] completion
        prob.addConstraint(cmax >= C[j])                                         # [BASE] makespan
        prob.addConstraint(T[j] >= C[j] - jobs[j][2])                            # [NEW] tardiness
        prob.addConstraint(lmax >= C[j] - jobs[j][2])                            # [NEW] lateness

    for a, b in pairs:                                                           # [MOD] disjunctions
        on_setup = a["machine"] == SETUP_MACHINE
        s_ab = setup(a["job"], b["job"], setup_factor) if on_setup else 0
        s_ba = setup(b["job"], a["job"], setup_factor) if on_setup else 0
        ya = y[(a["id"], b["id"])]
        prob.addConstraint(start[b["id"]] >= start[a["id"]] + a["p"] + s_ab - big_m * (1 - ya))
        prob.addConstraint(start[a["id"]] >= start[b["id"]] + b["p"] + s_ba - big_m * ya)

    for o in maint_ops:                                                          # [NEW] maintenance
        ms, me = maint[o["machine"]]
        prob.addConstraint(start[o["id"]] + o["p"] <= ms + big_m * z[o["id"]])
        prob.addConstraint(start[o["id"]] >= me - big_m * (1 - z[o["id"]]))

    objectives = {"makespan": cmax, "lmax": lmax,
                  "penalty": xp.Sum(jobs[j][3] * T[j] for j in jobs)}
    prob.controls.outputlog = 0
    prob.controls.timelimit = time_limit

    # Lexicographic solve: primary, then secondary with primary held at its best
    statuses = []
    for stage, goal in enumerate([primary, secondary]):
        if goal is None:
            break
        if stage == 1:
            prob.addConstraint(objectives[primary] <= prob.getSolution(objectives[primary]) + 1e-6)
        prob.setObjective(objectives[goal], sense=xp.minimize)
        _, status = prob.optimize()
        statuses.append(status)
        if status not in (xp.SolStatus.OPTIMAL, xp.SolStatus.FEASIBLE):
            return {"status": str(status)}

    rows = []
    for j in jobs:
        cj = round(prob.getSolution(C[j]), 2)
        late = max(0.0, cj - jobs[j][2])
        rows.append((j, jobs[j][1], jobs[j][2], cj, late, late * jobs[j][3]))
    sched = [{**o, "start": round(prob.getSolution(start[o["id"]]), 2)} for o in ops]
    return {"status": "Optimal" if all(s == xp.SolStatus.OPTIMAL for s in statuses) else "Feasible (time limit)",
            "makespan": round(prob.getSolution(cmax), 2),
            "penalty": sum(r[5] for r in rows),
            "lmax": round(prob.getSolution(lmax), 2),
            "jobs": rows, "schedule": sched}


def print_result(name, r):
    print(f"\n{name}: {r['status']}, makespan = {r.get('makespan')}, "
          f"penalty = EUR {r.get('penalty', 0):,.0f}, max lateness = {r.get('lmax')}")
    if "jobs" not in r:
        return
    print(f"  {'Job':<4}{'Release':>8}{'Due':>6}{'Finish':>8}{'Late':>6}{'EUR':>8}")
    for j, rel, due, cj, late, pen in r["jobs"]:
        print(f"  J{j:<3}{rel:>8}{due:>6}{cj:>8.0f}{late:>6.0f}{pen:>8,.0f}")
    for m in sorted({s["machine"] for s in r["schedule"]}):
        row = sorted((s for s in r["schedule"] if s["machine"] == m), key=lambda s: s["start"])
        print(f"  {m}: " + "  ".join(f"{s['id']} {s['start']:.0f}-{s['start'] + s['p']:.0f}" for s in row))


if __name__ == "__main__":
    summary = []
    for name, primary, secondary, scen in RUNS:
        r = solve_extended(primary, secondary, **scen)
        print_result(name, r)
        summary.append((name, r))
    print(f"\n{'Run':<20}{'Status':<12}{'Makespan':>9}{'Penalty EUR':>13}{'Lmax':>6}")
    for name, r in summary:
        print(f"{name:<20}{r['status']:<12}{r.get('makespan')!s:>9}{r.get('penalty', 0):>13,.0f}{r.get('lmax')!s:>6}")
