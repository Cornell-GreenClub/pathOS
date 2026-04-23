"""
Flask Web Server — pathOS route optimization API.

Request flow for /optimize_route:
1. Client sends stops + config (vehicle weight, fuel type, maintainOrder flag).
2. Server wakes OSRM if needed, then calls OSRM Table API to get an NxN
   distance/duration matrix for all stops.
3. MatrixBuilder converts that into distance, speed, elevation, and fuel matrices.
4. RouteOptimizer reorders the middle stops to minimize physics-based fuel cost.
5. Server calls OSRM Route API on the optimized stop order to get the polyline
   geometry for the map (separate call — Table API only gives pairwise costs,
   not the actual path shape).
6. Response includes reordered stops, geometry, fuel/CO2 metrics, and
   before/after comparison values.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import logging
import re
import requests
import config
import time
from datetime import datetime
from pathlib import Path
from route_optimizer import RouteOptimizer
from matrix_builder import MatrixBuilder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://www.pathos.earth", "http://localhost:3000"]}})

try:
    optimizer = RouteOptimizer(app.config)
except Exception as e:
    logging.critical(f"Could not initialize RouteOptimizer: {e}")
    optimizer = None

matrix_builder = MatrixBuilder(ors_api_key=config.ORS_API_KEY)



def print_stops(label, stops):
    """Nicely print a list of stops with coordinates."""
    logging.info("=" * 60)
    logging.info(f"{label}")
    logging.info("=" * 60)
    for i, s in enumerate(stops):
        loc = s.get("location", "No Name")
        coords = s.get("coords", {})
        lat = coords.get("lat")
        lng = coords.get("lng")
        logging.info(f"{i+1}. {loc}  |  lat: {lat}, lng: {lng}")
    logging.info("=" * 60)


def normalize_stops_for_printing(stops):
    """Ensure every stop has a string 'location' for printing."""
    normalized = []
    for s in stops:
        stop_copy = s.copy()
        loc = s.get("location")
        if isinstance(loc, list) and len(loc) == 2:
            stop_copy["location"] = f"Lat {loc[1]:.6f}, Lng {loc[0]:.6f}"
        elif not isinstance(loc, str):
            stop_copy["location"] = "Unknown Location"
        normalized.append(stop_copy)
    return normalized


def get_osrm_host():
    """
    Wake up the OSRM server if a wake URL is provided, then return its host URL.
    The OSRM server runs on AWS EC2 and may be stopped to save cost — the wake
    URL hits a Lambda that starts it and polls until the OSRM engine is ready.
    """
    if not config.OSRM_WAKE_URL:
        return config.OSRM_HOST

    headers = {"x-osrm-secret": config.OSRM_WAKE_SECRET}
    max_retries = 18  # Up to 90 seconds

    for i in range(max_retries):
        try:
            resp = requests.get(config.OSRM_WAKE_URL, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "running" and data.get("ip"):
                    osrm_url = f"http://{data['ip']}:5000"
                    try:
                        requests.get(osrm_url, timeout=3)
                        return osrm_url
                    except requests.exceptions.RequestException:
                        logging.info("EC2 running, waiting for OSRM Engine to load into memory...")
                else:
                    logging.info(f"Lambda OK, but EC2 not running yet. Lambda output: {data}")
            elif resp.status_code == 202:
                logging.info(f"OSRM server is waking up... (attempt {i+1}/{max_retries})")
            else:
                logging.warning(f"Unexpected wake response: {resp.status_code} {resp.text}")
        except Exception as e:
            logging.error(f"Error waking OSRM server: {e}")

        time.sleep(5)

    logging.error("Failed to wake OSRM server within the timeout.")
    return None


def format_table_url(stops, osrm_host=None):
    """
    Build OSRM Table API URL — returns an NxN matrix of pairwise
    travel distances and durations between all stops.
    """
    host = osrm_host or config.OSRM_HOST
    coords_list = []
    for s in stops:
        c = s.get("coords")
        if c is None or "lat" not in c or "lng" not in c:
            raise ValueError("All stops must include coords with lat and lng.")
        coords_list.append(f"{c['lng']},{c['lat']}")
    return f"{host}/table/v1/driving/{';'.join(coords_list)}?annotations=distance,duration"


def format_route_url(stops, osrm_host=None):
    """
    Build OSRM Route API URL — returns the actual road path geometry
    (lat/lng polyline) for the ordered list of stops, used to draw the
    route on the map. Separate from the Table API call.
    """
    host = osrm_host or config.OSRM_HOST
    coords_list = [f"{s['coords']['lng']},{s['coords']['lat']}" for s in stops]
    return f"{host}/route/v1/driving/{';'.join(coords_list)}?overview=full&geometries=geojson&steps=false"



@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight endpoint to keep the Render server warm between requests."""
    return jsonify({"status": "ok"}), 200


@app.route("/run/<run_id>", methods=["GET"])
def get_run(run_id):
    """Return metadata for a saved optimization run."""
    if not re.match(r'^[\w\-]+$', run_id):
        return jsonify({"error": "Invalid run ID"}), 400
    data_root = Path(__file__).parent.parent.parent / 'data'
    meta_path = data_root / run_id / 'metadata.json'
    if not meta_path.exists():
        return jsonify({"error": "Run not found"}), 404
    with open(meta_path) as f:
        return jsonify(json.load(f)), 200


@app.route("/optimize_route", methods=["POST"])
def optimize_route():
    """
    Main optimization endpoint.

    Expected JSON Payload:
    {
        "stops": [
            {"location": "Address 1", "coords": {"lat": ..., "lng": ...}, "weightKg": float},
            ...
        ],
        "maintainOrder": boolean,  # If true, skips optimization and goes straight to geometry
        "vehicleWeightKg": int,    # Base vehicle weight (default 9000)
        "fuelType": string         # "diesel" or "gasoline" (default "diesel")
    }

    Returns optimized stop order, map geometry, and before/after fuel metrics.
    """
    if optimizer is None:
        return jsonify({"error": "Optimizer is not initialized. Check server logs."}), 500

    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No JSON payload provided."}), 400

    stops = payload.get("stops")
    if not isinstance(stops, list) or len(stops) < 2:
        return jsonify({"error": "Payload must include a 'stops' list with at least 2 stops."}), 400

    maintain_order     = bool(payload.get("maintainOrder", False))
    vehicle_weight_kg  = int(payload.get("vehicleWeightKg", 9000))
    fuel_type          = str(payload.get("fuelType", "diesel")).lower()

    for i, s in enumerate(stops):
        c = s.get("coords")
        if not c or "lat" not in c or "lng" not in c:
            return jsonify({"error": f"Stop at index {i} is missing coords.lat/coords.lng."}), 400

    try:
        osrm_host = get_osrm_host()
        if not osrm_host:
            return jsonify({"error": "The OSRM Server is still warming up. Please try again in a moment."}), 503

        print_stops("ORIGINAL STOP ORDER", normalize_stops_for_printing(stops))

        run_id   = None
        matrices = {}
        reordered = None
        original_distance_km  = None
        original_duration_min = None
        original_fuel_liters  = None
        original_co2_kg       = None

        if maintain_order:
            # Skip all matrix building and optimization — go straight to geometry.
            ordered_stops = stops
        else:
            # ── OSRM Table API: get pairwise distances and durations ──────────
            table_url = format_table_url(stops, osrm_host)
            table_resp = requests.get(table_url, timeout=10)
            table_data = table_resp.json()

            # Inject stop names into OSRM sources so the optimizer can log them
            if table_data and 'sources' in table_data:
                for i, source in enumerate(table_data['sources']):
                    if i < len(stops):
                        source['name'] = stops[i].get('location', 'Unknown')

            osrm_distances_m = table_data.get("distances", [])
            osrm_durations_s = table_data.get("durations", [])
            n = len(osrm_distances_m)

            # ── Build physics matrices ────────────────────────────────────────
            coords = [s["coords"] for s in stops]
            matrices = matrix_builder.build(
                osrm_distances_m=osrm_distances_m,
                osrm_durations_s=osrm_durations_s,
                coords_latlon=coords,
                vehicle_weight_kg=vehicle_weight_kg,
                fuel_type=fuel_type,
            )

            betas = matrix_builder.get_physics_betas(vehicle_weight_kg)

            # Per-stop pickup weights from the frontend (kg loaded at each stop).
            # Index 0 (depot) typically has weight 0; it's up to the frontend to set this.
            weights = {i: float(stops[i].get('weightKg', 0)) for i in range(n)}
            total_pickup_kg = sum(weights.values())
            logging.info(
                f"Per-stop weights: {weights} | total pickup: {total_pickup_kg:.1f} kg"
            )

            # ── Capture original route metrics BEFORE optimization ────────────
            # This gives the before/after comparison shown in the frontend analytics panel.
            # _route_cost returns raw model output; multiply by fuel_correction for liters.
            original_route = list(range(n))
            original_distance_km = round(
                sum(matrices['distance_matrix'][i][i + 1] for i in range(n - 1)), 2
            )
            original_duration_min = round(
                sum(matrices['duration_matrix'][i][i + 1] for i in range(n - 1)), 1
            )
            original_fuel_liters = round(
                optimizer._route_cost(
                    original_route,
                    matrices['distance_matrix'], matrices['elevation_matrix'],
                    matrices['speed_matrix'], weights, betas, vehicle_weight_kg,
                ) * matrices['fuel_correction'], 2
            )
            original_co2_kg = round(
                original_fuel_liters * matrix_builder.co2_kg_per_liter.get(fuel_type, 2.68), 2
            )
            logging.info(
                f"Original route: {original_distance_km} km | "
                f"{original_duration_min} min | {original_fuel_liters} L | {original_co2_kg} kg CO2"
            )

            # Fetch geometry for original stop order (for frontend overlay)
            original_route_geometry = None
            try:
                orig_route_url = format_route_url(stops, osrm_host)
                orig_route_resp = requests.get(orig_route_url, timeout=10)
                orig_route_data = orig_route_resp.json()
                orig_coords = orig_route_data["routes"][0]["geometry"]["coordinates"]
                original_route_geometry = [[c[1], c[0]] for c in orig_coords]
            except Exception as orig_err:
                logging.warning(f"Could not fetch original route geometry: {orig_err}")

            # ── Save matrices for debugging / analysis ────────────────────────
            run_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S') + f'_{n}stops'
            location_names = [s.get('location', f'Stop_{i}') for i, s in enumerate(stops)]
            try:
                matrix_path = matrix_builder.save(
                    matrices=matrices,
                    run_id=run_id,
                    location_names=location_names,
                    stop_weights=weights,
                    metadata={
                        'osrm_host': osrm_host,
                        'total_pickup_kg': total_pickup_kg,
                        'max_loaded_kg': vehicle_weight_kg + total_pickup_kg,
                    },
                )
                logging.info(f"Matrices saved: {matrix_path}")
            except Exception as save_err:
                logging.warning(f"Could not save matrices: {save_err}")
                matrix_path = None

            # ── Run optimizer ─────────────────────────────────────────────────
            reordered = optimizer.optimize_route(
                fuel_matrix=matrices['fuel_matrix'],
                distance_matrix=matrices['distance_matrix'],
                elevation_matrix=matrices['elevation_matrix'],
                speed_matrix=matrices['speed_matrix'],
                weights=weights,
                betas=betas,
                base_vehicle_kg=vehicle_weight_kg,
                location_names=location_names,
            )

            logging.info("=== OPTIMIZER RAW OUTPUT ===")
            logging.info(reordered)
            logging.info("============================")

            # Map optimizer index output back to stop dicts for the OSRM Route call
            ordered_stops = []
            if isinstance(reordered, list):
                if len(reordered) > 0 and isinstance(reordered[0], dict) and "coords" in reordered[0]:
                    ordered_stops = reordered
                elif all(isinstance(x, int) for x in reordered):
                    ordered_stops = [stops[i] for i in reordered]
                else:
                    try:
                        idxs = [int(x) for x in reordered]
                        ordered_stops = [stops[i] for i in idxs]
                    except Exception:
                        logging.warning("Could not parse optimizer output. Printing original stops as fallback.")
                        ordered_stops = stops
            else:
                logging.warning("Optimizer output not a list. Printing original stops as fallback.")
                ordered_stops = stops



        print_stops("OPTIMIZED STOP ORDER", normalize_stops_for_printing(ordered_stops))

        # ── OSRM Route API: get road geometry for the optimized order ─────────
        # This is a separate call from the Table API — it returns the actual
        # polyline path to draw on the map, not just pairwise cost numbers.
        # Distance/duration here may differ slightly from matrix values because
        # OSRM re-routes through all waypoints in sequence.
        route_url = format_route_url(ordered_stops, osrm_host)
        route_resp = requests.get(route_url, timeout=10)
        route_data = route_resp.json()

        geometry_coords = route_data["routes"][0]["geometry"]["coordinates"]
        route_geometry_latlng = [[coord[1], coord[0]] for coord in geometry_coords]

        distance = route_data["routes"][0].get("distance")   # metres
        duration = route_data["routes"][0].get("duration")   # seconds

        fuel_liters = None
        co2_kg      = None
        distance_km  = round(distance / 1000, 2) if distance else None
        duration_min = round(duration / 60, 1)   if duration else None

        if not maintain_order and isinstance(reordered, list) and all(isinstance(x, int) for x in reordered):
            try:
                # Recompute fuel from the matrix (not the OSRM route) so it's
                # on the same data source as originalFuelLiters — apples-to-apples.
                fuel_liters = round(
                    optimizer._route_cost(
                        reordered,
                        matrices['distance_matrix'], matrices['elevation_matrix'],
                        matrices['speed_matrix'], weights, betas, vehicle_weight_kg,
                    ) * matrices['fuel_correction'], 2
                )
                co2_kg = round(
                    fuel_liters * matrix_builder.co2_kg_per_liter.get(fuel_type, 2.68), 2
                )
                distance_km = round(
                    sum(matrices['distance_matrix'][reordered[i]][reordered[i + 1]]
                        for i in range(len(reordered) - 1)), 2
                )
                duration_min = round(
                    sum(matrices['duration_matrix'][reordered[i]][reordered[i + 1]]
                        for i in range(len(reordered) - 1)), 1
                )
            except Exception as metric_err:
                logging.warning(f"Could not compute fuel metrics: {metric_err}")

        return jsonify({
            "optimizedStops":       ordered_stops,
            "routeGeometry":        route_geometry_latlng,
            "distance":             distance,
            "duration":             duration,
            "distanceKm":           distance_km,
            "durationMin":          duration_min,
            "fuelLiters":           fuel_liters,
            "co2Kg":                co2_kg,
            "originalDistanceKm":      original_distance_km     if not maintain_order else None,
            "originalDurationMin":     original_duration_min    if not maintain_order else None,
            "originalFuelLiters":      original_fuel_liters     if not maintain_order else None,
            "originalCo2Kg":           original_co2_kg          if not maintain_order else None,
            "originalRouteGeometry":   original_route_geometry  if not maintain_order else None,
            "vehicleWeightKg":      vehicle_weight_kg,
            "fuelType":             fuel_type,
            "matrixRunId":          run_id if not maintain_order else None,
            "modelLoaded":          matrices.get("model_loaded") if not maintain_order else None,
            "modelR2":              matrices.get("model_r2")     if not maintain_order else None,
        })

    except Exception as e:
        logging.error(f"Exception in /optimize_route: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


if __name__ == "__main__":
    logging.info(f"Starting Flask server on {config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(debug=True, host=config.FLASK_HOST, port=config.FLASK_PORT)
