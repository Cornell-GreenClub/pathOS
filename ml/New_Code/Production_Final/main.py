"""
Fuel Matrix Builder (v4 - Vehicle Class Coefficients)

Creates an NxN fuel consumption matrix for a list of locations.
Uses pre-computed vehicle-class-specific coefficients.

Usage:
    from fuel_matrix_builder_v4 import FuelMatrixBuilder
    
    builder = FuelMatrixBuilder(
        api_keys=["key1", "key2"],
        vehicle_class='semi_truck_with_trailer',
    )
    matrix = builder.build_matrix(locations)
"""

import os
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import time
from typing import List, Optional, Union, Tuple, Dict, Any
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import openrouteservice


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
# CONSTANTS
# ============================================================

MAX_CONCURRENT = 2
REQUEST_DELAY = 1.5
MAX_RETRIES = 5
ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"


# ============================================================
# MAIN CLASS
# ============================================================

class FuelMatrixBuilder:
    
    def __init__(
        self,
        api_keys: Union[str, List[str]],
        vehicle_class: str = 'passenger_car',
        vehicle_weight_kg: Optional[float] = None,
        include_return: bool = False,
        max_concurrent: int = MAX_CONCURRENT
    ):
        self.api_keys = [api_keys] if isinstance(api_keys, str) else api_keys
        self._key_index = 0
        self._key_lock = threading.Lock()
        
        if vehicle_class not in VEHICLE_CLASSES:
            raise ValueError(f"Unknown vehicle_class: {vehicle_class}. Options: {list(VEHICLE_CLASSES.keys())}")
        
        vc = VEHICLE_CLASSES[vehicle_class]
        self.vehicle_class = vehicle_class
        self.vehicle_name = vc['name']
        self.coefficients = vc['coefficients']
        self.vehicle_weight_kg = vehicle_weight_kg or vc['default_weight_kg']
        
        self.include_return = include_return
        self.max_concurrent = max_concurrent
        self.client = openrouteservice.Client(key=self.api_keys[0])
        
        self._coord_cache = {}
        self.labels = []
        
        print(f"FuelMatrixBuilder: {self.vehicle_name}, {self.vehicle_weight_kg:,} kg")
    
    def _get_next_key(self) -> str:
        with self._key_lock:
            key = self.api_keys[self._key_index]
            self._key_index = (self._key_index + 1) % len(self.api_keys)
            return key
    
    def geocode(self, address: str) -> List[float]:
        if address in self._coord_cache:
            return self._coord_cache[address]
        result = self.client.pelias_search(text=address, size=1)
        if result and result.get('features'):
            coords = result['features'][0]['geometry']['coordinates']
            self._coord_cache[address] = coords
            return coords
        raise ValueError(f"Could not geocode: {address}")
    
    def geocode_all(self, locations: List[str]) -> List[List[float]]:
        coords = []
        for loc in locations:
            coords.append(self.geocode(loc))
            time.sleep(0.5)
        return coords
    
    async def _fetch_route(self, session, origin, destination, semaphore) -> Dict:
        async with semaphore:
            headers = {'Authorization': self._get_next_key(), 'Content-Type': 'application/json'}
            payload = {'coordinates': [origin, destination], 'elevation': True}
            
            for attempt in range(MAX_RETRIES):
                try:
                    async with session.post(ORS_URL, headers=headers, json=payload) as resp:
                        if resp.status == 429:
                            await asyncio.sleep((attempt + 1) * 5)
                            headers['Authorization'] = self._get_next_key()
                            continue
                        resp.raise_for_status()
                        data = await resp.json()
                        props = data['features'][0]['properties']
                        summary = props['summary']
                        dist_km = summary['distance'] / 1000
                        dur_hr = summary['duration'] / 3600
                        await asyncio.sleep(REQUEST_DELAY)
                        return {
                            'distance_km': dist_km,
                            'elevation_gain_m': props.get('ascent', 0),
                            'avg_speed_kmh': dist_km / dur_hr if dur_hr > 0 else 50.0,
                            'success': True
                        }
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        return {'success': False, 'error': str(e)}
                    await asyncio.sleep(2)
            return {'success': False}
    
    async def _fetch_all_routes(self, coords: List[List[float]]) -> Dict[Tuple[int, int], Dict]:
        n = len(coords)
        pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = {}
        
        async with aiohttp.ClientSession() as session:
            async def fetch_one(i, j):
                result = await self._fetch_route(session, coords[i], coords[j], semaphore)
                return (i, j), result
            
            responses = await asyncio.gather(*[fetch_one(i, j) for i, j in pairs])
            for (i, j), result in responses:
                results[(i, j)] = result
        
        return results
    
    def predict_fuel(self, distance_km: float, elevation_gain_m: float, 
                     avg_speed_kmh: float, weight_kg: Optional[float] = None) -> float:
        w = weight_kg or self.vehicle_weight_kg
        c = self.coefficients
        fuel = (
            c['intercept'] +
            c['Total_Distance_km'] * distance_km +
            c['Dist_x_Weight'] * distance_km * w +
            c['Elev_x_Weight'] * elevation_gain_m * w +
            c['Dist_x_Speed2'] * distance_km * avg_speed_kmh ** 2
        )
        return max(0, fuel)
    
    def build_matrix(self, locations: Union[List[str], List[List[float]]], 
                     output_path: Optional[str] = None) -> List[List[float]]:
        if isinstance(locations[0], str):
            print(f"Geocoding {len(locations)} locations...")
            coords = self.geocode_all(locations)
            self.labels = [loc.split(',')[0] for loc in locations]
        else:
            coords = locations
            self.labels = [f"Stop {i}" for i in range(len(locations))]
        
        n = len(coords)
        print(f"Fetching {n*(n-1)} routes...")
        
        route_results = asyncio.run(self._fetch_all_routes(coords))
        
        fuel_matrix = np.zeros((n, n))
        self.distance_matrix = np.zeros((n, n))
        self.elevation_matrix = np.zeros((n, n))
        self.speed_matrix = np.zeros((n, n))
        
        for (i, j), route in route_results.items():
            if route.get('success'):
                fuel_matrix[i, j] = self.predict_fuel(
                    route['distance_km'], route['elevation_gain_m'], route['avg_speed_kmh']
                )
                self.distance_matrix[i, j] = route['distance_km']
                self.elevation_matrix[i, j] = route['elevation_gain_m']
                self.speed_matrix[i, j] = route['avg_speed_kmh']
            else:
                fuel_matrix[i, j] = np.nan
        
        if self.include_return:
            return_col = fuel_matrix[:, 0].reshape(-1, 1)
            fuel_matrix = np.hstack([fuel_matrix, return_col])
            fuel_matrix = np.vstack([fuel_matrix, np.zeros((1, fuel_matrix.shape[1]))])
            self.labels.append(f"Return to {self.labels[0]}")
        
        success_rate = sum(1 for r in route_results.values() if r.get('success')) / len(route_results)
        print(f"Done. {success_rate*100:.0f}% success.")
        
        self.fuel_matrix = fuel_matrix.tolist()
        self.distance_matrix = self.distance_matrix.tolist()
        self.elevation_matrix = self.elevation_matrix.tolist()
        self.speed_matrix = self.speed_matrix.tolist()
        
        if output_path:
            self.save_matrices(output_path)
        
        return self.fuel_matrix
    
    def save_matrices(self, output_path: str):
        """
        Save all matrices to CSV files.
        
        Creates:
            {output_path}/fuel_matrix.csv
            {output_path}/distance_matrix.csv
            {output_path}/elevation_matrix.csv
            {output_path}/speed_matrix.csv
            {output_path}/labels.csv
        """
        import os
        os.makedirs(output_path, exist_ok=True)
        
        pd.DataFrame(self.fuel_matrix, index=self.labels, columns=self.labels).to_csv(
            f"{output_path}/fuel_matrix.csv")
        pd.DataFrame(self.distance_matrix, index=self.labels, columns=self.labels).to_csv(
            f"{output_path}/distance_matrix.csv")
        pd.DataFrame(self.elevation_matrix, index=self.labels, columns=self.labels).to_csv(
            f"{output_path}/elevation_matrix.csv")
        pd.DataFrame(self.speed_matrix, index=self.labels, columns=self.labels).to_csv(
            f"{output_path}/speed_matrix.csv")
        pd.DataFrame({'label': self.labels}).to_csv(
            f"{output_path}/labels.csv", index=False)
        
        print(f"Saved matrices to {output_path}/")
    
    def get_labels(self) -> List[str]:
        return self.labels
    
    def get_fuel_matrix(self) -> List[List[float]]:
        """Fuel consumption matrix in liters."""
        return self.fuel_matrix
    
    def get_distance_matrix(self) -> List[List[float]]:
        """Distance matrix in km."""
        return self.distance_matrix
    
    def get_elevation_matrix(self) -> List[List[float]]:
        """Elevation gain (ascent) matrix in meters."""
        return self.elevation_matrix
    
    def get_speed_matrix(self) -> List[List[float]]:
        """Average speed matrix in km/h."""
        return self.speed_matrix
    
    def calculate_route_fuel(
        self, 
        route: List[int], 
        stop_weights: Optional[Dict[int, float]] = None
    ) -> Tuple[float, List[Dict]]:
        """
        Calculate total fuel for a route with dynamic weight accumulation.
        
        As the vehicle visits each stop, it picks up weight (e.g., recycling),
        making subsequent legs more fuel-intensive.
        
        Args:
            route: List of stop indices in order (e.g., [0, 3, 5, 2, 0])
            stop_weights: Dict mapping stop index to pickup weight (kg).
                          If None, uses fixed vehicle_weight_kg for all legs.
        
        Returns:
            Tuple of (total_fuel_liters, leg_details)
            leg_details is a list of dicts with per-leg breakdown
        """
        if not hasattr(self, 'distance_matrix') or self.distance_matrix is None:
            raise ValueError("Must call build_matrix() first")
        
        total_fuel = 0
        current_weight = self.vehicle_weight_kg
        leg_details = []
        
        for i in range(len(route) - 1):
            origin = route[i]
            dest = route[i + 1]
            
            dist = self.distance_matrix[origin][dest]
            elev = self.elevation_matrix[origin][dest]
            speed = self.speed_matrix[origin][dest]
            
            # Predict fuel for this leg with current weight
            fuel = self.predict_fuel(dist, elev, speed, weight_kg=current_weight)
            total_fuel += fuel
            
            leg_details.append({
                'from': origin,
                'to': dest,
                'distance_km': dist,
                'elevation_m': elev,
                'weight_kg': current_weight,
                'fuel_L': fuel,
            })
            
            # Add pickup weight at destination (if provided)
            if stop_weights:
                pickup = stop_weights.get(dest, 0)
                current_weight += pickup
        
        return total_fuel, leg_details


# ============================================================
# HELPER
# ============================================================

def get_api_keys() -> List[str]:
    keys = []
    i = 1
    while True:
        key = os.getenv(f"ORS_API_KEY_{i}")
        if key:
            keys.append(key)
            i += 1
        else:
            break
    single = os.getenv("ORS_API_KEY") or os.getenv("OPENROUTESERVICE_API_KEY")
    if single and single not in keys:
        keys.insert(0, single)
    if not keys:
        raise RuntimeError("No API keys found")
    return keys


if __name__ == "__main__":
    API_KEYS = get_api_keys()
    
    locations = [
        "TST BOCES Tompkins, 555 Warren Rd, Ithaca, NY 14850",      # 0: Depot
        "DeWitt Middle School, 560 Warren Rd, Ithaca, NY 14850",     # 1
        "Northeast Elementary School, 425 Winthrop Dr, Ithaca, NY 14850",  # 2
        "Cayuga Heights Elementary School, 110 E Upland Rd, Ithaca, NY 14850",  # 3
    ]
    
    # === STOP PICKUP WEIGHTS (kg) ===
    # Weight picked up at each stop (e.g., recycling)
    STOP_WEIGHTS = {
        0: 0,        # Depot - no pickup
        1: 514.31,   # DeWitt Middle School
        2: 326.53,   # Northeast Elementary
        3: 251.81,   # Cayuga Heights Elementary
    }
    
    # === SPECIFY OUTPUT PATH HERE ===
    OUTPUT_PATH = None  # e.g., "/path/to/output/folder"
    
    builder = FuelMatrixBuilder(
        api_keys=API_KEYS,
        vehicle_class='school_bus_type_c',
        # vehicle_weight_kg=15000,  # Uses default if not specified
    )
    
    fuel_matrix = builder.build_matrix(locations, output_path=OUTPUT_PATH)
    labels = builder.get_labels()
    
    print("\nFuel Matrix (L):")
    print(pd.DataFrame(fuel_matrix, index=labels, columns=labels).round(3))
    
    # === DYNAMIC WEIGHT EXAMPLE ===
    # Route: Depot -> Stop 1 -> Stop 2 -> Stop 3 -> Depot
    route = [0, 1, 2, 3, 0]
    
    # Without dynamic weights (fixed weight)
    fuel_fixed, _ = builder.calculate_route_fuel(route)
    
    # With dynamic weights (accumulating)
    fuel_dynamic, legs = builder.calculate_route_fuel(route, stop_weights=STOP_WEIGHTS)
    
    print(f"\n--- Route: {' -> '.join(str(s) for s in route)} ---")
    print(f"Fixed weight:   {fuel_fixed:.2f} L")
    print(f"Dynamic weight: {fuel_dynamic:.2f} L (+{(fuel_dynamic/fuel_fixed - 1)*100:.1f}%)")
    
    print("\nLeg breakdown:")
    for leg in legs:
        print(f"  {leg['from']} -> {leg['to']}: {leg['distance_km']:.1f} km, "
              f"{leg['weight_kg']:,.0f} kg, {leg['fuel_L']:.2f} L")
        