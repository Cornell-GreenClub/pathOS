"""
Fuel Matrix Builder

Creates an NxN fuel consumption matrix for a list of locations.
Uses physics-informed model trained on eVED data with diesel correction.

Usage:
    from fuel_matrix_builder import FuelMatrixBuilder
    
    builder = FuelMatrixBuilder(api_key="...", vehicle_weight_kg=9000)
    matrix = builder.build_matrix(locations)
    print(matrix)

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
API_DELAY_SECONDS = 0.75


# ============ DATA CLASSES ============

@dataclass
class LegData:
    """Data for a single leg between two locations."""
    origin_idx: int
    dest_idx: int
    distance_km: float
    duration_min: float
    elevation_gain_m: float
    avg_speed_kmh: float
    fuel_liters: float


# ============ MAIN CLASS ============

class FuelMatrixBuilder:
    """
    Builds fuel consumption matrices for route planning.
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
                           (adds a row/column for returning to origin)
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
            '/Users/fli6/Desktop/Projects/pathos_model_updated/Final_Outputs/fuel_model_physics.joblib',
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
                    
                    # Handle different model storage formats
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
        """
        Geocode an address to [longitude, latitude].
        """
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
        """
        Geocode a list of addresses.
        """
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
    
    # ---------- ROUTE QUERIES ----------
    
    def _query_route(
        self, 
        origin: List[float], 
        destination: List[float]
    ) -> dict:
        """
        Query ORS for route data between two points.
        """
        route = self.client.directions(
            coordinates=[origin, destination],
            profile='driving-hgv',
            elevation=True,
            format='geojson'
        )
        
        feature = route['features'][0]
        props = feature['properties']
        summary = props['summary']
        
        distance_km = summary['distance'] / 1000
        duration_min = summary['duration'] / 60
        elevation_gain_m = props.get('ascent', 0)
        
        duration_hr = summary['duration'] / 3600
        avg_speed_kmh = distance_km / duration_hr if duration_hr > 0 else 50.0
        
        return {
            'distance_km': distance_km,
            'duration_min': duration_min,
            'elevation_gain_m': elevation_gain_m,
            'avg_speed_kmh': avg_speed_kmh
        }
    
    # ---------- FUEL PREDICTION ----------
    
    def _predict_fuel(
        self,
        distance_km: float,
        elevation_gain_m: float,
        avg_speed_kmh: float
    ) -> float:
        """
        Predict fuel consumption in liters.
        """
        w = self.vehicle_weight_kg
        
        # Build features array
        features = np.array([[
            distance_km,
            distance_km * w,              # Dist_x_Weight
            elevation_gain_m * w,         # Elev_x_Weight
            distance_km * avg_speed_kmh ** 2  # Dist_x_Speed2
        ]])
        
        # Use sklearn model if available, otherwise fallback
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
    
    def predict_leg(
        self,
        origin: List[float],
        destination: List[float],
        origin_idx: int = 0,
        dest_idx: int = 1
    ) -> LegData:
        """
        Predict fuel for a single leg.
        """
        route = self._query_route(origin, destination)
        
        fuel = self._predict_fuel(
            route['distance_km'],
            route['elevation_gain_m'],
            route['avg_speed_kmh']
        )
        
        return LegData(
            origin_idx=origin_idx,
            dest_idx=dest_idx,
            distance_km=route['distance_km'],
            duration_min=route['duration_min'],
            elevation_gain_m=route['elevation_gain_m'],
            avg_speed_kmh=route['avg_speed_kmh'],
            fuel_liters=fuel
        )
    
    # ---------- MATRIX BUILDING ----------
    
    def build_matrix(
        self,
        locations: Union[List[str], List[List[float]]],
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Build NxN fuel consumption matrix.
        
        Args:
            locations: List of addresses OR list of [lon, lat] coordinates
            verbose: Print progress
        
        Returns:
            Pandas DataFrame with fuel consumption (liters) between each pair.
            Rows = origins, Columns = destinations.
            
            If include_return=True:
                - First location (index 0) is treated as the depot/start
                - Matrix is (N+1) x (N+1) with last row/col being "Return to Start"
        """
        # Determine if we have addresses or coordinates
        if isinstance(locations[0], str):
            if verbose:
                print("="*60)
                print("GEOCODING LOCATIONS")
                print("="*60)
            coords = self.geocode_all(locations, verbose)
            labels = [loc.split(',')[0] for loc in locations]
        else:
            coords = locations
            labels = [f"Stop {i}" for i in range(len(locations))]
        
        n = len(coords)
        
        # If include_return, we add an extra row/col for "Return to Start"
        matrix_size = n + 1 if self.include_return else n
        fuel_matrix = np.zeros((matrix_size, matrix_size))
        distance_matrix = np.zeros((matrix_size, matrix_size))
        
        # Count API calls
        if self.include_return:
            # N*(N-1) for regular pairs + (N-1) for returns to start
            total_calls = n * (n - 1) + (n - 1)
        else:
            total_calls = n * (n - 1)
        
        call_count = 0
        
        if verbose:
            print("\n" + "="*60)
            print("BUILDING FUEL MATRIX")
            print(f"Locations: {n}")
            print(f"Include return to start: {self.include_return}")
            print(f"API calls needed: {total_calls}")
            print(f"Estimated time: {total_calls * API_DELAY_SECONDS / 60:.1f} minutes")
            print("="*60 + "\n")
        
        # Build main matrix (all pairs)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                
                call_count += 1
                if verbose:
                    print(f"[{call_count}/{total_calls}] {labels[i]} → {labels[j]}...", end=" ")
                
                try:
                    leg = self.predict_leg(coords[i], coords[j], i, j)
                    fuel_matrix[i, j] = leg.fuel_liters
                    distance_matrix[i, j] = leg.distance_km
                    
                    if verbose:
                        print(f"{leg.fuel_liters:.3f} L ({leg.distance_km:.1f} km)")
                    
                except Exception as e:
                    if verbose:
                        print(f"ERROR: {e}")
                    fuel_matrix[i, j] = np.nan
                
                time.sleep(API_DELAY_SECONDS)
        
        # If include_return, compute return trips from each location to start
        if self.include_return:
            return_label = f"Return to {labels[0]}"
            labels.append(return_label)
            
            # Return trips: from each non-start location back to start
            for i in range(1, n):
                call_count += 1
                if verbose:
                    print(f"[{call_count}/{total_calls}] {labels[i]} → {labels[0]} (return)...", end=" ")
                
                try:
                    leg = self.predict_leg(coords[i], coords[0], i, n)
                    fuel_matrix[i, n] = leg.fuel_liters
                    distance_matrix[i, n] = leg.distance_km
                    
                    if verbose:
                        print(f"{leg.fuel_liters:.3f} L ({leg.distance_km:.1f} km)")
                except Exception as e:
                    if verbose:
                        print(f"ERROR: {e}")
                    fuel_matrix[i, n] = np.nan
                
                time.sleep(API_DELAY_SECONDS)
            
            # "Return to Start" row is all zeros (can't go FROM return)
            # except diagonal which stays 0
        
        # Create DataFrame
        df = pd.DataFrame(fuel_matrix, index=labels, columns=labels)
        
        # Store distance matrix as attribute
        self.distance_matrix = pd.DataFrame(distance_matrix, index=labels, columns=labels)
        
        if verbose:
            print("\n" + "="*60)
            print("COMPLETE")
            print("="*60)
            print(f"\nFuel Matrix (liters):")
            print(df.round(3).to_string())
            
            print(f"\n--- Summary ---")
            print(f"Vehicle weight: {self.vehicle_weight_kg} kg")
            print(f"Fuel type: {self.fuel_type}")
            print(f"Include return: {self.include_return}")
            non_zero = fuel_matrix[fuel_matrix > 0]
            if len(non_zero) > 0:
                print(f"Min fuel (non-zero): {non_zero.min():.3f} L")
                print(f"Max fuel: {non_zero.max():.3f} L")
        
        return df
    
    def save_matrix(
        self,
        matrix: pd.DataFrame,
        filepath: str,
        include_distance: bool = True
    ):
        """
        Save matrix to CSV file(s).
        """
        matrix.to_csv(filepath)
        print(f"✓ Saved fuel matrix to {filepath}")
        
        if include_distance and hasattr(self, 'distance_matrix'):
            dist_path = filepath.replace('.csv', '_distance.csv')
            self.distance_matrix.to_csv(dist_path)
            print(f"✓ Saved distance matrix to {dist_path}")


# ============ MAIN (DEMO) ============

def get_api_key() -> str:
    """Get ORS API key from environment."""
    key = os.getenv("ORS_API_KEY") or os.getenv("OPENROUTESERVICE_API_KEY")
    if not key:
        raise RuntimeError(
            "OpenRouteService API key not found. Please create a .env file with ORS_API_KEY=your_key, "
            "or set OPENROUTESERVICE_API_KEY in your environment."
        )
    return key


if __name__ == "__main__":
    API_KEY = get_api_key()
    
    locations = [
        "TST BOCES Tompkins, 555 Warren Rd, Ithaca, NY 14850",                    # 0: Depot
        "DeWitt Middle School, 560 Warren Rd, Ithaca, NY 14850",                  # 1
        "Northeast Elementary School, 425 Winthrop Dr, Ithaca, NY 14850",         # 2
        "Cayuga Heights Elementary School, 110 E Upland Rd, Ithaca, NY 14850",    # 3
        "Belle Sherman Elementary School, 501 Mitchell St, Ithaca, NY 14850",     # 4
        "Caroline After School Program, 2439 Slaterville Rd, Slaterville Springs, NY 14881",  # 5
        "South Hill Elementary School, 520 Hudson St, Ithaca, NY 14850",          # 6
        "Beverly J. Martin Elementary School, 302 W Buffalo St, Ithaca, NY 14850",# 7
        "Fall Creek Elementary School, 202 King St, Ithaca, NY 14850",            # 8
        "Boynton Middle School, 1601 N Cayuga St, Ithaca, NY 14850",              # 9
        "ICSD Technology, 602 Hancock St, Ithaca, NY 14850",                      # 10
        "737 Willow Ave, Ithaca, NY 14850",                                       # 11
        "Enfield Elementary School, 20 Enfield Main Rd, Ithaca, NY 14850",        # 12
        "Lehman Alternative Community School, 111 Chestnut St, Ithaca, NY 14850", # 13
        "Tompkins County Recycling, 122 Commercial Ave, Ithaca, NY 14850",        # 14
    ]
    
    print("="*60)
    print("FUEL MATRIX BUILDER")
    print("="*60)
    
    # Example 1: Simple matrix (no return)
    print("\n--- Example 1: One-way matrix (first 4 locations) ---\n")
    
    builder = FuelMatrixBuilder(
        api_key=API_KEY,
        vehicle_weight_kg=9000,
        fuel_type='diesel',
        include_return=False
    )
    
    matrix = builder.build_matrix(locations)

    builder.save_matrix(matrix, '/Users/fli6/Desktop/Projects/pathos_model_updated/Final_Outputs/fuel_matrix.csv')