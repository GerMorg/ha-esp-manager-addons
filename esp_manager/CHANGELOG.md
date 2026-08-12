# Changelog

## 0.7.2
- OTA-Download verwendet einen eigenen WiFiClient statt der aktiven MQTT-Verbindung.
- Behebt das Hängen bei `validating` beziehungsweise 0 %, obwohl die Firmware-URL erreichbar ist.
- Geräte können aus der Übersicht vergessen werden; retained Statusdaten werden entfernt.
- Einzelne Builds können gelöscht werden.
- Builds können angeheftet und damit vor automatischer Bereinigung geschützt werden.
- Schaltfläche zum Behalten der letzten fünf nicht angehefteten Builds.
- Nach erfolgreichem Build erfolgt automatische Bereinigung auf fünf nicht angeheftete Builds.
- Alle bisherigen USB-, MQTT-, OTA-, Status- und Projektfunktionen bleiben erhalten.
