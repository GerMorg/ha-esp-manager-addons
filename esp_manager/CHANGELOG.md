# Changelog

## Stable 0.7.3
- Bleibt unverändert und eingefroren.

## Dev 0.8.1
- Persistente OTA-Zielversion wird nach Add-on-Neustart wieder in den Gerätestatus übernommen.
- Neue Firmwareversion bestätigt OTA zuverlässig als `confirmed` und `success`.
- Fehler beim Schreiben des Geräteverlaufs verhindern nicht mehr das Parsen eines gültigen Statuspakets.
- Veraltetes `raw_status` wird nach erfolgreichem JSON-Parsing entfernt.
- Identische retained OTA-Meldungen werden auf der Hardwareseite nicht mehr bei jedem Poll erneut ins Protokoll geschrieben.
- Nach bestätigtem OTA wird die Timeoutüberwachung beendet.
- Automatische Buildbereinigung schreibt Ergebnis und konfiguriertes Limit ins Buildprotokoll.
- Diagnose-API für Build-Aufbewahrung ergänzt.
