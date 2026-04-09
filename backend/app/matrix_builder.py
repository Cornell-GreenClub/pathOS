"""
Matrix Builder - Generates all NxN matrices needed by RouteOptimizer.

Given OSRM table output (distances in meters, durations in seconds) and stop
coordinates, produces:
  - distance_matrix  (NxN, km)
  - duration_matrix  (NxN, minutes)
  - speed_matrix     (NxN, km/h)
  - elevation_matrix (NxN, elevation gain in meters, i→j)
  - fuel_matrix      (NxN, liters, physics model)

Fetches elevation from ORS API when ORS_API_KEY is set; otherwise falls back
to 0 m for all stops.

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

# Physics model fallback coefficients (trained on eVED data, March 2026)
_COEFF = {
    'intercept':       0.025024,
    'Total_Distance_km': 0.06962583,
    'Dist_x_Weight':   0.00005552431,
    'Elev_x_Weight':   0.000002550080,
    'Dist_x_Speed2':   0.000001102072,
}

DIESEL_CORRECTION   = 0.65
GASOLINE_CORRECTION = 1.0

CO2_KG_PER_LITER = {
    'diesel':   2.68,
    'gasoline': 2.31,
}

# Betas for RouteOptimizer (match physics model coefficients exactly)
PHYSICS_BETAS = {
    'Intercept':         _COEFF['intercept'],
    'Total_Distance_km': _COEFF['Total_Distance_km'],
    'Dist_x_Weight':     _COEFF['Dist_x_Weight'],
    'Elev_x_Weight':     _COEFF['Elev_x_Weight'],
    'Dist_x_Speed2':     _COEFF['Dist_x_Speed2'],
}


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

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

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
        fuel_correction = (
            DIESEL_CORRECTION if fuel_type == 'diesel' else GASOLINE_CORRECTION
        )

        # OSRM meters → km, seconds → minutes
        dist_km  = [[osrm_distances_m[i][j] / 1000.0 for j in range(n)] for i in range(n)]
        dur_min  = [[osrm_durations_s[i][j]  / 60.0  for j in range(n)] for i in range(n)]

        # Speed matrix (km/h) = dist_km / dur_hr
        speed_kmh = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dur_hr = dur_min[i][j] / 60.0
                if i != j and dur_hr > 0:
                    speed_kmh[i][j] = dist_km[i][j] / dur_hr
                else:
                    speed_kmh[i][j] = 50.0  # sensible default

        # Elevation (one ORS call, or zeros)
        elevations = self._get_elevations(coords_latlon)

        # Elevation gain matrix: metres gained travelling from i to j
        elev_gain = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    elev_gain[i][j] = max(0.0, elevations[j] - elevations[i])

        # Fuel matrix (liters) using physics model
        w = vehicle_weight_kg
        fuel = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d = dist_km[i][j]
                e = elev_gain[i][j]
                s = speed_kmh[i][j]
                raw = (
                    _COEFF['intercept']
                    + _COEFF['Total_Distance_km'] * d
                    + _COEFF['Dist_x_Weight']     * (d * w)
                    + _COEFF['Elev_x_Weight']      * (e * w)
                    + _COEFF['Dist_x_Speed2']      * (d * s * s)
                )
                fuel[i][j] = max(0.0, raw * fuel_correction)

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

        # Per-stop pickup weights (load-dependent VRP input for SA)
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
