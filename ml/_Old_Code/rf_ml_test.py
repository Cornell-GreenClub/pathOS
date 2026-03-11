from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import matplotlib.pyplot as plt
import pandas as pd


# 1. Load Static Data & Get Weights
# We only need VehId and Generalized_Weight[lb]
df_static = pd.read_excel('eved-dataset/class_data/VED_Static_Data_ICE&HEV.xlsx')
df_weights = df_static[['VehId', 'Generalized_Weight']].dropna()

# 2. Load the 13M row Master CSV
# Only loading the columns we care about to save memory
cols_to_use = [
    'VehId', 'Vehicle Speed[km/h]', 'Gradient', 
    'Elevation Smoothed[m]', 'MAF[g/sec]'
]
df_dynamic = pd.read_csv('final_ice_trips_master.csv', usecols=cols_to_use, low_memory=False)

# 3. Merge Weight into the Dynamic Data
# This maps the correct weight to every single GPS point based on VehId
df_modeling = pd.merge(df_dynamic, df_weights, on='VehId', how='inner')

# 4. Final Cleanup
# Rename for easier coding and drop rows missing our key variables
df_modeling = df_modeling.dropna()
df_modeling = df_modeling.rename(columns={
    'Vehicle Speed[km/h]': 'Speed',
    'Generalized_Weight': 'Weight',
    'MAF[g/sec]': 'Target_MAF'
})

# Select only the final features for the optimizer project
final_dataset = df_modeling[['Speed', 'Gradient', 'Weight', 'Target_MAF']]

print(f"Dataset ready! Total rows: {len(final_dataset):,}")
print(final_dataset.head())


'''
final_ice_eved_df = pd.read_csv('final_ice_trips_master.csv')

# Filter for rows where MAF, Load, and RPM all exist
# We're ignoring 'Fuel Rate' for now because it's mostly empty
clean_df = final_ice_eved_df.dropna(subset=['MAF[g/sec]', 'Absolute Load[%]', 'Engine RPM[RPM]', 'Gradient'])

if len(clean_df) > 1000:
    # Use a random sample of 50,000 for speed
    sample_df = clean_df.sample(n=50000)
    # Expanded features for better physics modeling
    X = sample_df[['Absolute Load[%]', 'Engine RPM[RPM]', 'Gradient']]
    y = sample_df['MAF[g/sec]']

    model = LinearRegression()
    model.fit(X, y)

    print(f"Improved R^2 Score: {model.score(X, y):.4f}")
    
    print(f"Validation Success! R^2 Score (MAF Prediction): {model.score(X, y):.4f}")
else:
    print("Still too few rows. Check your ICE filtering logic.")
'''

'''
# 1. Take a manageable sample (e.g., first 100,000 ICE records)
sample_df = final_ice_eved_df.iloc[:100000].dropna(subset=['MAF[g/sec]', 'Fuel Rate[L/hr]'])

# 2. Define features (X) and target (y)
X = sample_df[['MAF[g/sec]']]
print(X.head(5))
y = sample_df['Fuel Rate[L/hr]']
print(y.head(5))

# 3. Initialize and train the model
model = LinearRegression()
model.fit(X, y)

# 4. Predict and validate
y_pred = model.predict(X)
score = r2_score(y, y_pred)

print(f"Linear Regression R^2 Score: {score:.4f}")
print(f"Model Coefficient (Fuel per gram of air): {model.coef_[0]:.6f}")
'''

