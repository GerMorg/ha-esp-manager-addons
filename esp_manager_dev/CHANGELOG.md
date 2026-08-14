# Changelog

## 0.10.0.1-dev
- Docker-Build sammelt ausschließlich die kanonische Contract-Testdatei `tests/test_contract.py`.
- `pytest.ini` verhindert, dass eine bei einem GitHub-Overlay verbliebene alte `test_smoke.py` ausgeführt wird.
- Projektgedächtnis um Ursache, Entscheidung und Release ergänzt.
- Stable 0.7.3 bleibt unverändert.

## 0.10.0-dev
- Saubere modulare Dev-Codebasis ohne Patchkette.
- Vollständige Projekt- und Dateiverwaltung wiederhergestellt.
- ESP-Manager-ZIP-, Arduino-ZIP- und PlatformIO-Import vorhanden.
- Buildverwaltung, USB, Serial, Geräte, OTA und WLAN-Recovery integriert.
- Maschinenlesbares `project_memory` und vertragliche Regressionstests aufgenommen.
