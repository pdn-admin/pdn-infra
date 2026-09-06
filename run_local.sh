#!/bin/bash
# Run PDN Chat locally for development
# Usage: ./run_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Set Flask environment variables
export FLASK_APP=app.main:app
export FLASK_ENV=development
export FLASK_DEBUG=1

echo "🚀 Starting PDN Chat locally..."
echo "   URL: http://127.0.0.1:5000"
echo "   Admin: http://127.0.0.1:5000/pdn-admin/"
echo "   Diagnose: http://127.0.0.1:5000/pdn-diagnose/"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

# Run Flask development server
python -m flask run --port 5000 --host 127.0.0.1
