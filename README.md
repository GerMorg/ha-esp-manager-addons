# ESP Manager Repository-Inhalte 0.11.0-dev

Diese Ausgabe enthält die neuen und zu ersetzenden Repository-Dateien für die allgemeine MQTT-Discovery-Funktion.

## Einspielen

Den Inhalt dieses Ordners in den Stamm des vorhandenen Repositorys kopieren. Vorhandene Dateien ersetzen, andere Dateien nicht löschen. Stable `esp_manager` 0.7.3 bleibt unverändert.

## Enthalten

- allgemeine `ESPManager.registerSensor()`-API
- retained MQTT Discovery und erneute Veröffentlichung nach MQTT-Reconnect
- Availability und Gerätezuordnung
- Smartmeter-Rückwärtskompatibilität mit bisherigen `unique_id`-Werten
- bestätigte WLAN-Recovery
- Tests, Changelog, Übergabe und vollständiges Project Memory

Siehe `MQTT_DISCOVERY.md` für die Nutzung in neuen Projekten.
