"""
Fuel Consumption Prediction - Production Module

A clean, production-ready module for predicting fuel consumption on routes
using physics-informed linear regression trained on eVED data.

Features:
    - Single route prediction (A → B)
    - Multi-stop route prediction (A → B → C → ...)
    - Route optimization (find best order to visit all stops)
    - Support for fixed start and/or end points

Usage:
    from fuel_predictor_prod import FuelPredictor
    
    predictor = FuelPredictor(api_key="your_ors_key")
    
    # Define stops as [lon, lat] coordinates
    stops = [
        [-76.4966, 42.4440],  # Ithaca (depot)
        [-76.4799, 42.5260],  # Lansing
        [-76.2974, 42.4908],  # Dryden
        [-76.1805, 42.6012],  # Cortland
    ]
    
    # Optimize route starting from first stop, returning to start
    result = predictor.optimize_route(
        stops=stops,
        start_index=0,
        return_to_start=True,
        vehicle_weight_kg=9000
    )
    
    print(f"Optimal order: {result['optimal_order']}")
    print(f"Total fuel: {result['total_fuel_liters']:.2f} L")

Authors: Justin Li
Date: February 2026
"""

import openrouteservice
import joblib
import numpy as np
import time
from itertools import permutations
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict, Any, Union
from pathlib import Path


# ============ CONSTANTS ============

CO2_KG_PER_LITER_DIESEL = 2.68
CO2_KG_PER_LITER_GASOLINE = 2.31
DEFAULT_FUEL_PRICE_PER_LITER = 1.00
API_DELAY_SECONDS = 1.5


# ============ DATA CLASSES ============

@dataclass
class LegResult:
    """Result for a single leg of a route."""
    origin_index: int
    destination_index: int
    distance_km: float
    duration_minutes: float
    elevation_gain_m: float
    average_speed_kmh: float
    fuel_liters: float
    fuel_gallons: float
    co2_kg: float
    cost_usd: float
    fuel_economy_l_per_100km: float
    fuel_economy_mpg: float


@dataclass
class RouteResult:
    """Complete result for a multi-stop route."""
    # Route order
    stop_order: List[int]
    num_stops: int
    num_legs: int
    
    # Totals
    total_distance_km: float
    total_duration_minutes: float
    total_elevation_gain_m: float
    total_fuel_liters: float
    total_fuel_gallons: float
    total_co2_kg: float
    total_cost_usd: float
    
    # Efficiency
    overall_fuel_economy_l_per_100km: float
    overall_fuel_economy_mpg: float
    
    # Vehicle
    vehicle_weight_kg: float
    
    # Leg details
    legs: List[LegResult]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = asdict(self)
        result['legs'] = [asdict(leg) for leg in self.legs]
        return result


# ============ MAIN PREDICTOR CLASS ============

class FuelPredictor:
    """
    Production fuel consumption predictor.
    
    Uses physics-informed linear regression to predict fuel consumption
    based on distance, elevation, speed, and vehicle weight.
    """
    
    def __init__(
        self,
        api_key: str,
        model_path: Optional[str] = None,
        fuel_price_per_liter: float = DEFAULT_FUEL_PRICE_PER_LITER,
        co2_per_liter: float = CO2_KG_PER_LITER_DIESEL
    ):
        """
        Initialize the predictor.
        
        Args:
            api_key: OpenRouteService API key
            model_path: Path to trained model (.joblib). Auto-detected if None.
            fuel_price_per_liter: Fuel price in $/L
            co2_per_liter: CO2 emissions factor (kg/L)
        """
        self.client = openrouteservice.Client(key=api_key)
        self.fuel_price_per_liter = fuel_price_per_liter
        self.co2_per_liter = co2_per_liter
        
        # Load model
        self.model = None
        self.sklearn_model = None
        
        if model_path is None:
            for path in ['physics_informed_fuel_model.joblib',
                        '../physics_informed_fuel_model.joblib',
                        'models/physics_informed_fuel_model.joblib']:
                if Path(path).exists():
                    model_path = path
                    break
        
        if model_path and Path(model_path).exists():
            self.model = joblib.load(model_path)
            if isinstance(self.model, dict) and 'model' in self.model:
                self.sklearn_model = self.model['model']
            elif hasattr(self.model, 'predict'):
                self.sklearn_model = self.model
        
        # Fallback coefficients if model not found
        self._coefficients = {
            'intercept': 0.009311,
            'Total_Distance_km': 0.0204307599,
            'Distance_x_Weight': 0.0000498374,
            'Elevation_x_Weight': 0.0000004255,
            'Distance_x_Speed_sq': -0.0000036306,
        }
    
    def _query_ors(
        self,
        origin: List[float],
        destination: List[float]
    ) -> Dict:
        """Query OpenRouteService for route data."""
        route = self.client.directions(
            coordinates=[origin, destination],
            profile='driving-hgv',
            elevation=True,
            format='geojson'
        )
        
        feature = route['features'][0]
        props = feature['properties']
        summary = props['summary']
        
        return {
            'distance_m': summary['distance'],
            'duration_s': summary['duration'],
            'elevation_gain_m': props.get('ascent', 0),
            'elevation_loss_m': props.get('descent', 0),
        }
    
    def _compute_features(
        self,
        distance_km: float,
        elevation_gain_m: float,
        avg_speed_kmh: float,
        vehicle_weight_kg: float
    ) -> np.ndarray:
        """Compute physics-informed features."""
        return np.array([[
            distance_km,
            distance_km * vehicle_weight_kg,
            elevation_gain_m * vehicle_weight_kg,
            distance_km * (avg_speed_kmh ** 2)
        ]])
    
    def _predict_fuel(
        self,
        distance_km: float,
        elevation_gain_m: float,
        avg_speed_kmh: float,
        vehicle_weight_kg: float
    ) -> float:
        """Predict fuel consumption in liters."""
        features = self._compute_features(
            distance_km, elevation_gain_m, avg_speed_kmh, vehicle_weight_kg
        )
        
        if self.sklearn_model is not None:
            fuel_liters = self.sklearn_model.predict(features)[0]
        else:
            c = self._coefficients
            fuel_liters = (
                c['intercept'] +
                c['Total_Distance_km'] * distance_km +
                c['Distance_x_Weight'] * (distance_km * vehicle_weight_kg) +
                c['Elevation_x_Weight'] * (elevation_gain_m * vehicle_weight_kg) +
                c['Distance_x_Speed_sq'] * (distance_km * avg_speed_kmh ** 2)
            )
        
        return max(0, fuel_liters)
    
    def predict_leg(
        self,
        origin: List[float],
        destination: List[float],
        vehicle_weight_kg: float,
        origin_index: int = 0,
        destination_index: int = 1
    ) -> LegResult:
        """
        Predict fuel consumption for a single leg.
        
        Args:
            origin: [longitude, latitude]
            destination: [longitude, latitude]
            vehicle_weight_kg: Vehicle weight in kg
            origin_index: Index of origin in stops list
            destination_index: Index of destination in stops list
        
        Returns:
            LegResult with all metrics
        """
        # Query ORS
        route_data = self._query_ors(origin, destination)
        
        # Extract values
        distance_km = route_data['distance_m'] / 1000
        duration_minutes = route_data['duration_s'] / 60
        elevation_gain_m = route_data['elevation_gain_m']
        
        # Compute speed
        duration_hours = route_data['duration_s'] / 3600
        avg_speed_kmh = distance_km / duration_hours if duration_hours > 0 else 50.0
        
        # Predict fuel
        fuel_liters = self._predict_fuel(
            distance_km, elevation_gain_m, avg_speed_kmh, vehicle_weight_kg
        )
        fuel_gallons = fuel_liters / 3.78541
        
        # Compute derived metrics
        distance_miles = distance_km * 0.621371
        fuel_economy_l_per_100km = (fuel_liters / distance_km) * 100 if distance_km > 0 else 0
        fuel_economy_mpg = distance_miles / fuel_gallons if fuel_gallons > 0 else float('inf')
        
        co2_kg = fuel_liters * self.co2_per_liter
        cost_usd = fuel_liters * self.fuel_price_per_liter
        
        return LegResult(
            origin_index=origin_index,
            destination_index=destination_index,
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            elevation_gain_m=elevation_gain_m,
            average_speed_kmh=avg_speed_kmh,
            fuel_liters=fuel_liters,
            fuel_gallons=fuel_gallons,
            co2_kg=co2_kg,
            cost_usd=cost_usd,
            fuel_economy_l_per_100km=fuel_economy_l_per_100km,
            fuel_economy_mpg=fuel_economy_mpg
        )
    
    def predict_route(
        self,
        stops: List[List[float]],
        stop_order: List[int],
        vehicle_weight_kg: float,
        rate_limit: bool = True
    ) -> RouteResult:
        """
        Predict fuel consumption for a route with specified stop order.
        
        Args:
            stops: List of [longitude, latitude] coordinates
            stop_order: Order to visit stops (list of indices into stops)
            vehicle_weight_kg: Vehicle weight in kg
            rate_limit: Add delay between API calls
        
        Returns:
            RouteResult with totals and leg details
        """
        if len(stop_order) < 2:
            raise ValueError("Need at least 2 stops")
        
        legs = []
        
        for i in range(len(stop_order) - 1):
            origin_idx = stop_order[i]
            dest_idx = stop_order[i + 1]
            
            leg = self.predict_leg(
                origin=stops[origin_idx],
                destination=stops[dest_idx],
                vehicle_weight_kg=vehicle_weight_kg,
                origin_index=origin_idx,
                destination_index=dest_idx
            )
            legs.append(leg)
            
            if rate_limit and i < len(stop_order) - 2:
                time.sleep(API_DELAY_SECONDS)
        
        # Compute totals
        total_distance_km = sum(leg.distance_km for leg in legs)
        total_duration_minutes = sum(leg.duration_minutes for leg in legs)
        total_elevation_gain_m = sum(leg.elevation_gain_m for leg in legs)
        total_fuel_liters = sum(leg.fuel_liters for leg in legs)
        total_fuel_gallons = total_fuel_liters / 3.78541
        total_co2_kg = sum(leg.co2_kg for leg in legs)
        total_cost_usd = sum(leg.cost_usd for leg in legs)
        
        # Overall efficiency
        total_distance_miles = total_distance_km * 0.621371
        overall_l_per_100km = (total_fuel_liters / total_distance_km) * 100 if total_distance_km > 0 else 0
        overall_mpg = total_distance_miles / total_fuel_gallons if total_fuel_gallons > 0 else float('inf')
        
        return RouteResult(
            stop_order=stop_order,
            num_stops=len(stop_order),
            num_legs=len(legs),
            total_distance_km=total_distance_km,
            total_duration_minutes=total_duration_minutes,
            total_elevation_gain_m=total_elevation_gain_m,
            total_fuel_liters=total_fuel_liters,
            total_fuel_gallons=total_fuel_gallons,
            total_co2_kg=total_co2_kg,
            total_cost_usd=total_cost_usd,
            overall_fuel_economy_l_per_100km=overall_l_per_100km,
            overall_fuel_economy_mpg=overall_mpg,
            vehicle_weight_kg=vehicle_weight_kg,
            legs=legs
        )
    
    def build_fuel_matrix(
        self,
        stops: List[List[float]],
        vehicle_weight_kg: float,
        rate_limit: bool = True
    ) -> np.ndarray:
        """
        Build a matrix of fuel consumption between all pairs of stops.
        
        Args:
            stops: List of [longitude, latitude] coordinates
            vehicle_weight_kg: Vehicle weight in kg
            rate_limit: Add delay between API calls
        
        Returns:
            NxN numpy array where matrix[i][j] = fuel (liters) from stop i to stop j
        """
        n = len(stops)
        matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                
                leg = self.predict_leg(
                    origin=stops[i],
                    destination=stops[j],
                    vehicle_weight_kg=vehicle_weight_kg,
                    origin_index=i,
                    destination_index=j
                )
                matrix[i][j] = leg.fuel_liters
                
                if rate_limit:
                    time.sleep(API_DELAY_SECONDS)
        
        return matrix
    
    def optimize_route(
        self,
        stops: List[List[float]],
        vehicle_weight_kg: float,
        start_index: int = 0,
        end_index: Optional[int] = None,
        return_to_start: bool = False,
        stop_names: Optional[List[str]] = None,
        rate_limit: bool = True
    ) -> Dict[str, Any]:
        """
        Find the optimal order to visit all stops minimizing fuel consumption.
        
        Uses brute-force permutation search (suitable for < 10 stops).
        
        Args:
            stops: List of [longitude, latitude] coordinates
            vehicle_weight_kg: Vehicle weight in kg
            start_index: Index of starting stop (must visit first)
            end_index: Index of ending stop (must visit last). If None, can end anywhere.
            return_to_start: If True, return to start_index at end (overrides end_index)
            stop_names: Optional list of stop names for display
            rate_limit: Add delay between API calls
        
        Returns:
            Dictionary containing:
                - optimal_order: List of stop indices in optimal order
                - optimal_order_names: List of stop names (if provided)
                - total_fuel_liters: Total fuel for optimal route
                - total_distance_km: Total distance
                - total_co2_kg: Total CO2 emissions
                - route_result: Full RouteResult object
                - all_permutations: List of all evaluated orderings with fuel (for analysis)
        """
        n = len(stops)
        
        if n > 10:
            raise ValueError(f"Too many stops ({n}) for brute-force optimization. Max is 10.")
        
        # Build fuel matrix
        fuel_matrix = self.build_fuel_matrix(stops, vehicle_weight_kg, rate_limit)
        
        # Determine which stops to permute
        fixed_start = start_index
        fixed_end = end_index
        
        if return_to_start:
            fixed_end = start_index
        
        # Get intermediate stops (those that can be reordered)
        all_indices = set(range(n))
        fixed_indices = {fixed_start}
        if fixed_end is not None and fixed_end != fixed_start:
            fixed_indices.add(fixed_end)
        
        intermediate_indices = list(all_indices - fixed_indices)
        
        # Evaluate all permutations
        best_order = None
        best_fuel = float('inf')
        all_results = []
        
        for perm in permutations(intermediate_indices):
            # Build full order
            order = [fixed_start] + list(perm)
            if fixed_end is not None:
                if return_to_start:
                    order.append(fixed_start)
                elif fixed_end != fixed_start:
                    order.append(fixed_end)
            
            # Calculate total fuel using matrix
            total_fuel = 0
            for i in range(len(order) - 1):
                total_fuel += fuel_matrix[order[i]][order[i + 1]]
            
            all_results.append({
                'order': order,
                'fuel_liters': total_fuel
            })
            
            if total_fuel < best_fuel:
                best_fuel = total_fuel
                best_order = order
        
        # Sort all results by fuel
        all_results.sort(key=lambda x: x['fuel_liters'])
        
        # Get detailed result for optimal route
        optimal_result = self.predict_route(
            stops=stops,
            stop_order=best_order,
            vehicle_weight_kg=vehicle_weight_kg,
            rate_limit=rate_limit
        )
        
        # Build response
        response = {
            'optimal_order': best_order,
            'total_fuel_liters': optimal_result.total_fuel_liters,
            'total_fuel_gallons': optimal_result.total_fuel_gallons,
            'total_distance_km': optimal_result.total_distance_km,
            'total_duration_minutes': optimal_result.total_duration_minutes,
            'total_elevation_gain_m': optimal_result.total_elevation_gain_m,
            'total_co2_kg': optimal_result.total_co2_kg,
            'total_cost_usd': optimal_result.total_cost_usd,
            'fuel_economy_mpg': optimal_result.overall_fuel_economy_mpg,
            'fuel_economy_l_per_100km': optimal_result.overall_fuel_economy_l_per_100km,
            'vehicle_weight_kg': vehicle_weight_kg,
            'num_stops': len(stops),
            'route_result': optimal_result,
            'fuel_matrix': fuel_matrix,
            'all_permutations': all_results,
        }
        
        if stop_names:
            response['optimal_order_names'] = [stop_names[i] for i in best_order]
            response['all_permutations'] = [
                {
                    'order': r['order'],
                    'order_names': [stop_names[i] for i in r['order']],
                    'fuel_liters': r['fuel_liters']
                }
                for r in all_results
            ]
        
        return response
    
    def predict_simple(
        self,
        stops: List[List[float]],
        vehicle_weight_kg: float,
        rate_limit: bool = True
    ) -> RouteResult:
        """
        Simple prediction: visit stops in the order given.
        
        Args:
            stops: List of [longitude, latitude] coordinates in order
            vehicle_weight_kg: Vehicle weight in kg
            rate_limit: Add delay between API calls
        
        Returns:
            RouteResult for the route
        """
        stop_order = list(range(len(stops)))
        return self.predict_route(stops, stop_order, vehicle_weight_kg, rate_limit)


# ============ CONVENIENCE FUNCTIONS ============

def create_predictor(api_key: str, model_path: Optional[str] = None) -> FuelPredictor:
    """Create a FuelPredictor instance."""
    return FuelPredictor(api_key=api_key, model_path=model_path)


def quick_predict(
    api_key: str,
    stops: List[List[float]],
    vehicle_weight_kg: float,
    optimize: bool = False,
    start_index: int = 0,
    return_to_start: bool = False
) -> Dict:
    """
    Quick prediction without creating a predictor object.
    
    Args:
        api_key: OpenRouteService API key
        stops: List of [longitude, latitude] coordinates
        vehicle_weight_kg: Vehicle weight in kg
        optimize: If True, find optimal ordering
        start_index: Starting stop index (for optimization)
        return_to_start: Return to start at end (for optimization)
    
    Returns:
        Dictionary with results
    """
    predictor = FuelPredictor(api_key=api_key)
    
    if optimize:
        return predictor.optimize_route(
            stops=stops,
            vehicle_weight_kg=vehicle_weight_kg,
            start_index=start_index,
            return_to_start=return_to_start
        )
    else:
        result = predictor.predict_simple(stops, vehicle_weight_kg)
        return result.to_dict()


# ============ MAIN (DEMO) ============

if __name__ == "__main__":
    
    # Configuration
    API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM1MGEyMjY3ZTZjMDRlYmI4ZGJhZGI5ZTk5M2ZkYTY3IiwiaCI6Im11cm11cjY0In0="
    
    # Example stops
    stops = [
        [-76.4966, 42.4440],  # 0: Ithaca (depot)
        [-76.4799, 42.5260],  # 1: Lansing
        [-76.2974, 42.4908],  # 2: Dryden
        [-76.1805, 42.6012],  # 3: Cortland
        [-76.6663, 42.5423],  # 4: Trumansburg
    ]
    
    stop_names = ["Ithaca", "Lansing", "Dryden", "Cortland", "Trumansburg"]
    
    # Create predictor
    predictor = FuelPredictor(api_key=API_KEY)
    
    print("=" * 60)
    print("FUEL PREDICTOR - PRODUCTION DEMO")
    print("=" * 60)
    
    # Demo 1: Simple route (visit in order)
    print("\n--- Demo 1: Simple Route (In Order) ---")
    result = predictor.predict_simple(
        stops=stops[:4],
        vehicle_weight_kg=9000
    )
    print(f"Order: {[stop_names[i] for i in result.stop_order]}")
    print(f"Total fuel: {result.total_fuel_liters:.2f} L ({result.total_fuel_gallons:.2f} gal)")
    print(f"Total distance: {result.total_distance_km:.2f} km")
    print(f"Total CO2: {result.total_co2_kg:.2f} kg")
    print(f"Efficiency: {result.overall_fuel_economy_mpg:.1f} MPG")
    
    # Demo 2: Optimized route
    print("\n--- Demo 2: Optimized Route ---")
    opt_result = predictor.optimize_route(
        stops=stops[:4],
        vehicle_weight_kg=9000,
        start_index=0,
        return_to_start=True,
        stop_names=stop_names[:4]
    )
    print(f"Optimal order: {opt_result['optimal_order_names']}")
    print(f"Total fuel: {opt_result['total_fuel_liters']:.2f} L")
    print(f"Total distance: {opt_result['total_distance_km']:.2f} km")
    print(f"Total CO2: {opt_result['total_co2_kg']:.2f} kg")
    
    # Show all permutations
    print("\nAll route options (ranked by fuel):")
    for i, perm in enumerate(opt_result['all_permutations'][:5]):
        print(f"  {i+1}. {' → '.join(perm['order_names'])}: {perm['fuel_liters']:.2f} L")
    
    print("\n" + "=" * 60)
    print("END DEMO")
    print("=" * 60)