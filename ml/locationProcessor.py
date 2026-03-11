"""
Geocoding Helper for Fuel Predictor

Converts location names (addresses, place names) to [longitude, latitude] coordinates
using OpenRouteService's geocoding API.

Usage:
    from geocode_helper import Geocoder
    
    geocoder = Geocoder(api_key="your_ors_key")
    
    # Single location
    coords = geocoder.geocode("Ithaca High School, Ithaca, NY")
    print(coords)  # [-76.4966, 42.4440]
    
    # Multiple locations
    locations = [
        "Ithaca High School, Ithaca, NY",
        "Cortland High School, Cortland, NY",
        "Dryden Central School, Dryden, NY"
    ]
    results = geocoder.geocode_batch(locations)
    
    # Use with FuelPredictor
    from fuel_predictor_prod import FuelPredictor
    predictor = FuelPredictor(api_key="your_key")
    result = predictor.predict_simple(
        stops=[r['coords'] for r in results],
        vehicle_weight_kg=9000
    )

Authors: Justin Li
Date: February 2026
"""

import openrouteservice
import time
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass


# ============ CONSTANTS ============

API_DELAY_SECONDS = 1.0


# ============ DATA CLASSES ============

@dataclass
class GeocodedLocation:
    """Result from geocoding a location name."""
    original_name: str
    formatted_address: str
    coords: List[float]  # [longitude, latitude]
    longitude: float
    latitude: float
    confidence: float
    source: str
    
    def __str__(self):
        return f"{self.original_name} → [{self.longitude:.4f}, {self.latitude:.4f}]"


# ============ GEOCODER CLASS ============

class Geocoder:
    """
    Geocodes location names to coordinates using OpenRouteService.
    """
    
    def __init__(
        self,
        api_key: str,
        default_country: str = "USA",
        default_region: Optional[str] = None
    ):
        """
        Initialize the geocoder.
        
        Args:
            api_key: OpenRouteService API key
            default_country: Default country for searches (helps accuracy)
            default_region: Default region/state for searches
        """
        self.client = openrouteservice.Client(key=api_key)
        self.default_country = default_country
        self.default_region = default_region
    
    def geocode(
        self,
        location_name: str,
        country: Optional[str] = None,
        region: Optional[str] = None
    ) -> Optional[GeocodedLocation]:
        """
        Geocode a single location name to coordinates.
        
        Args:
            location_name: Address or place name to geocode
            country: Country to restrict search (e.g., "USA")
            region: Region/state to restrict search (e.g., "New York")
        
        Returns:
            GeocodedLocation object, or None if not found
        """
        try:
            # Build search query
            query = location_name
            
            # Add region/country context if not already in query
            if region or self.default_region:
                r = region or self.default_region
                if r.lower() not in query.lower():
                    query = f"{query}, {r}"
            
            if country or self.default_country:
                c = country or self.default_country
                if c.lower() not in query.lower():
                    query = f"{query}, {c}"
            
            # Call ORS geocoding API
            result = self.client.pelias_search(
                text=query,
                size=1,  # Only need top result
                country=country or self.default_country
            )
            
            if result and 'features' in result and len(result['features']) > 0:
                feature = result['features'][0]
                coords = feature['geometry']['coordinates']  # [lon, lat]
                props = feature['properties']
                
                return GeocodedLocation(
                    original_name=location_name,
                    formatted_address=props.get('label', location_name),
                    coords=coords,
                    longitude=coords[0],
                    latitude=coords[1],
                    confidence=props.get('confidence', 0),
                    source=props.get('source', 'unknown')
                )
            else:
                return None
                
        except Exception as e:
            print(f"Error geocoding '{location_name}': {e}")
            return None
    
    def geocode_batch(
        self,
        location_names: List[str],
        country: Optional[str] = None,
        region: Optional[str] = None,
        rate_limit: bool = True,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Geocode multiple location names.
        
        Args:
            location_names: List of addresses or place names
            country: Country to restrict search
            region: Region/state to restrict search
            rate_limit: Add delay between API calls
            verbose: Print progress
        
        Returns:
            List of dictionaries with:
                - name: Original location name
                - coords: [longitude, latitude] or None if failed
                - formatted_address: Full address from geocoder
                - success: Boolean indicating if geocoding succeeded
        """
        results = []
        
        for i, name in enumerate(location_names):
            if verbose:
                print(f"Geocoding [{i+1}/{len(location_names)}]: {name}...", end=" ")
            
            location = self.geocode(name, country, region)
            
            if location:
                results.append({
                    'index': i,
                    'name': name,
                    'coords': location.coords,
                    'longitude': location.longitude,
                    'latitude': location.latitude,
                    'formatted_address': location.formatted_address,
                    'confidence': location.confidence,
                    'success': True
                })
                if verbose:
                    print(f"✓ [{location.longitude:.4f}, {location.latitude:.4f}]")
            else:
                results.append({
                    'index': i,
                    'name': name,
                    'coords': None,
                    'longitude': None,
                    'latitude': None,
                    'formatted_address': None,
                    'confidence': 0,
                    'success': False
                })
                if verbose:
                    print("✗ NOT FOUND")
            
            if rate_limit and i < len(location_names) - 1:
                time.sleep(API_DELAY_SECONDS)
        
        return results
    
    def geocode_to_coords_list(
        self,
        location_names: List[str],
        country: Optional[str] = None,
        region: Optional[str] = None,
        rate_limit: bool = True,
        verbose: bool = True
    ) -> List[List[float]]:
        """
        Geocode multiple locations and return just the coordinates list.
        
        Raises an error if any location fails to geocode.
        
        Args:
            location_names: List of addresses or place names
            country: Country to restrict search
            region: Region/state to restrict search
            rate_limit: Add delay between API calls
            verbose: Print progress
        
        Returns:
            List of [longitude, latitude] coordinates
        """
        results = self.geocode_batch(
            location_names, country, region, rate_limit, verbose
        )
        
        # Check for failures
        failed = [r for r in results if not r['success']]
        if failed:
            failed_names = [r['name'] for r in failed]
            raise ValueError(f"Failed to geocode: {failed_names}")
        
        return [r['coords'] for r in results]


# ============ CONVENIENCE FUNCTIONS ============

def geocode_locations(
    api_key: str,
    locations: List[str],
    region: Optional[str] = None
) -> List[List[float]]:
    """
    Quick function to geocode a list of location names.
    
    Args:
        api_key: OpenRouteService API key
        locations: List of location names/addresses
        region: Region to help with accuracy (e.g., "New York")
    
    Returns:
        List of [longitude, latitude] coordinates
    """
    geocoder = Geocoder(api_key=api_key, default_region=region)
    return geocoder.geocode_to_coords_list(locations)


def locations_to_route(
    api_key: str,
    location_names: List[str],
    vehicle_weight_kg: float,
    region: Optional[str] = None,
    optimize: bool = False,
    start_index: int = 0,
    return_to_start: bool = False
) -> Dict[str, Any]:
    """
    All-in-one function: geocode locations and predict/optimize route.
    
    Args:
        api_key: OpenRouteService API key
        location_names: List of location names/addresses
        vehicle_weight_kg: Vehicle weight in kg
        region: Region to help with geocoding accuracy
        optimize: If True, find optimal route ordering
        start_index: Starting location index (for optimization)
        return_to_start: Return to start at end (for optimization)
    
    Returns:
        Dictionary with:
            - locations: Geocoded location info
            - route_result: Route prediction result
            - optimal_order_names: (if optimize=True) Names in optimal order
    """
    # Import here to avoid circular dependency
    from prod_tester import FuelPredictor
    
    # Geocode locations
    geocoder = Geocoder(api_key=api_key, default_region=region)
    geocoded = geocoder.geocode_batch(location_names)
    
    # Check for failures
    failed = [g for g in geocoded if not g['success']]
    if failed:
        raise ValueError(f"Failed to geocode: {[f['name'] for f in failed]}")
    
    # Extract coordinates
    coords = [g['coords'] for g in geocoded]
    
    # Create predictor and run
    predictor = FuelPredictor(api_key=api_key)
    
    if optimize:
        result = predictor.optimize_route(
            stops=coords,
            vehicle_weight_kg=vehicle_weight_kg,
            start_index=start_index,
            return_to_start=return_to_start,
            stop_names=location_names
        )
        return {
            'locations': geocoded,
            'route_result': result,
            'optimal_order': result['optimal_order'],
            'optimal_order_names': result['optimal_order_names'],
            'total_fuel_liters': result['total_fuel_liters'],
            'total_distance_km': result['total_distance_km'],
            'total_co2_kg': result['total_co2_kg'],
        }
    else:
        result = predictor.predict_simple(coords, vehicle_weight_kg)
        return {
            'locations': geocoded,
            'route_result': result.to_dict(),
            'stop_order': list(range(len(location_names))),
            'stop_order_names': location_names,
            'total_fuel_liters': result.total_fuel_liters,
            'total_distance_km': result.total_distance_km,
            'total_co2_kg': result.total_co2_kg,
        }


# ============ MAIN (DEMO) ============

if __name__ == "__main__":
    
    # Configuration
    API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM1MGEyMjY3ZTZjMDRlYmI4ZGJhZGI5ZTk5M2ZkYTY3IiwiaCI6Im11cm11cjY0In0="
    
    # Example locations (names, not coordinates)
    locations = [
        "TST BOCES Tompkins, 555 Warren Rd, Ithaca, NY 14850",                    # 0: Start
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
    
    print("=" * 60)
    print("GEOCODING DEMO")
    print("=" * 60)
    
    # Create geocoder
    geocoder = Geocoder(api_key=API_KEY, default_region="New York")
    
    # Geocode all locations
    print("\n--- Geocoding Locations ---")
    results = geocoder.geocode_batch(locations)
    
    print("\n--- Results ---")
    for r in results:
        if r['success']:
            print(f"  ✓ {r['name']}")
            print(f"    → {r['formatted_address']}")
            print(f"    → [{r['longitude']:.4f}, {r['latitude']:.4f}]")
        else:
            print(f"  ✗ {r['name']} - NOT FOUND")
    
    # Get just coordinates
    print("\n--- Coordinates List ---")
    try:
        coords = geocoder.geocode_to_coords_list(locations)
        print(f"  {coords}")
    except ValueError as e:
        print(f"  Error: {e}")
    
    # All-in-one route prediction
    print("\n--- All-in-One Route Prediction ---")
    try:
        route_result = locations_to_route(
            api_key=API_KEY,
            location_names=locations,
            vehicle_weight_kg=9000,
            region="New York",
            optimize=False
        )
        print(f"  Total fuel: {route_result['total_fuel_liters']:.2f} L")
        print(f"  Total distance: {route_result['total_distance_km']:.2f} km")
        print(f"  Total CO2: {route_result['total_co2_kg']:.2f} kg")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n" + "=" * 60)
    print("END DEMO")
    print("=" * 60)