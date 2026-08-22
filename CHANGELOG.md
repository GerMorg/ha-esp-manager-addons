# Changelog
## 0.12.1-dev
- Smartmeter MQTT Discovery praktisch bestätigt: Alle manuellen MQTT-Konfigurationen entfernt; nach Neustart von HA und ESP erschienen alle Werte weiterhin.
- Allgemeine Discovery für Sensor, Binärsensor, Schalter, Zahlenwert und Cover.
- HA-Befehle über `onCommand`; Zustandsbestätigung über `publishState`.
- `publishSensor`, OTA und bestätigte WLAN-Recovery bleiben erhalten.
- Smartmeter-Empfangslogik bleibt unverändert.
