import pandas as pd
import os
import glob

# Load reference data
df_vehicles = pd.read_excel('eved-dataset/class_data/VED_Static_Data_ICE&HEV.xlsx')

#We only want to keep the ICE vehicles, so we create a set of their IDs for quick lookup
ice_ids = set(df_vehicles[df_vehicles['Vehicle Type'] == 'ICE']['VehId'].dropna().astype(int))

# Setup file paths
folder_path = 'eved-dataset/data/eVED/'
file_pattern = os.path.join(folder_path, 'eVED_*_week.csv')
all_files = glob.glob(file_pattern)

filtered_fragments = []


#check that the file is being loaded correct, check that the filter works

# Process each file, filter for ICE vehicles, and store results
for filename in all_files:

    # Read with low_memory=False to handle the mixed types in column 30
    temp_df = pd.read_csv(filename, low_memory=False)
    print(1)
    
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
final_ice_eved_df.to_csv('/Users/fli6/Desktop/Projects/pathos_model_updated/Final_Outputs/final_ice_trips_master.csv')
print('Done')