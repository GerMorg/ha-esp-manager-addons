# Changelog

## Stable 0.7.3
- Unverändert.

## Dev 0.9.0.1 clean
- Docker-Testfehler behoben: pytest erhält explizit `PYTHONPATH=/opt/esp_manager`.
- Dadurch ist das im Container kopierte Python-Paket `app` während der Tests importierbar.
- Saubere 0.9-Codebasis ohne Patchkette bleibt erhalten.
- Python-, JavaScript- und API-Tests bleiben verpflichtende Docker-Buildschritte.
