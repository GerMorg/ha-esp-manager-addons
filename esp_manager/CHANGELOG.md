# Changelog

## 0.5.7
- ESP-Web-Tools-Manifestpfad unter Home-Assistant-Ingress korrigiert.
- `USB & Status` öffnet Projekte nun mit abschließendem Schrägstrich, damit `manifest.json` relativ zum Projekt aufgelöst wird.
- Anzeige `Install undefined` und Hängen bei `Preparing installation` durch falschen Manifestpfad behoben.
- Sichtbare Manifest-Vorprüfung ergänzt: Projektname, Version und erkannte Chipfamilie werden vor dem Flash angezeigt.
- Bestehender serieller Monitor, Mehrchip-Initial-Images und MQTT-Status bleiben erhalten.
