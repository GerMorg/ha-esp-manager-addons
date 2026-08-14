# Changelog

## 0.10.2-dev
- WLAN-Recovery als explizite Zustandsmaschine.
- Fallback-Portal wird nur einmal gestartet.
- STA-Verbindungsversuche laufen parallel zum Portal alle `wifi_reconnect_interval` Millisekunden.
- Bei erfolgreicher Verbindung werden Portal und SoftAP beendet, STA-Modus und MQTT wiederhergestellt.
- Standard-Neustart nach 15 Minuten Gesamtausfall; letzte Minute nur STA-Verbindungsversuche.
- Serielle Meldungen für alle Zustandswechsel.
