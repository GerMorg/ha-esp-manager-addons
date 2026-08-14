# Changelog

## Stable 0.7.3
- Bleibt unverändert und eingefroren.

## Dev 0.8.2
- Geräteübersicht zeigt wieder einen grünen Online- beziehungsweise roten Offline-Punkt.
- Online-Zustand berücksichtigt Availability und Alter der letzten Statusmeldung.
- `device_offline_after` ist zwischen 35 und 600 Sekunden konfigurierbar.
- Geräte werden online zuerst und danach alphabetisch sortiert.
- Leere retained MQTT-Löschmeldungen erzeugen kein Phantomgerät mehr.
- Gerät löschen entfernt zusätzlich persistenten OTA-Auftrag und gespeicherte Projektzuordnung.
- Gelöschter Gerätename wird unmittelbar aus der Hardwareauswahl entfernt.
- Ein aktives Gerät erscheint erst mit einer neuen echten Statusmeldung wieder.
