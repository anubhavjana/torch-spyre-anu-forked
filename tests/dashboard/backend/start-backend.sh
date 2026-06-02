#!/bin/bash
# Load environment variables from .env file and start backend server

cd "$(dirname "$0")"

# Load .env file (skip comments and empty lines)
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Start the backend server
echo "Starting Spyre Dashboard Backend API..."
echo "Backend will be available at: http://localhost:5000"
echo "Press Ctrl+C to stop"
echo ""

python3 backend-api.py

# Made with Bob
