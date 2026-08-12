# Changelog

## 0.7.0
- Ingress-sicheren Zurück-Button auf der Hardwareseite ergänzt.
- Erkannte Geräte können dauerhaft einem Projekt zugeordnet werden.
- Erfolgreiche Builds sind für OTA auswählbar, einschließlich älterer Builds.
- OTA-Auftrag wird token-geschützt per MQTT an das ausgewählte Gerät gesendet.
- Firmwaredownload ist projektspezifisch token-geschützt.
- SHA256 des Build-Artefakts wird vor Auftrag und vor Download erneut geprüft.
- Firmwaredownload liefert zusätzlich einen `x-MD5`-Header für die Integritätsprüfung durch HTTPUpdate.
- OTA-Zustände: validating, started, progress, finished, failed und no_update.
- Fortschritt und Fehler werden seriell und über MQTT veröffentlicht.
- Hardwareseite zeigt OTA-Fortschrittsbalken, Status und Protokoll.
- Erfolgreiches HTTPUpdate startet den ESP anschließend neu.
- USB-Flash, serieller Monitor, MQTT-Geräteliste und Projektfunktionen bleiben erhalten.
