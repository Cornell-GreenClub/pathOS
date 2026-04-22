"""
Matrix Builder - Generates all NxN matrices needed by RouteOptimizer.

Given OSRM table output (distances in meters, durations in seconds) and stop
coordinates, produces:
  - distance_matrix  (NxN, km)
  - duration_matrix  (NxN, minutes)
  - speed_matrix     (NxN, km/h)
  - elevation_matrix (NxN, elevation gain in meters, i→j)
  - fuel_matrix      (NxN, liters, physics model at base vehicle weight)

The fuel_matrix uses the BASE vehicle weight throughout (not load-accumulating).
This is intentional: the TSP solver only needs relative leg costs to find a
distance-efficient ordering — load awareness is handled later by RouteOptimizer's
SA step, which uses the full _route_cost model with cumulative pickup weights.

Fetches elevation from ORS API when ORS_API_KEY is set; otherwise falls back
to 0 m for all stops (elevation is a secondary cost term, so the fallback still
produces a useful optimization).

Saves all matrices as CSV to pathos/data/{run_id}/.
"""

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import openrouteservice
    _ORS_AVAILABLE = True
except ImportError:
    _ORS_AVAILABLE = False

try:
    import joblib
    import numpy as np
    _JOBLIB_AVAILABLE = True
except ImportError:
    _JOBLIB_AVAILABLE = False


# Default model path: ml/Final_Outputs/ relative to the project root.
# backend/app/matrix_builder.py → parent.parent.parent = project root
_DEFAULT_MODEL_PATH = (
    Path(__file__).parent.parent.parent / 'ml' / 'Final_Outputs' / 'fuel_model_physics.joblib'
)


class MatrixBuilder:
    """
    Builds all NxN matrices needed by RouteOptimizer from OSRM + ORS data.
    """

    def __init__(self, ors_api_key: Optional[str] = None):
        key = ors_api_key or os.environ.get('ORS_API_KEY')
        self._ors_client = None
        if key and _ORS_AVAILABLE:
            try:
                self._ors_client = openrouteservice.Client(key=key)
                logging.info("ORS client ready for elevation queries.")
            except Exception as exc:
                logging.warning(f"ORS client init failed: {exc}")

        # Beta boundaries define which ML coefficients to use based on vehicle weight class.
        # Heavier vehicles have different fuel consumption characteristics.
        _bb_path = Path(__file__).parent / 'beta_boundaries.json'
        with open(_bb_path, 'r', encoding='utf-8') as _f:
            self._beta_boundaries: dict = json.load(_f)
        logging.info(f"Loaded beta boundaries ({list(self._beta_boundaries.keys())})")
        self.fuel_corrections  = self._beta_boundaries['fuel_corrections']
        self.co2_kg_per_liter  = self._beta_boundaries['co2_kg_per_liter']

        # The sklearn model is loaded for metadata only (model_loaded, model_r2 in API response).
        # The actual beta coefficients used for routing come from beta_boundaries.json,
        # not from the model object directly — this keeps the optimizer deterministic
        # even if the model file is unavailable.
        self._sklearn_model = None
        self._model_metrics = None

        if _JOBLIB_AVAILABLE:
            _env_path = os.environ.get('MODEL_PATH', '')
            model_path = Path(_env_path) if _env_path else _DEFAULT_MODEL_PATH
            try:
                model_data = joblib.load(model_path)
                sk_model = model_data.get('model') if isinstance(model_data, dict) else model_data
                if hasattr(sk_model, 'predict') and hasattr(sk_model, 'coef_'):
                    self._sklearn_model = sk_model
                    self._model_metrics = model_data.get('metrics') if isinstance(model_data, dict) else None
                    r2 = self._model_metrics.get('r2') if self._model_metrics else None
                    logging.info(
                        f"Loaded fuel model from: {model_path}"
                        + (f" (R²={r2:.4f})" if r2 is not None else "")
                    )
                else:
                    logging.warning("Model file found but object is not a fitted sklearn model. Model metadata unavailable.")
            except Exception as exc:
                logging.warning(f"Could not load fuel model ({exc}). Model metadata unavailable.")
        else:
            logging.warning("joblib/numpy not available. Model metadata unavailable.")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_physics_betas(self, vehicle_weight_kg: int) -> Dict:
        """
        Return the beta coefficient dict for RouteOptimizer for the given vehicle weight.
        Bucket: <5000 kg → 0_5k, 5000–9999 → 5k_10k, 10000–19999 → 10k_20k, ≥20000 → 20k.
        """
        c = self._select_betas(vehicle_weight_kg)
        return {
            'Intercept':         c['Intercept'],
            'Total_Distance_km': c['Total_Distance_km'],
            'Dist_x_Weight':     c['Dist_x_Weight'],
            'Elev_x_Weight':     c['Elev_x_Weight'],
            'Dist_x_Speed2':     c['Dist_x_Speed2'],
        }

    def _select_betas(self, vehicle_weight_kg: int) -> Dict:
        """Return the raw beta dict from beta_boundaries.json for the given vehicle weight (kg)."""
        w = int(vehicle_weight_kg)
        if w < 5000:
            return self._beta_boundaries['0_5k']
        elif w < 10000:
            return self._beta_boundaries['5k_10k']
        elif w < 20000:
            return self._beta_boundaries['10k_20k']
        else:
            return self._beta_boundaries['20k']

    def build(
        self,
        osrm_distances_m:  List[List[float]],
        osrm_durations_s:  List[List[float]],
        coords_latlon:     List[Dict],          # [{"lat": …, "lng": …}, …]
        vehicle_weight_kg: float = 9000,
        fuel_type:         str   = 'diesel',
    ) -> Dict:
        """
        Build all matrices from OSRM table data.

        Returns a dict with keys:
          distance_matrix, duration_matrix, speed_matrix,
          elevation_matrix, fuel_matrix, elevations,
          vehicle_weight_kg, fuel_type, fuel_correction
        """
        n = len(osrm_distances_m)
        fuel_type = fuel_type.lower()
        fuel_correction = self.fuel_corrections.get(fuel_type, 1.0)

        # OSRM meters → km, seconds → minutes
        dist_km  = [[osrm_distances_m[i][j] / 1000.0 for j in range(n)] for i in range(n)]
        dur_min  = [[osrm_durations_s[i][j]  / 60.0  for j in range(n)] for i in range(n)]

        # Speed = distance / time. Diagonal defaults to 50 km/h (never used in routing,
        # but prevents division-by-zero if the matrix is ever accessed on the diagonal).
        speed_kmh = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dur_hr = dur_min[i][j] / 60.0
                if i != j and dur_hr > 0:
                    speed_kmh[i][j] = dist_km[i][j] / dur_hr
                else:
                    speed_kmh[i][j] = 50.0

        # Elevation (one ORS call, or zeros)
        elevations = self._get_elevations(coords_latlon)

        # Only uphill elevation counts as extra fuel cost — coasting downhill
        # is not modeled as regenerative energy recovery in this diesel model.
        elev_gain = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    elev_gain[i][j] = max(0.0, elevations[j] - elevations[i])

        # Fuel matrix uses the static base vehicle weight throughout.
        # This is intentional: the TSP solver needs relative leg costs to find a
        # geographically efficient starting order. Load-aware costs are applied
        # later in RouteOptimizer._route_cost during the SA refinement step.
        w = vehicle_weight_kg
        fuel = [[0.0] * n for _ in range(n)]
        c = self._select_betas(vehicle_weight_kg)

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d = dist_km[i][j]
                e = elev_gain[i][j]
                s = speed_kmh[i][j]
                raw = (
                    c['Intercept']
                    + c['Total_Distance_km'] * d
                    + c['Dist_x_Weight']     * (d * w)
                    + c['Elev_x_Weight']     * (e * w)
                    + c['Dist_x_Speed2']     * (d * s * s)
                )
                # fuel_correction converts raw model output to liters for the given fuel type.
                # Note: RouteOptimizer._route_cost does NOT apply this factor —
                # app.py multiplies the cost output by fuel_correction externally.
                fuel[i][j] = max(0.0, raw * fuel_correction)

        model_r2 = (
            self._model_metrics.get('r2') if self._model_metrics else None
        )

        return {
            'distance_matrix':  dist_km,
            'duration_matrix':  dur_min,
            'speed_matrix':     speed_kmh,
            'elevation_matrix': elev_gain,
            'fuel_matrix':      fuel,
            'elevations':       elevations,
            'vehicle_weight_kg': vehicle_weight_kg,
            'fuel_type':        fuel_type,
            'fuel_correction':  fuel_correction,
            'model_loaded':     self._sklearn_model is not None,
            'model_r2':         model_r2,
        }

    def save(
        self,
        matrices:       Dict,
        run_id:         str,
        location_names: Optional[List[str]] = None,
        stop_weights:   Optional[Dict[int, float]] = None,
        metadata:       Optional[Dict] = None,
    ) -> str:
        """
        Save matrices to pathos/data/{run_id}/.

        Returns the absolute path to the folder.
        """
        data_root = Path(__file__).parent.parent.parent / 'data'
        run_dir   = data_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        n      = len(matrices['distance_matrix'])
        labels = location_names or [f'Stop_{i}' for i in range(n)]

        def _write_csv(name: str, matrix: List[List[float]]) -> None:
            with open(run_dir / name, 'w', newline='', encoding='utf-8') as fh:
                w = csv.writer(fh)
                w.writerow([''] + labels)
                for i, row in enumerate(matrix):
                    w.writerow([labels[i]] + [round(v, 6) for v in row])

        _write_csv('distance_matrix.csv',  matrices['distance_matrix'])
        _write_csv('duration_matrix.csv',  matrices['duration_matrix'])
        _write_csv('speed_matrix.csv',     matrices['speed_matrix'])
        _write_csv('elevation_matrix.csv', matrices['elevation_matrix'])
        _write_csv('fuel_matrix.csv',      matrices['fuel_matrix'])

        with open(run_dir / 'elevations.json', 'w', encoding='utf-8') as fh:
            json.dump(
                {labels[i]: matrices['elevations'][i] for i in range(n)},
                fh, indent=2
            )

        if stop_weights is not None:
            total_pickup = sum(stop_weights.values())
            weights_out = {
                'by_index':        {str(i): stop_weights.get(i, 0.0) for i in range(n)},
                'by_name':         {labels[i]: stop_weights.get(i, 0.0) for i in range(n)},
                'total_pickup_kg': round(total_pickup, 4),
                'base_vehicle_kg': matrices['vehicle_weight_kg'],
                'max_loaded_kg':   round(matrices['vehicle_weight_kg'] + total_pickup, 4),
            }
            with open(run_dir / 'stop_weights.json', 'w', encoding='utf-8') as fh:
                json.dump(weights_out, fh, indent=2)

        meta = {
            'run_id':            run_id,
            'n_stops':           n,
            'vehicle_weight_kg': matrices['vehicle_weight_kg'],
            'fuel_type':         matrices['fuel_type'],
            'fuel_correction':   matrices['fuel_correction'],
            'timestamp':         datetime.utcnow().isoformat() + 'Z',
            'labels':            labels,
        }
        if metadata:
            meta.update(metadata)

        with open(run_dir / 'metadata.json', 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=2)

        logging.info(f"Matrices saved → {run_dir}")
        return str(run_dir)

    def total_fuel(
        self,
        route:        List[int],
        fuel_matrix:  List[List[float]],
    ) -> float:
        """Sum fuel consumption along a route (list of stop indices)."""
        return sum(
            fuel_matrix[route[i]][route[i + 1]]
            for i in range(len(route) - 1)
        )

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_elevations(self, coords_latlon: List[Dict]) -> List[float]:
        """Return elevation (metres) for each stop. Falls back to zeros."""
        if self._ors_client is None:
            logging.info("ORS not configured — using 0 m elevation for all stops.")
            return [0.0] * len(coords_latlon)

        # ORS elevation_line expects [[lon, lat], …]
        coords_lonlat = [[c['lng'], c['lat']] for c in coords_latlon]
        try:
            result = self._ors_client.elevation_line(
                format_in='polyline',
                format_out='polyline',
                geometry=coords_lonlat,
            )
            if result and 'geometry' in result:
                elevs = [pt[2] for pt in result['geometry']]
                logging.info(f"ORS elevation: {len(elevs)} stops queried.")
                return elevs
        except Exception as exc:
            logging.warning(f"ORS elevation query failed ({exc}) — using 0 m fallback.")

        return [0.0] * len(coords_latlon)
