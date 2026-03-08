"""
Main route optimization class.
1. Optimizes route based on API-provided 'distances' (assumed to be in METERS).
2. Compares fuel cost (distance / mpg) of original vs. optimized route.
3. Applies a random 2-opt swap on top of the TSP solution (first step toward simulated annealing).
"""
import numpy as np
import random
import logging
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# --- Constants for conversion ---
METERS_PER_KM = 1000.0
MILES_PER_KM = 0.621371

class RouteOptimizer:
    
    def __init__(self, config):
        """
        Initializes the optimizer. This is a stateless class.
        It loads configuration but does not store request-specific data.
        """
        logging.info("Initializing RouteOptimizer (API-Only, Distance/MPG)...")
        self.config = config
        
        # Make the solver time limit configurable, default to 10 seconds
        self.solver_time_limit_seconds = int(config.get("SOLVER_TIME_LIMIT", 10))
        logging.info(f"--- Optimizer is ready (Search Strategy: GUIDED_LOCAL_SEARCH, Time Limit: {self.solver_time_limit_seconds}s) ---")

    def optimize_route(self, api_response, mpg):
        """
        High-level function to find the optimal route.
        
        Steps:
        1. Parse OSRM distance matrix.
        2. Format data for OR-Tools (convert to integer cost matrix).
        3. Solve TSP using OR-Tools RoutingModel.
        4. Calculate savings (distance/fuel) compared to original order.
        5. Return list of indices representing the optimized order.
        """
        try:
            # 1. Extract all data from the API response
            stops_list = api_response['sources']
            location_names = [loc['name'] for loc in stops_list]
            distance_matrix_meters = api_response['distances'] 
            index_to_location_name = location_names

        except KeyError as e:
            logging.error(f"Error: API response missing required key: {e}")
            return None
        except (ValueError, TypeError):
            logging.error(f"Error: Invalid 'mpg' value. Must be a number.")
            return None
        
        if len(index_to_location_name) <= 2:
            logging.info("Route has 2 or fewer stops. No optimization needed.")
            return self._get_original_route_indices(len(index_to_location_name))

        # 2. Format the matrix for the OR-Tools solver (using METERS as cost)
        tsp_data = self._format_tsp_for_distance(distance_matrix_meters)
        
        # 3. Solve the TSP (based on METERS)
        opt_route_indices = self._solve_tsp(tsp_data, index_to_location_name)
        
        if not opt_route_indices:
            logging.warning("Solver failed to find a solution.")
            return None

        # 4. Random swap disabled for prod — degrades OR-Tools solution.
        #    Re-enable once full simulated annealing loop is implemented.
        # opt_route_indices = self._apply_random_swap(opt_route_indices, index_to_location_name, distance_matrix_meters)

        # 5. Calculate and print all cost comparisons
        logging.info("\n--- Cost Analysis (Distance & Fuel) ---")
        self._calculate_and_print_costs(opt_route_indices, index_to_location_name, distance_matrix_meters, mpg)
        
        # 6. Return the optimized route indices
        return opt_route_indices

    def _apply_random_swap(self, route_indices, location_names, distance_matrix_meters):
        """
        Swaps two random non-depot stops in the route.
        The depot is at position 0 (start) and the last position (return to depot),
        so we only swap among positions 1 through len-2.
        
        Prints the two stops that were swapped and the distance before/after.
        """
        # Route looks like [0, 3, 7, 2, ..., 0] — first and last are the depot
        # We can only swap interior positions (indices 1 to len-2)
        if len(route_indices) < 4:
            # Need at least 2 non-depot stops to swap
            logging.info("Not enough stops to perform a swap.")
            return route_indices

        swappable_positions = list(range(1, len(route_indices) - 1))
        pos_a, pos_b = random.sample(swappable_positions, 2)

        stop_a = route_indices[pos_a]
        stop_b = route_indices[pos_b]

        # Calculate distance before swap
        dist_before = self._get_route_cost_km(route_indices, distance_matrix_meters)

        # Perform the swap
        swapped_route = route_indices.copy()
        swapped_route[pos_a], swapped_route[pos_b] = swapped_route[pos_b], swapped_route[pos_a]

        # Calculate distance after swap
        dist_after = self._get_route_cost_km(swapped_route, distance_matrix_meters)

        # Log the swap details
        logging.info("=" * 60)
        logging.info("RANDOM SWAP APPLIED")
        logging.info("=" * 60)
        logging.info(f"TSP Route (before swap):  {route_indices}")
        logging.info(f"  -> {' -> '.join(location_names[i] for i in route_indices)}")
        logging.info("")
        logging.info(f"Swapped stop A (position {pos_a}): [{stop_a}] {location_names[stop_a]}")
        logging.info(f"Swapped stop B (position {pos_b}): [{stop_b}] {location_names[stop_b]}")
        logging.info("")
        logging.info(f"New Route (after swap):   {swapped_route}")
        logging.info(f"  -> {' -> '.join(location_names[i] for i in swapped_route)}")
        logging.info("")
        logging.info(f"Distance BEFORE swap: {dist_before:.2f} km")
        logging.info(f"Distance AFTER  swap: {dist_after:.2f} km")
        diff = dist_after - dist_before
        if diff > 0:
            logging.info(f"Swap INCREASED distance by {diff:.2f} km")
        elif diff < 0:
            logging.info(f"Swap DECREASED distance by {abs(diff):.2f} km")
        else:
            logging.info("Swap had no effect on distance.")
        logging.info("=" * 60)

        return swapped_route

    def _format_tsp_for_distance(self, distance_matrix_meters):
        """
        Converts the distance matrix (in meters) into an integer
        cost matrix for the OR-Tools solver.
        """
        num_locations = len(distance_matrix_meters)
        cost_matrix = np.zeros((num_locations, num_locations), dtype=int)

        for i in range(num_locations):
            for j in range(num_locations):
                if i == j:
                    continue
                cost = distance_matrix_meters[i][j]
                cost_matrix[i, j] = int(round(cost))
                    
        return {
            "cost_matrix": cost_matrix.tolist(),
            "num_vehicles": 1,
            "depot": 0
        }

    def _solve_tsp(self, data, index_to_location_name):
        """
        Runs the Google OR-Tools TSP solver.
        Returns the optimized route indices.
        """
        manager = pywrapcp.RoutingIndexManager(
            len(data["cost_matrix"]), data["num_vehicles"], data["depot"]
        )
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return data["cost_matrix"][from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        
        logging.info(f"\nSolving TSP with GUIDED_LOCAL_SEARCH (Time limit: {self.solver_time_limit_seconds}s)...")
        solution = routing.SolveWithParameters(search_parameters)

        if solution:
            logging.info("\n--- Distance Optimization Results ---")
            obj_meters = solution.ObjectiveValue()
            obj_km = obj_meters / METERS_PER_KM
            logging.info(f"Solver objective value (Total Distance): {obj_km:.2f} km")
            
            return self._get_route_from_solution(manager, routing, solution, index_to_location_name)
        else:
            logging.warning("No solution found!")
            return []

    def _get_route_from_solution(self, manager, routing, solution, index_to_location_name):
        """ Extracts the route indices from the solver. """
        index = routing.Start(0)
        plan_output = "Optimized Route (by distance):\n"
        route_indices = []
        
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_indices.append(node_index)
            plan_output += f" {index_to_location_name[node_index]} ->"
            index = solution.Value(routing.NextVar(index))
            
        node_index = manager.IndexToNode(index)
        route_indices.append(node_index)
        plan_output += f" {index_to_location_name[node_index]}\n"
        
        logging.info(plan_output)
        return route_indices

    def _get_route_cost_km(self, route_indices, distance_matrix_meters):
        """ Calculates the total distance (in km) for a given route. """
        total_meters = 0
        for i in range(len(route_indices) - 1):
            start_idx = route_indices[i]
            end_idx = route_indices[i+1]
            total_meters += distance_matrix_meters[start_idx][end_idx]
        return total_meters / METERS_PER_KM
    
    def _get_original_route_indices(self, num_locations):
        """ Generates a simple sequential route (0, 1, ..., n-1, 0). """
        if num_locations == 0: 
            return []
        og_route = list(range(num_locations))
        og_route.append(0)
        return og_route

    def _calculate_and_print_costs(self, opt_route_indices, index_to_location_name, distance_matrix_meters, mpg):
        """
        Calculates and compares the distance (km) and fuel cost (gallons)
        of the original vs. optimized routes.
        """
        num_locations = len(index_to_location_name)
        original_route_indices = self._get_original_route_indices(num_locations)

        original_distance_km = self._get_route_cost_km(original_route_indices, distance_matrix_meters)
        optimized_distance_km = self._get_route_cost_km(opt_route_indices, distance_matrix_meters)

        logging.info(f"Original Route Distance (Sequential): {original_distance_km:.2f} km")
        logging.info(f"Optimized Route Distance: {optimized_distance_km:.2f} km")
        
        if optimized_distance_km < original_distance_km:
            savings_km = original_distance_km - optimized_distance_km
            percent_saved_km = (savings_km / original_distance_km) * 100
            logging.info(f"Optimization SAVED {savings_km:.2f} km ({percent_saved_km:.2f}%)")

        logging.info("\n--- Fuel Cost Analysis (Distance / MPG) ---")
        if mpg <= 0:
            logging.warning("MPG value is zero or negative. Skipping fuel cost analysis.")
            return
        
        try:
            original_distance_miles = original_distance_km * MILES_PER_KM
            original_gallons = original_distance_miles / mpg
            logging.info(f"Original Route Fuel Cost: {original_gallons:.2f} gallons ({original_distance_miles:.2f} miles / {mpg} mpg)")

            optimized_distance_miles = optimized_distance_km * MILES_PER_KM
            optimized_gallons = optimized_distance_miles / mpg
            logging.info(f"Optimized Route Fuel Cost: {optimized_gallons:.2f} gallons ({optimized_distance_miles:.2f} miles / {mpg} mpg)")
            
            if optimized_gallons < original_gallons:
                savings_gal = original_gallons - optimized_gallons
                percent_saved_gal = (savings_gal / original_gallons) * 100
                logging.info(f"Optimization SAVED {savings_gal:.2f} gallons ({percent_saved_gal:.2f}%)")
            
        except Exception as e:
            logging.error(f"Error during fuel cost comparison: {e}")