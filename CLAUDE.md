# pathOS — CLAUDE.md

## What This Is
pathOS is a fuel-optimized route planner for commercial fleets (originally Ithaca, NY school district food delivery buses). Users enter stops, the system finds the order that minimizes fuel consumption and CO₂ — not just shortest distance — using a physics-based ML model trained on real vehicle data.

## Architecture

```
Frontend (Next.js / Vercel)
  ↓ POST /optimize_route
Backend (Flask / Render)
  ↓ OSRM Table API → distance/duration matrices
  ↓ MatrixBuilder → elevation (ORS), speed, fuel matrices
  ↓ RouteOptimizer → TSP (OR-Tools) + Simulated Annealing (5 rounds)
  ↓ OSRM Route API → polyline geometry
  ↑ optimizedStops, routeGeometry, metrics (distance/duration/fuel/CO2), modelLoaded, modelR2
```

## Key Files

| File | Role |
|------|------|
| `backend/app/app.py` | Flask entry point, `/optimize_route` and `/health` endpoints |
| `backend/app/matrix_builder.py` | Builds NxN matrices (distance, duration, speed, elevation, fuel); loads trained ML model |
| `backend/app/route_optimizer.py` | TSP (OR-Tools) + Simulated Annealing optimizer |
| `backend/app/config.py` | Env vars: OSRM_HOST, OSRM_WAKE_URL, ORS_API_KEY, MODEL_PATH |
| `frontend/src/app/explore/page.tsx` | Route input form, state management, backend calls |
| `frontend/src/app/explore/MapView.tsx` | Leaflet map, AnalyticsPanel, model info display |
| `frontend/src/app/explore/PlacesAutocomplete.tsx` | Nominatim (OSM) address search |
| `ml/New_Code/ML_Regression/linear_regression.py` | Training pipeline → produces fuel_model_physics.joblib |
| `ml/Final_Outputs/fuel_model_physics.joblib` | Trained LinearRegression (R²=0.8888) |

## ML Model Integration (wired April 2026)

The physics-informed fuel model is now loaded at backend startup:
- `MatrixBuilder.__init__()` loads `ml/Final_Outputs/fuel_model_physics.joblib`
- Features: `[Total_Distance_km, Dist_x_Weight, Elev_x_Weight, Dist_x_Speed2]`
- If load fails → falls back to hardcoded coefficients (same values, no behavior change)
- `get_physics_betas()` exposes model coefficients to `RouteOptimizer`
- `build()` returns `model_loaded: bool` and `model_r2: float | null`
- API response includes `modelLoaded` and `modelR2`, displayed in frontend AnalyticsPanel
- Override model path: set `MODEL_PATH` env var on Render

## Cost Model (per leg)
```
fuel = β₀ + β₁·dist + β₂·(dist×weight) + β₃·(elev×weight) + β₄·(dist×speed²)
```
Weight accumulates as pickups are made (load-aware VRP). Diesel correction = 0.65.

## Infrastructure
| Component | Provider | Notes |
|-----------|----------|-------|
| Frontend | Vercel | Next.js App Router |
| Backend | Render | Free tier, cold starts mitigated by /health ping |
| OSRM | AWS EC2 t3.large | NYS dataset; can be paused; woken via OSRM_WAKE_URL |
| ORS | External API | Elevation only; optional (falls back to 0m) |

## Known Gaps (as of April 2026)
- `maintainOrder` checkbox commented out in UI (backend fully supports it)
- `currentFuel`, `time`, `vehicleNumber` in frontend formData but unused by backend
- `matrixRunId` stored in metrics but not surfaced in UI
- `data/{run_id}/` matrices saved per-run but no retrieval API
- `archive/` and `ml/No_N2_production.py` are dead/disconnected code
- Footer hidden on mobile; contact page has `[EMAIL_ADDRESS]` placeholder

## Training Pipeline
Run from `ml/New_Code/ML_Regression/`:
```bash
python linear_regression.py
```
Input: `ml/Final_Outputs/trip_summaries_clean.csv` (1.7M eVED vehicle trips)
Output: `ml/Final_Outputs/fuel_model_physics.joblib` (and lasso variant)
Paths are now relative — no hardcoded user paths.

## Changes Log
- **April 2026**: Wired ML pipeline into backend — `MatrixBuilder` now loads trained `.joblib` model instead of using hardcoded coefficients. Model metadata exposed in API response and frontend AnalyticsPanel. Fixed hardcoded `/Users/fli6/...` paths in `linear_regression.py`. Added `scikit-learn` and `joblib` to `requirements.txt`.
