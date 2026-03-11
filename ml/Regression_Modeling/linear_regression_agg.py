import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import joblib

# ============================================================
# 1. LOAD DATA
# ============================================================

df = pd.read_csv('/Users/fli6/Desktop/Projects/pathos_model_updated/Data/trip_summaries_clean.csv')
print(f"Loaded {len(df):,} trips")

# ============================================================
# 2. CREATE PHYSICS-INFORMED FEATURES
# ============================================================

print("\nCreating physics-informed features...")

# The physics tells us:
#   F_rolling = Cr × m × g           → Energy = Cr × m × g × distance
#   F_aero = ½ρCdAv²                 → Energy = ½ρCdAv² × distance
#   F_grade = m × g × sin(θ)        → Energy = m × g × Δh (elevation gain)
#
# So fuel should be proportional to:
#   - Distance × Weight              (rolling resistance)
#   - Distance × Speed²              (aerodynamic drag)
#   - Elevation_Gain × Weight        (grade resistance)

# Create interaction features that match physics
df['Distance_x_Weight'] = df['Total_Distance_km'] * df['Weight_kg']
df['Elevation_x_Weight'] = df['Elevation_Gain_m'] * df['Weight_kg']
df['Distance_x_Speed_sq'] = df['Total_Distance_km'] * (df['Avg_Speed_kmh'] ** 2)

# Also keep raw distance (captures baseline consumption)
# and raw elevation (in case there's a weight-independent component)

print("Features created:")
print("  - Distance_x_Weight     (rolling resistance)")
print("  - Elevation_x_Weight    (grade resistance)")
print("  - Distance_x_Speed_sq   (aerodynamic drag)")
print("  - Total_Distance_km     (baseline)")

# ============================================================
# 3. PREPARE FEATURES AND TARGET
# ============================================================

# Physics-informed features
features_physics = [
    'Total_Distance_km',        # Baseline fuel use
    'Distance_x_Weight',        # Rolling resistance ∝ distance × weight
    'Elevation_x_Weight',       # Grade resistance ∝ elevation × weight
    'Distance_x_Speed_sq',      # Aero drag ∝ distance × speed²
]

# For comparison: raw features (what we used in RF)
features_raw = [
    'Total_Distance_km',
    'Avg_Speed_kmh', 
    'Elevation_Gain_m',
    'Weight_kg'
]

target = 'Total_Fuel_Liters'

X_physics = df[features_physics]
X_raw = df[features_raw]
y = df[target]

# Train/test split (same random state for fair comparison)
X_train_p, X_test_p, y_train, y_test = train_test_split(
    X_physics, y, test_size=0.2, random_state=42
)
X_train_r, X_test_r, _, _ = train_test_split(
    X_raw, y, test_size=0.2, random_state=42
)

print(f"\nTraining samples: {len(X_train_p):,}")
print(f"Testing samples:  {len(X_test_p):,}")

# ============================================================
# 4. TRAIN MODELS
# ============================================================

print("\n" + "="*50)
print("TRAINING MODELS")
print("="*50)

# Model 1: Physics-informed Linear Regression
print("\n1. Physics-Informed Linear Regression...")
model_physics = Ridge(alpha=1.0)  # Small regularization for stability
model_physics.fit(X_train_p, y_train)

# Model 2: Raw features Linear Regression (for comparison)
print("2. Raw Features Linear Regression...")
model_raw = Ridge(alpha=1.0)
model_raw.fit(X_train_r, y_train)

# ============================================================
# 5. EVALUATE MODELS
# ============================================================

print("\n" + "="*50)
print("MODEL PERFORMANCE COMPARISON")
print("="*50)

def evaluate_model(model, X_train, X_test, y_train, y_test, name):
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    
    r2_train = r2_score(y_train, y_pred_train)
    r2_test = r2_score(y_test, y_pred_test)
    rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
    mae_test = mean_absolute_error(y_test, y_pred_test)
    mape_test = np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100
    
    print(f"\n{name}:")
    print(f"  Training R²:  {r2_train:.4f}")
    print(f"  Testing R²:   {r2_test:.4f}")
    print(f"  Testing RMSE: {rmse_test:.4f} L")
    print(f"  Testing MAE:  {mae_test:.4f} L")
    print(f"  Testing MAPE: {mape_test:.1f}%")
    
    return r2_test, y_pred_test

r2_physics, pred_physics = evaluate_model(
    model_physics, X_train_p, X_test_p, y_train, y_test, 
    "Physics-Informed Linear Regression"
)

r2_raw, pred_raw = evaluate_model(
    model_raw, X_train_r, X_test_r, y_train, y_test,
    "Raw Features Linear Regression"
)

# ============================================================
# 6. EXAMINE LEARNED COEFFICIENTS
# ============================================================

print("\n" + "="*50)
print("LEARNED COEFFICIENTS (Physics-Informed Model)")
print("="*50)

print(f"\nIntercept: {model_physics.intercept_:.6f}")
print("\nFeature Coefficients:")
for feat, coef in zip(features_physics, model_physics.coef_):
    print(f"  {feat:25s}: {coef:.10f}")

print("\nInterpretation:")
print("  - Distance_x_Weight coef     → Rolling resistance factor")
print("  - Elevation_x_Weight coef    → Grade resistance factor")
print("  - Distance_x_Speed_sq coef   → Aerodynamic drag factor")
print("  - Total_Distance_km coef     → Baseline consumption rate")

# ============================================================
# 7. WEIGHT EXTRAPOLATION TEST
# ============================================================

print("\n" + "="*50)
print("WEIGHT EXTRAPOLATION TEST")
print("="*50)

test_distance = 10   # km
test_speed = 50      # km/h
test_elevation = 50  # m

weights_to_test = [1500, 2000, 2500, 3000, 4000, 5000, 6000, 8000, 10000, 12000]

print(f"\nTest trip: {test_distance} km, {test_speed} km/h, {test_elevation}m elevation gain")
print("-" * 60)

results_weight = []
for w in weights_to_test:
    # Create physics features
    dist_x_weight = test_distance * w
    elev_x_weight = test_elevation * w
    dist_x_speed_sq = test_distance * (test_speed ** 2)
    
    X_pred = [[test_distance, dist_x_weight, elev_x_weight, dist_x_speed_sq]]
    pred = model_physics.predict(X_pred)[0]
    
    results_weight.append({
        'Weight_kg': w, 
        'Predicted_Fuel_L': pred,
        'L_per_100km': pred / test_distance * 100
    })
    
    in_training = "✓" if w <= 2722 else "⚠ extrapolated"
    print(f"Weight {w:,} kg → Fuel {pred:.3f} L ({pred/test_distance*100:.1f} L/100km) {in_training}")

# ============================================================
# 8. ELEVATION EXTRAPOLATION TEST
# ============================================================

print("\n" + "="*50)
print("ELEVATION EXTRAPOLATION TEST")
print("="*50)

test_distance = 10    # km
test_speed = 50       # km/h
test_weight = 2000    # kg

elevations_to_test = [0, 50, 100, 150, 200, 300, 400, 500, 600, 800, 1000]

print(f"\nTest trip: {test_distance} km, {test_speed} km/h, {test_weight} kg")
print("-" * 60)

results_elevation = []
for e in elevations_to_test:
    dist_x_weight = test_distance * test_weight
    elev_x_weight = e * test_weight
    dist_x_speed_sq = test_distance * (test_speed ** 2)
    
    X_pred = [[test_distance, dist_x_weight, elev_x_weight, dist_x_speed_sq]]
    pred = model_physics.predict(X_pred)[0]
    
    results_elevation.append({
        'Elevation_m': e,
        'Predicted_Fuel_L': pred,
        'L_per_100km': pred / test_distance * 100
    })
    
    in_training = "✓" if e <= 660 else "⚠ extrapolated"
    print(f"Elevation {e:4}m → Fuel {pred:.3f} L ({pred/test_distance*100:.1f} L/100km) {in_training}")

# ============================================================
# 9. VISUALIZATION
# ============================================================

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Predicted vs Actual
axes[0, 0].scatter(y_test, pred_physics, alpha=0.5, s=20)
axes[0, 0].plot([0, y_test.max()], [0, y_test.max()], 'r--', label='Perfect')
axes[0, 0].set_xlabel('Actual Fuel (L)')
axes[0, 0].set_ylabel('Predicted Fuel (L)')
axes[0, 0].set_title(f'Physics-Informed Linear Regression (R² = {r2_physics:.3f})')
axes[0, 0].legend()
axes[0, 0].grid(True, alpha=0.3)

# Plot 2: Weight Extrapolation
df_weight = pd.DataFrame(results_weight)
axes[0, 1].plot(df_weight['Weight_kg'], df_weight['Predicted_Fuel_L'], 'bo-', markersize=8, linewidth=2)
axes[0, 1].axvline(x=2722, color='r', linestyle='--', label='Max training weight')
axes[0, 1].axvline(x=9000, color='g', linestyle='--', label='Bus weight (~9000 kg)')
axes[0, 1].set_xlabel('Weight (kg)')
axes[0, 1].set_ylabel('Predicted Fuel (L)')
axes[0, 1].set_title('Weight Extrapolation\n(10 km, 50 km/h, 50m elevation)')
axes[0, 1].legend()
axes[0, 1].grid(True, alpha=0.3)

# Plot 3: Elevation Extrapolation
df_elev = pd.DataFrame(results_elevation)
axes[1, 0].plot(df_elev['Elevation_m'], df_elev['Predicted_Fuel_L'], 'go-', markersize=8, linewidth=2)
axes[1, 0].axvline(x=660, color='r', linestyle='--', label='Max training elevation')
axes[1, 0].set_xlabel('Elevation Gain (m)')
axes[1, 0].set_ylabel('Predicted Fuel (L)')
axes[1, 0].set_title('Elevation Extrapolation\n(10 km, 50 km/h, 2000 kg)')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.3)

# Plot 4: Coefficient visualization
coef_df = pd.DataFrame({
    'Feature': features_physics,
    'Coefficient': model_physics.coef_
})
colors = ['blue', 'orange', 'green', 'red']
axes[1, 1].barh(coef_df['Feature'], coef_df['Coefficient'], color=colors)
axes[1, 1].set_xlabel('Coefficient Value')
axes[1, 1].set_title('Learned Coefficients')
axes[1, 1].grid(True, alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig('physics_informed_regression_results.png', dpi=150)
plt.show()

print("\n✓ Plot saved as 'physics_informed_regression_results.png'")

# ============================================================
# 10. BUS PREDICTION EXAMPLE
# ============================================================

print("\n" + "="*50)
print("BUS ROUTE PREDICTION EXAMPLE")
print("="*50)

# Example: Ithaca to Cortland route
bus_weight = 9000     # kg (loaded school bus)
route_distance = 30   # km
avg_speed = 55        # km/h
elevation_gain = 150  # m

dist_x_weight = route_distance * bus_weight
elev_x_weight = elevation_gain * bus_weight
dist_x_speed_sq = route_distance * (avg_speed ** 2)

X_bus = [[route_distance, dist_x_weight, elev_x_weight, dist_x_speed_sq]]
fuel_pred = model_physics.predict(X_bus)[0]

print(f"\nRoute: Ithaca → Cortland (example)")
print(f"  Distance: {route_distance} km")
print(f"  Avg Speed: {avg_speed} km/h")
print(f"  Elevation Gain: {elevation_gain} m")
print(f"  Bus Weight: {bus_weight:,} kg")
print(f"\n  Predicted Fuel: {fuel_pred:.2f} L ({fuel_pred * 0.264172:.2f} gallons)")
print(f"  Fuel Efficiency: {fuel_pred/route_distance*100:.1f} L/100km ({235.215/(fuel_pred/route_distance*100):.1f} MPG)")

# ============================================================
# 11. SUMMARY
# ============================================================

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(f"""
Model Performance:
  - Testing R²:   {r2_physics:.4f}
  - Model Type:   Physics-Informed Linear Regression

Key Advantage over Random Forest:
  - RF plateaus at edge of training data (can't extrapolate)
  - Linear model continues the learned trend (CAN extrapolate)

Learned Coefficients:
  - These represent the physics relationships learned from real driving data
  - Can be applied to any weight/distance/elevation combination

Extrapolation Behavior:
  - Weight: {"Linear increase ✓" if results_weight[-1]['Predicted_Fuel_L'] > results_weight[0]['Predicted_Fuel_L'] else "Check plot!"}
  - Elevation: {"Linear increase ✓" if results_elevation[-1]['Predicted_Fuel_L'] > results_elevation[0]['Predicted_Fuel_L'] else "Check plot!"}
""")

# ============================================================
# 12. SAVE MODEL
# ============================================================

# Save the model and feature names
model_data = {
    'model': model_physics,
    'features': features_physics,
    'feature_formulas': {
        'Distance_x_Weight': 'Total_Distance_km * Weight_kg',
        'Elevation_x_Weight': 'Elevation_Gain_m * Weight_kg',
        'Distance_x_Speed_sq': 'Total_Distance_km * (Avg_Speed_kmh ** 2)'
    }
}
joblib.dump(model_data, 'physics_informed_fuel_model.joblib')
print("✓ Model saved as 'physics_informed_fuel_model.joblib'")