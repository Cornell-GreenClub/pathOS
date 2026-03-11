"""
TST BOCES Route Fuel Calculation

Calculates fuel consumption for the actual route as driven,
visiting stops in the specified order and returning to start.
"""

from prod_tester import FuelPredictor
from locationProcessor import Geocoder
import time

# ============ CONFIGURATION ============

API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImM1MGEyMjY3ZTZjMDRlYmI4ZGJhZGI5ZTk5M2ZkYTY3IiwiaCI6Im11cm11cjY0In0="  # Replace with your key

VEHICLE_WEIGHT_KG = 9000  # School bus weight (adjust as needed)

# Route stops IN ORDER (as driven)
LOCATIONS = [
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


# ============ MAIN ============

def main():
    print("=" * 70)
    print("TST BOCES ROUTE - FUEL CALCULATION")
    print("=" * 70)
    
    # Step 1: Geocode locations
    print("\n[1/3] Geocoding locations...")
    geocoder = Geocoder(api_key=API_KEY, default_region="New York")
    
    geocoded = geocoder.geocode_batch(LOCATIONS, verbose=True)
    
    # Check for failures
    failed = [g for g in geocoded if not g['success']]
    if failed:
        print(f"\n❌ Failed to geocode {len(failed)} locations:")
        for f in failed:
            print(f"   - {f['name']}")
        return
    
    # Extract coordinates
    coords = [g['coords'] for g in geocoded]
    
    # Add return to start
    coords.append(coords[0])
    stop_names = [g['name'].split(',')[0] for g in geocoded]  # Short names
    stop_names.append(stop_names[0])  # Return to start
    
    print(f"\n✓ All {len(LOCATIONS)} locations geocoded successfully")
    print(f"✓ Route: {len(coords)} stops (including return to start)")
    
    # Step 2: Calculate fuel for each leg
    print("\n[2/3] Calculating fuel for each leg...")
    print("-" * 70)
    
    predictor = FuelPredictor(api_key=API_KEY)
    
    legs = []
    total_fuel = 0
    total_distance = 0
    total_elevation = 0
    total_duration = 0
    
    for i in range(len(coords) - 1):
        origin = coords[i]
        destination = coords[i + 1]
        origin_name = stop_names[i]
        dest_name = stop_names[i + 1]
        
        print(f"\n  Leg {i + 1}: {origin_name} → {dest_name}")
        
        leg = predictor.predict_leg(
            origin=origin,
            destination=destination,
            vehicle_weight_kg=VEHICLE_WEIGHT_KG,
            origin_index=i,
            destination_index=i + 1
        )
        
        legs.append({
            'leg': i + 1,
            'from': origin_name,
            'to': dest_name,
            'distance_km': leg.distance_km,
            'elevation_gain_m': leg.elevation_gain_m,
            'duration_min': leg.duration_minutes,
            'fuel_liters': leg.fuel_liters,
            'fuel_economy_mpg': leg.fuel_economy_mpg,
        })
        
        total_fuel += leg.fuel_liters
        total_distance += leg.distance_km
        total_elevation += leg.elevation_gain_m
        total_duration += leg.duration_minutes
        
        print(f"      Distance: {leg.distance_km:.2f} km")
        print(f"      Elevation: +{leg.elevation_gain_m:.1f} m")
        print(f"      Fuel: {leg.fuel_liters:.3f} L ({leg.fuel_economy_mpg:.1f} MPG)")
        
        time.sleep(1.5)  # Rate limiting
    
    # Step 3: Summary
    print("\n" + "=" * 70)
    print("[3/3] ROUTE SUMMARY")
    print("=" * 70)
    
    total_fuel_gallons = total_fuel / 3.78541
    total_distance_miles = total_distance * 0.621371
    overall_mpg = total_distance_miles / total_fuel_gallons if total_fuel_gallons > 0 else 0
    overall_l_per_100km = (total_fuel / total_distance) * 100 if total_distance > 0 else 0
    co2_kg = total_fuel * 2.68
    
    print(f"""
ROUTE
  Stops:              {len(LOCATIONS)} locations + return to start
  Total Distance:     {total_distance:.2f} km ({total_distance_miles:.2f} miles)
  Total Elevation:    {total_elevation:.1f} m gain
  Total Duration:     {total_duration:.1f} minutes ({total_duration/60:.2f} hours)

VEHICLE
  Weight:             {VEHICLE_WEIGHT_KG:,} kg

FUEL CONSUMPTION
  Total Fuel:         {total_fuel:.3f} L ({total_fuel_gallons:.3f} gallons)
  Fuel Economy:       {overall_l_per_100km:.1f} L/100km ({overall_mpg:.1f} MPG)

EMISSIONS
  CO2 Emissions:      {co2_kg:.2f} kg
""")
    
    # Leg-by-leg table
    print("-" * 70)
    print("LEG-BY-LEG BREAKDOWN")
    print("-" * 70)
    print(f"{'Leg':<4} {'From':<25} {'To':<25} {'Dist (km)':<10} {'Fuel (L)':<10}")
    print("-" * 70)
    
    for leg in legs:
        from_short = leg['from'][:23] + ".." if len(leg['from']) > 25 else leg['from']
        to_short = leg['to'][:23] + ".." if len(leg['to']) > 25 else leg['to']
        print(f"{leg['leg']:<4} {from_short:<25} {to_short:<25} {leg['distance_km']:<10.2f} {leg['fuel_liters']:<10.3f}")
    
    print("-" * 70)
    print(f"{'TOTAL':<4} {'':<25} {'':<25} {total_distance:<10.2f} {total_fuel:<10.3f}")
    print("=" * 70)
    
    return {
        'total_fuel_liters': total_fuel,
        'total_fuel_gallons': total_fuel_gallons,
        'total_distance_km': total_distance,
        'total_distance_miles': total_distance_miles,
        'total_elevation_m': total_elevation,
        'total_duration_minutes': total_duration,
        'fuel_economy_mpg': overall_mpg,
        'fuel_economy_l_per_100km': overall_l_per_100km,
        'co2_kg': co2_kg,
        'legs': legs,
    }


if __name__ == "__main__":
    result = main()