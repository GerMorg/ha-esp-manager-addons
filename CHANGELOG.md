# Changelog

## 0.6.4
- MQTT-Statusmonitor unter Home-Assistant-Ingress korrigiert.
- API-Basispfad wird aus dem tatsächlichen Ingress-Pfad der Hardwareseite ermittelt; kein versehentliches Abrufen der Home-Assistant-API mehr.
- Neuer MQTT-Verbindungsstatus des ESP-Manager-Add-ons.
- Liste aller über MQTT erkannten ESP-Geräte.
- Geräteauswahl im Statusmonitor ergänzt.
- Projektname wird als bevorzugte Geräte-ID verwendet; bei nur einem erkannten Gerät wird dieses automatisch gewählt.
- Statusanzeige enthält das gewählte Gerät statt einer fest verdrahteten, möglicherweise falschen Geräte-ID.
- Serielles Trennen aus 0.6.3 und alle bisherigen Funktionen bleiben erhalten.
