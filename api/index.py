import sys
import os

# Add root directory to path so imports work identically to running locally
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel needs the flask app to be exposed exactly like this in api/index.py
