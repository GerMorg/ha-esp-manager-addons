# Changelog

## 0.6.2
- Hardwaretest-Seite vollständig geprüft und repariert.
- Zweiten JavaScript-Syntaxfehler in der seriellen Fehlerausgabe behoben.
- Dadurch läuft `checkManifest()` wieder und die Anzeige bleibt nicht mehr bei `Prüfe Manifest ...` stehen.
- ESP-Web-Tools erhält den Manifestpfad erst nach erfolgreicher Initialisierung der Hardwareseite.
- Implizite globale DOM-Variablen auf der Hardwareseite durch `document.getElementById()` ersetzt.
- Automatische Prüfungen jetzt für Hauptseite und Hardwareseite.
- Manifest-Workflow mit simuliertem Projekt, Buildhistorie und Initial-Firmware validiert.
- Projektliste, Projektanlage und Datenpfade aus 0.6.1 bleiben erhalten.
