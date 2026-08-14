#!/usr/bin/env bash
set -euo pipefail
export ESP_MANAGER_ROOT=/config/esp_manager_dev
mkdir -p "$ESP_MANAGER_ROOT"/{projects,firmware,backups}
cd /opt/esp_manager
. venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port 8100
