import sys
import os
import csv
import json
import logging

logging.basicConfig(level=logging.WARNING, format='%(message)s')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from route_optimizer import RouteOptimizer


def load_csv_matrix(filepath):
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        matrix = []
        row_names = []
        for row in reader:
            row_names.append(row[0])
            matrix.append([float(x) for x in row[1:]])
    return row_names, matrix


def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)


def main():
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'testing', 'sample_route_matrices')
    suite_dir = os.path.join(os.path.dirname(__file__), '..', 'testing', 'testing_suite')

    dist_names, distance_matrix  = load_csv_matrix(os.path.join(data_dir, 'distance_matrix.csv'))
    _,          elevation_matrix = load_csv_matrix(os.path.join(data_dir, 'elevation_matrix.csv'))
    _,          speed_matrix     = load_csv_matrix(os.path.join(data_dir, 'speed_matrix.csv'))
    _,          fuel_matrix      = load_csv_matrix(os.path.join(data_dir, 'fuel_matrix.csv'))

    weights_data = load_json(os.path.join(data_dir, 'stop_weights.json'))
    betas        = load_json(os.path.join(suite_dir, 'beta_coefficients.json'))

    weights = {int(k): v for k, v in weights_data["by_index"].items()}
    base_vehicle_kg = weights_data["base_vehicle_kg"]
    location_names = dist_names
    n = len(location_names)

    initial_route = list(range(n))
    runs = 1

    initial_distance = sum(distance_matrix[initial_route[i]][initial_route[i + 1]]
                           for i in range(len(initial_route) - 1))

    final_costs = []
    reduction_pcts = []
    best_route = None
    best_cost = float('inf')

    print(f"Running optimizer {runs} times...\n")

    for i in range(1, runs + 1):
        optimizer = RouteOptimizer({"SOLVER_TIME_LIMIT": 10})
        final_route = optimizer.optimize_route(
            fuel_matrix=fuel_matrix,
            distance_matrix=distance_matrix,
            elevation_matrix=elevation_matrix,
            speed_matrix=speed_matrix,
            weights=weights,
            betas=betas,
            base_vehicle_kg=base_vehicle_kg,
            location_names=location_names,
        )

        initial_cost = optimizer._route_cost(initial_route, distance_matrix, elevation_matrix,
                                              speed_matrix, weights, betas, base_vehicle_kg)
        final_cost = optimizer._route_cost(final_route, distance_matrix, elevation_matrix,
                                            speed_matrix, weights, betas, base_vehicle_kg)

        reduction = (initial_cost - final_cost) / initial_cost * 100

        final_costs.append(final_cost)
        reduction_pcts.append(reduction)

        if final_cost < best_cost:
            best_cost = final_cost
            best_route = final_route

        print(f"  Run {i:3d}: cost = {final_cost:.4f}  |  reduction vs initial = {reduction:+.2f}%")

    avg_cost = sum(final_costs) / runs
    avg_reduction = sum(reduction_pcts) / runs
    best_reduction = max(reduction_pcts)

    best_distance = sum(distance_matrix[best_route[i]][best_route[i + 1]]
                        for i in range(len(best_route) - 1))
    distance_saved = initial_distance - best_distance

    print("\n" + "=" * 60)
    print(f"RESULTS OVER {runs} RUNS")
    print("=" * 60)
    print(f"  Avg cost:           {avg_cost:.4f}")
    print(f"  Avg reduction:      {avg_reduction:+.2f}%")
    print(f"  Best cost:          {best_cost:.4f}")
    print(f"  Best reduction:     {best_reduction:+.2f}%")
    print(f"  Distance saved:     {distance_saved:.2f} km  ({initial_distance:.2f} -> {best_distance:.2f})")
    print("=" * 60)

if __name__ == "__main__":
    main()
