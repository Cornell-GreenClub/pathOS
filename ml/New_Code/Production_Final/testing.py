"""
Route Fuel Calculator

Calculates total fuel consumption for a route with dynamic weight accumulation.
Uses pre-built matrices (distance, elevation, speed) and vehicle class coefficients.

Usage:
    python route_fuel_calculator.py
    
    Or import:
    from route_fuel_calculator import calculate_route_fuel, predict_fuel
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple


# ============================================================
# VEHICLE CLASS COEFFICIENTS
# ============================================================

VEHICLE_CLASSES = {
    'passenger_car': {
        'name': 'Passenger Car',
        'default_weight_kg': 1800,
        'coefficients': {
            'intercept':         2.5024e-02,
            'Total_Distance_km': 6.9626e-02,
            'Dist_x_Weight':     5.5524e-05,
            'Elev_x_Weight':     2.5501e-06,
            'Dist_x_Speed2':     1.1021e-06,
        },
    },
    'suv_crossover': {
        'name': 'SUV / Crossover',
        'default_weight_kg': 2100,
        'coefficients': {
            'intercept':         2.5024e-02,
            'Total_Distance_km': 6.9626e-02,
            'Dist_x_Weight':     6.1077e-05,
            'Elev_x_Weight':     2.5501e-06,
            'Dist_x_Speed2':     1.6355e-06,
        },
    },
    'pickup_truck': {
        'name': 'Pickup Truck',
        'default_weight_kg': 2800,
        'coefficients': {
            'intercept':         2.5024e-02,
            'Total_Distance_km': 6.9626e-02,
            'Dist_x_Weight':     5.5524e-05,
            'Elev_x_Weight':     2.5501e-06,
            'Dist_x_Speed2':     2.3077e-06,
        },
    },
    'delivery_van': {
        'name': 'Delivery Van',
        'default_weight_kg': 3500,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     2.8873e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     2.2723e-06,
        },
    },
    'box_truck': {
        'name': 'Box Truck',
        'default_weight_kg': 7000,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     2.5264e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     3.6935e-06,
        },
    },
    'school_bus_type_a': {
        'name': 'School Bus Type A',
        'default_weight_kg': 4500,
        'coefficients': {
            'intercept':         2.5024e-02,
            'Total_Distance_km': 6.9626e-02,
            'Dist_x_Weight':     4.4419e-05,
            'Elev_x_Weight':     2.5501e-06,
            'Dist_x_Speed2':     3.4440e-06,
        },
    },
    'school_bus_type_c': {
        'name': 'School Bus Type C',
        'default_weight_kg': 15000,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     2.1654e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     5.0925e-06,
        },
    },
    'school_bus_type_d': {
        'name': 'School Bus Type D',
        'default_weight_kg': 18000,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     2.1654e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     5.8762e-06,
        },
    },
    'transit_bus_40ft': {
        'name': 'Transit Bus (40ft)',
        'default_weight_kg': 18000,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     2.1654e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     5.8203e-06,
        },
    },
    'semi_truck_with_trailer': {
        'name': 'Semi Truck (w/ trailer)',
        'default_weight_kg': 36000,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     1.9850e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     7.8354e-06,
        },
    },
    'dump_truck': {
        'name': 'Dump Truck',
        'default_weight_kg': 28000,
        'coefficients': {
            'intercept':         1.6266e-02,
            'Total_Distance_km': 4.5257e-02,
            'Dist_x_Weight':     2.5264e-05,
            'Elev_x_Weight':     1.6576e-06,
            'Dist_x_Speed2':     7.1413e-06,
        },
    },
}


# ============================================================
# FUEL PREDICTION
# ============================================================

def predict_fuel(
    distance_km: float,
    elevation_m: float,
    speed_kmh: float,
    weight_kg: float,
    vehicle_class: str = 'school_bus_type_c'
) -> float:
    """
    Predict fuel consumption for a single leg.
    
    Args:
        distance_km: Distance in kilometers
        elevation_m: Elevation gain (ascent) in meters
        speed_kmh: Average speed in km/h
        weight_kg: Current vehicle weight in kg
        vehicle_class: Vehicle class key
    
    Returns:
        Fuel consumption in liters
    """
    c = VEHICLE_CLASSES[vehicle_class]['coefficients']
    
    fuel = (
        c['intercept'] +
        c['Total_Distance_km'] * distance_km +
        c['Dist_x_Weight'] * distance_km * weight_kg +
        c['Elev_x_Weight'] * elevation_m * weight_kg +
        c['Dist_x_Speed2'] * distance_km * speed_kmh ** 2
    )
    
    return max(0, fuel)


# ============================================================
# ROUTE FUEL CALCULATION
# ============================================================

def calculate_route_fuel(
    route: List[int],
    stop_weights: Dict[int, float],
    distance_matrix: List[List[float]],
    elevation_matrix: List[List[float]],
    speed_matrix: List[List[float]],
    base_weight_kg: float,
    vehicle_class: str = 'school_bus_type_c'
) -> Tuple[float, List[Dict]]:
    """
    Calculate total fuel for a route with dynamic weight accumulation.
    
    Args:
        route: List of stop indices in order (e.g., [0, 1, 2, 3, 0])
        stop_weights: Dict mapping stop index to pickup weight (kg)
        distance_matrix: NxN distance matrix (km)
        elevation_matrix: NxN elevation gain matrix (m)
        speed_matrix: NxN average speed matrix (km/h)
        base_weight_kg: Starting vehicle weight (empty)
        vehicle_class: Vehicle class key
    
    Returns:
        Tuple of (total_fuel_liters, leg_details)
    """
    total_fuel = 0.0
    current_weight = base_weight_kg
    leg_details = []
    
    for i in range(len(route) - 1):
        origin = route[i]
        dest = route[i + 1]
        
        dist = distance_matrix[origin][dest]
        elev = elevation_matrix[origin][dest]
        speed = speed_matrix[origin][dest]
        
        # Predict fuel for this leg
        fuel = predict_fuel(dist, elev, speed, current_weight, vehicle_class)
        total_fuel += fuel
        
        leg_details.append({
            'leg': i + 1,
            'from': origin,
            'to': dest,
            'distance_km': dist,
            'elevation_m': elev,
            'speed_kmh': speed,
            'weight_kg': current_weight,
            'fuel_L': fuel,
        })
        
        # Add pickup weight at destination
        pickup = stop_weights.get(dest, 0)
        current_weight += pickup
    
    return total_fuel, leg_details


def print_route_summary(
    route: List[int],
    total_fuel: float,
    leg_details: List[Dict],
    labels: Optional[List[str]] = None
):
    """Print a formatted summary of the route."""
    
    print("\n" + "=" * 70)
    print("ROUTE FUEL CALCULATION")
    print("=" * 70)
    
    # Route string
    if labels:
        route_str = " -> ".join(labels[i] for i in route)
    else:
        route_str = " -> ".join(str(i) for i in route)
    print(f"\nRoute: {route_str}")
    
    # Leg details
    print(f"\n{'Leg':<5} {'From->To':<12} {'Dist(km)':<10} {'Elev(m)':<10} {'Weight(kg)':<12} {'Fuel(L)':<10}")
    print("-" * 70)
    
    for leg in leg_details:
        from_to = f"{leg['from']}->{leg['to']}"
        print(f"{leg['leg']:<5} {from_to:<12} {leg['distance_km']:<10.2f} {leg['elevation_m']:<10.1f} {leg['weight_kg']:<12,.0f} {leg['fuel_L']:<10.3f}")
    
    print("-" * 70)
    
    # Totals
    total_dist = sum(leg['distance_km'] for leg in leg_details)
    total_elev = sum(leg['elevation_m'] for leg in leg_details)
    
    print(f"{'TOTAL':<5} {'':<12} {total_dist:<10.2f} {total_elev:<10.1f} {'':<12} {total_fuel:<10.3f}")
    
    # Conversions
    gallons = total_fuel / 3.78541
    miles = total_dist * 0.621371
    mpg = miles / gallons if gallons > 0 else 0
    
    print(f"\nTotal: {total_fuel:.2f} L ({gallons:.2f} gal)")
    print(f"Distance: {total_dist:.2f} km ({miles:.2f} mi)")
    print(f"Implied MPG: {mpg:.1f}")


# ============================================================
# EXAMPLE / TEST
# ============================================================

if __name__ == "__main__":
    
    # === CONFIGURATION ===
    VEHICLE_CLASS = 'school_bus_type_c'
    BASE_WEIGHT_KG = 9000  # Empty vehicle weight
    
    # === STOP LABELS ===
    LABELS = [
        "TST BOCES Depot",           # 0
        "DeWitt Middle",             # 1
        "Northeast Elementary",      # 2
        "Cayuga Heights Elementary", # 3
        "Belle Sherman Elementary",  # 4
    ]
    
    # === STOP PICKUP WEIGHTS (kg) ===
    STOP_WEIGHTS = {
        0: 0,        # Depot - no pickup
        1: 514.31,   # DeWitt Middle
        2: 326.53,   # Northeast Elementary
        3: 251.81,   # Cayuga Heights Elementary
        4: 240.97,   # Belle Sherman Elementary
    }
    
    # === EXAMPLE MATRICES (replace with actual data) ===
    # These are placeholder values - use actual matrices from FuelMatrixBuilder
    
    DISTANCE_MATRIX = [
        [0.0,  0.5,  3.2,  4.1,  5.3],
        [0.5,  0.0,  2.8,  3.7,  4.9],
        [3.2,  2.8,  0.0,  1.5,  2.7],
        [4.1,  3.7,  1.5,  0.0,  1.8],
        [5.3,  4.9,  2.7,  1.8,  0.0],
    ]
    
    ELEVATION_MATRIX = [
        [0.0,  10,   45,   60,   80],
        [5.0,  0.0,  35,   50,   70],
        [40,   30,   0.0,  20,   40],
        [55,   45,   15,   0.0,  25],
        [75,   65,   35,   20,   0.0],
    ]
    
    SPEED_MATRIX = [
        [0.0,  25,   35,   40,   45],
        [25,   0.0,  35,   40,   45],
        [35,   35,   0.0,  30,   35],
        [40,   40,   30,   0.0,  30],
        [45,   45,   35,   30,   0.0],
    ]
    
    # === ROUTE ORDER ===
    # Depot -> Stop 1 -> Stop 2 -> Stop 3 -> Stop 4 -> Depot
    ROUTE = [0, 1, 2, 3, 4, 0]
    
    # === CALCULATE ===
    print(f"Vehicle: {VEHICLE_CLASSES[VEHICLE_CLASS]['name']}")
    print(f"Base weight: {BASE_WEIGHT_KG:,} kg")
    
    total_fuel, legs = calculate_route_fuel(
        route=ROUTE,
        stop_weights=STOP_WEIGHTS,
        distance_matrix=DISTANCE_MATRIX,
        elevation_matrix=ELEVATION_MATRIX,
        speed_matrix=SPEED_MATRIX,
        base_weight_kg=BASE_WEIGHT_KG,
        vehicle_class=VEHICLE_CLASS,
    )
    
    print_route_summary(ROUTE, total_fuel, legs, LABELS)
    
    # === COMPARE DIFFERENT ROUTE ORDERS ===
    print("\n" + "=" * 70)
    print("COMPARING ROUTE ORDERS")
    print("=" * 70)
    
    routes_to_test = [
        [0, 1, 2, 3, 4, 0],  # Original
    ]
    
    print(f"\n{'Route':<25} {'Fuel (L)':<12} {'Fuel (gal)':<12}")
    print("-" * 50)
    
    for route in routes_to_test:
        fuel, _ = calculate_route_fuel(
            route=route,
            stop_weights=STOP_WEIGHTS,
            distance_matrix=DISTANCE_MATRIX,
            elevation_matrix=ELEVATION_MATRIX,
            speed_matrix=SPEED_MATRIX,
            base_weight_kg=BASE_WEIGHT_KG,
            vehicle_class=VEHICLE_CLASS,
        )
        route_str = "->".join(str(i) for i in route)
        gallons = fuel / 3.78541
        print(f"{route_str:<25} {fuel:<12.3f} {gallons:<12.3f}")