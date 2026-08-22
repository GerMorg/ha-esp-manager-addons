# ESP Manager 0.12.2

Ausgangsbasis: Commit `c841129a51998a4dd3c102211a1f5929d11f650b`.

## Änderungen

- Die letzte getestete Dev-Version wird vollständig nach Stable übernommen.
- Der nächste Dev-Schritt ergänzt ein LED-/Zahlenwert-Hardwaretestprojekt unter `esp_manager_dev/examples/led_number_test`.
- Keine ausführbare Datei liegt im Repository-Stamm.

## Ausführung

Die Werkzeuge bleiben ausschließlich unter `esp_manager_dev/tools`. Ausführung aus diesem Ordner:

```bash
cd esp_manager_dev/tools
python3 promote_dev_to_stable_v0_12_2.py ../..
python3 validate_v0_12_2_promotion.py ../..
```

Danach `git diff` prüfen. Stable-Laufzeitdaten unter `/config/esp_manager` werden nicht verändert.
