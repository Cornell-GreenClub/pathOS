# Algorithm Overview and Data Flow

## File Overview

| File (In `app/`) | Purpose |
| :--- | :--- |
| `app.py` | Main backend API; handles frontend integration and file orchestration |
| `matrix_builder.py` | Builds the necessary matrices for a route query |
| `route_optimizer.py` | Optimizes route based on matrix data |

## Algorithm Overview and Data Flow
Currently, the backend works by taking in a route, constructing the proper matrices according to the key below, and sending the Fuel matrix to the OR-Tools TSP solver:

| Matrix | How It’s Constructed |
| :--- | :--- |
| **Distance** | OSRM server |
| **Duration** | OSRM server |
| **Speed** | Calculated from Distance matrix |
| **Elevation** | ORS API |
| **Fuel** | Based on Distance, Speed, Elevation, the vehicle weight constant, the physics model equation, and specified beta coefficients based on user-inputted vehicle weight. This matrix is weight agnostic (not accounting for load pickups) |

All these matrices are constructed with `app/matrix_builder.py`. `matrix_builder.py` creates a new folder in `pathos/data/` for that route query, and `app/route_optimizer.py` uses these newly constructed matrices as its data for the optimization.

As stated previously, the Fuel matrix is then sent to OR-Tools (via `route_optimizer.py`) and that weight-agnostic route is then sent to the simulated annealing algorithm to account for load pickups.

Data that is sent to the frontend is then calculated and formatted in the `/optimize_route` endpoint (`app.py`).

> **NOTE**
> Although the following testing was done on round trips, we have adjusted the algorithm to no longer do so, as it fits better with our frontend design and user experience.

The entire optimization algorithm does a few steps:
1. Takes in an original route
2. Optimizes this route by sending the generated fuel matrix to the OR-tools TSP solver, giving us a weight-blind, fuel-matrix optimized route (“TSP-optimized”)
3. Sends this route into the simulated annealing (SA) algorithm, getting us our finalized route (“fully optimized”)

*(SA algorithm optimization will be discussed further in this document)*

---

## Optimization Iteration Environment Generation

A few notes about the environment we used to inform our optimization of the SA algorithm:
* Claude-generated route that has a distinct TSP-optimized and fully optimized route. Ideal routes’ costs, distances, and stop order are documented and compared against.
    * Claude was specifically told not to run the routes it generated through the optimization algorithm it had generated, as this would defeat the purpose of generating the baseline test environment. Instead, Claude calculated the costs, distances, and stop order on its own, meaning the environment Claude generated is a valid baseline to test our algorithm against.
* The beta coefficients that were generated with this environment are different from the ones we have derived from the logistic regression we performed on the physics model, however, this shouldn’t affect the validity of our testing.
* The end-to-end optimization algorithm is ran 1000 times, with the average TSP-optimized to fully optimized route improvement being compared against the theoretically best improvement.

---

## Optimization Overview

There are multiple versions of SA we can play around with. The final algorithm we decided on keeping is a combination of all of these:
* **Basic SA**: Randomized pair swaps, keeping the best one.
* **SA with modified temperature, cooling rates, and greediness** (acceptance probabilities).
* **2-opt vs. randomized pair swaps**: Also the probability of which we perform a 2-opt or a pair swap.
* **Multiple “rounds” of SA**: Feed the best SA-generated route into a new SA instance, keeping the best route generated from this round and repeating.

### Optimization Method 1 (OM1): Basic SA With Dynamic Temperature
We first have the temperature parameter set to a relatively high value (100). This gets us close to the best improvement possible per our training data (2.64% away).

However, scaling temperature to the route's cost ensures that the acceptance probability stays in a meaningful range regardless of the magnitude of the cost values (since acceptance probability for a worse swap is $e^{-\Delta / temp}$), making the algorithm self-tuning across different datasets. Therefore, by setting the initial temperature to be half the cost of the initial route, we get an optimization that is now 2.45% away from the best optimization and theoretically better suited for different data.

**TLDR:**
* **Expected** | TSP-optimized → fully optimized improvement: **13.01%**
* **Initial temperature = 100** | TSP-optimized → fully optimized improvement: **10.37%**
* **OM1** | TSP-optimized → fully optimized improvement: **10.56%**

### Optimization Method 2 (OM2): 50% 2-Opt, 50% Randomized Pair Swaps
Building on top of OM1, we can implement a 2-opt approach where on every iteration of the SA algorithm, we have a 50% chance of performing a randomized pair swap (traditional SA) and a 50% chance of performing a 2-opt (two random end points, reverse the sub-route end-to-end). This enhances the optimization by a significant amount, where every SA runthrough gets us the expected improvement.

The reasoning behind a 50/50 split between 2-opt and random pair swaps is to explore many different neighborhoods. With the split, we are able to explore more drastic routes while still getting the added benefits of 2-opt.

**TLDR:**
* **Expected** | TSP-optimized → fully optimized improvement: **13.01%**
* **OM1** | TSP-optimized → fully optimized improvement: **10.37%**
* **OM1 + OM2** | TSP-optimized → fully optimized improvement: **13.01%**

### Optimization Method 3 (OM3): Multi-Round Cooling SA
To ensure the route generated from OM1 + OM2 is the best possible route, we can chain SA algorithms together, passing in the best route generated from SA1 into SA2, then passing the best route from SA2 into SA3, etc.. We have 5 rounds of SA, each one being greedier than the last (lower temperature, faster cooling rate, lower acceptance probabilities of worse routes). Although OM1 + OM2 produces the best optimal route per the training data, because it is a heuristic, adding theoretical improvements can only better our algorithm.

The SA rounds get greedier and greedier as our rounds increase, therefore creating a funnel for the most optimal route. As expected, the output from this addition is the same as OM1 + OM2, but the addition of OM3 is nice to have as a theoretical safety net.

**TLDR:**
* **Expected** | TSP-optimized → fully optimized improvement: **13.01%**
* **OM1** | TSP-optimized → fully optimized improvement: **10.37%**
* **OM1 + OM2** | TSP-optimized → fully optimized improvement: **13.01%**
* **OM1 + OM2 + OM3** | TSP-optimized → fully optimized improvement: **13.01%**

---

## SA Optimization Summary
With all SA OMs applied, we achieve the pre-determined optimized route from the heuristic SA algorithm. The route we find from the TSP and SA (all OMs) finds the optimal route determined by Claude 100% of the time across 5,000 iterations. 

## Overall Performance
We asked Claude Code to generate matrices for ten mock routes (in a similar method to the Optimization Iteration Environment Creation), each consisting of 5-10 stops, and had it brute-force a carbon-optimized solution for all of them. The testing suite lives in `pathos/backend/testing/test_ten/`. Here lives all ten mock routes (`test_route_x/`), as well as a file called `test_ten.py` that is used to test the route optimization against these routes and their brute-force solution (`test_ten/test_route_x/expected_results.json`).

`test_ten.py` runs the route optimizer on each route 100 times, comparing the best optimization we found and average optimization across the 100 runs with the brute-force solution. For all ten routes and all 100 runs for each, the route optimizer found the best solution.
