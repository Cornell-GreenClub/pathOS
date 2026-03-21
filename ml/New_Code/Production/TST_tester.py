"""
Fuel Matrix Builder (v3 - Async/Parallel with Multi-Key Support)

Creates an NxN fuel consumption matrix for a list of locations.
Uses async/parallel API calls for speed (5-10x faster than sequential).
Supports multiple API keys to avoid rate limits.

Usage:
    from fuel_matrix_builder_async import FuelMatrixBuilder
    
    builder = FuelMatrixBuilder(
        api_keys=["key1", "key2", "key3"],  # Multiple keys!
        vehicle_weight_kg=9000
    )
    matrix = builder.build_matrix(locations)
    
Author: Justin Li
Date: March 2026
"""

import os
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import joblib
import time
from pathlib import Path
from typing import List, Optional, Union, Tuple, Dict, Any
from dataclasses import dataclass
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import openrouteservice


# ============ CONSTANTS ============

FALLBACK_COEFFICIENTS = {
    'intercept': 0.025024,
    'Total_Distance_km': 0.06962583,
    'Dist_x_Weight': 0.00005552431,
    'Elev_x_Weight': 0.000002550080,
    'Dist_x_Speed2': 0.000001102072,
}

DIESEL_CORRECTION = 0.65
GASOLINE_CORRECTION = 1.0

MAX_CONCURRENT_REQUESTS = 5
REQUEST_DELAY = 0.5
MAX_RETRIES = 10

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"


# ============ MAIN CLASS ============

class FuelMatrixBuilder:
    """
    Builds fuel consumption matrices for route planning.
    
    - Runs up to 5 API calls simultaneously
    - Rotates through multiple API keys
    """
    
    def __init__(
        self,
        api_keys: Union[str, List[str]],
        vehicle_weight_kg: float = 9000,
        fuel_type: str = 'diesel',
        include_return: bool = False,
        model_path: Optional[str] = None,
        max_concurrent: int = MAX_CONCURRENT_REQUESTS
    ):
        # Handle single key or list of keys
        if isinstance(api_keys, str):
            self.api_keys = [api_keys]
        else:
            self.api_keys = api_keys
        
        self._key_index = 0
        self._key_lock = threading.Lock()
        
        print(f"✓ Loaded {len(self.api_keys)} API key(s)")
        
        self.vehicle_weight_kg = vehicle_weight_kg
        self.fuel_type = fuel_type.lower()
        self.include_return = include_return
        self.max_concurrent = max_concurrent
        
        # For sync geocoding (uses first key)
        self.client = openrouteservice.Client(key=self.api_keys[0])
        
        if self.fuel_type == 'diesel':
            self.fuel_correction = DIESEL_CORRECTION
        elif self.fuel_type == 'gasoline':
            self.fuel_correction = GASOLINE_CORRECTION
        else:
            raise ValueError(f"Unknown fuel_type: {fuel_type}")
        
        # Load model
        self.sklearn_model = None
        search_paths = [
            model_path,
            '/Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/fuel_model_physics.joblib',
            'fuel_model_physics.joblib',
            'Final_Outputs/fuel_model_physics.joblib',
            '../Final_Outputs/fuel_model_physics.joblib',
        ]
        
        for path in search_paths:
            if path and Path(path).exists():
                try:
                    model = joblib.load(path)
                    print(f"✓ Loaded model from: {path}")
                    if isinstance(model, dict):
                        self.sklearn_model = model.get('model')
                    elif hasattr(model, 'predict'):
                        self.sklearn_model = model
                    break
                except Exception as e:
                    print(f"Warning: Could not load model from {path}: {e}")
        
        if self.sklearn_model is None:
            print("⚠ No model file found. Using fallback coefficients.")
        
        self._coord_cache = {}
        self.labels = []
    
    def _get_next_key(self) -> str:
        """Get next API key (rotates through list)."""
        with self._key_lock:
            key = self.api_keys[self._key_index]
            self._key_index = (self._key_index + 1) % len(self.api_keys)
            return key
    
    # ---------- GEOCODING ----------
    
    def geocode(self, address: str) -> List[float]:
        if address in self._coord_cache:
            return self._coord_cache[address]
        
        result = self.client.pelias_search(text=address, size=1)
        
        if result and 'features' in result and len(result['features']) > 0:
            coords = result['features'][0]['geometry']['coordinates']
            self._coord_cache[address] = coords
            return coords
        else:
            raise ValueError(f"Could not geocode: {address}")
    
    def geocode_all(self, locations: List[str], verbose: bool = True) -> List[List[float]]:
        coords = []
        
        for i, loc in enumerate(locations):
            if verbose:
                print(f"Geocoding [{i+1}/{len(locations)}]: {loc[:50]}...", end=" ")
            
            try:
                coord = self.geocode(loc)
                coords.append(coord)
                if verbose:
                    print(f"✓")
            except ValueError as e:
                if verbose:
                    print(f"✗ FAILED")
                raise e
            
            time.sleep(0.5)
        
        return coords
    
    # ---------- ASYNC API CALLS ----------
    
    async def _fetch_route(
        self,
        session: aiohttp.ClientSession,
        origin: List[float],
        destination: List[float],
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        async with semaphore:
            api_key = self._get_next_key()
            
            headers = {
                'Authorization': api_key,
                'Content-Type': 'application/json'
            }
            
            payload = {
                'coordinates': [origin, destination],
                'elevation': True
            }
            
            for attempt in range(MAX_RETRIES):
                try:
                    async with session.post(
                        ORS_DIRECTIONS_URL,
                        headers=headers,
                        json=payload
                    ) as response:
                        
                        if response.status == 429:
                            api_key = self._get_next_key()
                            headers['Authorization'] = api_key
                            wait_time = (attempt + 1) * 2
                            await asyncio.sleep(wait_time)
                            continue
                        
                        response.raise_for_status()
                        data = await response.json()
                        
                        feature = data['features'][0]
                        props = feature['properties']
                        summary = props['summary']
                        
                        distance_km = summary['distance'] / 1000
                        duration_min = summary['duration'] / 60
                        elevation_gain_m = props.get('ascent', 0)
                        
                        duration_hr = summary['duration'] / 3600
                        avg_speed_kmh = distance_km / duration_hr if duration_hr > 0 else 50.0
                        
                        await asyncio.sleep(REQUEST_DELAY)
                        
                        return {
                            'distance_km': distance_km,
                            'duration_min': duration_min,
                            'elevation_gain_m': elevation_gain_m,
                            'avg_speed_kmh': avg_speed_kmh,
                            'success': True
                        }
                
                except Exception as e:
                    if attempt == MAX_RETRIES - 1:
                        return {
                            'distance_km': 0,
                            'duration_min': 0,
                            'elevation_gain_m': 0,
                            'avg_speed_kmh': 50.0,
                            'success': False,
                            'error': str(e)
                        }
                    await asyncio.sleep(1)
        
        return {'success': False, 'error': 'Max retries exceeded'}
    
    async def _fetch_all_routes(
        self,
        coords: List[List[float]],
        verbose: bool = True
    ) -> Dict[Tuple[int, int], Dict]:
        n = len(coords)
        pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
        total = len(pairs)
        
        if verbose:
            print(f"\nFetching {total} routes ({self.max_concurrent} concurrent, {len(self.api_keys)} keys)...")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = {}
        completed = 0
        
        async with aiohttp.ClientSession() as session:
            
            async def fetch_one(i: int, j: int):
                nonlocal completed
                result = await self._fetch_route(session, coords[i], coords[j], semaphore)
                completed += 1
                
                if verbose and completed % 20 == 0:
                    print(f"  Progress: {completed}/{total} ({completed/total*100:.0f}%)")
                
                return (i, j), result
            
            tasks = [fetch_one(i, j) for i, j in pairs]
            responses = await asyncio.gather(*tasks)
            
            for (i, j), result in responses:
                results[(i, j)] = result
        
        if verbose:
            success_count = sum(1 for r in results.values() if r.get('success', False))
            print(f"  ✓ Completed: {success_count}/{total} successful")
        
        return results
    
    # ---------- FUEL PREDICTION ----------
    
    def _predict_fuel(
        self,
        distance_km: float,
        elevation_gain_m: float,
        avg_speed_kmh: float
    ) -> float:
        w = self.vehicle_weight_kg
        
        features = np.array([[
            distance_km,
            distance_km * w,
            elevation_gain_m * w,
            distance_km * avg_speed_kmh ** 2
        ]])
        
        if self.sklearn_model is not None:
            fuel_gasoline = self.sklearn_model.predict(features)[0]
        else:
            c = FALLBACK_COEFFICIENTS
            fuel_gasoline = (
                c['intercept'] +
                c['Total_Distance_km'] * distance_km +
                c['Dist_x_Weight'] * (distance_km * w) +
                c['Elev_x_Weight'] * (elevation_gain_m * w) +
                c['Dist_x_Speed2'] * (distance_km * avg_speed_kmh ** 2)
            )
        
        fuel_liters = fuel_gasoline * self.fuel_correction
        return max(0, fuel_liters)
    
    # ---------- MATRIX BUILDING ----------
    
    def build_matrix(
        self,
        locations: Union[List[str], List[List[float]]],
        verbose: bool = True
    ) -> List[List[float]]:
        if isinstance(locations[0], str):
            if verbose:
                print("="*60)
                print("GEOCODING LOCATIONS")
                print("="*60)
            coords = self.geocode_all(locations, verbose)
            self.labels = [loc.split(',')[0] for loc in locations]
        else:
            coords = locations
            self.labels = [f"Stop {i}" for i in range(len(locations))]
        
        n = len(coords)
        total_calls = n * (n - 1)
        
        if verbose:
            print("\n" + "="*60)
            print("BUILDING FUEL MATRIX (Async + Multi-Key)")
            print(f"Locations: {n}")
            print(f"API calls: {total_calls}")
            print(f"Concurrent requests: {self.max_concurrent}")
            print(f"API keys: {len(self.api_keys)}")
            print(f"Estimated time: {total_calls * REQUEST_DELAY / self.max_concurrent / 60:.1f} minutes")
            print("="*60)
        
        start_time = time.time()
        route_results = asyncio.run(self._fetch_all_routes(coords, verbose))
        
        if verbose:
            print("\nComputing fuel consumption...")
        
        fuel_matrix = np.zeros((n, n))
        distance_matrix = np.zeros((n, n))
        
        for (i, j), route in route_results.items():
            if route.get('success', False):
                fuel = self._predict_fuel(
                    route['distance_km'],
                    route['elevation_gain_m'],
                    route['avg_speed_kmh']
                )
                fuel_matrix[i, j] = fuel
                distance_matrix[i, j] = route['distance_km']
            else:
                fuel_matrix[i, j] = np.nan
        
        self.distance_matrix = distance_matrix.tolist()
        
        if self.include_return:
            return_col = fuel_matrix[:, 0].reshape(-1, 1)
            fuel_matrix = np.hstack([fuel_matrix, return_col])
            return_row = np.zeros((1, fuel_matrix.shape[1]))
            fuel_matrix = np.vstack([fuel_matrix, return_row])
            self.labels.append(f"Return to {self.labels[0]}")
        
        elapsed = time.time() - start_time
        
        if verbose:
            print("\n" + "="*60)
            print("COMPLETE")
            print("="*60)
            print(f"Time elapsed: {elapsed:.1f} seconds")
            print(f"\nFuel Matrix ({len(fuel_matrix)}x{len(fuel_matrix[0])}):")
            
            df = pd.DataFrame(fuel_matrix, index=self.labels, columns=self.labels)
            print(df.round(3).to_string())
            
            print(f"\n--- Summary ---")
            print(f"Vehicle weight: {self.vehicle_weight_kg} kg")
            print(f"Fuel type: {self.fuel_type}")
            non_zero = fuel_matrix[fuel_matrix > 0]
            if len(non_zero) > 0:
                print(f"Min fuel (non-zero): {non_zero.min():.3f} L")
                print(f"Max fuel: {non_zero.max():.3f} L")
        
        return fuel_matrix.tolist()
    
    def get_labels(self) -> List[str]:
        return self.labels
    
    def get_distance_matrix(self) -> List[List[float]]:
        return self.distance_matrix


# ============ MAIN ============

def get_api_keys() -> List[str]:
    """Get ORS API keys from environment."""
    keys = []
    
    # Check for numbered keys: ORS_API_KEY_1, ORS_API_KEY_2, etc.
    i = 1
    while True:
        key = os.getenv(f"ORS_API_KEY_{i}")
        if key:
            keys.append(key)
            i += 1
        else:
            break
    
    # Also check for single key
    single_key = os.getenv("ORS_API_KEY") or os.getenv("OPENROUTESERVICE_API_KEY")
    if single_key and single_key not in keys:
        keys.insert(0, single_key)
    
    if not keys:
        raise RuntimeError("No API keys found. Set ORS_API_KEY or ORS_API_KEY_1, ORS_API_KEY_2, etc.")
    
    return keys


if __name__ == "__main__":
    API_KEYS = get_api_keys()
    
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
    
    print("="*60)
    print("FUEL MATRIX BUILDER (Async + Multi-Key)")
    print("="*60)
    
    builder = FuelMatrixBuilder(
        api_keys=API_KEYS,
        vehicle_weight_kg=9000,
        fuel_type='diesel',
        include_return=False,
        max_concurrent=5
    )
    
    fuel_matrix = builder.build_matrix(locations)
    
    # Save to CSV
    df = pd.DataFrame(fuel_matrix, index=builder.labels, columns=builder.labels)
    output_path = '/Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/fuel_matrix.csv'
    df.to_csv(output_path)
    print(f"\n✓ Saved to {output_path}")