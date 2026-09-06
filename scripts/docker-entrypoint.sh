#!/bin/sh
# Hive — rebuild-safe entrypoint
# If /root/.hive (named volume hive_data) is empty, seed it from host's ~/.hive mounted at /host_hive (read-only)
# This makes `docker compose down && up --build` preserve data (volume not deleted), and first run imports host data if available.

set -e

if [ -z "$(ls -A /root/.hive 2>/dev/null)" ]; then
  if [ -d "/host_hive" ] && [ -n "$(ls -A /host_hive 2>/dev/null)" ]; then
    echo "[entrypoint] /root/.hive empty — seeding from /host_hive (host ~/.hive)..."
    cp -a /host_hive/. /root/.hive/ 2>/dev/null || echo "[entrypoint] warning: copy from /host_hive failed"
  else
    echo "[entrypoint] /root/.hive empty and no /host_hive — initializing fresh"
    mkdir -p /root/.hive/machine/workspace /root/.hive/machine/workflows
  fi
else
  echo "[entrypoint] /root/.hive has data — keeping volume (rebuild-safe)"
fi

# Ensure workspace exists
mkdir -p /root/.hive/machine/workspace /root/.hive/machine/workflows /root/.hive/exports

# Exec the original command (hive web)
exec "$@"
