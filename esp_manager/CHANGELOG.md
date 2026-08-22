# Changelog
## 0.12.1-dev
- Smartmeter MQTT Discovery praktisch bestÃ¤tigt: Alle manuellen MQTT-Konfigurationen entfernt; nach Neustart von HA und ESP erschienen alle Werte weiterhin.
- Allgemeine Discovery fÃ¼r Sensor, BinÃ¤rsensor, Schalter, Zahlenwert und Cover.
- HA-Befehle Ã¼ber `onCommand`; ZustandsbestÃ¤tigung Ã¼ber `publishState`.
- `publishSensor`, OTA und bestÃ¤tigte WLAN-Recovery bleiben erhalten.
- Smartmeter-Empfangslogik bleibt unverÃ¤ndert.

## 0.12.2
- Hardwarebestätigten Dev-Stand in den Stable-Pfad übernommen.
- MQTT Discovery für Sensor, Binärsensor, Schalter, Number und Cover übernommen.
- Home-Assistant-Steuerung praktisch bestätigt.
- WLAN-Recovery praktisch bestätigt.
- Korrekte C++-Defaultparameter-Syntax in ESPManager.h vorausgesetzt und geprüft.
