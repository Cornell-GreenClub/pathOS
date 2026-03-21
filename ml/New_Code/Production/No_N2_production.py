"""
Fuel Matrix Builder (v2 - Optimized)

Creates an NxN fuel consumption matrix for a list of locations.
Uses ORS Matrix API for efficiency (1 call instead of N²).

Usage:
    from fuel_matrix_builder import FuelMatrixBuilder
    
    builder = FuelMatrixBuilder(api_key="...", vehicle_weight_kg=9000)
    matrix = builder.build_matrix(locations)  # Returns 2D list
    
Author: Justin Li
Date: March 2026
"""

import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *args, **kwargs: None

import numpy as np
import pandas as pd
import openrouteservice
import joblib
import time
from pathlib import Path
from typing import List, Optional, Union, Tuple
from dataclasses import dataclass

# Load environment variables from .env if present
load_dotenv()


# ============ CONSTANTS ============

# Fallback coefficients if model file not found
# (trained on eVED gasoline vehicles, March 2026)
FALLBACK_COEFFICIENTS = {
    'intercept': 0.025024,
    'Total_Distance_km': 0.06962583,
    'Dist_x_Weight': 0.00005552431,
    'Elev_x_Weight': 0.000002550080,
    'Dist_x_Speed2': 0.000001102072,
}

# Diesel correction factor
# Diesel is ~35% more efficient than gasoline for same work
# Derivation: (0.28 × 32) / (0.38 × 36) ≈ 0.65
DIESEL_CORRECTION = 0.65
GASOLINE_CORRECTION = 1.0

# CO2 emissions (kg per liter)
CO2_KG_PER_LITER = {
    'diesel': 2.68,
    'gasoline': 2.31
}

# API rate limiting
API_DELAY_SECONDS = 0.5


# ============ MAIN CLASS ============

class FuelMatrixBuilder:
    """
    Builds fuel consumption matrices for route planning.
    
    Uses ORS Matrix API for efficiency:
    - 1 matrix call for all distances/durations
    - 1 elevation call for all locations
    - Total: 2 API calls instead of N*(N-1)
    """
    
    def __init__(
        self,
        api_key: str,
        vehicle_weight_kg: float = 9000,
        fuel_type: str = 'diesel',
        include_return: bool = False,
        model_path: Optional[str] = None
    ):
        """
        Initialize the builder.
        
        Args:
            api_key: OpenRouteService API key
            vehicle_weight_kg: Vehicle weight in kg (default 9000 for school bus)
            fuel_type: 'diesel' or 'gasoline'
            include_return: If True, matrix includes return trip to start
            model_path: Path to trained model (.joblib). Auto-detected if None.
        """
        self.client = openrouteservice.Client(key=api_key)
        self.vehicle_weight_kg = vehicle_weight_kg
        self.fuel_type = fuel_type.lower()
        self.include_return = include_return
        
        # Set fuel correction
        if self.fuel_type == 'diesel':
            self.fuel_correction = DIESEL_CORRECTION
        elif self.fuel_type == 'gasoline':
            self.fuel_correction = GASOLINE_CORRECTION
        else:
            raise ValueError(f"Unknown fuel_type: {fuel_type}")
        
        # Load model from joblib
        self.model = None
        self.sklearn_model = None
        self.feature_names = None
        
        # Search paths for model file
        search_paths = [
            model_path,
            '//Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/fuel_model_physics.joblib',
            'fuel_model_physics.joblib',
            'Final_Outputs/fuel_model_physics.joblib',
            '../Final_Outputs/fuel_model_physics.joblib',
            'models/fuel_model_physics.joblib',
            'physics_informed_fuel_model.joblib',
        ]
        
        for path in search_paths:
            if path and Path(path).exists():
                try:
                    self.model = joblib.load(path)
                    print(f"✓ Loaded model from: {path}")
                    
                    if isinstance(self.model, dict):
                        self.sklearn_model = self.model.get('model')
                        self.feature_names = self.model.get('features')
                    elif hasattr(self.model, 'predict'):
                        self.sklearn_model = self.model
                    
                    break
                except Exception as e:
                    print(f"Warning: Could not load model from {path}: {e}")
        
        if self.sklearn_model is None:
            print("⚠ No model file found. Using fallback coefficients.")
        
        # Cache for geocoded locations
        self._coord_cache = {}
    
    # ---------- GEOCODING ----------
    
    def geocode(self, address: str) -> List[float]:
        """Geocode an address to [longitude, latitude]."""
        if address in self._coord_cache:
            return self._coord_cache[address]
        
        result = self.client.pelias_search(text=address, size=1)
        
        if result and 'features' in result and len(result['features']) > 0:
            coords = result['features'][0]['geometry']['coordinates']
            self._coord_cache[address] = coords
            return coords
        else:
            raise ValueError(f"Could not geocode: {address}")
    
    def geocode_all(
        self, 
        locations: List[str], 
        verbose: bool = True
    ) -> List[List[float]]:
        """Geocode a list of addresses."""
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
            
            if i < len(locations) - 1:
                time.sleep(API_DELAY_SECONDS)
        
        return coords
    
    # ---------- ELEVATION ----------
    
    def _get_elevations(
        self,
        coords: List[List[float]],
        verbose: bool = True
    ) -> List[float]:
        """
        Get elevation for all coordinates in ONE API call.
        
        Args:
            coords: List of [lon, lat] coordinates
            verbose: Print progress
        
        Returns:
            List of elevations in meters
        """
        if verbose:
            print(f"\nQuerying elevations for {len(coords)} locations (1 API call)...")
        
        try:
            # Pass all coordinates as a polyline - ORS returns elevation for each point
            result = self.client.elevation_line(
                format_in='polyline',
                format_out='polyline',
                geometry=coords
            )
            
            if result and 'geometry' in result:
                elevations = [point[2] for point in result['geometry']]
                
                if verbose:
                    for i, elev in enumerate(elevations):
                        print(f"  Location {i}: {elev:.1f}m")
                
                return elevations
            else:
                if verbose:
                    print("  No elevation data returned, using 0m for all")
                return [0] * len(coords)
                
        except Exception as e:
            if verbose:
                print(f"  Elevation query failed ({e}), using 0m for all")
            return [0] * len(coords)
    
    def _estimate_elevation_gain(
        self,
        elevations: List[float],
        i: int,
        j: int
    ) -> float:
        """
        Estimate elevation gain from location i to location j.
        
        Simple estimate: if destination is higher, that's the gain.
        Note: This underestimates for hilly routes that go up and down.
        """
        delta = elevations[j] - elevations[i]
        return max(0, delta)
    
    # ---------- MATRIX API ----------
    
    def _get_distance_duration_matrix(
        self,
        coords: List[List[float]],
        verbose: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get NxN distance and duration matrices using ORS Matrix API.
        
        Returns:
            (distance_matrix_km, duration_matrix_min)
        """
        if verbose:
            print("\nQuerying ORS Matrix API...")
        
        result = self.client.distance_matrix(
            locations=coords,
            profile='driving-hgv',
            metrics=['distance', 'duration'],
            units='m'
        )
        
        # Convert to numpy arrays
        distances_m = np.array(result['distances'])
        durations_s = np.array(result['durations'])
        
        # Convert units
        distances_km = distances_m / 1000
        durations_min = durations_s / 60
        
        if verbose:
            print(f"  ✓ Retrieved {len(coords)}x{len(coords)} matrix")
        
        return distances_km, durations_min
    
    # ---------- FUEL PREDICTION ----------
    
    def _predict_fuel(
        self,
        distance_km: float,
        elevation_gain_m: float,
        avg_speed_kmh: float
    ) -> float:
        """Predict fuel consumption in liters."""
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
        """
        Build NxN fuel consumption matrix.
        
        Args:
            locations: List of addresses OR list of [lon, lat] coordinates
            verbose: Print progress
        
        Returns:
            2D list with fuel consumption (liters) between each pair.
            matrix[i][j] = fuel to go from location i to location j
        """
        # Geocode if needed
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
        
        if verbose:
            print("\n" + "="*60)
            print("BUILDING FUEL MATRIX (Optimized)")
            print(f"Locations: {n}")
            print(f"API calls: 1 (matrix) + 1 (elevation) = 2 total")
            print(f"(vs {n*(n-1)} calls with old method)")
            print("="*60)
        
        # Step 1: Get distance/duration matrix (1 API call)
        distances_km, durations_min = self._get_distance_duration_matrix(coords, verbose)
        
        # Step 2: Get elevations (N API calls)
        elevations = self._get_elevations(coords, verbose)
        
        # Step 3: Compute fuel matrix
        if verbose:
            print("\nComputing fuel consumption...")
        
        fuel_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                
                distance = distances_km[i, j]
                duration_hr = durations_min[i, j] / 60
                avg_speed = distance / duration_hr if duration_hr > 0 else 50.0
                elev_gain = self._estimate_elevation_gain(elevations, i, j)
                
                fuel = self._predict_fuel(distance, elev_gain, avg_speed)
                fuel_matrix[i, j] = fuel
        
        # Store as attributes for reference
        self.distance_matrix = distances_km.tolist()
        self.duration_matrix = durations_min.tolist()
        self.elevations = elevations
        
        # Handle return to start if requested
        if self.include_return:
            # Add column for return to start (index 0)
            return_col = fuel_matrix[:, 0].reshape(-1, 1)
            fuel_matrix = np.hstack([fuel_matrix, return_col])
            
            # Add row of zeros (can't depart FROM "return")
            return_row = np.zeros((1, fuel_matrix.shape[1]))
            fuel_matrix = np.vstack([fuel_matrix, return_row])
            
            self.labels.append(f"Return to {self.labels[0]}")
        
        if verbose:
            print("\n" + "="*60)
            print("COMPLETE")
            print("="*60)
            print(f"\nFuel Matrix ({len(fuel_matrix)}x{len(fuel_matrix[0])}):")
            
            # Pretty print
            df = pd.DataFrame(fuel_matrix, index=self.labels, columns=self.labels)
            print(df.round(3).to_string())
            
            print(f"\n--- Summary ---")
            print(f"Vehicle weight: {self.vehicle_weight_kg} kg")
            print(f"Fuel type: {self.fuel_type}")
            print(f"Include return: {self.include_return}")
            non_zero = fuel_matrix[fuel_matrix > 0]
            if len(non_zero) > 0:
                print(f"Min fuel (non-zero): {non_zero.min():.3f} L")
                print(f"Max fuel: {non_zero.max():.3f} L")
        
        return fuel_matrix.tolist()
    
    def get_labels(self) -> List[str]:
        """Get location labels (after build_matrix is called)."""
        return self.labels
    
    def get_distance_matrix(self) -> List[List[float]]:
        """Get distance matrix in km (after build_matrix is called)."""
        return self.distance_matrix
    
    def get_duration_matrix(self) -> List[List[float]]:
        """Get duration matrix in minutes (after build_matrix is called)."""
        return self.duration_matrix


# ============ CONVENIENCE FUNCTION ============

def build_fuel_matrix(
    api_key: str,
    locations: List[str],
    vehicle_weight_kg: float = 9000,
    fuel_type: str = 'diesel',
    include_return: bool = False,
    verbose: bool = True
) -> Tuple[List[List[float]], List[str]]:
    """
    Quick function to build a fuel matrix.
    
    Returns:
        (fuel_matrix, labels) - 2D list and location labels
    """
    builder = FuelMatrixBuilder(
        api_key=api_key,
        vehicle_weight_kg=vehicle_weight_kg,
        fuel_type=fuel_type,
        include_return=include_return
    )
    
    matrix = builder.build_matrix(locations, verbose)
    labels = builder.get_labels()
    
    return matrix, labels


# ============ MAIN (DEMO) ============

def get_api_key() -> str:
    """Get ORS API key from environment."""
    key = os.getenv("ORS_API_KEY") or os.getenv("OPENROUTESERVICE_API_KEY")
    if not key:
        raise RuntimeError(
            "OpenRouteService API key not found. Please set ORS_API_KEY in your environment."
        )
    return key


if __name__ == "__main__":
    API_KEY = get_api_key()
    
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
    print("FUEL MATRIX BUILDER (Optimized)")
    print("="*60)
    
    # Build matrix
    builder = FuelMatrixBuilder(
        api_key=API_KEY,
        vehicle_weight_kg=9000,
        fuel_type='diesel',
        include_return=False
    )
    
    fuel_matrix = builder.build_matrix(locations)
    
    # Access as 2D list
    print(f"\nMatrix type: {type(fuel_matrix)}")
    print(f"Matrix shape: {len(fuel_matrix)} x {len(fuel_matrix[0])}")
    print(f"\nExample: fuel_matrix[0][1] = {fuel_matrix[0][1]:.3f} L")
    print(f"         ({builder.labels[0]} → {builder.labels[1]})")
    
    # Save to CSV for verification
    df = pd.DataFrame(fuel_matrix, index=builder.labels, columns=builder.labels)
    output_path = '/Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/fuel_matrix.csv'
    df.to_csv(output_path)
    print(f"\n✓ Saved to {output_path}")