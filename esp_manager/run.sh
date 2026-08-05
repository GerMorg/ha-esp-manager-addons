#!/usr/bin/env bash
set -euo pipefail
mkdir -p /config/esp_manager/projects /config/esp_manager/firmware /config/esp_manager/backups
cd /opt/esp_manager
. venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8099
