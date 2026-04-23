"""
Flask Web Server
Receives an API-style JSON object, optionally optimizes the route via your RouteOptimizer
(using an OSRM distance matrix), then returns the reordered stops and route geometry.

Data Flow:
1. Client sends a list of stops + config (fuel, maintainOrder).
2. Server calls OSRM Table API to get a distance matrix for all stops.
3. Server passes matrix to RouteOptimizer (OR-Tools) to find the optimal order (TSP).
4. Server reorders stops based on optimizer output.
5. Server calls OSRM Route API to get the final path geometry (lat/lng points) for the map.
6. Server returns optimized stops, geometry, and stats to client.
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
from matrix_builder import MatrixBuilder, CO2_KG_PER_LITER

# Configure logging
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
    Wake up the OSRM server if a wake URL is provided.
    Returns the OSRM host IP.
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
    Build OSRM table API URL for a list of stops.
    The Table API returns a square matrix of travel times/distances between all pairs of coordinates.
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
    Build OSRM route API URL for ordered stops with GeoJSON overview.
    The Route API returns the actual path geometry (waypoints) to draw on the map.
    """
    host = osrm_host or config.OSRM_HOST
    coords_list = [f"{s['coords']['lng']},{s['coords']['lat']}" for s in stops]
    return f"{host}/route/v1/driving/{';'.join(coords_list)}?overview=full&geometries=geojson&steps=false"



@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight endpoint to wake up the server."""
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
            {"location": "Address 1", "coords": {"lat": ..., "lng": ...}},
            ...
        ],
        "maintainOrder": boolean,  # If true, skips optimization
        "currentFuel": float       # MPG for cost calculation
    }

    Returns:
    {
        "optimizedStops": [...],   # Reordered list of stops
        "routeGeometry": [[lat, lng], ...], # Polyline points for map
        "distance": float,         # Total distance in meters
        "duration": float          # Total duration in seconds
    }
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
    vehicle_weight_kg  = float(payload.get("vehicleWeightKg", 9000))
    fuel_type          = str(payload.get("fuelType", "diesel")).lower()

    # Validate coords
    for i, s in enumerate(stops):
        c = s.get("coords")
        if not c or "lat" not in c or "lng" not in c:
            return jsonify({"error": f"Stop at index {i} is missing coords.lat/coords.lng."}), 400

    try:
        # --- Wake up OSRM server ---
        osrm_host = get_osrm_host()
        if not osrm_host:
            return jsonify({"error": "The OSRM Server is still warming up. Please try again in a moment."}), 503

        # --- PRINT ORIGINAL STOPS ---
        print_stops("ORIGINAL STOP ORDER", normalize_stops_for_printing(stops))

        run_id   = None
        matrices = {}
        reordered = None
        original_distance_km  = None
        original_duration_min = None
        original_fuel_liters  = None
        original_co2_kg       = None

        if maintain_order:
            ordered_stops = stops
        else:
            # --- Call OSRM Table API ---
            table_url = format_table_url(stops, osrm_host)
            table_resp = requests.get(table_url, timeout=10)
            table_data = table_resp.json()

            # Inject original location names into the OSRM response so the optimizer prints them
            if table_data and 'sources' in table_data:
                for i, source in enumerate(table_data['sources']):
                    if i < len(stops):
                        source['name'] = stops[i].get('location', 'Unknown')

            osrm_distances_m = table_data.get("distances", [])
            osrm_durations_s = table_data.get("durations", [])
            n = len(osrm_distances_m)

            # --- Build full physics matrices ---
            coords = [s["coords"] for s in stops]
            matrices = matrix_builder.build(
                osrm_distances_m=osrm_distances_m,
                osrm_durations_s=osrm_durations_s,
                coords_latlon=coords,
                vehicle_weight_kg=vehicle_weight_kg,
                fuel_type=fuel_type,
            )

            # Betas sourced from the loaded model (or fallback coefficients)
            betas = matrix_builder.get_physics_betas()

            # --- Build per-stop pickup weights from frontend inputs ---
            # TSP uses the weight-agnostic fuel_matrix (base vehicle weight only).
            # SA accumulates these weights stop-by-stop (load-dependent VRP).
            weights = {i: float(stops[i].get('weightKg', 0)) for i in range(n)}
            total_pickup_kg = sum(weights.values())
            logging.info(
                f"Per-stop weights: {weights} | total pickup: {total_pickup_kg:.1f} kg"
            )

            # --- Compute original (sequential) route metrics for before/after comparison ---
            # Fuel uses optimizer._route_cost so accumulated pickup weights are applied,
            # matching exactly how the optimizer evaluates routes (multiply by fuel_correction
            # to convert raw model output → litres).
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
                original_fuel_liters * CO2_KG_PER_LITER.get(fuel_type, 2.68), 2
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

            # --- Save matrices to pathos/data/ ---
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

            # --- Call RouteOptimizer with real physics matrices + stop weights ---
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

            # --- PRINT RAW OPTIMIZER OUTPUT ---
            logging.info("=== OPTIMIZER RAW OUTPUT ===")
            logging.info(reordered)
            logging.info("============================")

            # --- Map optimizer output ---
            ordered_stops = []
            if isinstance(reordered, list):
                # If elements are dicts with coords, use them directly
                if len(reordered) > 0 and isinstance(reordered[0], dict) and "coords" in reordered[0]:
                    ordered_stops = reordered
                # If elements are ints, treat as indices
                elif all(isinstance(x, int) for x in reordered):
                    ordered_stops = [stops[i] for i in reordered]
                # If elements are strings representing indices
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



        # --- PRINT OPTIMIZED STOPS ---
        print_stops("OPTIMIZED STOP ORDER", normalize_stops_for_printing(ordered_stops))

        # --- Call OSRM Route API ---
        route_url = format_route_url(ordered_stops, osrm_host)
        route_resp = requests.get(route_url, timeout=10)
        route_data = route_resp.json()

        geometry_coords = route_data["routes"][0]["geometry"]["coordinates"]
        route_geometry_latlng = [[coord[1], coord[0]] for coord in geometry_coords]

        distance = route_data["routes"][0].get("distance")   # metres
        duration = route_data["routes"][0].get("duration")   # seconds

        # --- Compute fuel / CO2 metrics if matrices were built ---
        fuel_liters = None
        co2_kg      = None
        # Default to OSRM Route API values; overridden by matrix values when available
        distance_km  = round(distance / 1000, 2) if distance else None
        duration_min = round(duration / 60, 1)   if duration else None

        if not maintain_order and isinstance(reordered, list) and all(isinstance(x, int) for x in reordered):
            try:
                # Weight-aware fuel: same accumulated-weight model the optimizer used
                fuel_liters = round(
                    optimizer._route_cost(
                        reordered,
                        matrices['distance_matrix'], matrices['elevation_matrix'],
                        matrices['speed_matrix'], weights, betas, vehicle_weight_kg,
                    ) * matrices['fuel_correction'], 2
                )
                co2_kg = round(
                    fuel_liters * CO2_KG_PER_LITER.get(fuel_type, 2.68), 2
                )
                # Recompute distance/duration from matrices so they're comparable to
                # originalDistanceKm / originalDurationMin (same data source, apples-to-apples)
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
