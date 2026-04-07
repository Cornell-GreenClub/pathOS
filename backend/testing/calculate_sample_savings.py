import requests
import logging
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../app'))

from route_optimizer import RouteOptimizer
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_sample_stops():
    """Returns the list of sample stops with trusted coordinates."""
    return [
        {
          "location": 'TST BOCES, 555 Warren Road, Northeast Ithaca, NY 14850',
          "coords": { "lat": 42.476169, "lng": -76.465092 },
        },
        {
          "location": 'Dewitt Middle School, 560 Warren Road, Ithaca, NY 14850',
          "coords": { "lat": 42.475434, "lng": -76.468026 },
        },
        {
          "location":
            'Northeast Elementary School, 425 Winthrop Dr, Ithaca, NY 14850',
          "coords": { "lat": 42.472932, "lng": -76.468742 },
        },
        {
          "location":
            'Cayuga Heights Elementary School, 110 E Upland Rd, Ithaca, NY 14850',
          "coords": { "lat": 42.465637, "lng": -76.488499 },
        },
        {
          "location":
            'Belle Sherman Elementary School, Valley Road, Ithaca, NY 14853',
          "coords": { "lat": 42.435757, "lng": -76.481317 },
        },
        {
          "location":
            'Caroline Elementary School, Slaterville Road, Besemer, NY 14881',
          "coords": { "lat": 42.392593, "lng": -76.3715585 },
        },
        {
          "location":
            'South Hill Elementary School, 520 Hudson Street, Ithaca, NY 14850',
          "coords": { "lat": 42.4338533, "lng": -76.4931807 },
        },
        {
          "location":
            'Beverly J. Martin Elementary School, 302 West Buffalo Street, Ithaca, NY',
          "coords": { "lat": 42.4422, "lng": -76.4976 },
        },
        {
          "location": 'Fall Creek School, Linn Street, Ithaca, NY 14850',
          "coords": { "lat": 42.4415514, "lng": -76.5021644 },
        },
        {
          "location":
            'Boynton Middle School, 1601 North Cayuga Street, Ithaca, NY 14850',
          "coords": { "lat": 42.4606674, "lng": -76.500035 },
        },
        {
          "location": '602 Hancock Street, Ithaca, NY 14850',
          "coords": { "lat": 42.4460873, "lng": -76.5065422 },
        },
        {
          "location": '737 Willow Ave, Ithaca, NY 14850',
          "coords": { "lat": 42.453183, "lng": -76.5053133 },
        },
        {
          "location": 'Enfield School, 20 Enfield Main Road, Ithaca, NY 14850',
          "coords": { "lat": 42.449517, "lng": -76.6316132 },
        },
        {
          "location":
            'Lehmann Alternative Community School, 111 Chestnut Street, Ithaca, NY',
          "coords": { "lat": 42.440077, "lng": -76.5177744 },
        },
        {
          "location":
            'Recycling and Solid Waste Center, 160 Commercial Avenue, Ithaca, NY',
          "coords": { "lat": 42.4242689, "lng": -76.5159428 },
        },
    ]

def get_osrm_matrix(stops, osrm_host):
    """
    Fetches the distance matrix from the OSRM server.
    """
    coords_list = [f"{s['coords']['lng']},{s['coords']['lat']}" for s in stops]
    osrm_url = f"{osrm_host}/table/v1/driving/{';'.join(coords_list)}?annotations=distance,duration"
    
    print(f"Fetching distance matrix from: {osrm_host}...")
    try:
        response = requests.get(osrm_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching from OSRM: {e}")
        return None

def print_original_route_breakdown(stops, table_data):
    """
    Prints the leg-by-leg breakdown of the original route.
    """
    print("\n--- Original Route Breakdown ---")
    distances = table_data['distances']
    total_dist = 0
    for i in range(len(stops)):
        from_idx = i
        to_idx = (i + 1) % len(stops) # Wrap around to start (TSP cycle)
        dist = distances[from_idx][to_idx]
        total_dist += dist
        print(f"{i}->{to_idx}: {stops[from_idx]['location'][:30]}... -> {stops[to_idx]['location'][:30]}... : {dist/1000.0:.2f} km")
    print(f"Total Original Distance: {total_dist/1000.0:.2f} km\n")

def main():
    stops = get_sample_stops()
    
    # 1. Get Distance Matrix
    from app import get_osrm_host
    osrm_host = get_osrm_host()
    table_data = get_osrm_matrix(stops, osrm_host)
    
    if not table_data:
        return

    # 2. Print Original Route Stats
    print_original_route_breakdown(stops, table_data)

    # 3. Run Optimizer
    optimizer = RouteOptimizer({"SOLVER_TIME_LIMIT": 10})
    print(f"Optimizing route (Distance Only)...")
    # We know TST BOCES burns 246 L per week (5 trips)
    
    # Inject original location names into the OSRM response so the optimizer prints them
    if table_data and 'sources' in table_data:
        for i, source in enumerate(table_data['sources']):
            source['name'] = stops[i]['location']

    optimizer.optimize_route(table_data, mpg=3.65873553349)

if __name__ == "__main__":
    main()
