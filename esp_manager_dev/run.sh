#!/usr/bin/env bash
set -euo pipefail
mkdir -p /config/esp_manager_dev/projects /config/esp_manager_dev/firmware /config/esp_manager_dev/backups
cd /opt/esp_manager
. venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8100
