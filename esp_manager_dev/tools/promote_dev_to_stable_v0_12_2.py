#!/usr/bin/env python3
from pathlib import Path
import re, shutil, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
dev = root / "esp_manager_dev"
stable = root / "esp_manager"
if not dev.is_dir() or not stable.is_dir():
    raise SystemExit("esp_manager_dev oder esp_manager fehlt")

required = [
    dev / "app/main.py",
    dev / "app/templates/lib/ESPManager/src/ESPManager.h",
    dev / "app/templates/lib/ESPManager/src/ESPManager.cpp",
    dev / "config.yaml",
    dev / "Dockerfile",
    dev / "run.sh",
]
missing = [str(p.relative_to(root)) for p in required if not p.exists()]
if missing:
    raise SystemExit("Pflichtdateien fehlen: " + ", ".join(missing))

# Abort instead of promoting the known broken C++ header syntax.
hdr = required[1].read_text(errors="replace")
if re.search(r"const\s+char\s*\*=", hdr):
    raise SystemExit("Abbruch: ESPManager.h enthält noch ungültiges const char*= Token")

# Keep an in-repository source backup for review/rollback, never runtime data.
backup = root / "promotion_backup_0.12.2" / "esp_manager"
if backup.exists():
    shutil.rmtree(backup)
shutil.copytree(stable, backup, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))

# Promote the complete add-on implementation, not isolated files.
if stable.exists():
    shutil.rmtree(stable)
shutil.copytree(dev, stable, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"))

# Stable identity and isolated data path. Apply across text files because main.py,
# scripts and templates may contain generated links, titles and storage paths.
text_suffixes = {".py", ".yaml", ".yml", ".md", ".txt", ".sh", ".json", ".html", ".js", ".css", ".h", ".hpp", ".cpp", ""}
for p in stable.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in text_suffixes:
        continue
    try:
        s = p.read_text()
    except UnicodeDecodeError:
        continue
    s = s.replace("/config/esp_manager_dev", "/config/esp_manager")
    s = s.replace("esp_manager_dev", "esp_manager")
    s = s.replace("ESP Manager Dev", "ESP Manager")
    s = s.replace("ESP_MANAGER_DEV", "ESP_MANAGER")
    # Stable ingress port. Word boundaries avoid changing unrelated larger numbers.
    s = re.sub(r"(?<!\d)8100(?!\d)", "8099", s)
    p.write_text(s)

config = stable / "config.yaml"
s = config.read_text()
s = re.sub(r"(?m)^name:\s*.*$", "name: ESP Manager", s, count=1)
s = re.sub(r"(?m)^slug:\s*.*$", "slug: esp_manager", s, count=1)
s = re.sub(r"(?m)^version:\s*.*$", "version: 0.12.2", s, count=1) if re.search(r"(?m)^version:", s) else s
if not re.search(r"(?m)^version:", s):
    lines = s.splitlines(); lines.insert(2, "version: 0.12.2"); s = "\n".join(lines) + "\n"
s = re.sub(r"(?m)^ingress_port:\s*.*$", "ingress_port: 8099", s, count=1)
s = re.sub(r"(?m)^panel_title:\s*.*$", "panel_title: ESP Manager", s, count=1)
config.write_text(s)

# Required repository documentation copies.
root_changelog = root / "CHANGELOG.md"
entry = """\n## 0.12.2\n- Hardwarebestätigten Dev-Stand in den Stable-Pfad übernommen.\n- MQTT Discovery für Sensor, Binärsensor, Schalter, Number und Cover übernommen.\n- Home-Assistant-Steuerung praktisch bestätigt.\n- WLAN-Recovery praktisch bestätigt.\n- Korrekte C++-Defaultparameter-Syntax in ESPManager.h vorausgesetzt und geprüft.\n"""
old = root_changelog.read_text() if root_changelog.exists() else "# Changelog\n"
if "## 0.12.2\n" not in old:
    root_changelog.write_text(old.rstrip() + "\n" + entry)
for target in (stable / "CHANGELOG.md", dev / "CHANGELOG.md"):
    current = target.read_text() if target.exists() else "# Changelog\n"
    if "## 0.12.2\n" not in current:
        target.write_text(current.rstrip() + "\n" + entry)

handover = root / "PROJECT_HANDOVER.txt"
h = handover.read_text() if handover.exists() else ""
line = "\n0.12.2 Stable: Dev-Stand vollständig nach esp_manager promoviert; Stable-Datenpfad /config/esp_manager und Port 8099 bleiben getrennt. WLAN-Recovery und HA-Steuerung sind hardwarebestätigt.\n"
if "0.12.2 Stable:" not in h:
    handover.write_text(h.rstrip() + "\n" + line)

# Append-only project ledgers.
pm = root / "project_memory"; pm.mkdir(exist_ok=True)
entries = {
 "DECISIONS.jsonl": '{"id":"dec-0122-stable-01","status":"active","decision":"Der hardwarebestätigte 0.12.2-Dev-Stand wird vollständig nach esp_manager promoviert; Stable-Datenpfad und Port bleiben isoliert."}\n',
 "INCIDENTS.jsonl": '{"id":"inc-0122-header-01","status":"closed","title":"Ungültige Defaultparameter-Syntax im generierten ESPManager.h","resolution":"Manuelle Minimalreparatur bestätigt; Promotion prüft und blockiert const char*= Regressionen"}\n',
 "RELEASE_LEDGER.jsonl": '{"version":"0.12.2","channel":"stable","status":"promoted","evidence":["project_compile_confirmed","home_assistant_control_confirmed","wifi_recovery_confirmed"]}\n',
}
for name, entry_text in entries.items():
    p=pm/name; old=p.read_text() if p.exists() else ""
    marker = "dec-0122-stable-01" if name.startswith("DEC") else "inc-0122-header-01" if name.startswith("INC") else '"version":"0.12.2"'
    if marker not in old: p.write_text(old+entry_text)

print("Stable 0.12.2 erfolgreich aus Dev promoviert")
print("Backup:", backup.relative_to(root))
