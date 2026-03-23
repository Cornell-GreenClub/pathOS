"""
Run TSP + Simulated Annealing on real matrices from CSV/JSON files.
No OSRM server needed.

Loads:
  - distance_matrix.csv
  - elevation_matrix.csv
  - speed_matrix.csv
  - fuel_matrix.csv
  - stop_weights.json
  - beta_coefficients.json
"""
import sys
import os
import csv
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

# Add parent directory so we can import route_optimizer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from route_optimizer import RouteOptimizer


def load_csv_matrix(filepath):
    """Load a CSV matrix with row/column headers. Returns (names, 2D float list)."""
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        col_names = header[1:]  # skip empty first cell

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
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'testing', 'test_matrices')

    # Load all matrices
    print("Loading matrices...")
    dist_names, distance_matrix   = load_csv_matrix(os.path.join(data_dir, 'distance_matrix.csv'))
    _,          elevation_matrix  = load_csv_matrix(os.path.join(data_dir, 'elevation_matrix.csv'))
    _,          speed_matrix      = load_csv_matrix(os.path.join(data_dir, 'speed_matrix.csv'))
    _,          fuel_matrix       = load_csv_matrix(os.path.join(data_dir, 'fuel_matrix.csv'))

    # Load JSON configs
    weights_data = load_json(os.path.join(data_dir, 'stop_weights.json'))
    betas        = load_json(os.path.join(data_dir, 'beta_coefficients.json'))

    # Build weights dict: {int_index: pickup_kg}
    weights = {int(k): v for k, v in weights_data["by_index"].items()}
    base_vehicle_kg = weights_data["base_vehicle_kg"]
    location_names = dist_names

    n = len(location_names)
    print(f"Loaded {n} stops: {', '.join(location_names)}")
    print(f"Base vehicle weight: {base_vehicle_kg} kg")
    print(f"Total pickup weight: {weights_data['total_pickup_kg']} kg")
    print(f"Betas: {betas}")
    print()

    # Validate dimensions
    for name, mat in [("distance", distance_matrix), ("elevation", elevation_matrix),
                      ("speed", speed_matrix), ("fuel", fuel_matrix)]:
        assert len(mat) == n and len(mat[0]) == n, f"{name} matrix shape mismatch: expected {n}x{n}"

    # Run optimizer
    optimizer = RouteOptimizer({"SOLVER_TIME_LIMIT": 10})
    result = optimizer.optimize_route(
        fuel_matrix=fuel_matrix,
        distance_matrix=distance_matrix,
        elevation_matrix=elevation_matrix,
        speed_matrix=speed_matrix,
        weights=weights,
        betas=betas,
        base_vehicle_kg=base_vehicle_kg,
        location_names=location_names,
    )

    print(f"\nFinal route indices: {result}")
    print(f"Final route: {[location_names[i] for i in result]}")


if __name__ == "__main__":
    main()