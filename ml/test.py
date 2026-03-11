import joblib
model = joblib.load('physics_informed_fuel_model.joblib')
print(type(model))
print(model.keys() if isinstance(model, dict) else dir(model))