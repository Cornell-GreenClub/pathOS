"""
Test the swap functionality with a fake distance matrix.
No OSRM server needed.
"""
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

from route_optimizer import RouteOptimizer

def main():
    fake_api_response = {
        "sources": [
            {"name": "Depot (TST BOCES)"},
            {"name": "School A"},
            {"name": "School B"},
            {"name": "School C"},
            {"name": "School D"},
        ],
        "distances": [
            [0,    5000, 8000, 12000, 3000],
            [5000, 0,    3000, 7000,  9000],
            [8000, 3000, 0,    2000,  6000],
            [12000,7000, 2000, 0,     4000],
            [3000, 9000, 6000, 4000,  0    ],
        ],
    }

    optimizer = RouteOptimizer({"SOLVER_TIME_LIMIT": 10})
    
    print("\n=== Running optimizer with random swap ===\n")
    result = optimizer.optimize_route(fake_api_response, mpg=10.0)
    
    print(f"\nFinal route indices: {result}")

if __name__ == "__main__":
    main()