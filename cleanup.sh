#!/bin/bash
# Daily disk cleanup for the host running anta-web-gui.
#
# restart.sh already prunes dangling images on every redeploy, but if days
# pass between redeploys (or anything else on this host fills the disk -
# other containers, logs, etc.) there's no cleanup happening in between.
# This is meant to run on a schedule (see install instructions below) as a
# standing safety net, independent of whether/when anyone redeploys.
#
# Only removes:
#   - dangling (untagged) Docker images - never anything tagged or in use
#     by a running container
#   - stopped containers - never a running one
# Does NOT touch the anta-web-gui-data volume or anything still in use.

echo "[$(date)] Running daily Docker cleanup..."
docker image prune -f
docker container prune -f
echo "[$(date)] Done. Disk usage:"
df -h /

# --- Install as a daily cron job ---
# Run once on the host (not inside the container):
#
#   chmod +x cleanup.sh
#   (crontab -l 2>/dev/null; echo "0 3 * * * $(pwd)/cleanup.sh >> $(pwd)/cleanup.log 2>&1") | crontab -
#
# This runs it every day at 03:00 and appends output to cleanup.log next to
# this script. Verify it's installed with `crontab -l`.
