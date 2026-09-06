#!/usr/bin/env python3
"""
Entry point for running the app package as a module.
Usage: python -m app
"""

import os
import sys

# Add the parent directory to the path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the create_app function directly from app.py
from app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8001)
