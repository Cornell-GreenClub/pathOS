# Physics-Based Fuel Consumption Model for Route Optimization and Validation

**Primary Authors:** Justin Li, Arnav Dangre  
**Date Drafted:** April 23rd, 2026  
**Authored For:** pathOS Internal, GreenClub Internal, GreenClub TA Suite  

---

## Introduction

To solve the wicked problem within the scope of the pathOS project, it is necessary for the technical team to produce a fuel consumption model that can give an accurate prediction for any given real beginning and destination. 

During the literature review process, the team found the approach for fuel consumption modeling by Zacharof et. al. (2024) especially inspiring. Essentially, Zacharof was able to take massive amounts of real world data and trip parameters (distance, elevation, average speed, etc.) and use statistics to make adjustments to theoretical coefficients.

This approach allowed the model to account for complex real-world behaviors (such as fuel cut-off during deceleration) that are not easily captured by standard physical equations. Furthermore, the authors demonstrated the effectiveness of a hybrid modeling approach: by combining physical coefficients (which account for aerodynamic drag, inertia, and rolling resistance) with a traditional statistical model, they were able to accurately predict fuel consumption across a wider range of driving conditions.

---

## Data

To ensure the pathOS routing matrix is robust across all vehicle types, the model relies on two distinct datasets that capture different ends of the vehicle weight spectrum:

### 1. The eVED Dataset (Light-Duty Baseline)
For passenger vehicles, the model utilizes a subset of the eVED dataset consisting of 3,305 valid trips. This dataset provides high-resolution, real-world telematics for gasoline-powered passenger cars (0 to 5,000 kg). Because these trips encompass real-world noise—such as traffic lights, driver behavior, and cold starts—it serves as a highly rigorous training set for standard commuter routing.

### 2. The Commercial Validation Set (Medium to Heavy-Duty Baseline)
Because heavy-duty telematics data is rarely open-source, we aggregated a highly curated, 27-row dataset from individual benchmark tests and fleet evaluations. Sourced from the NREL (National Renewable Energy Laboratory), NACFE (North American Council for Freight Efficiency), CARB (California Air Resources Board), and the PIT Group, this dataset spans vehicles from 5,000 kg box trucks up to 31,000 kg Class 8 tractor-trailers. Crucially, it includes distinct driving regimes (steady highway, urban stop-and-go, mixed rolling hills) and exact elevation gains.

---

## Modeling Assumptions

To prevent the statistical model from generating physically impossible coefficients (e.g., negative aerodynamic drag or "anti-gravity" climbing), several first-principles thermodynamic and physical assumptions were hardcoded into the baseline:

* **Dichotomous Thermal Efficiency ($\eta$)**: The model assumes light-duty passenger vehicles (0-5,000 kg) utilize Spark Ignition (Gasoline) engines with a peak thermal efficiency of roughly 30% ($\eta = 0.30$) and a Lower Heating Value of 34.2 MJ/L. Commercial vehicles (>5,000 kg) are assumed to utilize Compression Ignition (Diesel) engines with an efficiency of roughly 42% ($\eta = 0.42$) and an LHV of 35.8 MJ/L.
* **Rolling Resistance ($C_r$)**: Passenger tires prioritize comfort and grip ($C \approx 0.010$), whereas high-pressure commercial tires are optimized for minimal rolling friction ($C \approx 0.006$).
* **Aerodynamic Drag and Area ($C_d$ and $A$)**: Frontal area proxies were standardized across weight buckets, ranging from 2.5 m² (compact cars) to 10 m² (Class 8 tractors). Drag coefficients were assumed at 0.30 for aerodynamic passenger cars and 0.60 for flat-nosed commercial trucks.
* **Mechanical Isolation**: We assume that fundamental physics (gravity, aerodynamics, rolling resistance) scale universally, and therefore any remaining "unexplained" fuel consumption is purely the result of mechanical drivetrain loss and baseline idling, which scales linearly with distance. We also do not take into account stops and starts, opting to instead take the average values of speed. We do not consider acceleration either, since it is very difficult to model and has relatively small effects.

---

## Modeling

### The Limitation of Pure Linear Regression
Initial attempts to predict fuel consumption relied on a pure multiple linear regression model utilizing engineered features: Distance, Distance $\times$ Weight, Elevation $\times$ Weight, and Distance $\times$ Speed². For more information on these choices, please see Section IV (4) in the eVED modeling documentation.

While this performed well on the eVED passenger car dataset, scaling the coefficients to heavy-duty trucks resulted in severe over-prediction (exceeding 400% error for Class 8 trucks). When attempting to retrain the regression globally across all weight classes, the model suffered from severe collinearity. Because weight and high speeds are highly correlated in commercial highway data, the algorithm failed to untangle aerodynamics from mass, mathematically rejecting the aerodynamic terms in favor of over-fitting the weight coefficients.

### The Physics-Informed Hybrid Architecture
To resolve this, we adopted a hybrid architecture that mathematically isolates unchangeable physics from learned mechanical inefficiency. The governing equation is defined as:

$$Fuel = \beta_0 + \beta_1(Distance) + \beta_2 (Distance \times Weight) + \beta_3 (Elevation \times Weight) + \beta_4 (Distance \times Speed^2)$$

The modeling pipeline was executed in four steps:
1. **Hardcode Physical Constants**: $\beta_2$, $\beta_3$, and $\beta_4$ were derived directly from the physical assumptions (gravity, air density, thermal efficiency) rather than statistical regression.
2. **Calculate Theoretical Fuel**: A baseline "perfect machine" fuel burn was calculated for every route in the dataset.
3. **Isolate Mechanical Loss**: Theoretical fuel was subtracted from the actual observed fuel to isolate the true mechanical friction and idling losses.
4. **Constrained Optimization**: A non-negative least squares regression was run on the isolated mechanical loss for four distinct weight buckets. The algorithm learned $\beta_0$ (baseline idle loss) and $\beta_1$ (drivetrain loss per km) using only Distance as a feature.

---

## Validation and Results

The hybrid model architecture successfully resolved the commercial scaling failure without sacrificing passenger vehicle accuracy. By separating the variables, the algorithm was able to accurately recognize that Class 8 trucks have significant idle penalties but highly efficient highway power transfer, while urban delivery vans suffer from massive per-kilometer drivetrain inefficiencies due to stop-and-go shifting.

### Passenger Car (eVED) Performance:
When validated against the 3,305 trips in the eVED dataset, the hybrid model achieved:
* **$R^2$**: 0.855
* **Mean Absolute Error (MAE)**: 0.1537 Liters
* **Root Mean Squared Error (RMSE)**: 0.2668 Liters
* **MAPE**: 20.22% (Outperforming the pure ML baseline of 20.80%)

### Commercial Fleet Performance:
When applied to the 27-row mixed commercial dataset, the hybrid model achieved a global $R^2$ of 0.9705, demonstrating extreme resilience to weight scaling. On the TST BOCES route, with a weight of 28,000 kg and the original route described in past pathOS validation, we were able to achieve a 6.2 error [49.2 L (13.0 gal), 52.3 L (13.8 gal)]. 

### Final pathOS Routing Matrix:
Given that different vehicle classes have fundamentally different physics, we split our model to essentially become a piecewise linear function (or linear spline) based on weight. The model produces the following final coefficient matrix for deployment in the pathOS routing engine. *(Note: $\beta_4$ values below have the respective Frontal Area proxy pre-baked into the coefficient for computational efficiency).*

| Weight Class (kg) | $\beta_0$ (Idle/Base L) | $\beta_1$ (Drivetrain L/km) | $\beta_2$ (Rolling) | $\beta_3$ (Grade) | $\beta_4$ (Aero $\times$ Af) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0 - 5,000** | 0.0379 | 0.0539 | 9.56e-06 | 9.56e-07 | 3.45e-06 |
| **5,000 - 10,000** | 0.0000 | 0.1468 | 3.91e-06 | 6.52e-07 | 1.13e-05 |
| **10,000 - 20,000** | 0.0000 | 0.2870 | 3.91e-06 | 6.52e-07 | 1.41e-05 |
| **20,000+** | 2.7788 | 0.0101 | 3.91e-06 | 6.52e-07 | 1.41e-05 |

---

## Next Steps: Client Onboarding & Retraining Guide

### Overview
The pathOS routing engine utilizes a Physics-Informed Hybrid Model. It calculates fundamental thermodynamic and aerodynamic forces using locked physical constants, and utilizes machine learning purely to discover mechanical inefficiencies (drivetrain friction and idling). When working with new commercial clients, the goal is never to dump their raw data into a global pool. Instead, future teams must isolate the client’s data into specific weight-class buckets to retrain the local mechanical inefficiencies ($\beta_0$ and $\beta_1$) while preserving the global physics framework.

### 1. Client Telematics: Essential Parameters
When requesting route data from a new client, you must explicitly ask for the following parameters. Without these four pillars, the physics engine cannot calculate theoretical fuel consumption.

* **Total Distance (km)**: The exact driven length of the route.
* **Gross Vehicle Weight (kg)**: This must be the loaded weight of the vehicle for that specific trip, not just the curb weight of the empty chassis. Gravity and rolling resistance calculations scale exponentially with payload.
* **Net Elevation Gain (m)**: The total vertical meters climbed during the trip. (Elevation loss is generally excluded unless utilizing a specific regenerative braking sub-model).
* **Average Speed (km/h) OR Total Trip Time**: Necessary to calculate aerodynamic drag. If the client provides Total Time and Distance, you can engineer Average Speed via Distance / Time.
* **Total Fuel Consumed (Liters)**: The target variable for the model to predict.

> **Data Engineering Note**: Real-world client data is incredibly noisy. Future teams must aggressively filter out trips with 0 km distance, 0 L fuel, or impossible average speeds (>130 km/h) before passing the data into the retraining pipeline.

### 2. Weight Class Segmentation & Physics Baselines

Vehicles operate under fundamentally different laws of thermodynamics and aerodynamics depending on their size and engine type. All client data must be segmented into the following four strata:

| Strata Name | Weight Range (kg) | Default Engine | Thermal Eff. ($\eta$) | Base Aero Proxy (Af) |
| :--- | :--- | :--- | :--- | :--- |
| **Passenger** | 0 – 5,000 | Gasoline | 30% | 2.5 m² |
| **Light Truck** | 5,000 – 10,000 | Diesel | 42% | 6.0 m² |
| **Medium/Heavy** | 10,000 – 20,000 | Diesel | 42% | 7.5 m² |
| **Heavy (Class 8)** | 20,000+ | Diesel | 42% | 10.0 m² |

**The eVED Baseline Rule**  
The 0 – 5,000 kg bucket is permanently baselined using the eVED dataset (3,300+ real-world passenger car trips).  
Do not mix commercial client data into this bucket unless the client operates a specific fleet of light-duty passenger cars (e.g., a taxi or local courier service). Mixing heavy trucks into the eVED bucket will destroy the passenger car accuracy via dataset imbalance.

### 3. The Retraining Pipeline
When a client provides a new batch of telematics data for their fleet, follow these exact steps to update the pathOS matrix for their specific use case.

#### Step 1: Assign the Physics Constants
Filter the client’s data into the appropriate weight bucket. Apply the correct theoretical physics constants based on the vehicle type:
* **Gasoline (Light-duty)**: $\beta_2 = 9.56e-06$, $\beta_3 = 9.56e-07$, $\beta_4 = 1.38e-06 \times Af$
* **Diesel (Commercial)**: $\beta_2 = 3.91e-06$, $\beta_3 = 6.52e-07$, $\beta_4 = 1.88e-06 \times Af$

#### Step 2: Calculate Theoretical Fuel
Generate a new column calculating what a “perfect” version of the client’s truck would burn using pure physics: 
```text
Theoretical = β₂(Dist × Wt) + β₃(Elev × Wt) + β₄(Dist × Spd² × Af)
```

#### Step 3: Isolate Mechanical Loss
Subtract the theoretical fuel from the actual fuel the client’s fleet burned: 
```text
Mechanical_Loss = Observed_Fuel – Theoretical_Fuel
```

#### Step 4: Run Constrained Regression
Use a Non-Negative Least Squares (NNLS) optimizer (e.g., `scipy.optimize.lsq_linear`) to find the new $\beta_0$ and $\beta_1$ specifically for the client’s data.
* **Feature**: Distance
* **Target**: Mechanical_Loss
* **Constraint**: Bounds must be $\ge 0$ (a truck cannot generate fuel while idling).
 
The resulting $\beta_0$ represents the client’s baseline idle/accessory loss per trip, and $\beta_1$ represents their fleet’s specific transmission and axle friction per kilometer.

#### Step 5: Update the Matrix
Merge these newly learned coefficients into the pathOS JSON configuration for that specific client or region, leaving the fundamental physics ($\beta_2$, $\beta_3$, $\beta_4$) untouched.
