# Changelog

## 0.7.3
- OTA-Abschluss wird nach dem Neustart anhand der gemeldeten Firmwareversion bestätigt.
- Zielversion und Ziel-Build werden beim OTA-Auftrag im Gerätestatus hinterlegt.
- Meldet das Gerät danach dieselbe Firmwareversion, setzt der ESP Manager den Zustand auf `confirmed` und 100 Prozent.
- HTTPUpdate startet nicht mehr unmittelbar selbst neu.
- Agent sendet `finished`, verarbeitet MQTT kurz weiter und startet anschließend kontrolliert neu.
- OTA-Zeitüberschreitung nach drei Minuten ergänzt.
- Bestehende OTA-, Build-, Geräte-, USB- und Projektfunktionen bleiben erhalten.
