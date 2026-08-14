# ESP Manager Dev 0.10.2 WLAN-Recovery

Overlay für das bestehende 0.10.1-Repository. Die enthaltenen Dateien ersetzen die gleichnamigen Dateien. Danach Projekt neu bauen und die neue Agent-Firmware per USB oder OTA installieren.

Der kontrollierte Neustart erfolgt nach `wifi_recovery_restart_after` seit Beginn des Ausfalls. Standard sind 900000 ms, also 15 Minuten. Eine Minute davor wird das Fallback-Portal geschlossen und ausschließlich im STA-Modus weiter verbunden.
