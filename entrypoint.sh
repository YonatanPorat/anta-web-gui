#!/bin/sh
echo "=== Starting ANTA Web GUI ==="

export ANTA_USERNAME="${ANTA_USERNAME:-admin}"
export ANTA_PASSWORD="${ANTA_PASSWORD:-admin}"

# --server.maxUploadSize: Streamlit's own default is 200MB, applied to every
# st.file_uploader in the app - but the only upload here is the inventory CSV
# import, and a realistic 1000-row inventory CSV is ~35KB. Capping at 1MB is
# generous headroom for that use case while refusing anything wildly
# oversized that could otherwise eat server memory/disk.
#
# Start the Streamlit web server
streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.maxUploadSize=1