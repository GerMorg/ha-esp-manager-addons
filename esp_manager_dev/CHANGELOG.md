# Changelog

## 0.5.8
- Home-Assistant-Ingress-Problem mit `307 Temporary Redirect` auf `USB & Status` behoben.
- Hardwaretest-Seite ist nun sowohl unter `/usb/<projekt>` als auch `/usb/<projekt>/` direkt erreichbar.
- Kein automatischer Slash-Redirect mehr erforderlich.
- Manifest-URL wird im Browser aus dem tatsächlichen Seitenpfad gebildet.
- Installer erhält den vollständigen Ingress-kompatiblen Manifestpfad dynamisch.
- Mehrchip-Flash, serieller Monitor, WLAN-Anleitung und MQTT-Status bleiben erhalten.
