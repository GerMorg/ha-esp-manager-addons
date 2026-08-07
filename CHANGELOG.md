# Changelog

## 0.5.3
- Neue Dateien können wieder zuverlässig angelegt werden; fehlende Projektwahl, leerer Pfad und API-Fehler werden verständlich angezeigt.
- Dateipfade ohne Ordner werden automatisch unter `src/` angelegt.
- Neue Datei wird nach dem Anlegen automatisch geöffnet.
- WLAN-Erstkonfiguration über Fallback-Access-Point `ESPManager-<Gerätename>` vorbereitet.
- WLAN-Konfigurationsmaske bei bestehender Verbindung zehn Minuten nach Neustart über die lokale Geräte-IP erreichbar.
- Nach 60 Sekunden WLAN-Ausfall startet automatisch ein nicht blockierender Fallback-Access-Point.
- Das Geräteprogramm kann während des Fallback-Portals weiterlaufen.
- WLAN-Portal kann später token-geschützt per MQTT-Kommando geöffnet werden.
- MQTT, Status, Logs, OTA und `publishSensor()` im Agent erhalten.
- Agent-Bibliotheken WiFiManager, PubSubClient und ArduinoJson werden automatisch verwaltet.
