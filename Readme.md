# MIS41160 Team Assignment - Job Shop Scheduling (Wallpaper Printing)

Our code for the MIS41160 team assignment. We started from the job shop model in
Gueret, Prins and Sevaux (1999), Section 7.3, and extended it for a wallcovering plant.

## Files

- `Base_wallpaper_model.mos` - the book's model. Runs the book case (D1) or the ft06 benchmark (D3).
- `Extended_wallpaper_model.mos` - our extended model for the plant (8 jobs, 5 machines).

The data is written inside each .mos file, so no extra data files are needed.

## How to run

You need FICO Xpress with Mosel installed. We used Xpress 9.x; the free community licence is enough for these model sizes.

**Xpress Workbench:** open the .mos file and press Run. To change a setting, edit the default in the `parameters` block.

**Command line** (Xpress command prompt on Windows, or a terminal):

```
mosel exec Base_wallpaper_model.mos
mosel exec Base_wallpaper_model.mos DATA=D3
mosel exec Extended_wallpaper_model.mos
mosel exec Extended_wallpaper_model.mos PRIMARY=makespan SECONDARY=penalty
```

Each model takes only a few seconds. It prints the result and the schedule for each machine.

## What we changed from the book

Every part of the code has a label: [BASE] is unchanged from the book, [MOD] is a book part we changed, and [NEW] is something we added.

- [NEW] Release dates: a job cannot start before its order arrives.
- [NEW] Due dates with a EUR penalty for every minute late.
- [MOD] Setup (cleaning) times on M2 that depend on which job came before.
- [NEW] A maintenance window on M4 (minutes 100 to 130).
- [MOD] Bigger Big-M to allow for the release dates, setups and maintenance.
- [NEW] Two-stage solve: optimise PRIMARY, fix it at its best value, then optimise SECONDARY (`makespan`, `penalty` or `lmax`).

## Scenarios

| Scenario | Parameters |
|---|---|
| A - no maintenance | `USE_MAINT=false` |
| B' - maintenance moved later | `MAINT_S=240 MAINT_E=270` |
| C - rush order for J3 | `RUSH_JOB=3 RUSH_DUE=130` |
| D - setup times halved | `SETUP_FACTOR=0.5` |

## Expected results

| Run | Makespan (min) | Penalty (EUR) | Max lateness (min) |
|---|---|---|---|
| Base, D1 (book case) | 97 | - | - |
| Base, D3 (ft06) | 55 | - | - |
| PRIMARY=makespan SECONDARY=penalty | 255 | 10,375 | 125 |
| PRIMARY=penalty SECONDARY=makespan (default) | 295 | 7,425 | 105 |
| PRIMARY=lmax SECONDARY=penalty | 285 | 8,600 | 95 |
| Scenario A | 283 | 5,560 | 93 |
| Scenario B' | 283 | 5,560 | 93 |
| Scenario C | 295 | 9,425 | 105 |
| Scenario D | 295 | 6,655 | 125 |

Note: there can be more than one optimal schedule, so your start times might differ from ours. The objective values should be the same.

## Reference

Gueret, C., Prins, C. and Sevaux, M. (1999) *Applications of Optimization with Xpress-MP*. Dash Optimization.