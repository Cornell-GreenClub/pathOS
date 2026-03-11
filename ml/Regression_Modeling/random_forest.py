import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import joblib

# ============================================================
# 1. LOAD TRIP-LEVEL DATA
# ============================================================

df = pd.read_csv('trip_summaries_clean.csv')
print(f"Loaded {len(df):,} trips")

# ============================================================
# 2. PREPARE FEATURES
# ============================================================

# Features we can derive from ORS route data + known bus weight
features = ['Total_Distance_km', 'Avg_Speed_kmh', 'Elevation_Gain_m', 'Weight_kg']

# Target: total fuel consumed
target = 'Total_Fuel_Liters'

X = df[features]
y = df[target]

print(f"\nFeatures: {features}")
print(f"Target: {target}")
print(f"Samples: {len(X):,}")

# ============================================================
# 3. TRAIN/TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(f"\nTraining samples: {len(X_train):,}")
print(f"Testing samples:  {len(X_test):,}")

# ============================================================
# 4. TRAIN RANDOM FOREST
# ============================================================

print("\nTraining Random Forest...")

rf_model = RandomForestRegressor(
    n_estimators=200,      # More trees for better stability
    max_depth=20,          # Allow deeper trees for complex relationships
    min_samples_leaf=5,    # Prevent overfitting
    n_jobs=-1,
    random_state=42
)

rf_model.fit(X_train, y_train)

# ============================================================
# 5. EVALUATE MODEL
# ============================================================

train_score = rf_model.score(X_train, y_train)
test_score = rf_model.score(X_test, y_test)

y_pred_train = rf_model.predict(X_train)
y_pred_test = rf_model.predict(X_test)

# Calculate RMSE and MAE
from sklearn.metrics import mean_squared_error, mean_absolute_error

rmse_train = np.sqrt(mean_squared_error(y_train, y_pred_train))
rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
mae_train = mean_absolute_error(y_train, y_pred_train)
mae_test = mean_absolute_error(y_test, y_pred_test)

# Mean Absolute Percentage Error
mape_test = np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100

print(f"\n{'='*50}")
print("MODEL PERFORMANCE")
print(f"{'='*50}")
print(f"Training R²:  {train_score:.4f}")
print(f"Testing R²:   {test_score:.4f}")
print(f"\nTraining RMSE: {rmse_train:.4f} L")
print(f"Testing RMSE:  {rmse_test:.4f} L")
print(f"\nTraining MAE:  {mae_train:.4f} L")
print(f"Testing MAE:   {mae_test:.4f} L")
print(f"\nTesting MAPE:  {mape_test:.1f}%")

# ============================================================
# 6. FEATURE IMPORTANCE
# ============================================================

print(f"\n{'='*50}")
print("FEATURE IMPORTANCE")
print(f"{'='*50}")

importances = pd.Series(rf_model.feature_importances_, index=features)
importances_sorted = importances.sort_values(ascending=False)
print(importances_sorted)

# Plot feature importance
fig, ax = plt.subplots(figsize=(8, 5))
importances_sorted.plot(kind='barh', ax=ax)
ax.set_xlabel('Importance')
ax.set_title('Feature Importance for Fuel Prediction')
plt.tight_layout()
plt.savefig('feature_importance_trip_level.png', dpi=150)
plt.show()

# ============================================================
# 7. PREDICTED VS ACTUAL PLOT
# ============================================================

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Training
axes[0].scatter(y_train, y_pred_train, alpha=0.5, s=10)
axes[0].plot([0, y_train.max()], [0, y_train.max()], 'r--', label='Perfect prediction')
axes[0].set_xlabel('Actual Fuel (L)')
axes[0].set_ylabel('Predicted Fuel (L)')
axes[0].set_title(f'Training Set (R² = {train_score:.3f})')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Testing
axes[1].scatter(y_test, y_pred_test, alpha=0.5, s=10)
axes[1].plot([0, y_test.max()], [0, y_test.max()], 'r--', label='Perfect prediction')
axes[1].set_xlabel('Actual Fuel (L)')
axes[1].set_ylabel('Predicted Fuel (L)')
axes[1].set_title(f'Testing Set (R² = {test_score:.3f})')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('predicted_vs_actual_trip_level.png', dpi=150)
plt.show()

# ============================================================
# 8. WEIGHT EXTRAPOLATION TEST
# ============================================================

print(f"\n{'='*50}")
print("WEIGHT EXTRAPOLATION TEST")
print(f"{'='*50}")

# Test with a fixed "typical" trip: 10km, 50 km/h avg, 50m elevation gain
test_distance = 10  # km
test_speed = 50     # km/h
test_elevation = 50 # m

weights_to_test = [1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000]

print(f"\nTest trip: {test_distance} km, {test_speed} km/h avg, {test_elevation}m elevation gain")
print("-" * 50)

results = []
for w in weights_to_test:
    pred = rf_model.predict([[test_distance, test_speed, test_elevation, w]])[0]
    results.append({'Weight_kg': w, 'Predicted_Fuel_L': pred})
    in_training = "✓" if w <= 2722 else "⚠ extrapolated"
    print(f"Weight {w:,} kg → Fuel {pred:.3f} L ({pred/test_distance*100:.1f} L/100km) {in_training}")

# Plot extrapolation
df_extrap = pd.DataFrame(results)

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(df_extrap['Weight_kg'], df_extrap['Predicted_Fuel_L'], 'bo-', markersize=8, linewidth=2)
ax.axvline(x=2722, color='r', linestyle='--', label='Max training weight (2722 kg)')
ax.axvline(x=8000, color='g', linestyle='--', label='Typical bus weight (8000 kg)')
ax.set_xlabel('Vehicle Weight (kg)', fontsize=12)
ax.set_ylabel('Predicted Fuel (L)', fontsize=12)
ax.set_title(f'Weight Extrapolation Test\n(10km trip, 50 km/h, 50m elevation gain)', fontsize=14)
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('weight_extrapolation_trip_level.png', dpi=150)
plt.show()

# ============================================================
# 9. GRADIENT/ELEVATION TEST
# ============================================================

print(f"\n{'='*50}")
print("ELEVATION IMPACT TEST")
print(f"{'='*50}")

# Test with fixed distance, speed, weight - varying elevation gain
test_distance = 10    # km
test_speed = 50       # km/h
test_weight = 2000    # kg (mid-range car)

elevations_to_test = [0, 25, 50, 100, 150, 200, 300, 400, 500]

print(f"\nTest trip: {test_distance} km, {test_speed} km/h avg, {test_weight} kg")
print("-" * 50)

results_elev = []
for e in elevations_to_test:
    pred = rf_model.predict([[test_distance, test_speed, e, test_weight]])[0]
    results_elev.append({'Elevation_Gain_m': e, 'Predicted_Fuel_L': pred})
    print(f"Elevation gain {e:3}m → Fuel {pred:.3f} L ({pred/test_distance*100:.1f} L/100km)")

# ============================================================
# 10. SUMMARY
# ============================================================

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"""
Model Performance:
  - Training R²: {train_score:.4f}
  - Testing R²:  {test_score:.4f}
  - Testing MAPE: {mape_test:.1f}%

Feature Importance:
{importances_sorted.to_string()}

Key Findings:
  1. Does model fit well? R² = {test_score:.3f} ({"Good!" if test_score > 0.7 else "Moderate" if test_score > 0.5 else "Needs improvement"})
  2. Most important feature: {importances_sorted.index[0]}
  3. Check weight extrapolation plot - does it plateau or continue increasing?

Files Saved:
  - feature_importance_trip_level.png
  - predicted_vs_actual_trip_level.png
  - weight_extrapolation_trip_level.png
""")

# ============================================================
# 11. SAVE MODEL
# ============================================================

joblib.dump(rf_model, 'rf_fuel_model_trip_level.joblib')
print("✓ Model saved as 'rf_fuel_model_trip_level.joblib'")