"""
FastAPI entry point for Hugging Face Spaces and production deployment.
This file simply imports the main FastAPI application to ensure
consistent behavior across localhost and HF Spaces deployments.
"""

import sys
import os

# Add openenv-course-tmp to path to enable openenv imports
openenv_path = os.path.join(os.path.dirname(__file__), "openenv-course-tmp")
if os.path.exists(openenv_path) and openenv_path not in sys.path:
    sys.path.insert(0, openenv_path)


# Ensure only the correct FastAPI app is exposed for Hugging Face Spaces
from main import app

__all__ = ["app"]
