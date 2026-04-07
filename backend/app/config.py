"""
Central configuration file for the TSP route optimizer.
Holds all constants and server settings.
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# === SERVER SETTINGS ===
FLASK_HOST = '0.0.0.0'
FLASK_PORT = int(os.environ.get('PORT', 8000))
OSRM_HOST = os.environ.get('OSRM_HOST', "http://127.0.0.1:5000")
OSRM_WAKE_URL = os.environ.get('OSRM_WAKE_URL', None)
OSRM_WAKE_SECRET = os.environ.get('OSRM_WAKE_SECRET', None)