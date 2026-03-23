"""
Generate Synthetic Test Route for TSP vs Weight-Aware Comparison

Creates a 10-stop dataset where:
- TSP optimal (distance only) ≠ Weight-aware optimal (fuel with dynamic pickups)

Design: Heavy stops near depot, light stops far from depot
- TSP wants to visit nearby (heavy) stops first
- Weight-aware wants to visit heavy stops LAST

Author: Justin Li
Date: March 2026
"""

import json
import math
import numpy as np
from itertools import permutations
from pathlib import Path

# ============ STOP DEFINITIONS ============

# DESIGN: Two branches from depot at similar distances
# - Branch 1 (A, B): Close, HEAVY pickups
# - Branch 2 (I, J): Close-ish, LIGHT pickups
# - Middle stops (C-H): Form a loop connecting branches
#
# TSP will likely go: Depot → A → B → middle → I → J → Depot (shortest path)
# Weight-aware should: Depot → I → J → middle → B → A → Depot (save heavy for last)

STOPS = {
    'Depot': (0, 0),
    # Branch 1: Heavy stops, close to depot (NE direction)
    'Stop A': (2, 2),      # Close, HEAVY
    'Stop B': (3, 4),      # Close, HEAVY
    # Middle loop
    'Stop C': (5, 6),      
    'Stop D': (7, 5),      
    'Stop E': (9, 4),      
    'Stop F': (10, 2),     
    'Stop G': (9, 0),      
    'Stop H': (7, -1),     
    # Branch 2: Light stops, similar distance to depot (SE direction)
    'Stop I': (4, -2),     # Similar distance, LIGHT
    'Stop J': (2, -1),     # Similar distance, LIGHT
}

# Pickup weights (kg)
# Key: Heavy stops (A, B) are in one direction, light stops (I, J) in another
STOP_WEIGHTS = {
    'Depot': 0,
    'Stop A': 600,    # HEAVY
    'Stop B': 550,    # HEAVY  
    'Stop C': 100,    # Medium
    'Stop D': 90,     # Medium
    'Stop E': 80,     # Medium
    'Stop F': 70,     # Light
    'Stop G': 60,     # Light
    'Stop H': 50,     # Light
    'Stop I': 30,     # Very light
    'Stop J': 20,     # Very light
}

# Keep elevation relatively uniform (small variation)
# Format: elevation gain from each stop (meters), we'll compute matrix later
BASE_ELEVATION = 10  # Base elevation gain per leg
ELEVATION_VARIATION = 5  # ± variation

# Keep speed relatively uniform
BASE_SPEED = 35  # km/h (school bus speed)
SPEED_VARIATION = 5  # ± variation

# Model coefficients (from our trained model)
COEFFICIENTS = {
    'intercept': 0.025024,
    'Total_Distance_km': 0.06962583,
    'Dist_x_Weight': 0.00005552431,
    'Elev_x_Weight': 0.000002550080,
    'Dist_x_Speed2': 0.000001102072,
}

DIESEL_CORRECTION = 0.65
TIRE_CORRECTION = 0.5  # For heavy vehicles
BASE_VEHICLE_WEIGHT = 15000  # kg


# ============ HELPER FUNCTIONS ============

def euclidean_distance(p1, p2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def build_matrices(stops):
    """Build distance, elevation, and speed matrices."""
    labels = list(stops.keys())
    n = len(labels)
    
    distance_matrix = np.zeros((n, n))
    elevation_matrix = np.zeros((n, n))
    speed_matrix = np.zeros((n, n))
    
    np.random.seed(42)  # Reproducible
    
    for i in range(n):
        for j in range(n):
            if i != j:
                # Distance (Euclidean)
                distance_matrix[i, j] = euclidean_distance(stops[labels[i]], stops[labels[j]])
                
                # Elevation (small random variation)
                elevation_matrix[i, j] = BASE_ELEVATION + np.random.uniform(-ELEVATION_VARIATION, ELEVATION_VARIATION)
                
                # Speed (small random variation)
                speed_matrix[i, j] = BASE_SPEED + np.random.uniform(-SPEED_VARIATION, SPEED_VARIATION)
    
    return labels, distance_matrix, elevation_matrix, speed_matrix


def route_distance(route, distance_matrix):
    """Calculate total distance for a route."""
    total = 0
    for k in range(len(route) - 1):
        total += distance_matrix[route[k], route[k + 1]]
    return total


def predict_fuel(distance_km, ascent_m, avg_speed_kmh, weight_kg):
    """Predict fuel consumption for a single leg."""
    c = COEFFICIENTS
    
    fuel_gasoline = (
        c['intercept'] +
        c['Total_Distance_km'] * distance_km +
        c['Dist_x_Weight'] * TIRE_CORRECTION * distance_km * weight_kg +
        c['Elev_x_Weight'] * ascent_m * weight_kg +
        c['Dist_x_Speed2'] * distance_km * avg_speed_kmh ** 2
    )
    
    return max(0, fuel_gasoline * DIESEL_CORRECTION)


def route_fuel_dynamic(route, labels, distance_matrix, elevation_matrix, speed_matrix, stop_weights):
    """Calculate total fuel for a route with dynamic pickup weights."""
    total_fuel = 0
    current_weight = BASE_VEHICLE_WEIGHT
    
    for k in range(len(route) - 1):
        i, j = route[k], route[k + 1]
        
        fuel = predict_fuel(
            distance_matrix[i, j],
            elevation_matrix[i, j],
            speed_matrix[i, j],
            current_weight
        )
        total_fuel += fuel
        
        # Pick up load at destination
        current_weight += stop_weights[labels[j]]
    
    return total_fuel


def brute_force_tsp(labels, distance_matrix):
    """Find optimal TSP route (minimize distance)."""
    n = len(labels)
    depot = 0
    other_stops = list(range(1, n))
    
    best_route = None
    best_distance = float('inf')
    
    for perm in permutations(other_stops):
        route = [depot] + list(perm) + [depot]
        dist = route_distance(route, distance_matrix)
        
        if dist < best_distance:
            best_distance = dist
            best_route = route
    
    return best_route, best_distance


def brute_force_weight_aware(labels, distance_matrix, elevation_matrix, speed_matrix, stop_weights):
    """Find optimal weight-aware route (minimize fuel)."""
    n = len(labels)
    depot = 0
    other_stops = list(range(1, n))
    
    best_route = None
    best_fuel = float('inf')
    
    for perm in permutations(other_stops):
        route = [depot] + list(perm) + [depot]
        fuel = route_fuel_dynamic(route, labels, distance_matrix, elevation_matrix, speed_matrix, stop_weights)
        
        if fuel < best_fuel:
            best_fuel = fuel
            best_route = route
    
    return best_route, best_fuel


def route_to_names(route, labels):
    """Convert route indices to stop names."""
    return [labels[i] for i in route]


# ============ MAIN ============

def main():
    print("="*70)
    print("GENERATING SYNTHETIC TEST DATASET")
    print("="*70)
    
    # Build matrices
    labels, distance_matrix, elevation_matrix, speed_matrix = build_matrices(STOPS)
    
    # Convert stop weights to indexed dict
    stop_weights_indexed = {labels[i]: STOP_WEIGHTS[labels[i]] for i in range(len(labels))}
    
    print(f"\nStops: {len(labels)}")
    print(f"Total permutations to check: {math.factorial(len(labels) - 1):,}")
    
    # Show stop layout
    print("\n--- Stop Layout ---")
    print(f"{'Stop':<10} {'Coords':<15} {'Weight (kg)':<12} {'Dist from Depot':<15}")
    print("-"*52)
    for label in labels:
        coord = STOPS[label]
        weight = STOP_WEIGHTS[label]
        dist = euclidean_distance(coord, STOPS['Depot'])
        print(f"{label:<10} ({coord[0]:>4}, {coord[1]:>4})    {weight:<12} {dist:<15.2f}")
    
    # Brute force TSP
    print("\n--- Solving TSP (distance only) ---")
    tsp_route, tsp_distance = brute_force_tsp(labels, distance_matrix)
    tsp_route_names = route_to_names(tsp_route, labels)
    print(f"Optimal route: {' → '.join(tsp_route_names)}")
    print(f"Total distance: {tsp_distance:.2f} km")
    
    # Calculate fuel for TSP route (for comparison)
    tsp_fuel = route_fuel_dynamic(tsp_route, labels, distance_matrix, elevation_matrix, speed_matrix, stop_weights_indexed)
    print(f"Fuel (at TSP route): {tsp_fuel:.3f} L")
    
    # Brute force weight-aware
    print("\n--- Solving Weight-Aware (minimize fuel) ---")
    wa_route, wa_fuel = brute_force_weight_aware(labels, distance_matrix, elevation_matrix, speed_matrix, stop_weights_indexed)
    wa_route_names = route_to_names(wa_route, labels)
    print(f"Optimal route: {' → '.join(wa_route_names)}")
    wa_distance = route_distance(wa_route, distance_matrix)
    print(f"Total distance: {wa_distance:.2f} km")
    print(f"Fuel: {wa_fuel:.3f} L")
    
    # Comparison
    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70)
    
    routes_differ = tsp_route != wa_route
    print(f"\nRoutes are different: {routes_differ}")
    
    if routes_differ:
        fuel_savings = tsp_fuel - wa_fuel
        fuel_savings_pct = (fuel_savings / tsp_fuel) * 100
        print(f"\nFuel savings from weight-aware optimization:")
        print(f"  TSP route fuel:          {tsp_fuel:.3f} L")
        print(f"  Weight-aware route fuel: {wa_fuel:.3f} L")
        print(f"  Savings:                 {fuel_savings:.3f} L ({fuel_savings_pct:.1f}%)")
        
        distance_penalty = wa_distance - tsp_distance
        print(f"\nDistance tradeoff:")
        print(f"  TSP distance:            {tsp_distance:.2f} km")
        print(f"  Weight-aware distance:   {wa_distance:.2f} km")
        print(f"  Extra distance:          {distance_penalty:.2f} km ({(distance_penalty/tsp_distance)*100:.1f}%)")
    
    # Key insight
    print("\n--- Key Insight ---")
    print("TSP visits heavy stops (A, B) early because they're close to depot.")
    print("Weight-aware visits heavy stops (A, B) late to avoid carrying weight.")
    
    # Save outputs
    OUTPUT_DIR = Path('/mnt/user-data/outputs/test_suite')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save matrices as JSON (matching expected format)
    matrices_data = {
        'labels': labels,
        'distance_km': distance_matrix.tolist(),
        'ascent_m': elevation_matrix.tolist(),
        'speed_kmh': speed_matrix.tolist(),
        'stop_weights': STOP_WEIGHTS,
        'coordinates': STOPS,
    }
    
    with open(OUTPUT_DIR / 'test_matrices.json', 'w') as f:
        json.dump(matrices_data, f, indent=2)
    print(f"\n✓ Saved test_matrices.json")
    
    # Save expected results
    results = {
        'tsp_optimal': {
            'route_indices': tsp_route,
            'route_names': tsp_route_names,
            'total_distance_km': tsp_distance,
            'fuel_liters': tsp_fuel,
        },
        'weight_aware_optimal': {
            'route_indices': wa_route,
            'route_names': wa_route_names,
            'total_distance_km': wa_distance,
            'fuel_liters': wa_fuel,
        },
        'comparison': {
            'routes_differ': routes_differ,
            'fuel_savings_liters': tsp_fuel - wa_fuel if routes_differ else 0,
            'fuel_savings_percent': ((tsp_fuel - wa_fuel) / tsp_fuel * 100) if routes_differ else 0,
        }
    }
    
    with open(OUTPUT_DIR / 'expected_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ Saved expected_results.json")
    
    print(f"\nFiles saved to: {OUTPUT_DIR}")
    
    return tsp_route, wa_route


if __name__ == "__main__":
    main()
