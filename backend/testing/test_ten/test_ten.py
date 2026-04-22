#!/usr/bin/env python3
"""
test_ten.py — stress-test RouteOptimizer against 10 known test routes.

For each route in test_ten/:
  • Loads matrices from CSV + JSON files.
  • Runs RouteOptimizer.optimize_route() 100 times (SA is stochastic).
  • Prints a 3-field summary:
      - Original cost  (sequential order, from expected_results.json)
      - Optimal cost   (brute-force ground truth, from expected_results.json)
      - Optimizer cost (best and average of 100 runs)

Cost units: raw model output matching RouteOptimizer._route_cost()
(same scale as expected_results.json — no fuel_correction applied).
"""

import csv
import json
import logging
import sys
from pathlib import Path

# ── Suppress all RouteOptimizer/OR-Tools logging during the 100×10 runs ──────
logging.disable(logging.CRITICAL)

# ── Make backend/app importable ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "app"))
from route_optimizer import RouteOptimizer  # noqa: E402

# ── Constants (must match generate_test_ten.py and beta_boundaries.json) ─────
BETAS = {
    "Intercept":         0.025024,
    "Total_Distance_km": 0.06962583,
    "Dist_x_Weight":     5.552431e-5,
    "Elev_x_Weight":     2.55008e-6,
    "Dist_x_Speed2":     1.102072e-6,
}
BASE_VEHICLE_KG = 9000.0
RUNS = 100

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_matrix(path: Path):
    """Read a labelled NxN CSV → list[list[float]]."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    # Row 0 is the column-header row; column 0 of every data row is the row label.
    return [[float(v) for v in row[1:]] for row in rows[1:]]


def load_route(folder: Path) -> dict:
    return {
        "dm": read_matrix(folder / "distance_matrix.csv"),
        "em": read_matrix(folder / "elevation_matrix.csv"),
        "sm": read_matrix(folder / "speed_matrix.csv"),
        "fm": read_matrix(folder / "fuel_matrix.csv"),
        "weights":  json.loads((folder / "stop_weights.json").read_text()),
        "metadata": json.loads((folder / "metadata.json").read_text()),
        "expected": json.loads((folder / "expected_results.json").read_text()),
    }


def eval_cost(optimizer: RouteOptimizer, route: list, data: dict) -> float:
    """Raw RouteOptimizer cost for a route (no fuel_correction factor)."""
    return optimizer._route_cost(
        route,
        data["dm"], data["em"], data["sm"],
        data["weights_idx"],
        BETAS,
        BASE_VEHICLE_KG,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    test_dir = Path(__file__).parent
    optimizer = RouteOptimizer({})

    for route_num in range(1, 11):
        folder = test_dir / f"test_route_{route_num}"
        data = load_route(folder)

        labels      = data["metadata"]["labels"]
        n           = data["metadata"]["n_stops"]
        orig_cost   = data["expected"]["initial_route"]["fuel_cost"]
        opt_cost    = data["expected"]["optimal_route"]["fuel_cost"]
        description = data["expected"]["notes"]["description"]

        # weights keyed by int index (optimizer expects {int: float})
        data["weights_idx"] = {
            int(k): v for k, v in data["weights"]["by_index"].items()
        }

        # ── Run optimizer RUNS times ──────────────────────────────────────────
        costs = []
        print(f"Route {route_num:2d} ({n} stops) - running {RUNS}x...", end="", flush=True)

        for run in range(RUNS):
            route = optimizer.optimize_route(
                fuel_matrix      = data["fm"],
                distance_matrix  = data["dm"],
                elevation_matrix = data["em"],
                speed_matrix     = data["sm"],
                weights          = data["weights_idx"],
                betas            = BETAS,
                base_vehicle_kg  = BASE_VEHICLE_KG,
                location_names   = labels,
            )
            if route:
                costs.append(eval_cost(optimizer, route, data))

            if (run + 1) % 10 == 0:
                print(".", end="", flush=True)

        print()  # newline after progress dots

        if not costs:
            print(f"  !! Optimizer returned no valid routes for route {route_num}\n")
            continue

        best_cost  = min(costs)
        avg_cost   = sum(costs) / len(costs)

        savings_vs_orig  = (orig_cost - best_cost) / orig_cost * 100 if orig_cost else 0
        gap_to_opt       = (best_cost - opt_cost)  / opt_cost  * 100 if opt_cost  else 0

        # ── Print summary ─────────────────────────────────────────────────────
        sep = "=" * 62
        print(f"\n{sep}")
        print(f"  Route {route_num}  |  {n} stops")
        print(f"  {description}")
        print(sep)
        print(f"  Original cost  (sequential):         {orig_cost:>10.6f}")
        print(f"  Optimal cost   (brute-force):         {opt_cost:>10.6f}")
        print(f"  Optimizer cost (best  / {RUNS} runs):  {best_cost:>10.6f}")
        print(f"  Optimizer cost (avg   / {RUNS} runs):  {avg_cost:>10.6f}")
        print(f"  ----------------------------------------------------------")
        print(f"  Savings vs original:                  {savings_vs_orig:>9.1f}%")
        print(f"  Gap to brute-force optimal:           {gap_to_opt:>9.1f}%")
        print()


if __name__ == "__main__":
    main()
