"""
Fuel Matrix Builder (v4 - Vehicle Class Coefficients)

Creates four NxN matrices for route optimization:
- Fuel matrix (liters)
- Distance matrix (km)
- Elevation matrix (meters ascent)
- Speed matrix (km/h)

Usage:
    from fuel_matrix_builder import FuelMatrixBuilder
    
    builder = FuelMatrixBuilder(
        api_keys=["key1", "key2"],
        vehicle_class='school_bus_type_c',
    )
    builder.build_matrix(locations, output_path='./matrices/')
    
    fuel = builder.get_fuel_matrix()
    dist = builder.get_distance_matrix()
    elev = builder.get_elevation_matrix()
    speed = builder.get_speed_matrix()
"""

import os
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import time
from typing import List, Optional, Union, Tuple, Dict
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

MAX_CONCURRENT = 5
REQUEST_DELAY = 1.5
MAX_RETRIES = 5
ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"


# ============================================================
# MAIN CLASS
# ============================================================

class FuelMatrixBuilder:
    """
    Builds NxN matrices (fuel, distance, elevation, speed) for a set of locations.

    Uses OpenRouteService API to fetch route data between all location pairs,
    then applies physics-based fuel model to predict consumption.
    """

    def __init__(
        self,
        api_keys: Union[str, List[str]],
        vehicle_class: str = 'passenger_car',
        vehicle_weight_kg: Optional[float] = None,
        max_concurrent: int = MAX_CONCURRENT
    ):
        # Support single key or list of keys for rate-limit rotation
        self.api_keys = [api_keys] if isinstance(api_keys, str) else api_keys
        self._key_index = 0
        self._key_lock = threading.Lock()  # Thread-safe key rotation

        if vehicle_class not in VEHICLE_CLASSES:
            raise ValueError(f"Unknown vehicle_class: {vehicle_class}. Options: {list(VEHICLE_CLASSES.keys())}")

        # Load vehicle-specific parameters
        vc = VEHICLE_CLASSES[vehicle_class]
        self.vehicle_class = vehicle_class
        self.vehicle_name = vc['name']
        self.coefficients = vc['coefficients']
        self.vehicle_weight_kg = vehicle_weight_kg or vc['default_weight_kg']

        self.max_concurrent = max_concurrent
        self.client = openrouteservice.Client(key=self.api_keys[0])

        self._coord_cache = {}  # Cache geocoded addresses to avoid duplicate API calls
        self.labels = []  # Human-readable labels for each location

        print(f"FuelMatrixBuilder: {self.vehicle_name}, {self.vehicle_weight_kg:,} kg")
    
    def _get_next_key(self) -> str:
        """Round-robin API key selection to distribute rate limits across keys."""
        with self._key_lock:
            key = self.api_keys[self._key_index]
            self._key_index = (self._key_index + 1) % len(self.api_keys)
            return key

    def geocode(self, address: str) -> List[float]:
        """Convert address string to [lon, lat] coordinates using Pelias search."""
        if address in self._coord_cache:
            return self._coord_cache[address]
        result = self.client.pelias_search(text=address, size=1)
        if result and result.get('features'):
            coords = result['features'][0]['geometry']['coordinates']
            self._coord_cache[address] = coords
            return coords
        raise ValueError(f"Could not geocode: {address}")

    def geocode_all(self, locations: List[str]) -> List[List[float]]:
        """Geocode a list of addresses with rate limiting (0.5s between calls)."""
        coords = []
        for loc in locations:
            coords.append(self.geocode(loc))
            time.sleep(0.5)
        return coords
    
    async def _fetch_route(self, session, origin, destination, semaphore) -> Dict:
        """
        Fetch route data for a single origin-destination pair.

        Handles rate limiting (429 errors) with exponential backoff and key rotation.
        Returns distance, elevation gain, and average speed for the route.
        """
        async with semaphore:
            headers = {'Authorization': self._get_next_key(), 'Content-Type': 'application/json'}
            payload = {'coordinates': [origin, destination], 'elevation': True}

            for attempt in range(MAX_RETRIES):
                try:
                    async with session.post(ORS_URL, headers=headers, json=payload) as resp:
                        # Handle rate limiting with backoff and key rotation
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
                            'avg_speed_kmh': dist_km / dur_hr if dur_hr > 0 else 50.0,  # Fallback to 50 km/h
                            'success': True
                        }
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        return {'success': False, 'error': str(e)}
                    await asyncio.sleep(2)
            return {'success': False}

    async def _fetch_all_routes(self, coords: List[List[float]]) -> Dict[Tuple[int, int], Dict]:
        """
        Fetch route data for all origin-destination pairs concurrently.

        Uses semaphore to limit concurrent requests and avoid overwhelming the API.
        """
        n = len(coords)
        # Generate all i->j pairs (excluding i==j since distance to self is 0)
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
        """
        Predict fuel consumption (liters) using physics-informed linear model.

        Model: fuel = β₀ + β₁·dist + β₂·(dist×weight) + β₃·(elev×weight) + β₄·(dist×speed²)

        Captures: base consumption, rolling resistance (weight), gravitational work (elevation),
        and aerodynamic drag (speed squared).
        """
        w = weight_kg or self.vehicle_weight_kg
        c = self.coefficients
        fuel = (
            c['intercept'] +
            c['Total_Distance_km'] * distance_km +
            c['Dist_x_Weight'] * distance_km * w +
            c['Elev_x_Weight'] * elevation_gain_m * w +
            c['Dist_x_Speed2'] * distance_km * avg_speed_kmh ** 2
        )
        return max(0, fuel)  # Ensure non-negative fuel consumption
    
    def build_matrix(self, locations: Union[List[str], List[List[float]]],
                     output_path: Optional[str] = None) -> None:
        """
        Main entry point: builds all 4 matrices for the given locations.

        Args:
            locations: Either list of address strings OR list of [lon, lat] coordinates
            output_path: Optional directory to save CSV outputs
        """
        # Geocode addresses if needed, otherwise use coordinates directly
        if isinstance(locations[0], str):
            print(f"Geocoding {len(locations)} locations...")
            coords = self.geocode_all(locations)
            self.labels = [loc.split(',')[0] for loc in locations]  # Use first part of address as label
        else:
            coords = locations
            self.labels = [f"Stop {i}" for i in range(len(locations))]

        n = len(coords)
        print(f"Fetching {n*(n-1)} routes...")  # n² - n pairs (excluding self-to-self)

        # Async fetch all route data
        route_results = asyncio.run(self._fetch_all_routes(coords))

        # Initialize NxN matrices (diagonal stays 0)
        self.fuel_matrix = np.zeros((n, n))
        self.distance_matrix = np.zeros((n, n))
        self.elevation_matrix = np.zeros((n, n))
        self.speed_matrix = np.zeros((n, n))

        # Populate matrices from route results
        for (i, j), route in route_results.items():
            if route.get('success'):
                self.fuel_matrix[i, j] = self.predict_fuel(
                    route['distance_km'], route['elevation_gain_m'], route['avg_speed_kmh']
                )
                self.distance_matrix[i, j] = route['distance_km']
                self.elevation_matrix[i, j] = route['elevation_gain_m']
                self.speed_matrix[i, j] = route['avg_speed_kmh']
            else:
                # Mark failed routes as NaN
                self.fuel_matrix[i, j] = np.nan
                self.distance_matrix[i, j] = np.nan
                self.elevation_matrix[i, j] = np.nan
                self.speed_matrix[i, j] = np.nan

        success_rate = sum(1 for r in route_results.values() if r.get('success')) / len(route_results)
        print(f"Done. {success_rate*100:.0f}% success.")

        # Convert numpy arrays to lists for JSON compatibility
        self.fuel_matrix = self.fuel_matrix.tolist()
        self.distance_matrix = self.distance_matrix.tolist()
        self.elevation_matrix = self.elevation_matrix.tolist()
        self.speed_matrix = self.speed_matrix.tolist()

        if output_path:
            self.save_matrices(output_path)
    
    def save_matrices(self, output_path: str):
        """Save all matrices and labels as CSV files to the specified directory."""
        os.makedirs(output_path, exist_ok=True)

        # Save each matrix with row/column labels for easy inspection
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
    
    # --- Accessor methods for retrieving built matrices ---

    def get_labels(self) -> List[str]:
        """Return human-readable labels for each location."""
        return self.labels

    def get_fuel_matrix(self) -> List[List[float]]:
        """Return NxN fuel consumption matrix (liters)."""
        return self.fuel_matrix

    def get_distance_matrix(self) -> List[List[float]]:
        """Return NxN distance matrix (km)."""
        return self.distance_matrix

    def get_elevation_matrix(self) -> List[List[float]]:
        """Return NxN elevation gain matrix (meters ascent)."""
        return self.elevation_matrix

    def get_speed_matrix(self) -> List[List[float]]:
        """Return NxN average speed matrix (km/h)."""
        return self.speed_matrix


# ============================================================
# HELPER
# ============================================================

def get_api_keys() -> List[str]:
    """
    Load OpenRouteService API keys from environment variables.

    Looks for:
      - ORS_API_KEY_1, ORS_API_KEY_2, ... (numbered keys for rotation)
      - ORS_API_KEY or OPENROUTESERVICE_API_KEY (single key fallback)

    Multiple keys help avoid rate limits by rotating between them.
    """
    keys = []
    i = 1
    # Collect numbered keys (ORS_API_KEY_1, ORS_API_KEY_2, etc.)
    while True:
        key = os.getenv(f"ORS_API_KEY_{i}")
        if key:
            keys.append(key)
            i += 1
        else:
            break
    # Also check for single key environment variables
    single = os.getenv("ORS_API_KEY") or os.getenv("OPENROUTESERVICE_API_KEY")
    if single and single not in keys:
        keys.insert(0, single)
    if not keys:
        raise RuntimeError("No API keys found")
    return keys


if __name__ == "__main__":
    API_KEYS = get_api_keys()

    #need to pass in locations
    
    locations = [
        "TST BOCES Tompkins, 555 Warren Rd, Ithaca, NY 14850",
        "DeWitt Middle School, 560 Warren Rd, Ithaca, NY 14850",
        "Northeast Elementary School, 425 Winthrop Dr, Ithaca, NY 14850",
        "Cayuga Heights Elementary School, 110 E Upland Rd, Ithaca, NY 14850",
        "Belle Sherman Elementary School, 501 Mitchell St, Ithaca, NY 14850",
        "Caroline After School Program, 2439 Slaterville Rd, Slaterville Springs, NY 14881",
        "South Hill Elementary School, 520 Hudson St, Ithaca, NY 14850",
        "Beverly J. Martin Elementary School, 302 W Buffalo St, Ithaca, NY 14850",
        "Fall Creek Elementary School, 202 King St, Ithaca, NY 14850",
        "Boynton Middle School, 1601 N Cayuga St, Ithaca, NY 14850",
        "ICSD Technology, 602 Hancock St, Ithaca, NY 14850",
        "737 Willow Ave, Ithaca, NY 14850",
        "Enfield Elementary School, 20 Enfield Main Rd, Ithaca, NY 14850",
        "Lehman Alternative Community School, 111 Chestnut St, Ithaca, NY 14850",
        "Tompkins County Recycling, 122 Commercial Ave, Ithaca, NY 14850",
    ]

    #need to add output path
    
    # === SPECIFY OUTPUT PATH HERE ===
    OUTPUT_PATH = "ml/New_Code/Production_Final/Matricies"  # e.g., "/path/to/output/folder"
    
    builder = FuelMatrixBuilder(
        api_keys=API_KEYS,
        vehicle_class='dump_truck',
    )
    
    builder.build_matrix(locations, output_path=OUTPUT_PATH)
    
    print("\nFuel Matrix (L):")
    print(pd.DataFrame(builder.get_fuel_matrix(), 
                       index=builder.get_labels(), 
                       columns=builder.get_labels()).round(4))
    
    print("\nDistance Matrix (km):")
    print(pd.DataFrame(builder.get_distance_matrix(), 
                       index=builder.get_labels(), 
                       columns=builder.get_labels()).round(4))
    
    print("\nElevation Matrix (m):")
    print(pd.DataFrame(builder.get_elevation_matrix(), 
                       index=builder.get_labels(), 
                       columns=builder.get_labels()).round(4))
    
    print("\nSpeed Matrix (km/h):")
    print(pd.DataFrame(builder.get_speed_matrix(), 
                       index=builder.get_labels(), 
                       columns=builder.get_labels()).round(4))