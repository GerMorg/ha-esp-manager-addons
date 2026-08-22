# ESP Manager Entwicklungsprotokoll

## Lieferform
- Immer vollständige fertige Dateien in den korrekten Repository-Pfaden liefern.
- Keine Update-, Apply-, Overlay-, Patch- oder Promotion-Werkzeuge.
- Keine ausführbaren Hilfsdateien im Repository-Stamm.

## Versionsprozess
1. Ausgangsbasis und Commit dokumentieren.
2. Nur `esp_manager_dev` für unbestätigte Änderungen verwenden.
3. Alle bestehenden Funktionen gegen `FEATURE_CONTRACT.yaml` prüfen.
4. Automatische Prüfungen gemäß `TEST_MATRIX.yaml` ausführen.
5. Hardwareabhängige Funktionen praktisch testen.
6. Erst bestätigten Dev-Stand vollständig nach Stable übernehmen.
7. Changelog, Handover und gesamtes Project Memory aktualisieren.
8. Ledgers nur ergänzen, niemals rückwirkend umschreiben.

## Qualitätsregeln
- Benutzerdateien niemals ungefragt verändern oder entfernen.
- Öffentliche C++-API rückwärtskompatibel halten.
- Servergeneriertes JavaScript in gerenderter Form prüfen.
- Ingress-Pfade immer im realen Unterpfad testen.
- Build-, Firmware- und Persistenzdaten migrationskompatibel halten.
- Smartmeter-Referenzdecoder nur nach reproduzierbarem Hardwarebeweis ändern.
- `unique_id` ist eine dauerhafte Identität, kein Anzeigename.

## Definition of Done
- Quellstruktur vollständig.
- Stable/Dev getrennt.
- Keine verbotenen Tools.
- Python- und JavaScript-Prüfungen bestanden.
- API- und Kompatibilitätstests bestanden.
- ZIP-Integrität bestanden.
- Hardwarestatus korrekt als bestätigt oder ausständig dokumentiert.
- Project Memory und alle Ledgers aktualisiert.



