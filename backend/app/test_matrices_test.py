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
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'testing', 'testing_suite')

    dist_names, distance_matrix  = load_csv_matrix(os.path.join(data_dir, 'distance_matrix.csv'))
    _,          elevation_matrix = load_csv_matrix(os.path.join(data_dir, 'elevation_matrix.csv'))
    _,          speed_matrix     = load_csv_matrix(os.path.join(data_dir, 'speed_matrix.csv'))
    _,          fuel_matrix      = load_csv_matrix(os.path.join(data_dir, 'fuel_matrix.csv'))

    weights_data = load_json(os.path.join(data_dir, 'stop_weights.json'))
    betas        = load_json(os.path.join(data_dir, 'beta_coefficients.json'))

    weights = {int(k): v for k, v in weights_data["by_index"].items()}
    base_vehicle_kg = weights_data["base_vehicle_kg"]
    location_names = dist_names
    n = len(location_names)

    initial_route = list(range(n)) + [0]
    runs = 1000

    sa_vs_tsp_pcts = []
    sa_vs_init_pcts = []

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

        tsp_route = optimizer.last_tsp_route

        initial_cost = optimizer._route_cost(initial_route, distance_matrix, elevation_matrix,
                                              speed_matrix, weights, betas, base_vehicle_kg)
        tsp_cost = optimizer._route_cost(tsp_route, distance_matrix, elevation_matrix,
                                          speed_matrix, weights, betas, base_vehicle_kg)
        final_cost = optimizer._route_cost(final_route, distance_matrix, elevation_matrix,
                                            speed_matrix, weights, betas, base_vehicle_kg)

        sa_vs_tsp = (tsp_cost - final_cost) / tsp_cost * 100
        sa_vs_init = (initial_cost - final_cost) / initial_cost * 100

        sa_vs_tsp_pcts.append(sa_vs_tsp)
        sa_vs_init_pcts.append(sa_vs_init)

        print(f"  Run {i:3d}: SA vs TSP = {sa_vs_tsp:+.2f}%  |  SA vs Initial = {sa_vs_init:+.2f}%")

    avg_vs_tsp = sum(sa_vs_tsp_pcts) / runs
    avg_vs_init = sum(sa_vs_init_pcts) / runs
    best_vs_tsp = max(sa_vs_tsp_pcts)
    worst_vs_tsp = min(sa_vs_tsp_pcts)

    expected = load_json(os.path.join(data_dir, 'expected_results.json'))
    exp_init_cost = expected["initial_route"]["cost"]
    exp_tsp_cost = expected["tsp_route"]["cost"]
    exp_wa_cost = expected["weight_aware_route"]["cost"]
    best_possible_vs_tsp = (exp_tsp_cost - exp_wa_cost) / exp_tsp_cost * 100
    best_possible_vs_init = (exp_init_cost - exp_wa_cost) / exp_init_cost * 100

    print("\n" + "=" * 60)
    print(f"RESULTS OVER {runs} RUNS")
    print("=" * 60)
    print(f"  Avg SA vs TSP:     {avg_vs_tsp:+.2f}%")
    print(f"  Avg SA vs Initial: {avg_vs_init:+.2f}%")
    print(f"  Best SA vs TSP:    {best_vs_tsp:+.2f}%")
    print(f"  Worst SA vs TSP:   {worst_vs_tsp:+.2f}%")
    print(f"")
    print(f"  Best possible SA vs TSP:     {best_possible_vs_tsp:+.2f}%")
    print(f"  Best possible SA vs Initial: {best_possible_vs_init:+.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    main()