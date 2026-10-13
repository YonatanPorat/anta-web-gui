#!/bin/sh
echo "=== Starting ANTA Web GUI ==="

export ANTA_USERNAME="${ANTA_USERNAME:-admin}"
export ANTA_PASSWORD="${ANTA_PASSWORD:-admin}"

# Start the Streamlit web server
streamlit run app.py --server.port=8501 --server.address=0.0.0.0