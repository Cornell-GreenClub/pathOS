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
import logging
import requests
import config
import time
from route_optimizer import RouteOptimizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)
CORS(app)

try:
    optimizer = RouteOptimizer(app.config)
except Exception as e:
    logging.critical(f"Could not initialize RouteOptimizer: {e}")
    optimizer = None



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
    max_retries = 15  # Up to 75 seconds
    
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
            elif resp.status_code == 202:
                logging.info(f"OSRM server is waking up... (attempt {i+1}/{max_retries})")
            else:
                logging.warning(f"Unexpected wake response: {resp.status_code} {resp.text}")
        except Exception as e:
            logging.error(f"Error waking OSRM server: {e}")
            
        time.sleep(5)
        
    logging.error("Failed to wake OSRM server within the timeout.")
    return config.OSRM_HOST


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

    maintain_order = bool(payload.get("maintainOrder", False))

    # Validate coords
    for i, s in enumerate(stops):
        c = s.get("coords")
        if not c or "lat" not in c or "lng" not in c:
            return jsonify({"error": f"Stop at index {i} is missing coords.lat/coords.lng."}), 400

    try:
        # --- Wake up OSRM server ---
        osrm_host = get_osrm_host()

        # --- PRINT ORIGINAL STOPS ---
        print_stops("ORIGINAL STOP ORDER", normalize_stops_for_printing(stops))

        if maintain_order:
            ordered_stops = stops
        else:
            # --- Call OSRM Table API ---
            table_url = format_table_url(stops, osrm_host)
            table_resp = requests.get(table_url, timeout=10)
            table_data = table_resp.json()

            # Inject original location names into the OSRM response so the optimizer prints them
            # (Matches logic in calculate_sample_savings.py)
            if table_data and 'sources' in table_data:
                for i, source in enumerate(table_data['sources']):
                    # OSRM sources correspond to the input coordinates order
                    if i < len(stops):
                        source['name'] = stops[i].get('location', 'Unknown')

            # --- Call RouteOptimizer ---
            distances = table_data.get("distances", [])
            n = len(distances)
            
            # Bridge the new complex ML optimizer by passing distances as the primary cost function
            # and zeroing out the advanced machine-learning metrics until they are fully integrated.
            elev_matrix = [[0.0] * n for _ in range(n)]
            speed_matrix = [[1.0] * n for _ in range(n)]
            weights = {i: 0.0 for i in range(n)}
            betas = {"Intercept": 0.0, "Total_Distance_km": 1.0, "Dist_x_Weight": 0.0, "Elev_x_Weight": 0.0, "Dist_x_Speed2": 0.0}
            base_veh = 1000.0
            names = [str(i) for i in range(n)]

            reordered = optimizer.optimize_route(
                fuel_matrix=distances,
                distance_matrix=distances,
                elevation_matrix=elev_matrix,
                speed_matrix=speed_matrix,
                weights=weights,
                betas=betas,
                base_vehicle_kg=base_veh,
                location_names=names
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

        distance = route_data["routes"][0].get("distance")
        duration = route_data["routes"][0].get("duration")

        return jsonify({
            "optimizedStops": ordered_stops,
            "routeGeometry": route_geometry_latlng,
            "distance": distance,
            "duration": duration
        })

    except Exception as e:
        logging.error(f"Exception in /optimize_route: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


if __name__ == "__main__":
    logging.info(f"Starting Flask server on {config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(debug=True, host=config.FLASK_HOST, port=config.FLASK_PORT)
