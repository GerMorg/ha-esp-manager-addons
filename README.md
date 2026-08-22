# ESP Manager Add-ons

Sauber konsolidiertes Repository ohne Update-, Patch- oder Promotion-Werkzeuge.

- **Stable 0.12.2**: letzter wiederhergestellter Stable-Stand mit allgemeiner MQTT Discovery.
- **Dev 0.13.0-dev**: Stable-Funktionsumfang plus direkt integrierte grafische MQTT-Discovery-Entitätenverwaltung.

## Dev: grafische MQTT Discovery

Projekt öffnen und im Abschnitt **MQTT Discovery – Entitäten** Sensoren, Binärsensoren, Schalter, Numbers und Covers verwalten. Die Definitionen werden in `espmanager.yaml` gespeichert und beim Build als `include/ESPManagerEntities.h` erzeugt.

`unique_id` nach der ersten Veröffentlichung nicht mehr ändern, sofern bestehende Home-Assistant-Entitäten und Historie erhalten bleiben sollen.
