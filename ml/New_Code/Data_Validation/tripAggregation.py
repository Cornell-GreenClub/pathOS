import pandas as pd
import numpy as np
from tqdm import tqdm  # for progress bar - install with: pip install tqdm

# ============================================================
# 1. LOAD DATA
# ============================================================

# Load static data for weights
df_static = pd.read_excel('eved-dataset/class_data/VED_Static_Data_ICE&HEV.xlsx')
df_static['Generalized_Weight'] = pd.to_numeric(df_static['Generalized_Weight'], errors='coerce')
df_static = df_static[df_static['Generalized_Weight'].notna()]

# Vehicle weights are in pounds (per eVED paper Table III)
df_static['Weight_kg'] = df_static['Generalized_Weight'] * 0.453592
weight_map = df_static.set_index('VehId')['Weight_kg'].to_dict()

# Load dynamic data - only columns we need
cols_to_use = [
    'VehId', 'Trip', 'Timestamp(ms)',
    'Latitude[deg]', 'Longitude[deg]',
    'Vehicle Speed[km/h]', 'MAF[g/sec]',
    'Elevation Smoothed[m]'
]

df = pd.read_csv('/Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/final_ice_trips_master.csv', usecols=cols_to_use, low_memory=False)
print(f"Loaded {len(df):,} rows")

# Add weights
df['Weight_kg'] = df['VehId'].map(weight_map)
df = df[df['Weight_kg'].notna()]
print(f"After weight merge: {len(df):,} rows")



# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate distance between consecutive GPS points in km.
    Vectorized for speed.
    """
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


def aggregate_trip(trip_df):
    """
    Aggregate instantaneous GPS/sensor data to trip-level summary.
    
    Returns a dictionary with trip-level metrics.
    """
    # Need at least 2 points to calculate anything meaningful
    if len(trip_df) < 2:
        return None
    
    # Sort by timestamp
    trip_df = trip_df.sort_values('Timestamp(ms)').reset_index(drop=True)
    
    # --- TIME ---
    total_time_ms = trip_df['Timestamp(ms)'].iloc[-1] - trip_df['Timestamp(ms)'].iloc[0]
    total_time_hours = total_time_ms / (1000 * 3600)
    
    # Skip very short trips (less than 30 seconds)
    if total_time_hours < 0.00833:  # 30 seconds
        return None

    # --- DISTANCE ---
    lats = trip_df['Latitude[deg]'].values
    lons = trip_df['Longitude[deg]'].values
    timestamps = trip_df['Timestamp(ms)'].values

    # Time between readings (seconds)
    dt_seconds = np.diff(timestamps) / 1000

    # Calculate distances between consecutive points
    distances = haversine_km(lats[:-1], lons[:-1], lats[1:], lons[1:])

    # Filter GPS glitches: if implied speed > 200 km/h, it's bogus
    implied_speed_kmh = (distances / dt_seconds) * 3600
    distances[implied_speed_kmh > 200] = 0

    total_distance_km = np.nansum(distances)

    # Skip trips with no movement or unrealistic distance
    if total_distance_km < 0.1:  # less than 100 meters
        return None
        
    # --- ELEVATION ---
    elevations = trip_df['Elevation Smoothed[m]'].values
    elev_diffs = np.diff(elevations)
    
    # Handle NaN in elevation
    elev_diffs = elev_diffs[~np.isnan(elev_diffs)]
    
    if len(elev_diffs) > 0:
        elevation_gain_m = np.sum(elev_diffs[elev_diffs > 0])
        elevation_loss_m = np.abs(np.sum(elev_diffs[elev_diffs < 0]))
    else:
        elevation_gain_m = 0
        elevation_loss_m = 0
    
    # --- MAF / FUEL ---
    timestamps = trip_df['Timestamp(ms)'].values
    maf_values = trip_df['MAF[g/sec]'].values
    
    # Integrate MAF over time (using values at start of each interval)
    # MAF[i] * dt[i] gives grams of air in that interval
    maf_for_integration = maf_values[:-1]
    
    # Handle NaN
    valid_mask = ~np.isnan(maf_for_integration) & ~np.isnan(dt_seconds) & (dt_seconds > 0) & (dt_seconds < 60)
    
    if np.sum(valid_mask) > 0:
        total_maf_grams = np.sum(maf_for_integration[valid_mask] * dt_seconds[valid_mask])
    else:
        return None  # No valid MAF data
    
    # Convert MAF to fuel
    # Fuel (grams) = Air (grams) / AFR (14.7 for stoichiometric gasoline)
    # Fuel (liters) = Fuel (grams) / density (740 g/L for gasoline)
    total_fuel_grams = total_maf_grams / 14.7
    total_fuel_liters = total_fuel_grams / 740
    
    # Skip unrealistic fuel values
    if total_fuel_liters <= 0:
        return None
    
    # --- SPEED ---
    speeds = trip_df['Vehicle Speed[km/h]'].values
    avg_speed = np.nanmean(speeds)
    max_speed = np.nanmax(speeds)
    
    # --- WEIGHT ---
    weight_kg = trip_df['Weight_kg'].iloc[0]
    
    # --- DERIVED METRICS ---
    fuel_per_100km = (total_fuel_liters / total_distance_km * 100) if total_distance_km > 0 else np.nan
    
    # Meters gained per km traveled (hilliness metric)
    elevation_gain_per_km = elevation_gain_m / total_distance_km if total_distance_km > 0 else 0
    
    return {
        'Total_Time_hours': total_time_hours,
        'Total_Distance_km': total_distance_km,
        'Avg_Speed_kmh': avg_speed,
        'Max_Speed_kmh': max_speed,
        'Elevation_Gain_m': elevation_gain_m,
        'Elevation_Loss_m': elevation_loss_m,
        'Elevation_Gain_per_km': elevation_gain_per_km,
        'Total_Fuel_Liters': total_fuel_liters,
        'Fuel_L_per_100km': fuel_per_100km,
        'Weight_kg': weight_kg,
        'Num_Points': len(trip_df)
    }


# ============================================================
# 3. AGGREGATE ALL TRIPS
# ============================================================

# Get unique trip identifiers
trip_groups = df.groupby(['VehId', 'Trip'])
total_trips = len(trip_groups)
print(f"Total unique trips to process: {total_trips:,}")

# Process each trip
trip_summaries = []
skipped = 0

for (veh_id, trip_id), trip_df in tqdm(trip_groups, total=total_trips, desc="Processing trips"):
    result = aggregate_trip(trip_df)
    
    if result is not None:
        result['VehId'] = veh_id
        result['Trip'] = trip_id
        trip_summaries.append(result)
    else:
        skipped += 1

# Convert to DataFrame
df_trips = pd.DataFrame(trip_summaries)

print(f"\n{'='*50}")
print(f"Aggregation Complete!")
print(f"{'='*50}")
print(f"Total trips processed: {total_trips:,}")
print(f"Valid trips retained:  {len(df_trips):,}")
print(f"Trips skipped:         {skipped:,} ({skipped/total_trips*100:.1f}%)")



# ============================================================
# 4. DATA QUALITY CHECK
# ============================================================

print(f"\n{'='*50}")
print("DATA SUMMARY")
print(f"{'='*50}")
print(df_trips.describe().round(2))

print(f"\n{'='*50}")
print("SANITY CHECKS")
print(f"{'='*50}")

# Check for reasonable values
print(f"\nDistance range: {df_trips['Total_Distance_km'].min():.2f} - {df_trips['Total_Distance_km'].max():.2f} km")
print(f"Fuel range: {df_trips['Total_Fuel_Liters'].min():.3f} - {df_trips['Total_Fuel_Liters'].max():.2f} L")
print(f"Fuel efficiency range: {df_trips['Fuel_L_per_100km'].min():.1f} - {df_trips['Fuel_L_per_100km'].max():.1f} L/100km")
print(f"Elevation gain range: {df_trips['Elevation_Gain_m'].min():.0f} - {df_trips['Elevation_Gain_m'].max():.0f} m")
print(f"Weight range: {df_trips['Weight_kg'].min():.0f} - {df_trips['Weight_kg'].max():.0f} kg")

# Flag potentially bad data
unrealistic_fuel = df_trips[(df_trips['Fuel_L_per_100km'] < 3) | (df_trips['Fuel_L_per_100km'] > 50)]
print(f"\nTrips with unrealistic fuel efficiency (<3 or >50 L/100km): {len(unrealistic_fuel):,}")

# ============================================================
# 5. FILTER OUTLIERS (Optional but recommended)
# ============================================================

print(f"\n{'='*50}")
print("FILTERING OUTLIERS")
print(f"{'='*50}")

df_clean = df_trips[
    (df_trips['Fuel_L_per_100km'] >= 3) &      # Min realistic fuel efficiency
    (df_trips['Fuel_L_per_100km'] <= 50) &     # Max realistic fuel efficiency
    (df_trips['Total_Distance_km'] >= 0.5) &   # At least 500m trip
    (df_trips['Total_Distance_km'] <= 500) &   # Less than 500km trip
    (df_trips['Avg_Speed_kmh'] >= 5) &         # Moving, not just idling
    (df_trips['Avg_Speed_kmh'] <= 150) &       # Not unrealistic speed
    (df_trips['Total_Time_hours'] <= 8)        # Less than 8 hour trip
].copy()

print(f"Before filtering: {len(df_trips):,} trips")
print(f"After filtering:  {len(df_clean):,} trips")
print(f"Removed: {len(df_trips) - len(df_clean):,} outlier trips")

high_fuel_only = df_trips[(df_trips['Fuel_L_per_100km'] > 50) & (df_trips['Total_Distance_km'] >= 0.5)]
print(high_fuel_only[['Total_Distance_km', 'Total_Fuel_Liters', 'Fuel_L_per_100km', 'Avg_Speed_kmh', 'Total_Time_hours']].head(10))

# ============================================================
# 6. SAVE RESULTS
# ============================================================

# Save both versions
df_trips.to_csv('/Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/trip_summaries_all.csv', index=False)
df_clean.to_csv('/Users/fli6/Desktop/pathOS/pathOS/ml/Final_Outputs/trip_summaries_clean.csv', index=False)

print(f"\n✓ Saved 'trip_summaries_all.csv' ({len(df_trips):,} trips)")
print(f"✓ Saved 'trip_summaries_clean.csv' ({len(df_clean):,} trips)")
