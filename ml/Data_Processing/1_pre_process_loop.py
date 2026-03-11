import pandas as pd
import os
import glob

# Load reference data
df_vehicles = pd.read_excel('eved-dataset/class_data/VED_Static_Data_ICE&HEV.xlsx')
ice_ids = set(df_vehicles[df_vehicles['Vehicle Type'] == 'ICE']['VehId'].dropna().astype(int))

# Setup file paths
folder_path = 'eved-dataset/data/eVED/'
file_pattern = os.path.join(folder_path, 'eVED_*_week.csv')
all_files = glob.glob(file_pattern)

filtered_fragments = []

for filename in all_files:
    # Read with low_memory=False to handle the mixed types in column 30
    temp_df = pd.read_csv(filename, low_memory=False)
    print(temp_df.head(5))
    
    # Standardize ID type to integer for matching
    temp_df = temp_df.dropna(subset=['VehId'])
    temp_df['VehId'] = temp_df['VehId'].astype(int)
    
    # Filter and store
    ice_only = temp_df[temp_df['VehId'].isin(ice_ids)]
    filtered_fragments.append(ice_only)

# Combine results
final_ice_eved_df = pd.concat(filtered_fragments, ignore_index=True)

print(f"Processed {len(all_files)} files.")
print(f"Total ICE trip records: {len(final_ice_eved_df):,}")


print(final_ice_eved_df['VehId'])
# Recommended: Export to a format better suited for 13M rows than CSV
#final_ice_eved_df.to_csv('final_ice_trips_master.csv')