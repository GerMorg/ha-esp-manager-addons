# ESP Manager Update-Workflow

## Entwicklung

1. In `esp_manager_dev` entwickeln.
2. Version in `esp_manager_dev/config.yaml` erhoehen.
3. Repository pushen.
4. In Home Assistant Add-on Store `Nach Updates suchen` ausfuehren.
5. `ESP Manager Dev` aktualisieren.
6. Wenn stabil, Aenderungen nach `esp_manager` uebernehmen und dort ebenfalls die Version erhoehen.

## Warum Version erhoehen?

Home Assistant erkennt Add-on-Updates ueber die Version in `config.yaml`.

## Empfehlung

- Dev-Kanal fuer Experimente.
- Stable-Kanal fuer funktionierende Zwischenstaende.
