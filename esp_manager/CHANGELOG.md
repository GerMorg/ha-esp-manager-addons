# Changelog

## 0.6.3
- MQTT-Status 5 verständlich als nicht autorisierte Anmeldung dokumentiert.
- Serielle Agentmeldung nennt bei Status 5 jetzt ausdrücklich Geräte-Benutzer und Passwort.
- Seriellen Browsermonitor ohne TextDecoderStream-Pipeline neu implementiert.
- Beim Trennen wird der Reader abgebrochen, seine Sperre im Leseloop freigegeben und erst danach der Port geschlossen.
- Erneutes Verbinden nach dem Trennen vorbereitet.
- Verbindungs- und Trennschaltflächen zeigen ihren Zustand an.
- Manifestprüfung, USB-Flash und alle bisherigen Funktionen bleiben erhalten.
