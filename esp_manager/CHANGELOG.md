# Changelog

## 0.6.0
- Erste saubere Vollversion ohne Kette aus Build-Patchskripten.
- Hardware-Meilenstein bestätigt: ESP32 wurde per Browser geflasht, serieller Monitor funktionierte und WLAN wurde per Captive Portal eingerichtet.
- Internen Add-on-MQTT-Host und den vom ESP erreichbaren Geräte-MQTT-Host getrennt.
- Neue Optionen `device_mqtt_host`, `device_mqtt_port`, `device_mqtt_username` und `device_mqtt_password`.
- Standardziel der Firmware ist `homeassistant.local` statt des nur intern auflösbaren Namens `core-mosquitto`.
- Agent protokolliert MQTT-Ziel und Verbindungsfehler verständlicher seriell.
- Saubere Projekt-, Datei-, Build-, Backup-, Import-/Export-, USB- und Statusimplementierung zusammengeführt.
- Unterstützte Standardprofile: ESP8266, ESP32/WROOM-32, ESP32-S2, S3, C3 und C6.
- Mehrchip-Initial-Images und getrennte OTA-Firmware erhalten.
