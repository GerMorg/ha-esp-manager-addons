# Changelog

## Stable 0.7.3
- Als stabile Referenz festgeschrieben.
- Keine weiteren Entwicklungsänderungen im Stable-Ordner.
- Bestätigt: USB-Flash, WLAN-Provisioning, MQTT, Gerätestatus, OTA-Installation und Abschlussbestätigung.

## Dev 0.8.0
- OTA-Aufträge werden in `ota_jobs.json` persistent gespeichert.
- OTA-Bestätigung bleibt über einen Add-on-Neustart erhalten.
- Geräteverlauf wird begrenzt in `device_history.jsonl` gespeichert.
- API für OTA-Aufträge und Geräteverlauf ergänzt.
- Build-Aufbewahrung über `build_retention` konfigurierbar.
- ESP32 bestätigt eine ausstehende OTA-Firmware nach erfolgreicher WLAN- und MQTT-Verbindung als gültig, sofern Rollback-Unterstützung im Bootloader aktiv ist.
- Stable 0.7.3 bleibt unverändert.
