# Changelog

## 0.7.1
- OTA-MQTT-Kommando wird nicht mehr durch den Standardpuffer von PubSubClient verworfen.
- MQTT-Puffer des ESP-Agenten auf 2048 Bytes erhöht.
- OTA-Kommando wird kompakt serialisiert und seine Bytegröße ausgegeben.
- Unerwartet große OTA-Kommandos werden serverseitig abgelehnt.
- Gerät bestätigt ein empfangenes und token-validiertes OTA-Kommando sofort mit Status `received`.
- OTA-Antwort des Backends enthält `command_bytes` zur Diagnose.
- Bestehende OTA-, USB-, Status- und Projektfunktionen bleiben erhalten.
