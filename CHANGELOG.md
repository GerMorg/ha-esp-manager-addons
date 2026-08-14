# Changelog

## Stable 0.7.3
- Bleibt unverändert. Dieses Paket ersetzt ausschließlich `esp_manager_dev`.

## Dev 0.9.0 clean
- Entwicklungszweig ohne historische Patchkette vollständig neu konsolidiert.
- Projekt-, Datei-, Backup-, Import-/Export- und Buildfunktionen in einer einzelnen `main.py`.
- Mehrchip-USB-Manifest und vollständiges ESP32-Initial-Image.
- Serieller Monitor mit sauberem Reader-/Port-Abschluss.
- MQTT-Geräteübersicht mit Online-/Offline-Zustand und Verlauf.
- Gerät löschen, retained Daten entfernen und erneute Aufnahme bei neuer Statusmeldung.
- OTA mit Buildauswahl, Token, SHA256, MD5-Header, Fortschritt und Versionsbestätigung.
- Persistente OTA-Aufträge und begrenzter Geräteverlauf.
- Build-Anheften, Löschen und konfigurierbare Aufbewahrung.
- Aktive WLAN-Wiederverbindung, Fallback-Portal und kontrollierter Recovery-Neustart.
- Keine `patch_v*.py`-Dateien mehr.
- Docker-Build prüft Python-Syntax, tatsächlich ausgeliefertes JavaScript und API-Smoke-Tests.
