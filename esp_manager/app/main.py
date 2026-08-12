from __future__ import annotations
import hashlib, io, json, os, secrets, shutil, subprocess, sys, threading, time, zipfile
from pathlib import Path
from typing import Any
import paho.mqtt.client as mqtt
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

ROOT=Path(os.getenv('ESP_MANAGER_ROOT','/config/esp_manager')); PROJECTS=ROOT/'projects'; FIRMWARE=ROOT/'firmware'; BACKUPS=ROOT/'backups'; OPTFILE=Path('/data/options.json'); T=Path(__file__).parent/'templates'
for d in (PROJECTS,FIRMWARE,BACKUPS):d.mkdir(parents=True,exist_ok=True)
DEFAULTS={'mqtt_host':'core-mosquitto','mqtt_port':1883,'mqtt_username':'','mqtt_password':'','device_mqtt_host':'homeassistant.local','device_mqtt_port':1883,'device_mqtt_username':'','device_mqtt_password':'','public_base_url':'http://homeassistant.local:8099'}
def options():
 d=dict(DEFAULTS)
 if OPTFILE.exists():
  try:d.update(json.loads(OPTFILE.read_text()))
  except Exception:pass
 return d
OPT=options();app=FastAPI(title='ESP Manager');JOBS={};PROCS={};DEVICES={};MQTT=None
BOARDS={'nodemcuv2':('NodeMCU 1.0 ESP8266MOD','ESP8266','esp8266',0),'esp12e':('ESP8266 ESP-12E','ESP8266','esp8266',0),'esp32dev':('ESP32 DevKit / WROOM-32','ESP32','esp32',0x1000),'esp32-s2-saola-1':('ESP32-S2 Saola','ESP32-S2','esp32s2',0x1000),'esp32-s3-devkitc-1':('ESP32-S3 DevKitC-1','ESP32-S3','esp32s3',0),'esp32-c3-devkitm-1':('ESP32-C3 DevKitM-1','ESP32-C3','esp32c3',0),'esp32-c6-devkitc-1':('ESP32-C6 DevKitC-1','ESP32-C6','esp32c6',0)}

def clean(v):
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in str(v).strip()).split('_') if x)
 if not n:raise HTTPException(400,'Ungültiger Name')
 return n[:64]
def pdir(project):
 p=PROJECTS/clean(project)
 if not p.exists():raise HTTPException(404,'Projekt nicht gefunden')
 return p
def load_meta(project):return migrate(yaml.safe_load((pdir(project)/'espmanager.yaml').read_text()) or {})
def save_meta(project,m):(pdir(project)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False))
def migrate(m):
 m.setdefault('display_name',m.get('name','').replace('_',' ').title());m.setdefault('board','esp32dev');m.setdefault('version','0.1.0');m.setdefault('monitor_speed',115200);m.setdefault('libraries',[]);m.setdefault('build_flags',[]);m.setdefault('ota_token',secrets.token_urlsafe(32));return m
def public(m):r=dict(m);r.pop('ota_token',None);return r
def backup(project,reason):
 out=BACKUPS/f'{clean(project)}-{time.strftime("%Y%m%d-%H%M%S")}-{reason}.zip';p=pdir(project)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 return out
def copy_system(p):
 shutil.copy2(T/'src'/'main.cpp',p/'src'/'main.cpp');dst=p/'lib'/'ESPManager'
 if dst.exists():shutil.rmtree(dst)
 shutil.copytree(T/'lib'/'ESPManager',dst)
def render_pio(p,m):
 platform='espressif8266' if m['board'] in ('nodemcuv2','esp12e') else 'espressif32';req=['tzapu/WiFiManager@^2.0.17','knolleary/PubSubClient@^2.8','bblanchon/ArduinoJson@^7.2.1'];libs=req+[x for x in m['libraries'] if x not in req]
 flags=[f'-D ESPMANAGER_DEVICE_ID=\\"{m["name"]}\\"',f'-D ESPMANAGER_FW_VERSION=\\"{m["version"]}\\"',f'-D ESPMANAGER_MQTT_HOST=\\"{OPT["device_mqtt_host"]}\\"',f'-D ESPMANAGER_MQTT_PORT={int(OPT["device_mqtt_port"])}',f'-D ESPMANAGER_MQTT_USER=\\"{OPT["device_mqtt_username"]}\\"',f'-D ESPMANAGER_MQTT_PASS=\\"{OPT["device_mqtt_password"]}\\"',f'-D ESPMANAGER_OTA_TOKEN=\\"{m["ota_token"]}\\"']+m['build_flags']
 text=f'[env:{m["board"]}]\nplatform = {platform}\nboard = {m["board"]}\nframework = arduino\nmonitor_speed = {m["monitor_speed"]}\nlib_deps =\n'+'\n'.join('  '+x for x in libs)+'\nbuild_flags =\n'+'\n'.join('  '+x for x in flags)+'\n';(p/'platformio.ini').write_text(text)
def safe_file(project,rel,exists=True):
 rel=str(rel).replace('\\','/').lstrip('/')
 if '..' in Path(rel).parts or not rel.startswith(('src/','include/','lib/')) or rel=='src/main.cpp' or rel.startswith('lib/ESPManager/'):raise HTTPException(403,'Systemdatei oder ungültiger Pfad')
 f=pdir(project)/rel
 if exists and not f.is_file():raise HTTPException(404,'Datei fehlt')
 return f
def list_files(project):
 p=pdir(project);out=[]
 for root in ('src','include','lib'):
  for f in (p/root).rglob('*'):
   if f.is_file():
    r=f.relative_to(p).as_posix()
    if r!='src/main.cpp' and not r.startswith('lib/ESPManager/'):out.append(r)
 return sorted(out)
def initial_image(p,m,out):
 build=p/'.pio'/'build'/m['board'];target=out/'initial_firmware.bin';label,family,chip,boot=BOARDS[m['board']]
 if family=='ESP8266':shutil.copy2(build/'firmware.bin',target);return family
 esptool=Path('/data/platformio/packages/tool-esptoolpy/esptool.py');parts=[hex(boot),str(build/'bootloader.bin'),hex(0x8000),str(build/'partitions.bin'),hex(0x10000),str(build/'firmware.bin')];bootapp=Path('/data/platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin')
 if bootapp.exists():parts[4:4]=[hex(0xE000),str(bootapp)]
 r=subprocess.run([sys.executable,str(esptool),'--chip',chip,'merge_bin','-o',str(target),'--flash_mode','dio','--flash_freq','40m','--flash_size','4MB']+parts,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return family

def on_connect(c,u,f,reason,properties=None):
 for t in ('espmanager/+/status','espmanager/+/availability','espmanager/+/log','espmanager/+/ota/progress'):c.subscribe(t)
def on_message(c,u,msg):
 parts=msg.topic.split('/');
 if len(parts)<3:return
 dev,kind=parts[1],parts[2];e=DEVICES.setdefault(dev,{'device_id':dev,'logs':[]});e['last_seen']=int(time.time());text=msg.payload.decode(errors='replace')
 if kind=='status':
  try:e.update(json.loads(text))
  except Exception:e['raw_status']=text
 elif kind=='availability':e['availability']=text
 elif kind=='log':e['logs']=(e['logs']+[{'ts':int(time.time()),'line':text}])[-200:]
 elif kind=='ota':e['ota_progress']=text
@app.on_event('startup')
def start_mqtt():
 global MQTT
 c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='esp-manager-addon');
 if OPT['mqtt_username']:c.username_pw_set(OPT['mqtt_username'],OPT['mqtt_password'])
 c.on_connect=on_connect;c.on_message=on_message
 try:c.connect(OPT['mqtt_host'],int(OPT['mqtt_port']),60);c.loop_start();MQTT=c
 except Exception as e:print('MQTT disabled:',e)

def ui_html():
 boardopts=''.join(f'<option value="{k}">{v[0]}</option>' for k,v in BOARDS.items())
 return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP Manager</title><style>body{{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}}.card{{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:15px;margin:12px 0}}button,input,select,textarea{{font:inherit;padding:8px;margin:4px;border-radius:8px;border:1px solid #475569}}button{{background:#2563eb;color:white}}.danger{{background:#991b1b}}textarea{{box-sizing:border-box;width:100%;height:280px;background:#030712;color:#e5e7eb;font-family:monospace}}pre{{background:#030712;padding:12px;white-space:pre-wrap;max-height:420px;overflow:auto}}.item{{padding:8px;border-bottom:1px solid #374151}}a{{color:#93c5fd;margin-left:8px}}.warn{{color:#fbbf24}}</style></head><body><h1>ESP Manager 0.6.1</h1><div class="card"><b>Geräte-MQTT:</b> {OPT['device_mqtt_host']}:{OPT['device_mqtt_port']} <span class="warn">Das muss vom ESP im Heimnetz erreichbar sein. core-mosquitto ist nur intern.</span></div><div class="grid"><section class="card"><h2>Neues Projekt</h2><input id="pn" placeholder="Projektname"><select id="pb">{boardopts}</select><button onclick="createP()">Anlegen</button><h3>Projekt importieren</h3><input id="imp" type="file" accept=".zip"><button onclick="importP()">Importieren</button></section><section class="card"><h2>Projekte</h2><div id="projects"></div></section><section class="card"><h2>Geräte</h2><div id="devices"></div></section></div><section class="card"><h2>Projekt <span id="title"></span></h2><button onclick="duplicateP()">Duplizieren</button><button onclick="backupP()">Backup</button><button onclick="exportP()">Export</button><button class="danger" onclick="deleteP()">Löschen</button><h3>Einstellungen</h3><input id="display" placeholder="Anzeigename"><select id="board">{boardopts}</select><input id="version" placeholder="0.1.0"><button onclick="saveSettings()">Speichern</button><details><summary>PlatformIO Experteneinstellungen</summary><input id="speed" type="number"><p>Bibliotheken, eine pro Zeile</p><textarea id="libraries"></textarea><p>Build-Flags, eine pro Zeile</p><textarea id="flags"></textarea></details><h3>Dateien</h3><input id="newfile" placeholder="src/datei.cpp"><button onclick="newF()">Anlegen</button><div id="files"></div><h4 id="filename"></h4><button onclick="saveF()">Speichern</button><button class="danger" onclick="deleteF()">Datei löschen</button><textarea id="editor"></textarea></section><section class="card"><h2>Build</h2><button onclick="startBuild()">Kompilieren</button><button class="danger" onclick="cancelBuild()">Abbrechen</button><div id="status">Bereit</div><pre id="log"></pre><h3>Historie</h3><div id="history"></div></section><script>let project=null,file=null,job=null,timer=null;async function api(p,o){{let r=await fetch(p,o);if(!r.ok)throw Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}}async function refresh(){{let ps=await api('api/projects');projects.innerHTML=ps.map(x=>`<div class="item"><b>${{x.name}}</b> ${{x.version}}<br><button onclick="openP('${{x.name}}')">Öffnen</button><button onclick="quickBuild('${{x.name}}')">Build</button><a href="usb/${{x.name}}">USB & Status</a></div>`).join('')||'Keine Projekte';refreshDevices()}}async function refreshDevices(){{let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class="item"><b>${{x.device_id}}</b> ${{x.availability||''}}<br>${{x.ip||''}} ${{x.ssid||''}} RSSI ${{x.rssi||'-'}}</div>`).join('')||'Noch keine Geräte'}}async function createP(){{try{{await api('api/projects',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:pn.value,board:pb.value}})}});pn.value='';refresh()}}catch(e){{alert(e.message)}}}}async function openP(p){{project=p;file=null;title.textContent='- '+p;let m=await api(`api/projects/${{p}}`);display.value=m.display_name;board.value=m.board;version.value=m.version;speed.value=m.monitor_speed;libraries.value=(m.libraries||[]).join('\\n');flags.value=(m.build_flags||[]).join('\\n');refreshFiles();refreshHistory()}}async function saveSettings(){{await api(`api/projects/${{project}}`,{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{display_name:display.value,board:board.value,version:version.value,monitor_speed:+speed.value,libraries:libraries.value.split('\\n').filter(Boolean),build_flags:flags.value.split('\\n').filter(Boolean)}})}});alert('Gespeichert')}}async function refreshFiles(){{let fs=await api(`api/projects/${{project}}/files`);files.innerHTML=fs.map(x=>`<div class="item" onclick="openF('${{x}}')">${{x}}</div>`).join('')}}async function openF(f){{file=f;filename.textContent=f;editor.value=await api(`api/projects/${{project}}/file?path=${{encodeURIComponent(f)}}`)}}async function saveF(){{if(!file)return alert('Datei auswählen');await api(`api/projects/${{project}}/file?path=${{encodeURIComponent(file)}}`,{{method:'PUT',body:editor.value}})}}async function deleteF(){{if(file&&confirm(file+' löschen?')){{await api(`api/projects/${{project}}/file?path=${{encodeURIComponent(file)}}`,{{method:'DELETE'}});file=null;editor.value='';refreshFiles()}}}}async function newF(){{if(!project)return alert('Projekt öffnen');let p=newfile.value.trim();if(!p)return;if(!p.includes('/'))p='src/'+p;try{{await api(`api/projects/${{project}}/files`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{path:p}})}});newfile.value='';refreshFiles();openF(p)}}catch(e){{alert(e.message)}}}}async function quickBuild(p){{project=p;startBuild()}}async function startBuild(){{if(!project)return alert('Projekt öffnen');let r=await api(`api/projects/${{project}}/build-start`,{{method:'POST'}});job=r.job_id;log.textContent='';clearInterval(timer);timer=setInterval(poll,700)}}async function poll(){{let r=await api(`api/builds/${{job}}`);status.textContent='Status: '+r.status;log.textContent=r.log||'';log.scrollTop=log.scrollHeight;if(['success','failed','cancelled'].includes(r.status)){{clearInterval(timer);refreshHistory()}}}}async function cancelBuild(){{if(job)await api(`api/builds/${{job}}/cancel`,{{method:'POST'}})}}async function refreshHistory(){{let hs=await api(`api/projects/${{project}}/builds`);history.innerHTML=hs.map(x=>`<div class="item">${{x.version}} ${{x.chip_family}} ${{new Date(x.built_at*1000).toLocaleString()}}<br><a href="api/projects/${{project}}/builds/${{x.id}}/firmware">OTA-Firmware</a></div>`).join('')||'Keine Builds'}}async function duplicateP(){{let n=prompt('Neuer Name');if(n){{await api(`api/projects/${{project}}/duplicate`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n}})}});refresh()}}}}async function backupP(){{await api(`api/projects/${{project}}/backup`,{{method:'POST'}});alert('Backup erstellt')}}function exportP(){{location.href=`api/projects/${{project}}/export`}}async function deleteP(){{if(confirm('Projekt löschen?')){{await api(`api/projects/${{project}}`,{{method:'DELETE'}});project=null;refresh()}}}}async function importP(){{if(!imp.files[0])return alert('ZIP auswählen');let n=prompt('Neuer Projektname');if(!n)return;let fd=new FormData();fd.append('name',n);fd.append('archive',imp.files[0]);try{{await api('api/projects/import',{{method:'POST',body:fd}});refresh()}}catch(e){{alert(e.message)}}}}refresh();setInterval(refreshDevices,5000)</script></body></html>'''
@app.get('/',response_class=HTMLResponse)
def ui():return HTMLResponse(ui_html())

@app.get('/api/projects')
def projects():return [public(migrate(yaml.safe_load(f.read_text()) or {})) for f in sorted(PROJECTS.glob('*/espmanager.yaml'))]
@app.post('/api/projects')
async def create_project(payload:dict[str,Any]):
 name=clean(payload.get('name',''));board=payload.get('board','esp32dev')
 if board not in BOARDS:raise HTTPException(400,'Board nicht unterstützt')
 p=PROJECTS/name
 if p.exists():raise HTTPException(409,'Projekt existiert')
 for d in ('src','include','lib'):(p/d).mkdir(parents=True,exist_ok=True)
 m=migrate({'name':name,'board':board});(p/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));shutil.copytree(T/'src',p/'src',dirs_exist_ok=True);copy_system(p);render_pio(p,m);return public(m)
@app.get('/api/projects/{project}')
def get_project(project):m=load_meta(project);save_meta(project,m);return public(m)
@app.put('/api/projects/{project}')
async def put_project(project,payload:dict[str,Any]):
 backup(project,'before-settings');m=load_meta(project)
 for k in ('display_name','board','version','monitor_speed','libraries','build_flags'):
  if k in payload:m[k]=payload[k]
 if m['board'] not in BOARDS:raise HTTPException(400,'Board nicht unterstützt')
 save_meta(project,m);render_pio(pdir(project),m);return public(m)
@app.get('/api/projects/{project}/files')
def files(project):return list_files(project)
@app.post('/api/projects/{project}/files')
async def create_file(project,payload:dict[str,Any]):
 f=safe_file(project,payload.get('path',''),False);f.parent.mkdir(parents=True,exist_ok=True)
 if f.exists():raise HTTPException(409,'Datei existiert')
 f.write_text('// Neue Datei\n');return {'ok':True}
@app.get('/api/projects/{project}/file',response_class=PlainTextResponse)
def read_file(project,path):return safe_file(project,path).read_text(errors='replace')
@app.put('/api/projects/{project}/file')
async def write_file(project,path,request:Request):safe_file(project,path).write_bytes(await request.body());return {'ok':True}
@app.delete('/api/projects/{project}/file')
def delete_file(project,path):backup(project,'before-file-delete');safe_file(project,path).unlink();return {'ok':True}
@app.post('/api/projects/{project}/duplicate')
async def duplicate(project,payload:dict[str,Any]):
 src=pdir(project);name=clean(payload.get('name',''));dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Ziel existiert')
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.pio'));m=migrate(yaml.safe_load((dst/'espmanager.yaml').read_text()) or {});m.update(name=name,display_name=name.replace('_',' ').title(),ota_token=secrets.token_urlsafe(32));(dst/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));render_pio(dst,m);return public(m)
@app.post('/api/projects/{project}/backup')
def make_backup(project):return {'file':backup(project,'manual').name}
@app.get('/api/projects/{project}/export')
def export_project(project):return FileResponse(backup(project,'export'),filename=f'{clean(project)}-export.zip')
@app.delete('/api/projects/{project}')
def delete_project(project):backup(project,'before-delete');shutil.rmtree(pdir(project));shutil.rmtree(FIRMWARE/clean(project),ignore_errors=True);return {'ok':True}
@app.post('/api/projects/import')
async def import_project(name:str=Form(...),archive:UploadFile=File(...)):
 name=clean(name);dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Projekt existiert')
 try:z=zipfile.ZipFile(io.BytesIO(await archive.read()))
 except Exception as e:raise HTTPException(400,f'Ungültiges ZIP: {e}')
 tmp=PROJECTS/f'.import-{name}-{time.time_ns()}';tmp.mkdir()
 try:
  for it in z.infolist():
   if not it.is_dir() and '..' not in Path(it.filename).parts:
    out=tmp/it.filename;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(it))
  if not (tmp/'espmanager.yaml').exists():raise HTTPException(400,'espmanager.yaml fehlt')
  m=migrate(yaml.safe_load((tmp/'espmanager.yaml').read_text()) or {});m.update(name=name,display_name=name.replace('_',' ').title(),ota_token=secrets.token_urlsafe(32));(tmp/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));copy_system(tmp);render_pio(tmp,m);tmp.rename(dst);return public(m)
 except Exception:shutil.rmtree(tmp,ignore_errors=True);raise

def worker(jid):
 j=JOBS[jid];p=pdir(j['project']);m=load_meta(j['project']);copy_system(p);render_pio(p,m);j['status']='running'
 try:
  proc=subprocess.Popen(['/opt/esp_manager/venv/bin/pio','run'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1);PROCS[jid]=proc
  for line in proc.stdout or []:j['log']=(j['log']+line)[-100000:]
  code=proc.wait();PROCS.pop(jid,None)
  if j.get('cancel'):j['status']='cancelled';return
  if code:j['status']='failed';return
  src=p/'.pio'/'build'/m['board']/'firmware.bin';data=src.read_bytes();bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/j['project']/bid;out.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out/'firmware.bin');family=initial_image(p,m,out);rec={'id':bid,'version':m['version'],'board':m['board'],'chip_family':family,'built_at':int(time.time()),'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'initial_size':(out/'initial_firmware.bin').stat().st_size};(out/'manifest.json').write_text(json.dumps(rec,indent=2));j['status']='success';j['build']=rec
 except Exception as e:j['status']='failed';j['log']+='\n'+repr(e)
@app.post('/api/projects/{project}/build-start')
def start_build(project):
 pdir(project);jid=f'{clean(project)}-{time.time_ns()}';JOBS[jid]={'project':clean(project),'status':'queued','log':''};threading.Thread(target=worker,args=(jid,),daemon=True).start();return {'job_id':jid}
@app.get('/api/builds/{jid}')
def get_build(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 return JOBS[jid]
@app.post('/api/builds/{jid}/cancel')
def cancel(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 JOBS[jid]['cancel']=True;proc=PROCS.get(jid)
 if proc and proc.poll() is None:proc.terminate()
 JOBS[jid]['status']='cancelled';return {'ok':True}
def build_list(project):
 root=FIRMWARE/clean(project);out=[]
 if root.exists():
  for f in root.glob('*/manifest.json'):
   try:d=json.loads(f.read_text());d['_dir']=f.parent;out.append(d)
   except Exception:pass
 return sorted(out,key=lambda x:x.get('built_at',0),reverse=True)
@app.get('/api/projects/{project}/builds')
def builds(project):return [{k:v for k,v in d.items() if k!='_dir'} for d in build_list(project)]
@app.get('/api/projects/{project}/builds/{bid}/firmware')
def firmware(project,bid):
 f=FIRMWARE/clean(project)/clean(bid)/'firmware.bin'
 if not f.exists():raise HTTPException(404,'Firmware fehlt')
 return FileResponse(f,filename=f'{clean(project)}-{bid}.bin')
@app.get('/api/devices')
def devices():return list(DEVICES.values())
@app.get('/api/devices/{device}')
def device(device):
 if clean(device) not in DEVICES:raise HTTPException(404,'Gerät hat sich noch nicht gemeldet')
 return DEVICES[clean(device)]

def hardware_page(project):
 return """<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><script type='module' src='https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module'></script><style>body{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}.card{background:#1f2937;padding:16px;border-radius:14px;margin:12px 0}button{padding:8px}pre{background:#030712;padding:12px;min-height:220px;white-space:pre-wrap}a{color:#93c5fd}</style></head><body><h1>USB & Status: PROJECT</h1><div class='card'><h2>USB-Erstinstallation</h2><div id='manifestState'>Prüfe Manifest ...</div><esp-web-install-button id='installer'></esp-web-install-button></div><div class='card'><h2>Serieller Monitor</h2><button onclick='connectSerial()'>Verbinden</button><button onclick='disconnectSerial()'>Trennen</button><pre id='serialLog'></pre></div><div class='card'><h2>WLAN</h2><p>Nach dem Flash mit <b>ESPManager-PROJECT</b> verbinden. Falls nötig 192.168.4.1 öffnen.</p></div><div class='card'><h2>MQTT-Status</h2><pre id='deviceStatus'>Noch kein Status</pre></div><a href='../..'>Zurück</a><script>let port,reader,reading=false;async function checkManifest(){try{let base=location.pathname.endsWith('/')?location.pathname:location.pathname+'/';let url=base+'manifest.json';installer.setAttribute('manifest',url);let r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(await r.text());let m=await r.json();manifestState.textContent='Bereit: '+m.name+' '+m.version+' / '+m.builds[0].chipFamily}catch(e){manifestState.textContent='Manifest-Fehler: '+e.message}}async function connectSerial(){try{port=await navigator.serial.requestPort();await port.open({baudRate:115200});reading=true;const dec=new TextDecoderStream();port.readable.pipeTo(dec.writable);reader=dec.readable.getReader();while(reading){let r=await reader.read();if(r.done)break;serialLog.textContent+=r.value;serialLog.scrollTop=serialLog.scrollHeight}}catch(e){serialLog.textContent+='\nFehler: '+e.message}}async function disconnectSerial(){reading=false;try{await reader?.cancel();reader?.releaseLock();await port?.close()}catch(e){}}async function refreshStatus(){try{let r=await fetch('../../api/devices/PROJECT');if(!r.ok)throw Error(await r.text());deviceStatus.textContent=JSON.stringify(await r.json(),null,2)}catch(e){deviceStatus.textContent='Noch kein MQTT-Status: '+e.message}}checkManifest();refreshStatus();setInterval(refreshStatus,5000)</script></body></html>""".replace('PROJECT',clean(project))
@app.get('/usb/{project}',response_class=HTMLResponse,include_in_schema=False)
@app.get('/usb/{project}/',response_class=HTMLResponse)
def usb_page(project):pdir(project);return HTMLResponse(hardware_page(project))
@app.get('/usb/{project}/manifest.json')
def manifest(project):
 m=load_meta(project);bs=build_list(project)
 if not bs:raise HTTPException(404,'Zuerst kompilieren')
 b=bs[0];return {'name':m['display_name'],'version':b['version'],'new_install_prompt_erase':True,'builds':[{'chipFamily':b['chip_family'],'parts':[{'path':'initial_firmware.bin','offset':0}]}]}
@app.get('/usb/{project}/initial_firmware.bin')
def initial_firmware(project):
 bs=build_list(project)
 if not bs:raise HTTPException(404,'Zuerst kompilieren')
 return FileResponse(bs[0]['_dir']/'initial_firmware.bin',media_type='application/octet-stream')
