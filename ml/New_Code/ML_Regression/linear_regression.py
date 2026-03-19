"""
3_train_model.py

Trains and compares fuel consumption models:
  1. Physics-informed linear regression (our theory-driven features)
  2. LASSO regression (data-driven feature selection from full feature set)

Input:  trip_summaries_clean.csv
Output: fuel_model_physics.joblib, fuel_model_lasso.joblib
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LinearRegression, LassoCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error, r2_score
import joblib
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 1. LOAD DATA
# ============================================================

print("="*60)
print("FUEL CONSUMPTION MODEL TRAINING")
print("="*60)

df = pd.read_csv('/Users/fli6/Desktop/Projects/pathos_model_updated/Final_Outputs/trip_summaries_clean.csv')
print(f"\nLoaded {len(df):,} trips")

# ============================================================
# 2. CREATE FEATURES
# ============================================================

print("\n" + "="*60)
print("FEATURE ENGINEERING")
print("="*60)

# --- Physics-Informed Features ---
df['Dist_x_Weight'] = df['Total_Distance_km'] * df['Weight_kg']
df['Elev_x_Weight'] = df['Elevation_Gain_m'] * df['Weight_kg']
df['Dist_x_Speed2'] = df['Total_Distance_km'] * (df['Avg_Speed_kmh'] ** 2)

physics_features = [
    'Total_Distance_km',
    'Dist_x_Weight',
    'Elev_x_Weight', 
    'Dist_x_Speed2'
]

# --- Extended Features for LASSO ---
df['Speed2'] = df['Avg_Speed_kmh'] ** 2
df['Speed_x_Weight'] = df['Avg_Speed_kmh'] * df['Weight_kg']
df['Elev_x_Speed'] = df['Elevation_Gain_m'] * df['Avg_Speed_kmh']
df['Dist_x_Speed'] = df['Total_Distance_km'] * df['Avg_Speed_kmh']
df['Elev_x_Dist'] = df['Elevation_Gain_m'] * df['Total_Distance_km']
df['Elev2'] = df['Elevation_Gain_m'] ** 2
df['Weight2'] = df['Weight_kg'] ** 2
df['Elev_x_Weight_x_Dist'] = df['Elevation_Gain_m'] * df['Weight_kg'] / (df['Total_Distance_km'] + 0.01)  # Grade factor

all_features = [
    # Main effects
    'Total_Distance_km',
    'Weight_kg',
    'Elevation_Gain_m',
    'Avg_Speed_kmh',
    # Squared terms
    'Speed2',
    'Elev2',
    'Weight2',
    # Two-way interactions
    'Dist_x_Weight',
    'Elev_x_Weight',
    'Dist_x_Speed2',
    'Speed_x_Weight',
    'Elev_x_Speed',
    'Dist_x_Speed',
    'Elev_x_Dist',
    # Three-way
    'Elev_x_Weight_x_Dist'
]

print(f"Physics-informed features: {len(physics_features)}")
print(f"Full feature set for LASSO: {len(all_features)}")

# Target
y = df['Total_Fuel_Liters'].values

# ============================================================
# 3. TRAIN/TEST SPLIT
# ============================================================

X_physics = df[physics_features].values
X_full = df[all_features].values

X_phys_train, X_phys_test, y_train, y_test = train_test_split(
    X_physics, y, test_size=0.2, random_state=42
)

X_full_train, X_full_test, _, _ = train_test_split(
    X_full, y, test_size=0.2, random_state=42
)

print(f"\nTrain set: {len(y_train):,} trips")
print(f"Test set:  {len(y_test):,} trips")

# ============================================================
# 4. MODEL 1: PHYSICS-INFORMED
# ============================================================

print("\n" + "="*60)
print("MODEL 1: PHYSICS-INFORMED LINEAR REGRESSION")
print("="*60)

model_physics = LinearRegression()
model_physics.fit(X_phys_train, y_train)

# Predictions
y_pred_phys_train = model_physics.predict(X_phys_train)
y_pred_phys_test = model_physics.predict(X_phys_test)

# Metrics
r2_phys_train = r2_score(y_train, y_pred_phys_train)
r2_phys_test = r2_score(y_test, y_pred_phys_test)
rmse_phys = np.sqrt(mean_squared_error(y_test, y_pred_phys_test))
mape_phys = mean_absolute_percentage_error(y_test, y_pred_phys_test) * 100

print(f"\nCoefficients:")
print(f"  Intercept: {model_physics.intercept_:.6f}")
for name, coef in zip(physics_features, model_physics.coef_):
    print(f"  {name}: {coef:.6e}")

print(f"\nPerformance:")
print(f"  Train R²: {r2_phys_train:.4f}")
print(f"  Test R²:  {r2_phys_test:.4f}")
print(f"  RMSE:     {rmse_phys:.4f} L")
print(f"  MAPE:     {mape_phys:.1f}%")

# Cross-validation
cv_scores_phys = cross_val_score(model_physics, X_physics, y, cv=5, scoring='r2')
print(f"  5-Fold CV R²: {cv_scores_phys.mean():.4f} (±{cv_scores_phys.std():.4f})")

# ============================================================
# 5. MODEL 2: LASSO (DATA-DRIVEN FEATURE SELECTION)
# ============================================================

print("\n" + "="*60)
print("MODEL 2: LASSO REGRESSION")
print("="*60)

# Scale features for LASSO (required for fair penalization)
scaler = StandardScaler()
X_full_train_scaled = scaler.fit_transform(X_full_train)
X_full_test_scaled = scaler.transform(X_full_test)
X_full_scaled = scaler.transform(X_full)

# LassoCV finds optimal alpha via cross-validation
model_lasso = LassoCV(cv=5, random_state=42, max_iter=10000)
model_lasso.fit(X_full_train_scaled, y_train)

print(f"\nOptimal alpha: {model_lasso.alpha_:.6f}")

# Which features survived?
print(f"\nFeature Selection (non-zero coefficients):")
surviving_features = []
for name, coef in zip(all_features, model_lasso.coef_):
    if abs(coef) > 1e-6:
        surviving_features.append(name)
        print(f"  {name}: {coef:.6e}")
    else:
        print(f"  {name}: DROPPED")

print(f"\nFeatures kept: {len(surviving_features)} / {len(all_features)}")

# Predictions
y_pred_lasso_train = model_lasso.predict(X_full_train_scaled)
y_pred_lasso_test = model_lasso.predict(X_full_test_scaled)

# Metrics
r2_lasso_train = r2_score(y_train, y_pred_lasso_train)
r2_lasso_test = r2_score(y_test, y_pred_lasso_test)
rmse_lasso = np.sqrt(mean_squared_error(y_test, y_pred_lasso_test))
mape_lasso = mean_absolute_percentage_error(y_test, y_pred_lasso_test) * 100

print(f"\nPerformance:")
print(f"  Train R²: {r2_lasso_train:.4f}")
print(f"  Test R²:  {r2_lasso_test:.4f}")
print(f"  RMSE:     {rmse_lasso:.4f} L")
print(f"  MAPE:     {mape_lasso:.1f}%")

# Cross-validation
cv_scores_lasso = cross_val_score(model_lasso, X_full_scaled, y, cv=5, scoring='r2')
print(f"  5-Fold CV R²: {cv_scores_lasso.mean():.4f} (±{cv_scores_lasso.std():.4f})")

# ============================================================
# 6. MODEL COMPARISON
# ============================================================

print("\n" + "="*60)
print("MODEL COMPARISON")
print("="*60)

# --- F-Test (Physics vs Full OLS) ---
# Fit full OLS for F-test comparison
model_full_ols = LinearRegression()
model_full_ols.fit(X_full_train, y_train)
y_pred_full = model_full_ols.predict(X_full_test)

# Residual sum of squares
rss_physics = np.sum((y_test - y_pred_phys_test) ** 2)
rss_full = np.sum((y_test - y_pred_full) ** 2)

# Degrees of freedom
n = len(y_test)
p_physics = len(physics_features) + 1  # +1 for intercept
p_full = len(all_features) + 1

# F-statistic
f_stat = ((rss_physics - rss_full) / (p_full - p_physics)) / (rss_full / (n - p_full))

from scipy import stats
f_pvalue = 1 - stats.f.cdf(f_stat, p_full - p_physics, n - p_full)

print(f"\nF-Test (Physics vs Full Model):")
print(f"  F-statistic: {f_stat:.2f}")
print(f"  p-value: {f_pvalue:.4e}")
if f_pvalue < 0.05:
    print(f"  → Full model is significantly better (p < 0.05)")
else:
    print(f"  → No significant improvement from extra features")

# --- AIC/BIC ---
def calc_aic_bic(y_true, y_pred, k):
    """Calculate AIC and BIC. k = number of parameters."""
    n = len(y_true)
    rss = np.sum((y_true - y_pred) ** 2)
    
    # Log-likelihood (assuming normal errors)
    ll = -n/2 * (np.log(2 * np.pi) + np.log(rss/n) + 1)
    
    aic = 2*k - 2*ll
    bic = k*np.log(n) - 2*ll
    return aic, bic

aic_phys, bic_phys = calc_aic_bic(y_test, y_pred_phys_test, p_physics)
aic_lasso, bic_lasso = calc_aic_bic(y_test, y_pred_lasso_test, len(surviving_features) + 1)
aic_full, bic_full = calc_aic_bic(y_test, y_pred_full, p_full)

print(f"\nInformation Criteria (lower is better):")
print(f"  {'Model':<20} {'AIC':>12} {'BIC':>12}")
print(f"  {'-'*20} {'-'*12} {'-'*12}")
print(f"  {'Physics (4 feat)':<20} {aic_phys:>12.1f} {bic_phys:>12.1f}")
print(f"  {f'LASSO ({len(surviving_features)} feat)':<20} {aic_lasso:>12.1f} {bic_lasso:>12.1f}")
print(f"  {f'Full OLS ({len(all_features)} feat)':<20} {aic_full:>12.1f} {bic_full:>12.1f}")

# --- Summary Table ---
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"\n  {'Model':<15} {'Test R²':>10} {'RMSE':>10} {'MAPE':>10} {'Features':>10}")
print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
print(f"  {'Physics':<15} {r2_phys_test:>10.4f} {rmse_phys:>10.4f} {mape_phys:>9.1f}% {len(physics_features):>10}")
print(f"  {'LASSO':<15} {r2_lasso_test:>10.4f} {rmse_lasso:>10.4f} {mape_lasso:>9.1f}% {len(surviving_features):>10}")
print(f"  {'Full OLS':<15} {r2_score(y_test, y_pred_full):>10.4f} {np.sqrt(mean_squared_error(y_test, y_pred_full)):>10.4f} {mean_absolute_percentage_error(y_test, y_pred_full)*100:>9.1f}% {len(all_features):>10}")

# ============================================================
# 7. SAVE MODELS
# ============================================================

print(f"\n{'='*60}")
print("SAVING MODELS")
print(f"{'='*60}")

output_dir = '/Users/fli6/Desktop/Projects/pathos_model_updated/Final_Outputs/'

joblib.dump({
    'model': model_physics,
    'features': physics_features,
    'metrics': {'r2': r2_phys_test, 'rmse': rmse_phys, 'mape': mape_phys}
}, output_dir + 'fuel_model_physics.joblib')

joblib.dump({
    'model': model_lasso,
    'scaler': scaler,
    'features': all_features,
    'surviving_features': surviving_features,
    'metrics': {'r2': r2_lasso_test, 'rmse': rmse_lasso, 'mape': mape_lasso}
}, output_dir + 'fuel_model_lasso.joblib')

print(f"✓ Saved fuel_model_physics.joblib")
print(f"✓ Saved fuel_model_lasso.joblib")

# ============================================================
# 8. RECOMMENDATION
# ============================================================

print(f"\n{'='*60}")
print("RECOMMENDATION")
print(f"{'='*60}")

if r2_lasso_test > r2_phys_test + 0.02:
    print("\n→ LASSO model shows meaningful improvement.")
    print(f"  Consider using LASSO features: {surviving_features}")
elif r2_phys_test >= r2_lasso_test:
    print("\n→ Physics-informed model performs as well or better.")
    print("  Prefer it for interpretability and extrapolation.")
else:
    print("\n→ Models are comparable. Physics model preferred for:")
    print("  - Interpretability (coefficients have physical meaning)")
    print("  - Extrapolation to school buses (different weight range)")