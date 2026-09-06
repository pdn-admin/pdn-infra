# This file makes the app directory a Python package
# It's needed for the utility modules to import each other properly

import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import create_app from the main module
from .main import create_app
