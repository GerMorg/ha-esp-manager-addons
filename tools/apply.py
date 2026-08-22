#!/usr/bin/env python3
from pathlib import Path
import re,sys,shutil
root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
app=root/'esp_manager_dev/app';static=app/'static';templates=app/'templates'
for p in (app,static,templates):
 if not p.exists():raise SystemExit(f'Fehlt: {p}')
shutil.copy2(Path(__file__).parents[1]/'payload/app/discovery.py',app/'discovery.py')
core=app/'core.py';s=core.read_text()
if 'from .discovery import generate as generate_discovery' not in s:s='from .discovery import generate as generate_discovery, load as load_discovery\n'+s
if 'ESPManagerDiscoveryGenerated.h' not in s:
 a=s.index('def render_pio(p,m):');b=s.find('\ndef ',a+1);b=len(s) if b<0 else b
 s=s[:b].rstrip()+"\n generate_discovery(load_discovery(p/'ha_discovery.yaml'),p/'include/ESPManagerDiscoveryGenerated.h')\n"+s[b:]
core.write_text(s)
main=app/'main.py';s=main.read_text()
if 'from .discovery import load as load_discovery' not in s:s=s.replace('from .core import *','from .core import *\nfrom .discovery import load as load_discovery, save as save_discovery, generate as generate_discovery',1)
if "'/api/projects/{name}/discovery'" not in s:s+="""\n@app.get('/api/projects/{name}/discovery')\ndef discovery_get(name): return load_discovery(pdir(name)/'ha_discovery.yaml')\n@app.put('/api/projects/{name}/discovery')\nasync def discovery_put(name,data:list[dict[str,Any]]):\n p=pdir(name);items=save_discovery(p/'ha_discovery.yaml',data);generate_discovery(items,p/'include/ESPManagerDiscoveryGenerated.h');return items\n"""
main.write_text(s)
(templates/'src/main.cpp').write_text('#include <Arduino.h>\n#include <ESPManager.h>\n#include <ESPManagerDiscoveryGenerated.h>\nextern void setupDevice(); extern void loopDevice();\nvoid setup(){ESPManagerRegisterGenerated();ESPManager.begin();setupDevice();}\nvoid loop(){ESPManager.loop();loopDevice();}\n')
index=static/'index.html';h=index.read_text()
if 'haDiscoveryEditor' not in h:
 panel='<details><summary>Home Assistant / MQTT Discovery</summary><p>sensor, binary_sensor, switch, number und cover projektbezogen definieren.</p><textarea id="haDiscoveryEditor"></textarea><div class="row"><button id="loadDiscovery">Laden</button><button id="saveDiscovery">Speichern</button></div><pre id="discoveryResult"></pre></details>'
 h=h.replace('<h3>Build</h3>',panel+'<h3>Build</h3>',1)
index.write_text(h)
js=static/'app.js';j=js.read_text()
if 'loadDiscoveryConfig' not in j:j+='''\nasync function loadDiscoveryConfig(){if(!project)return;let x=await api(`api/projects/${project}/discovery`);$('haDiscoveryEditor').value=JSON.stringify(x,null,2);$('discoveryResult').textContent=`${x.length} Entitäten geladen`;}\nasync function saveDiscoveryConfig(){if(!project)return;try{let d=JSON.parse($('haDiscoveryEditor').value||'[]');let x=await api(`api/projects/${project}/discovery`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});$('discoveryResult').textContent=`${x.length} Entitäten gespeichert. Neu kompilieren.`;}catch(e){$('discoveryResult').textContent='Fehler: '+e.message;}}\n$('loadDiscovery').onclick=loadDiscoveryConfig;$('saveDiscovery').onclick=saveDiscoveryConfig;\n'''
js.write_text(j)
# Install complete generic agent while retaining Wi-Fi recovery and publishSensor compatibility.
agent=Path(__file__).parents[1]/'payload/app/templates/lib/ESPManager/src'
shutil.copy2(agent/'ESPManager.h',templates/'lib/ESPManager/src/ESPManager.h')
shutil.copy2(agent/'ESPManager.cpp',templates/'lib/ESPManager/src/ESPManager.cpp')
# Version bump
cfg=root/'esp_manager_dev/config.yaml'
if cfg.exists():cfg.write_text(re.sub(r'(?m)^version:\s*.*$','version: 0.12.0-dev',cfg.read_text(),count=1))
print('Generic HA entity configuration 0.12.0 applied')
