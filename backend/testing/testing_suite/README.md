# Synthetic Test Dataset for TSP vs Weight-Aware Route Optimization

## Overview

This document describes a synthetic 10-stop test dataset designed to demonstrate the difference between:

1. **TSP (Traveling Salesman Problem)** — Minimizes total distance only
2. **Weight-Aware Optimization** — Minimizes total fuel consumption, accounting for dynamic pickup weights

The key insight: **when pickup weights vary significantly across stops, the optimal fuel route may differ from the shortest distance route.**

---

## Dataset Design

### Design Principle

We created a scenario where:
- **Heavy stops (A, B)** are located in one direction from the depot
- **Light stops (I, J)** are located in a similar distance but different direction
- **Middle stops (C-H)** form a connecting loop

This creates a conflict:
- **TSP** will visit stops in geographic order (A → B → ... → J)
- **Weight-aware** should visit heavy stops **last** to avoid carrying extra weight over long distances

### Stop Layout

| Stop | Coordinates (km) | Weight (kg) | Distance from Depot |
|------|------------------|-------------|---------------------|
| Depot | (0, 0) | 0 | 0.00 |
| Stop A | (2, 2) | **600** | 2.83 |
| Stop B | (3, 4) | **550** | 5.00 |
| Stop C | (5, 6) | 100 | 7.81 |
| Stop D | (7, 5) | 90 | 8.60 |
| Stop E | (9, 4) | 80 | 9.85 |
| Stop F | (10, 2) | 70 | 10.20 |
| Stop G | (9, 0) | 60 | 9.00 |
| Stop H | (7, -1) | 50 | 7.07 |
| Stop I | (4, -2) | **30** | 4.47 |
| Stop J | (2, -1) | **20** | 2.24 |

**Total pickup weight:** 1,650 kg

### Visualization

```
        Stop C (100kg)
           *
      Stop B (550kg)
         *      * Stop D (90kg)
    Stop A (600kg)
       *              * Stop E (80kg)
                           
                            * Stop F (70kg)
  Depot *                  
                         * Stop G (60kg)
       * Stop J (20kg)
            * Stop I (30kg)  * Stop H (50kg)
```

---

## Results

### TSP Optimal (Distance Only)

```
Depot → Stop A → Stop B → Stop C → Stop D → Stop E → Stop F → Stop G → Stop H → Stop I → Stop J → Depot
```

- **Total distance:** 26.71 km
- **Fuel consumption:** 12.222 L

### Weight-Aware Optimal (Minimize Fuel)

```
Depot → Stop J → Stop I → Stop H → Stop G → Stop F → Stop E → Stop D → Stop C → Stop B → Stop A → Depot
```

- **Total distance:** 26.71 km
- **Fuel consumption:** 11.497 L

### Comparison

| Metric | TSP | Weight-Aware | Difference |
|--------|-----|--------------|------------|
| Distance | 26.71 km | 26.71 km | 0.00 km (0%) |
| Fuel | 12.222 L | 11.497 L | **-0.725 L (5.9%)** |

---

## Key Insight

The two routes are **exact reverses** of each other, resulting in identical total distance. However:

- **TSP route:** Picks up heavy stops (A=600kg, B=550kg) early, then carries 1,150 kg of extra weight for most of the route
- **Weight-aware route:** Picks up light stops first, saves heavy stops for last, minimizing fuel burned while carrying heavy loads

This demonstrates that **route optimization for fuel efficiency is not equivalent to TSP** when pickup weights vary.

---

## Fuel Model

The fuel prediction uses a physics-informed model trained on the eVED dataset:

```
Fuel = β₀ + β₁(distance) + β₂(distance × weight) + β₃(elevation × weight) + β₄(distance × speed²)
```

With corrections for heavy vehicles:
- **Tire correction:** 0.5× on rolling resistance term (truck tires have lower Crr than car tires)
- **Diesel correction:** 0.65× (diesel engines more efficient than gasoline)
- **Base vehicle weight:** 15,000 kg

---

## Files

| File | Description |
|------|-------------|
| `test_matrices.json` | Distance, elevation, speed matrices + stop weights + coordinates |
| `expected_results.json` | Optimal routes and fuel values for both TSP and weight-aware |
| `generate_test_route.py` | Script to regenerate the dataset and verify results |

---

## Usage

### Validating a TSP Implementation

```python
# Your TSP should return this route (or its reverse):
expected_tsp = ['Depot', 'Stop A', 'Stop B', 'Stop C', 'Stop D', 'Stop E', 
                'Stop F', 'Stop G', 'Stop H', 'Stop I', 'Stop J', 'Depot']

# Total distance should be 26.71 km
```

### Validating a Weight-Aware (SA) Implementation

```python
# Your SA should converge to this route (or equivalent fuel):
expected_wa = ['Depot', 'Stop J', 'Stop I', 'Stop H', 'Stop G', 'Stop F', 
               'Stop E', 'Stop D', 'Stop C', 'Stop B', 'Stop A', 'Depot']

# Total fuel should be ~11.50 L (5.9% savings vs TSP)
```

---

## Author

Justin Li  
March 2026  
pathOS Project — TST BOCES Route Optimization
