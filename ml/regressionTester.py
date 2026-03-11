"""
Fuel Consumption Prediction - Deployment Pipeline

This module provides the deployment pipeline for predicting fuel consumption
on arbitrary routes using:
    1. OpenRouteService API for route data (distance, elevation, duration)
    2. Physics-informed linear regression model trained on eVED data

The model predicts fuel consumption based on physics-informed features:
    - Distance × Weight (rolling resistance)
    - Elevation × Weight (grade resistance)  
    - Distance × Speed² (aerodynamic/efficiency effects)
    - Distance (baseline consumption)

Usage:
    from fuel_predictor import FuelPredictor
    
    predictor = FuelPredictor(api_key="your_ors_api_key")
    
    # Single route
    result = predictor.predict_route(
        origin=[-76.4966, 42.4440],      # [lon, lat]
        destination=[-76.1805, 42.6012],
        vehicle_weight_kg=9000
    )
    
    # Multi-stop route
    result = predictor.predict_multi_stop_route(
        stops=[
            [-76.4966, 42.4440],   # Start
            [-76.4799, 42.5260],   # Stop 1
            [-76.2974, 42.4908],   # Stop 2
            [-76.1805, 42.6012],   # End
        ],
        vehicle_weight_kg=9000
    )

Authors: Justin Li
Date: February 2026
"""

import openrouteservice
import joblib
import numpy as np
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path


# ============ CONSTANTS ============

# Conversion factors
CO2_KG_PER_LITER_DIESEL = 2.68      # kg CO2 per liter of diesel
CO2_KG_PER_LITER_GASOLINE = 2.31    # kg CO2 per liter of gasoline
DEFAULT_DIESEL_PRICE_PER_LITER = 1.00  # $/L (adjust as needed)

# API rate limiting
API_DELAY_SECONDS = 1.5


# ============ DATA CLASSES ============

@dataclass
class RouteData:
    """Raw route data from ORS API."""
    distance_m: float
    duration_s: float
    elevation_gain_m: float
    elevation_loss_m: float
    geometry: Optional[List] = None


@dataclass
class ModelFeatures:
    """Physics-informed features for the model."""
    total_distance_km: float
    distance_x_weight: float
    elevation_x_weight: float
    distance_x_speed_sq: float
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array in model's expected order."""
        return np.array([[
            self.total_distance_km,
            self.distance_x_weight,
            self.elevation_x_weight,
            self.distance_x_speed_sq
        ]])


@dataclass
class PredictionResult:
    """Full prediction result with breakdown."""
    # Fuel consumption
    fuel_liters: float
    fuel_gallons: float
    
    # Emissions and cost
    co2_kg: float
    cost_usd: float
    
    # Route information
    distance_km: float
    distance_miles: float
    elevation_gain_m: float
    duration_minutes: float
    average_speed_kmh: float
    
    # Vehicle
    vehicle_weight_kg: float
    
    # Efficiency metrics
    fuel_economy_l_per_100km: float
    fuel_economy_mpg: float
    
    # Model features (for transparency)
    features: Dict[str, float]
    
    def __str__(self) -> str:
        """Pretty print the result."""
        return f"""
═══════════════════════════════════════════════════════════
FUEL CONSUMPTION PREDICTION
═══════════════════════════════════════════════════════════

ROUTE SUMMARY
  Distance:        {self.distance_km:.2f} km ({self.distance_miles:.2f} mi)
  Elevation Gain:  {self.elevation_gain_m:.1f} m
  Duration:        {self.duration_minutes:.1f} minutes
  Average Speed:   {self.average_speed_kmh:.1f} km/h

VEHICLE
  Weight:          {self.vehicle_weight_kg:,.0f} kg

FUEL CONSUMPTION
  Predicted:       {self.fuel_liters:.3f} L ({self.fuel_gallons:.3f} gal)
  Efficiency:      {self.fuel_economy_l_per_100km:.1f} L/100km ({self.fuel_economy_mpg:.1f} MPG)

EMISSIONS & COST
  CO2 Emissions:   {self.co2_kg:.2f} kg
  Estimated Cost:  ${self.cost_usd:.2f}

MODEL FEATURES
  Distance (km):           {self.features['Total_Distance_km']:.4f}
  Distance × Weight:       {self.features['Distance_x_Weight']:.4f}
  Elevation × Weight:      {self.features['Elevation_x_Weight']:.4f}
  Distance × Speed²:       {self.features['Distance_x_Speed_sq']:.4f}

═══════════════════════════════════════════════════════════
"""


@dataclass 
class MultiStopResult:
    """Result for multi-stop routes."""
    # Totals
    total_fuel_liters: float
    total_fuel_gallons: float
    total_co2_kg: float
    total_cost_usd: float
    total_distance_km: float
    total_elevation_gain_m: float
    total_duration_minutes: float
    
    # Per-leg details
    legs: List[PredictionResult]
    
    # Vehicle
    vehicle_weight_kg: float
    
    # Efficiency
    overall_fuel_economy_l_per_100km: float
    overall_fuel_economy_mpg: float
    
    def __str__(self) -> str:
        """Pretty print the result."""
        lines = [
            "",
            "═" * 65,
            "MULTI-STOP ROUTE PREDICTION",
            "═" * 65,
            "",
            "ROUTE TOTALS",
            f"  Stops:           {len(self.legs) + 1}",
            f"  Total Distance:  {self.total_distance_km:.2f} km ({self.total_distance_km * 0.621371:.2f} mi)",
            f"  Elevation Gain:  {self.total_elevation_gain_m:.1f} m",
            f"  Total Duration:  {self.total_duration_minutes:.1f} minutes",
            "",
            f"VEHICLE",
            f"  Weight:          {self.vehicle_weight_kg:,.0f} kg",
            "",
            "FUEL CONSUMPTION",
            f"  Total Fuel:      {self.total_fuel_liters:.3f} L ({self.total_fuel_gallons:.3f} gal)",
            f"  Efficiency:      {self.overall_fuel_economy_l_per_100km:.1f} L/100km ({self.overall_fuel_economy_mpg:.1f} MPG)",
            "",
            "EMISSIONS & COST",
            f"  CO2 Emissions:   {self.total_co2_kg:.2f} kg",
            f"  Estimated Cost:  ${self.total_cost_usd:.2f}",
            "",
            "─" * 65,
            "LEG-BY-LEG BREAKDOWN",
            "─" * 65,
        ]
        
        for i, leg in enumerate(self.legs):
            lines.extend([
                f"",
                f"  Leg {i + 1}:",
                f"    Distance:    {leg.distance_km:.2f} km",
                f"    Elevation:   +{leg.elevation_gain_m:.1f} m",
                f"    Fuel:        {leg.fuel_liters:.3f} L ({leg.fuel_economy_l_per_100km:.1f} L/100km)",
                f"    CO2:         {leg.co2_kg:.2f} kg",
            ])
        
        lines.extend(["", "═" * 65, ""])
        
        return "\n".join(lines)


# ============ MAIN PREDICTOR CLASS ============

class FuelPredictor:
    """
    Fuel consumption predictor using physics-informed linear regression.
    
    This class:
        1. Queries OpenRouteService for route data
        2. Computes physics-informed features
        3. Uses trained model to predict fuel consumption
        4. Returns comprehensive results
    """
    
    def __init__(
        self,
        api_key: str,
        model_path: Optional[str] = None,
        fuel_price_per_liter: float = DEFAULT_DIESEL_PRICE_PER_LITER,
        co2_per_liter: float = CO2_KG_PER_LITER_DIESEL
    ):
        """
        Initialize the predictor.
        
        Args:
            api_key: OpenRouteService API key
            model_path: Path to trained model file (.joblib)
                       If None, uses default path
            fuel_price_per_liter: Fuel price in $/L for cost estimation
            co2_per_liter: CO2 emissions factor (kg CO2 per liter)
        """
        # Initialize ORS client
        self.client = openrouteservice.Client(key=api_key)
        
        # Load trained model
        if model_path is None:
            # Try common locations
            possible_paths = [
                'physics_informed_fuel_model.joblib',
                '../physics_informed_fuel_model.joblib',
                'models/physics_informed_fuel_model.joblib',
            ]
            for path in possible_paths:
                if Path(path).exists():
                    model_path = path
                    break
        
        if model_path and Path(model_path).exists():
            self.model = joblib.load(model_path)
            print(f"✓ Model loaded from: {model_path}")
            self._print_model_info()
        else:
            print("⚠ Warning: Model file not found. Using coefficient estimates.")
            self.model = None
            # Fallback coefficients from training (if model not available)
            self._fallback_coefficients = {
                'intercept': 0.009311,
                'Total_Distance_km': 0.0204307599,
                'Distance_x_Weight': 0.0000498374,
                'Elevation_x_Weight': 0.0000004255,
                'Distance_x_Speed_sq': -0.0000036306,
            }
            print("\n  Using fallback coefficients:")
            for name, value in self._fallback_coefficients.items():
                print(f"    {name}: {value}")
        
        self.fuel_price_per_liter = fuel_price_per_liter
        self.co2_per_liter = co2_per_liter
    
    def _print_model_info(self):
        """Print detailed information about the loaded model."""
        print("\n" + "─" * 50)
        print("MODEL DETAILS")
        print("─" * 50)
        
        if isinstance(self.model, dict):
            print(f"  Format: Dictionary")
            print(f"  Keys: {list(self.model.keys())}")
            
            if 'features' in self.model:
                print(f"\n  Features (in order):")
                for i, feat in enumerate(self.model['features']):
                    print(f"    [{i}] {feat}")
            
            if 'feature_formulas' in self.model:
                print(f"\n  Feature formulas:")
                for name, formula in self.model['feature_formulas'].items():
                    print(f"    {name}: {formula}")
            
            if 'model' in self.model:
                sklearn_model = self.model['model']
                print(f"\n  Sklearn model type: {type(sklearn_model).__name__}")
                
                if hasattr(sklearn_model, 'intercept_'):
                    print(f"\n  Intercept: {sklearn_model.intercept_:.6f}")
                
                if hasattr(sklearn_model, 'coef_'):
                    print(f"\n  Coefficients:")
                    feature_names = self.model.get('features', [f'feature_{i}' for i in range(len(sklearn_model.coef_))])
                    for name, coef in zip(feature_names, sklearn_model.coef_):
                        print(f"    {name}: {coef:.10f}")
        
        elif hasattr(self.model, 'coef_'):
            print(f"  Format: Sklearn model")
            print(f"  Model type: {type(self.model).__name__}")
            print(f"\n  Intercept: {self.model.intercept_:.6f}")
            print(f"\n  Coefficients:")
            for i, coef in enumerate(self.model.coef_):
                print(f"    [{i}]: {coef:.10f}")
        
        print("─" * 50 + "\n")
    
    def _query_ors(
        self,
        origin: List[float],
        destination: List[float],
        verbose: bool = True
    ) -> RouteData:
        """
        Query OpenRouteService for route data.
        
        Args:
            origin: [longitude, latitude]
            destination: [longitude, latitude]
            verbose: Print detailed output
        
        Returns:
            RouteData with distance, duration, elevation
        """
        if verbose:
            print(f"\n  📍 Querying ORS: [{origin[0]:.4f}, {origin[1]:.4f}] → [{destination[0]:.4f}, {destination[1]:.4f}]")
        
        route = self.client.directions(
            coordinates=[origin, destination],
            profile='driving-hgv',  # Heavy goods vehicle profile
            elevation=True,
            format='geojson'
        )
        
        feature = route['features'][0]
        props = feature['properties']
        summary = props['summary']
        
        route_data = RouteData(
            distance_m=summary['distance'],
            duration_s=summary['duration'],
            elevation_gain_m=props.get('ascent', 0),
            elevation_loss_m=props.get('descent', 0),
            geometry=feature['geometry']['coordinates']
        )
        
        if verbose:
            print(f"  ✓ ORS Response:")
            print(f"      Distance:       {route_data.distance_m:.1f} m ({route_data.distance_m/1000:.2f} km)")
            print(f"      Duration:       {route_data.duration_s:.1f} s ({route_data.duration_s/60:.1f} min)")
            print(f"      Elevation gain: {route_data.elevation_gain_m:.1f} m")
            print(f"      Elevation loss: {route_data.elevation_loss_m:.1f} m")
            avg_speed = (route_data.distance_m / 1000) / (route_data.duration_s / 3600) if route_data.duration_s > 0 else 0
            print(f"      Avg speed:      {avg_speed:.1f} km/h")
        
        return route_data
    
    def _compute_features(
        self,
        route_data: RouteData,
        vehicle_weight_kg: float,
        verbose: bool = True
    ) -> ModelFeatures:
        """
        Compute physics-informed features from route data.
        
        Args:
            route_data: Raw route data from ORS
            vehicle_weight_kg: Total vehicle weight in kg
            verbose: Print detailed output
        
        Returns:
            ModelFeatures ready for prediction
        """
        # Convert units
        distance_km = route_data.distance_m / 1000
        
        # Compute average speed (km/h)
        duration_hours = route_data.duration_s / 3600
        if duration_hours > 0:
            avg_speed_kmh = distance_km / duration_hours
        else:
            avg_speed_kmh = 50.0  # Default assumption
        
        # Compute physics-informed features
        features = ModelFeatures(
            total_distance_km=distance_km,
            distance_x_weight=distance_km * vehicle_weight_kg,
            elevation_x_weight=route_data.elevation_gain_m * vehicle_weight_kg,
            distance_x_speed_sq=distance_km * (avg_speed_kmh ** 2)
        )
        
        if verbose:
            print(f"\n  🔧 Computing features (weight = {vehicle_weight_kg:,} kg):")
            print(f"      Total_Distance_km:    {features.total_distance_km:.4f}")
            print(f"      Distance_x_Weight:    {features.distance_x_weight:,.2f}  ({distance_km:.2f} km × {vehicle_weight_kg:,} kg)")
            print(f"      Elevation_x_Weight:   {features.elevation_x_weight:,.2f}  ({route_data.elevation_gain_m:.1f} m × {vehicle_weight_kg:,} kg)")
            print(f"      Distance_x_Speed_sq:  {features.distance_x_speed_sq:,.2f}  ({distance_km:.2f} km × {avg_speed_kmh:.1f}² km²/h²)")
        
        return features
    
    def _predict_fuel(self, features: ModelFeatures, verbose: bool = True) -> float:
        """
        Predict fuel consumption using trained model.
        
        Args:
            features: Physics-informed features
            verbose: Print detailed output
        
        Returns:
            Predicted fuel consumption in liters
        """
        if self.model is not None:
            # Check if model is a sklearn model or a dictionary
            if hasattr(self.model, 'predict'):
                # sklearn model with predict method
                X = features.to_array()
                fuel_liters = self.model.predict(X)[0]
                if verbose:
                    print(f"\n  🧮 Prediction (sklearn model):")
                    print(f"      Input array: {X[0]}")
                    print(f"      Predicted:   {fuel_liters:.4f} L")
            elif isinstance(self.model, dict):
                # Model saved as dictionary of coefficients
                # Handle different possible dictionary formats
                if 'intercept' in self.model:
                    # Format: {'intercept': x, 'coefficients': {...}} or similar
                    c = self.model
                    if 'coefficients' in c:
                        coef = c['coefficients']
                        fuel_liters = (
                            c.get('intercept', 0) +
                            coef.get('Total_Distance_km', 0) * features.total_distance_km +
                            coef.get('Distance_x_Weight', 0) * features.distance_x_weight +
                            coef.get('Elevation_x_Weight', 0) * features.elevation_x_weight +
                            coef.get('Distance_x_Speed_sq', 0) * features.distance_x_speed_sq
                        )
                    else:
                        # Coefficients at top level
                        fuel_liters = (
                            c.get('intercept', 0) +
                            c.get('Total_Distance_km', 0) * features.total_distance_km +
                            c.get('Distance_x_Weight', 0) * features.distance_x_weight +
                            c.get('Elevation_x_Weight', 0) * features.elevation_x_weight +
                            c.get('Distance_x_Speed_sq', 0) * features.distance_x_speed_sq
                        )
                    if verbose:
                        print(f"\n  🧮 Prediction (dict coefficients):")
                        print(f"      Predicted:   {fuel_liters:.4f} L")
                elif 'model' in self.model:
                    # Format: {'model': sklearn_model, ...}
                    X = features.to_array()
                    sklearn_model = self.model['model']
                    fuel_liters = sklearn_model.predict(X)[0]
                    
                    if verbose:
                        print(f"\n  🧮 Prediction (sklearn model from dict):")
                        print(f"      Input array: {X[0]}")
                        
                        # Show contribution of each term
                        if hasattr(sklearn_model, 'intercept_') and hasattr(sklearn_model, 'coef_'):
                            print(f"\n      Breakdown:")
                            print(f"        Intercept:            {sklearn_model.intercept_:+.6f}")
                            feature_names = self.model.get('features', ['feat_0', 'feat_1', 'feat_2', 'feat_3'])
                            feature_values = [features.total_distance_km, features.distance_x_weight, 
                                            features.elevation_x_weight, features.distance_x_speed_sq]
                            total = sklearn_model.intercept_
                            for name, coef, val in zip(feature_names, sklearn_model.coef_, feature_values):
                                contribution = coef * val
                                total += contribution
                                print(f"        {name}: {coef:+.10f} × {val:.2f} = {contribution:+.6f}")
                            print(f"        ─────────────────────────────────")
                            print(f"        Total:                {total:.6f} L")
                        
                        print(f"\n      Predicted:   {fuel_liters:.4f} L")
                else:
                    # Unknown format - print keys for debugging
                    print(f"⚠ Unknown model dictionary format. Keys: {list(self.model.keys())}")
                    # Try to use fallback
                    c = self._fallback_coefficients
                    fuel_liters = (
                        c['intercept'] +
                        c['Total_Distance_km'] * features.total_distance_km +
                        c['Distance_x_Weight'] * features.distance_x_weight +
                        c['Elevation_x_Weight'] * features.elevation_x_weight +
                        c['Distance_x_Speed_sq'] * features.distance_x_speed_sq
                    )
            else:
                # Unknown type - use fallback
                print(f"⚠ Unknown model type: {type(self.model)}")
                c = self._fallback_coefficients
                fuel_liters = (
                    c['intercept'] +
                    c['Total_Distance_km'] * features.total_distance_km +
                    c['Distance_x_Weight'] * features.distance_x_weight +
                    c['Elevation_x_Weight'] * features.elevation_x_weight +
                    c['Distance_x_Speed_sq'] * features.distance_x_speed_sq
                )
        else:
            # Use fallback coefficients
            c = self._fallback_coefficients
            fuel_liters = (
                c['intercept'] +
                c['Total_Distance_km'] * features.total_distance_km +
                c['Distance_x_Weight'] * features.distance_x_weight +
                c['Elevation_x_Weight'] * features.elevation_x_weight +
                c['Distance_x_Speed_sq'] * features.distance_x_speed_sq
            )
            if verbose:
                print(f"\n  🧮 Prediction (fallback coefficients):")
                print(f"      Predicted:   {fuel_liters:.4f} L")
        
        # Ensure non-negative
        return max(0, fuel_liters)
    
    def predict_route(
        self,
        origin: List[float],
        destination: List[float],
        vehicle_weight_kg: float,
        verbose: bool = True
    ) -> PredictionResult:
        """
        Predict fuel consumption for a single route.
        
        Args:
            origin: [longitude, latitude] of start point
            destination: [longitude, latitude] of end point
            vehicle_weight_kg: Total vehicle weight in kg
            verbose: Print detailed debug output
        
        Returns:
            PredictionResult with full breakdown
        """
        if verbose:
            print(f"\n{'═' * 60}")
            print(f"PREDICTING ROUTE")
            print(f"{'═' * 60}")
            print(f"  Vehicle weight: {vehicle_weight_kg:,} kg")
        
        # Query ORS
        route_data = self._query_ors(origin, destination, verbose=verbose)
        
        # Compute features
        features = self._compute_features(route_data, vehicle_weight_kg, verbose=verbose)
        
        # Predict fuel
        fuel_liters = self._predict_fuel(features, verbose=verbose)
        fuel_gallons = fuel_liters / 3.78541
        
        # Compute derived values
        distance_km = route_data.distance_m / 1000
        distance_miles = distance_km * 0.621371
        duration_minutes = route_data.duration_s / 60
        avg_speed_kmh = distance_km / (route_data.duration_s / 3600) if route_data.duration_s > 0 else 0
        
        # Efficiency metrics
        fuel_economy_l_per_100km = (fuel_liters / distance_km) * 100 if distance_km > 0 else 0
        fuel_economy_mpg = distance_miles / fuel_gallons if fuel_gallons > 0 else float('inf')
        
        # Emissions and cost
        co2_kg = fuel_liters * self.co2_per_liter
        cost_usd = fuel_liters * self.fuel_price_per_liter
        
        if verbose:
            print(f"\n  📊 Results:")
            print(f"      Fuel:       {fuel_liters:.3f} L ({fuel_gallons:.3f} gal)")
            print(f"      Efficiency: {fuel_economy_l_per_100km:.1f} L/100km ({fuel_economy_mpg:.1f} MPG)")
            print(f"      CO2:        {co2_kg:.2f} kg")
            print(f"      Cost:       ${cost_usd:.2f}")
            print(f"{'═' * 60}\n")
        
        return PredictionResult(
            fuel_liters=fuel_liters,
            fuel_gallons=fuel_gallons,
            co2_kg=co2_kg,
            cost_usd=cost_usd,
            distance_km=distance_km,
            distance_miles=distance_miles,
            elevation_gain_m=route_data.elevation_gain_m,
            duration_minutes=duration_minutes,
            average_speed_kmh=avg_speed_kmh,
            vehicle_weight_kg=vehicle_weight_kg,
            fuel_economy_l_per_100km=fuel_economy_l_per_100km,
            fuel_economy_mpg=fuel_economy_mpg,
            features={
                'Total_Distance_km': features.total_distance_km,
                'Distance_x_Weight': features.distance_x_weight,
                'Elevation_x_Weight': features.elevation_x_weight,
                'Distance_x_Speed_sq': features.distance_x_speed_sq,
            }
        )
    
    def predict_multi_stop_route(
        self,
        stops: List[List[float]],
        vehicle_weight_kg: float,
        rate_limit: bool = True,
        verbose: bool = True
    ) -> MultiStopResult:
        """
        Predict fuel consumption for a multi-stop route.
        
        Args:
            stops: List of [longitude, latitude] coordinates
                   First stop is origin, last is final destination
            vehicle_weight_kg: Total vehicle weight in kg
            rate_limit: Whether to add delay between API calls
            verbose: Print detailed debug output
        
        Returns:
            MultiStopResult with totals and per-leg breakdown
        """
        if len(stops) < 2:
            raise ValueError("Need at least 2 stops (origin and destination)")
        
        if verbose:
            print(f"\n{'═' * 60}")
            print(f"MULTI-STOP ROUTE PREDICTION")
            print(f"{'═' * 60}")
            print(f"  Number of stops: {len(stops)}")
            print(f"  Number of legs:  {len(stops) - 1}")
            print(f"  Vehicle weight:  {vehicle_weight_kg:,} kg")
            print(f"{'─' * 60}")
        
        legs = []
        
        for i in range(len(stops) - 1):
            origin = stops[i]
            destination = stops[i + 1]
            
            if verbose:
                print(f"\n  LEG {i + 1} of {len(stops) - 1}")
            
            # Predict this leg (with reduced verbosity for legs)
            leg_result = self.predict_route(origin, destination, vehicle_weight_kg, verbose=verbose)
            legs.append(leg_result)
            
            # Rate limiting
            if rate_limit and i < len(stops) - 2:
                time.sleep(API_DELAY_SECONDS)
        
        # Compute totals
        total_fuel_liters = sum(leg.fuel_liters for leg in legs)
        total_fuel_gallons = total_fuel_liters / 3.78541
        total_co2_kg = sum(leg.co2_kg for leg in legs)
        total_cost_usd = sum(leg.cost_usd for leg in legs)
        total_distance_km = sum(leg.distance_km for leg in legs)
        total_elevation_gain_m = sum(leg.elevation_gain_m for leg in legs)
        total_duration_minutes = sum(leg.duration_minutes for leg in legs)
        
        # Overall efficiency
        total_distance_miles = total_distance_km * 0.621371
        overall_l_per_100km = (total_fuel_liters / total_distance_km) * 100 if total_distance_km > 0 else 0
        overall_mpg = total_distance_miles / total_fuel_gallons if total_fuel_gallons > 0 else float('inf')
        
        if verbose:
            print(f"\n{'─' * 60}")
            print(f"MULTI-STOP SUMMARY")
            print(f"{'─' * 60}")
            print(f"  Total distance:  {total_distance_km:.2f} km")
            print(f"  Total elevation: {total_elevation_gain_m:.1f} m")
            print(f"  Total duration:  {total_duration_minutes:.1f} min")
            print(f"  Total fuel:      {total_fuel_liters:.3f} L ({total_fuel_gallons:.3f} gal)")
            print(f"  Overall MPG:     {overall_mpg:.1f}")
            print(f"  Total CO2:       {total_co2_kg:.2f} kg")
            print(f"{'═' * 60}\n")
        
        return MultiStopResult(
            total_fuel_liters=total_fuel_liters,
            total_fuel_gallons=total_fuel_gallons,
            total_co2_kg=total_co2_kg,
            total_cost_usd=total_cost_usd,
            total_distance_km=total_distance_km,
            total_elevation_gain_m=total_elevation_gain_m,
            total_duration_minutes=total_duration_minutes,
            legs=legs,
            vehicle_weight_kg=vehicle_weight_kg,
            overall_fuel_economy_l_per_100km=overall_l_per_100km,
            overall_fuel_economy_mpg=overall_mpg
        )
    
    def compare_routes(
        self,
        origin: List[float],
        destination: List[float],
        vehicle_weight_kg: float,
        via_points_options: List[List[List[float]]],
        verbose: bool = True
    ) -> List[Tuple[int, MultiStopResult]]:
        """
        Compare multiple route options between same origin/destination.
        
        Args:
            origin: [longitude, latitude] of start
            destination: [longitude, latitude] of end
            vehicle_weight_kg: Vehicle weight in kg
            via_points_options: List of different via-point combinations
                               Each option is a list of [lon, lat] waypoints
            verbose: Print detailed debug output
        
        Returns:
            List of (option_index, result) tuples, sorted by fuel consumption
        """
        results = []
        
        for i, via_points in enumerate(via_points_options):
            if verbose:
                print(f"\n{'═' * 60}")
                print(f"ROUTE OPTION {i + 1} of {len(via_points_options)}")
                if len(via_points) == 0:
                    print(f"  (Direct route)")
                else:
                    print(f"  (Via {len(via_points)} waypoint(s))")
            
            # Build full route: origin + via_points + destination
            full_route = [origin] + via_points + [destination]
            
            result = self.predict_multi_stop_route(
                stops=full_route,
                vehicle_weight_kg=vehicle_weight_kg,
                verbose=verbose
            )
            
            results.append((i, result))
        
        # Sort by fuel consumption (lowest first)
        results.sort(key=lambda x: x[1].total_fuel_liters)
        
        return results


# ============ MAIN EXECUTION (DEMO) ============

if __name__ == "__main__":
    
    # ----- Configuration -----
    # Replace with your ORS API key
    API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM1MGEyMjY3ZTZjMDRlYmI4ZGJhZGI5ZTk5M2ZkYTY3IiwiaCI6Im11cm11cjY0In0="
    
    # Example locations (Tompkins County, NY)
    ITHACA = [-76.4966, 42.4440]
    CORTLAND = [-76.1805, 42.6012]
    DRYDEN = [-76.2974, 42.4908]
    TRUMANSBURG = [-76.6663, 42.5423]
    LANSING = [-76.4799, 42.5260]
    
    # School bus weight
    BUS_WEIGHT_KG = 9000
    
    # ----- Initialize Predictor -----
    print("=" * 65)
    print("FUEL CONSUMPTION PREDICTOR - DEMO")
    print("=" * 65)
    
    predictor = FuelPredictor(
        api_key=API_KEY,
        fuel_price_per_liter=1.00,  # $1/L diesel
        co2_per_liter=CO2_KG_PER_LITER_DIESEL
    )
    
    # ----- Demo 1: Single Route -----
    print("\n" + "─" * 65)
    print("DEMO 1: Single Route (Ithaca → Cortland)")
    print("─" * 65)
    
    result = predictor.predict_route(
        origin=ITHACA,
        destination=CORTLAND,
        vehicle_weight_kg=BUS_WEIGHT_KG
    )
    print(result)
    
    # ----- Demo 2: Multi-Stop Route -----
    print("\n" + "─" * 65)
    print("DEMO 2: Multi-Stop Route")
    print("─" * 65)
    
    multi_result = predictor.predict_multi_stop_route(
        stops=[ITHACA, LANSING, DRYDEN, CORTLAND],
        vehicle_weight_kg=BUS_WEIGHT_KG
    )
    print(multi_result)
    
    # ----- Demo 3: Route Comparison -----
    print("\n" + "─" * 65)
    print("DEMO 3: Compare Routes (Ithaca → Cortland)")
    print("─" * 65)
    
    options = [
        [],                     # Direct route
        [LANSING],              # Via Lansing
        [DRYDEN],               # Via Dryden
        [LANSING, DRYDEN],      # Via Lansing and Dryden
    ]
    
    comparisons = predictor.compare_routes(
        origin=ITHACA,
        destination=CORTLAND,
        vehicle_weight_kg=BUS_WEIGHT_KG,
        via_points_options=options
    )
    
    print("\nRoute options ranked by fuel efficiency:\n")
    for rank, (option_idx, result) in enumerate(comparisons, 1):
        via_names = ["Direct", "Via Lansing", "Via Dryden", "Via Lansing+Dryden"]
        print(f"  {rank}. {via_names[option_idx]}")
        print(f"     Fuel: {result.total_fuel_liters:.3f} L")
        print(f"     Distance: {result.total_distance_km:.2f} km")
        print(f"     CO2: {result.total_co2_kg:.2f} kg")
        print()
    
    print("=" * 65)
    print("END DEMO")
    print("=" * 65)