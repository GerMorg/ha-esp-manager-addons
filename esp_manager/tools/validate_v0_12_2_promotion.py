#!/usr/bin/env python3
from pathlib import Path
import re, sys
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
dev=root/'esp_manager'; stable=root/'esp_manager'
errors=[]
for d in (dev,stable):
    for rel in ['app/main.py','app/templates/lib/ESPManager/src/ESPManager.h','app/templates/lib/ESPManager/src/ESPManager.cpp','config.yaml','Dockerfile','run.sh']:
        if not (d/rel).exists(): errors.append(f"fehlt: {(d/rel).relative_to(root)}")
sh=stable/'app/templates/lib/ESPManager/src/ESPManager.h'
if sh.exists():
    text=sh.read_text(errors='replace')
    if re.search(r"const\s+char\s*\*=",text): errors.append('Stable-Header enthält const char*=')
    for api in ['publishSensor','registerSensor','registerBinarySensor','registerSwitch','registerNumber','registerCover','publishState','onCommand']:
        if api not in text: errors.append('Stable-API fehlt: '+api)
config=(stable/'config.yaml').read_text(errors='replace') if (stable/'config.yaml').exists() else ''
for expected in ['slug: esp_manager','version: 0.12.2','ingress_port: 8099']:
    if expected not in config: errors.append('Stable-Konfiguration fehlt: '+expected)
for p in stable.rglob('*'):
    if p.is_file():
        try:s=p.read_text()
        except UnicodeDecodeError:continue
        if '/config/esp_manager' in s:errors.append('Dev-Datenpfad in Stable: '+str(p.relative_to(root)))
if not (root/'project_memory').is_dir(): errors.append('project_memory fehlt')
if errors:
    print('\n'.join(errors));raise SystemExit(1)
print('Promotion 0.12.2 validiert')
