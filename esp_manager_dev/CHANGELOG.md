# Changelog

## Stable 0.7.3
- Unverändert und eingefroren.

## Dev 0.8.4
- Robuste WLAN-Wiederherstellung im ESP-Agenten.
- ESP32-Autoreconnect wird aktiviert.
- Alle 15 Sekunden wird bei Trennung aktiv `WiFi.reconnect()` versucht.
- Captive-Portal-Fallback nach 60 Sekunden bleibt erhalten.
- Kontrollierter Neustart nach standardmäßig 15 Minuten erfolgloser Wiederherstellung.
- Intervalle über Add-on-Optionen konfigurierbar.
- Gerätekarten sind anklickbar.
- Geräte-Detailansicht zeigt Firmware, IP, RSSI, Uptime und Heap.
- Die letzten 50 Verlaufseinträge werden sichtbar angezeigt.
