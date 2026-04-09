"""
Route Optimization: TSP + Simulated Annealing with multi-factor cost model.

Pipeline:
1. TSP solver (OR-Tools) finds initial round-trip route using fuel consumption matrix.
   Route starts and ends at depot (index 0).
2. Simulated Annealing refines using full cost model:
   cost_per_leg = B0 + B1(Dist) + B2(Dist*Weight) + B3(Elev*Weight) + B4(Dist*Speed^2)
   where Weight = base_vehicle_kg + accumulated pickup weight.
"""
import math
import random
import logging
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

FUEL_SCALE = 10000  # Scale fuel floats to ints for OR-Tools


class RouteOptimizer:

    def __init__(self, config):
        logging.info("Initializing RouteOptimizer...")
        self.config = config
        self.solver_time_limit_seconds = int(config.get("SOLVER_TIME_LIMIT", 10))
        logging.info(f"Optimizer ready (Time Limit: {self.solver_time_limit_seconds}s)")

    def optimize_route(self, fuel_matrix, distance_matrix, elevation_matrix,
                       speed_matrix, weights, betas, base_vehicle_kg,
                       location_names):
        """
        Main entry point. Returns open-path route [0, ..., n-1].
        Start (index 0) and end (index n-1) are fixed; middle stops are optimized.
        """
        n = len(location_names)
        if n <= 2:
            logging.info("2 or fewer stops - no optimization needed.")
            return list(range(n))

        # Step 1: TSP on fuel matrix (open path: fixed start 0, fixed end n-1)
        tsp_route = self._solve_tsp(fuel_matrix, location_names)
        if not tsp_route:
            logging.warning("TSP solver failed.")
            return None

        self.last_tsp_route = tsp_route
        tsp_dist = self._route_distance(tsp_route, distance_matrix)
        tsp_cost = self._route_cost(tsp_route, distance_matrix, elevation_matrix,
                                     speed_matrix, weights, betas, base_vehicle_kg)

        logging.info("=" * 80)
        logging.info("TSP RESULT (fuel-matrix based, open path)")
        logging.info(f"  Route:    {' -> '.join(location_names[i] for i in tsp_route)}")
        logging.info(f"  Distance: {tsp_dist:.4f} km")
        logging.info(f"  Cost:     {tsp_cost:.6f}")
        logging.info("=" * 80)

        # Step 2: Simulated Annealing (5 rounds, each more greedy than the last)
        sa_configs = [
            {"initial_temp_pct": 0.8,  "cooling_rate": 0.998, "max_iterations": 5000},
            {"initial_temp_pct": 0.5,  "cooling_rate": 0.997, "max_iterations": 5000},
            {"initial_temp_pct": 0.3,  "cooling_rate": 0.995, "max_iterations": 4000},
            {"initial_temp_pct": 0.2,  "cooling_rate": 0.993, "max_iterations": 3000},
            {"initial_temp_pct": 0.1,  "cooling_rate": 0.990, "max_iterations": 2000},
        ]

        sa_route = tsp_route
        for i, cfg in enumerate(sa_configs, 1):
            logging.info(f"\n--- SA ROUND {i}/5 ---")
            candidate = self._simulated_annealing(
                sa_route, location_names, distance_matrix, elevation_matrix,
                speed_matrix, weights, betas, base_vehicle_kg,
                initial_temp_pct=cfg["initial_temp_pct"],
                cooling_rate=cfg["cooling_rate"],
                max_iterations=cfg["max_iterations"],
            )
            cand_cost = self._route_cost(candidate, distance_matrix, elevation_matrix,
                                          speed_matrix, weights, betas, base_vehicle_kg)
            sa_cost = self._route_cost(sa_route, distance_matrix, elevation_matrix,
                                        speed_matrix, weights, betas, base_vehicle_kg)
            if cand_cost < sa_cost:
                sa_route = candidate

        sa_dist = self._route_distance(sa_route, distance_matrix)
        sa_cost = self._route_cost(sa_route, distance_matrix, elevation_matrix,
                                    speed_matrix, weights, betas, base_vehicle_kg)

        logging.info("=" * 80)
        logging.info("FINAL RESULT")
        logging.info(f"  Route:    {' -> '.join(location_names[i] for i in sa_route)}")
        logging.info(f"  Distance: {sa_dist:.4f} km")
        logging.info(f"  Cost:     {sa_cost:.6f}")
        diff = tsp_cost - sa_cost
        if diff > 0:
            logging.info(f"  SA saved: {diff:.6f} ({(diff / tsp_cost) * 100:.2f}% vs TSP)")
        else:
            logging.info(f"  SA did not improve on TSP.")
        logging.info("=" * 80)

        return sa_route

    # ==================== COST MODEL ====================

    def _leg_cost(self, from_idx, to_idx, cumulative_weight,
                  distance_matrix, elevation_matrix, speed_matrix, betas):
        d = distance_matrix[from_idx][to_idx]
        e = elevation_matrix[from_idx][to_idx]
        s = speed_matrix[from_idx][to_idx]
        w = cumulative_weight
        return (betas["Intercept"]
                + betas["Total_Distance_km"] * d
                + betas["Dist_x_Weight"] * (d * w)
                + betas["Elev_x_Weight"] * (e * w)
                + betas["Dist_x_Speed2"] * (d * s * s))

    def _route_cost(self, route, distance_matrix, elevation_matrix,
                    speed_matrix, weights, betas, base_vehicle_kg):
        total = 0.0
        cumulative_weight = base_vehicle_kg
        for i in range(len(route) - 1):
            cumulative_weight += weights.get(route[i], 0)
            total += self._leg_cost(route[i], route[i + 1], cumulative_weight,
                                     distance_matrix, elevation_matrix,
                                     speed_matrix, betas)
        return total

    def _route_distance(self, route, distance_matrix):
        return sum(distance_matrix[route[i]][route[i + 1]]
                   for i in range(len(route) - 1))

    # ==================== SIMULATED ANNEALING ====================

    def _simulated_annealing(self, route, location_names,
                              distance_matrix, elevation_matrix, speed_matrix,
                              weights, betas, base_vehicle_kg,
                              initial_temp_pct=0.5, cooling_rate=0.995,
                              min_temp=0.0001, max_iterations=5000):
        """
        SA with full cost model. First and last stops (depot) are FIXED.
        All middle stops are free to swap.
        """
        swappable = list(range(1, len(route) - 1))
        if len(swappable) < 2:
            logging.info("Not enough middle stops for SA.")
            return route

        current = route.copy()
        current_cost = self._route_cost(current, distance_matrix, elevation_matrix,
                                         speed_matrix, weights, betas, base_vehicle_kg)
        start_cost = current_cost
        best = current.copy()
        best_cost = current_cost

        initial_temp = max(abs(start_cost) * initial_temp_pct, 1.0)
        temp = initial_temp

        accepted = improved = worse_accepted = 0

        for it in range(1, max_iterations + 1):
            if temp < min_temp:
                break

            # 2-opt
            pos_a, pos_b = sorted(random.sample(swappable, 2))
            candidate = current.copy()
            if random.random() < 0.5:
                candidate[pos_a], candidate[pos_b] = candidate[pos_b], candidate[pos_a]
            else:
                candidate[pos_a:pos_b + 1] = reversed(candidate[pos_a:pos_b + 1])

            pos_a, pos_b = random.sample(swappable, 2)
            candidate = current.copy()
            candidate[pos_a], candidate[pos_b] = candidate[pos_b], candidate[pos_a]

            cand_cost = self._route_cost(candidate, distance_matrix, elevation_matrix,
                                          speed_matrix, weights, betas, base_vehicle_kg)

            delta = cand_cost - current_cost
            swap_label = f"{location_names[current[pos_a]]} <-> {location_names[current[pos_b]]}"

            if delta < 0:
                current, current_cost = candidate, cand_cost
                result = "ACCEPT (better)"
                accepted += 1; improved += 1
            else:
                prob = math.exp(-delta / max(temp, 1e-15))
                if random.random() < prob:
                    current, current_cost = candidate, cand_cost
                    result = f"ACCEPT (worse p={prob:.3f})"
                    accepted += 1; worse_accepted += 1
                else:
                    result = "REJECT"

            if current_cost < best_cost:
                best, best_cost = current.copy(), current_cost

            if it <= 10 or it % 500 == 0:
                logging.info(f"{it:<6} {swap_label:<55} {cand_cost:>10.4f} {temp:>10.4f} {result}")

            temp *= cooling_rate

        logging.info("-" * 95)
        logging.info(f"SA done: {it} iters | accepted: {accepted} "
                     f"(improved: {improved}, worse: {worse_accepted})")
        logging.info(f"Input cost: {start_cost:.6f}  ->  SA best: {best_cost:.6f}")
        change = start_cost - best_cost
        if change > 0:
            logging.info(f"SA IMPROVED by {change:.6f} ({(change / start_cost) * 100:.2f}%)")
        else:
            logging.info("SA did not improve.")
        logging.info("=" * 95)

        return best

    # ==================== TSP SOLVER ====================

    def _solve_tsp(self, fuel_matrix, location_names):
        """
        Solves open-path TSP: fixed start at index 0, fixed end at index n-1.

        Technique: use OR-Tools round-trip formulation but block middle stops
        from returning to the depot (cost = INF) and make the end stop's return
        to the depot free (cost = 0). This forces the route:
            0 -> [middle stops] -> n-1 -> depot (free)
        The trailing depot is stripped before returning.
        """
        n = len(fuel_matrix)
        INF = 10 ** 9

        int_matrix = [[int(round(fuel_matrix[i][j] * FUEL_SCALE))
                        for j in range(n)] for i in range(n)]

        # Block middle stops (1..n-2) from returning to depot
        for i in range(1, n - 1):
            int_matrix[i][0] = INF
        # End stop (n-1) returns to depot for free — not a real leg
        int_matrix[n - 1][0] = 0

        manager = pywrapcp.RoutingIndexManager(n, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def cost_cb(fi, ti):
            return int_matrix[manager.IndexToNode(fi)][manager.IndexToNode(ti)]

        cb_idx = routing.RegisterTransitCallback(cost_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(cb_idx)

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

        logging.info(f"\nSolving TSP on fuel matrix ({n} stops, open path 0 -> {n-1})...")
        solution = routing.SolveWithParameters(params)

        if not solution:
            logging.warning("No TSP solution found.")
            return []

        route = []
        idx = routing.Start(0)
        while not routing.IsEnd(idx):
            route.append(manager.IndexToNode(idx))
            idx = solution.Value(routing.NextVar(idx))
        # Do not append the end depot node — the route already ends at n-1

        logging.info(f"TSP route: {' -> '.join(location_names[i] for i in route)}")
        return route