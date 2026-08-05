from __future__ import annotations
import hashlib, io, json, re, secrets, shutil, subprocess, threading, time, zipfile
from pathlib import Path
from typing import Any
import paho.mqtt.client as mqtt
import yaml
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

ROOT=Path('/config/esp_manager_dev'); PROJECTS=ROOT/'projects'; FIRMWARE=ROOT/'firmware'; OPTIONS_FILE=Path('/data/options.json'); TEMPLATES=Path(__file__).parent/'templates'
for d in (PROJECTS,FIRMWARE): d.mkdir(parents=True,exist_ok=True)
def options():
 d={'mqtt_host':'core-mosquitto','mqtt_port':1883,'mqtt_username':'','mqtt_password':'','discovery_prefix':'homeassistant','public_base_url':'http://homeassistant.local:8099'}
 if OPTIONS_FILE.exists():
  try:d.update(json.loads(OPTIONS_FILE.read_text()))
  except Exception:pass
 return d
OPT=options(); app=FastAPI(title='ESP Manager'); JOBS={}; DEVICES={}; MQTT=None

def clean_name(v:str)->str:
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in v.strip()).split('_') if x)
 if not n:raise HTTPException(400,'Ungültiger Name')
 return n[:64]
def project_path(project:str)->Path:
 p=PROJECTS/clean_name(project)
 if not p.exists():raise HTTPException(404,'Projekt nicht gefunden')
 return p
def load_meta(project):return yaml.safe_load((project_path(project)/'espmanager.yaml').read_text())
def save_meta(project,m):(project_path(project)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False))
def copy_agent(p):
 dst=p/'lib'/'ESPManager'
 if dst.exists():shutil.rmtree(dst)
 shutil.copytree(TEMPLATES/'lib'/'ESPManager',dst)
def write_pio(p,m):
 board=m['board']; platform='espressif8266' if board in ('esp12e','nodemcuv2') else 'espressif32'
 p.joinpath('platformio.ini').write_text(f'''[env:{board}]\nplatform = {platform}\nboard = {board}\nframework = arduino\nmonitor_speed = 115200\nlib_deps =\n  knolleary/PubSubClient@^2.8\n  bblanchon/ArduinoJson@^7.2.1\n  tzapu/WiFiManager@^2.0.17\nbuild_flags =\n  -D ESPMANAGER_DEVICE_ID=\\"{m['name']}\\"\n  -D ESPMANAGER_FW_VERSION=\\"{m.get('version','0.1.0')}\\"\n  -D ESPMANAGER_MQTT_HOST=\\"{OPT.get('mqtt_host','core-mosquitto')}\\"\n  -D ESPMANAGER_MQTT_PORT={int(OPT.get('mqtt_port',1883))}\n  -D ESPMANAGER_MQTT_USER=\\"{OPT.get('mqtt_username','')}\\"\n  -D ESPMANAGER_MQTT_PASS=\\"{OPT.get('mqtt_password','')}\\"\n  -D ESPMANAGER_OTA_TOKEN=\\"{m['ota_token']}\\"\n''')
def user_file(project,rel,must_exist=True):
 rel=rel.replace('\\','/').lstrip('/'); parts=Path(rel).parts
 if '..' in parts or not rel.startswith(('src/','include/','lib/')):raise HTTPException(400,'Pfad nicht erlaubt')
 if rel=='src/main.cpp' or rel.startswith('lib/ESPManager/'):raise HTTPException(403,'Automatisch verwaltete Systemdatei')
 p=project_path(project)/rel
 if must_exist and not p.is_file():raise HTTPException(404,'Datei nicht gefunden')
 return p
def list_user_files(project):
 p=project_path(project); result=[]
 for root in ('src','include','lib'):
  for f in sorted((p/root).rglob('*')):
   if f.is_file():
    rel=f.relative_to(p).as_posix()
    if rel!='src/main.cpp' and not rel.startswith('lib/ESPManager/'):result.append(rel)
 return result

def on_connect(c,u,f,reason,properties=None):
 for t in ('espmanager/+/status','espmanager/+/availability','espmanager/+/log','espmanager/+/ota/progress'):c.subscribe(t)
def on_message(c,u,msg):
 parts=msg.topic.split('/');
 if len(parts)<3:return
 dev,kind=parts[1],parts[2]; e=DEVICES.setdefault(dev,{'device_id':dev,'logs':[]}); e['last_seen']=int(time.time()); text=msg.payload.decode(errors='replace')
 if kind=='status':
  try:e.update(json.loads(text))
  except Exception:e['status_payload']=text
 elif kind=='availability':e['availability']=text
 elif kind=='log':e['logs'].append({'ts':int(time.time()),'line':text});e['logs']=e['logs'][-300:]
 elif kind=='ota':e['ota_progress']=text
@app.on_event('startup')
def startup():
 global MQTT
 c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='esp-manager-addon')
 if OPT.get('mqtt_username'):c.username_pw_set(OPT['mqtt_username'],OPT.get('mqtt_password'))
 c.on_connect=on_connect;c.on_message=on_message
 try:c.connect(OPT['mqtt_host'],int(OPT['mqtt_port']),60);c.loop_start();MQTT=c
 except Exception as ex:print('MQTT disabled:',ex)

@app.get('/',response_class=HTMLResponse)
def ui():return HTMLResponse(r'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP Manager</title><style>body{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:15px;margin:12px 0}button,input,select,textarea{font:inherit;padding:8px;margin:4px;border-radius:8px;border:1px solid #475569}button{background:#2563eb;color:#fff;cursor:pointer}.danger{background:#991b1b}.secondary{background:#475569}textarea{box-sizing:border-box;width:100%;height:430px;background:#030712;color:#e5e7eb;font-family:monospace}pre{background:#030712;padding:12px;white-space:pre-wrap;max-height:440px;overflow:auto}a{color:#93c5fd;margin:5px}.muted{color:#9ca3af}.file{display:flex;justify-content:space-between;gap:8px;padding:5px;border-bottom:1px solid #374151}.ok{color:#86efac}.bad{color:#fca5a5}</style></head><body><h1>ESP Manager Dev 0.4.0-dev</h1><div class="grid"><section class="card"><h2>Neues Projekt</h2><input id="pname" placeholder="stromzaehler_sagemcom"><select id="pboard"><option value="esp32dev">ESP32 DevKit</option><option value="esp12e">ESP8266 ESP-12E</option><option value="esp32-s3-devkitc-1">ESP32-S3</option><option value="esp32-c3-devkitm-1">ESP32-C3</option><option value="esp32-s2-saola-1">ESP32-S2</option></select><button onclick="createProject()">Anlegen</button><h3>Arduino-Projekt importieren</h3><input id="zipfile" type="file" accept=".zip"><button onclick="importZip()">ZIP importieren</button></section><section class="card"><h2>Projekte</h2><div id="projects"></div></section><section class="card"><h2>Geräte</h2><div id="devices"></div></section></div><section class="card"><h2>Mein Programm <span id="current" class="muted"></span></h2><p class="muted">Hier bearbeitest du deine Anwendung. <code>main.cpp</code>, der ESPManager-Agent und <code>platformio.ini</code> werden automatisch verwaltet.</p><div><input id="newfile" placeholder="z. B. src/sagemcom.cpp"><button onclick="newFile()">Datei anlegen</button><input id="uploadfiles" type="file" multiple><button onclick="uploadFiles()">Dateien hochladen</button></div><div id="files"></div><h3 id="editorname"></h3><button onclick="saveFile()">Speichern</button><button class="danger" onclick="deleteFile()">Datei löschen</button><textarea id="editor" placeholder="Projekt öffnen und Datei auswählen"></textarea></section><section class="card"><h2>Build und Installation</h2><div id="buildstatus" class="muted">Bereit.</div><pre id="log">Noch kein Build gestartet.</pre></section><script>
let project=null,file=null,job=null,timer=null;async function api(p,o){const r=await fetch(p,o);if(!r.ok)throw new Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}async function refresh(){const ps=await api('api/projects');projects.innerHTML=ps.map(p=>`<div class="card"><b>${p.name}</b><br>${p.board}, Firmware ${p.version}<br><button onclick="openProject('${p.name}')">Projekt öffnen</button><button onclick="build('${p.name}')">Kompilieren</button><a href="webflash/${p.name}">USB-Erstinstallation</a><button onclick="ota('${p.name}')">Über WLAN aktualisieren (OTA)</button></div>`).join('')||'Keine Projekte';refreshDevices()}async function refreshDevices(){const ds=await api('api/devices');devices.innerHTML=ds.map(d=>`<div><b>${d.device_id}</b>: ${d.availability||'unbekannt'} ${d.ip||''} FW ${d.firmware_version||'-'}</div>`).join('')||'Noch keine Geräte'}async function createProject(){try{await api('api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pname.value,board:pboard.value})});pname.value='';refresh()}catch(e){alert(e.message)}}async function openProject(p){project=p;file=null;current.textContent='- '+p;editor.value='';editorname.textContent='';await refreshFiles()}async function refreshFiles(){if(!project)return;const fs=await api(`api/projects/${project}/files`);files.innerHTML=fs.map(f=>`<div class="file"><span onclick="openFile('${f}')" style="cursor:pointer">${f}</span><button class="secondary" onclick="renameFile('${f}')">Umbenennen</button></div>`).join('')||'Noch keine Benutzerdateien'}async function openFile(f){file=f;editorname.textContent=f;editor.value=await api(`api/projects/${project}/file?path=${encodeURIComponent(f)}`)}async function saveFile(){if(!project||!file)return alert('Datei auswählen');await api(`api/projects/${project}/file?path=${encodeURIComponent(file)}`,{method:'PUT',headers:{'Content-Type':'text/plain'},body:editor.value});alert('Gespeichert')}async function newFile(){if(!project)return alert('Projekt öffnen');await api(`api/projects/${project}/files`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:newfile.value})});newfile.value='';refreshFiles()}async function deleteFile(){if(!file||!confirm(file+' löschen?'))return;await api(`api/projects/${project}/file?path=${encodeURIComponent(file)}`,{method:'DELETE'});file=null;editor.value='';editorname.textContent='';refreshFiles()}async function renameFile(old){const n=prompt('Neuer Pfad',old);if(!n||n===old)return;await api(`api/projects/${project}/file-rename`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({old_path:old,new_path:n})});if(file===old){file=n;editorname.textContent=n}refreshFiles()}async function uploadFiles(){if(!project)return alert('Projekt öffnen');const fd=new FormData();for(const f of uploadfiles.files)fd.append('files',f);await api(`api/projects/${project}/upload`,{method:'POST',body:fd});uploadfiles.value='';refreshFiles()}async function importZip(){if(!zipfile.files[0])return;const name=prompt('Projektname');if(!name)return;const fd=new FormData();fd.append('archive',zipfile.files[0]);fd.append('name',name);fd.append('board',pboard.value);await api('api/projects/import',{method:'POST',body:fd});refresh()}async function build(p){const r=await api(`api/projects/${p}/build-start`,{method:'POST'});job=r.job_id;log.textContent='';if(timer)clearInterval(timer);timer=setInterval(poll,800);poll()}async function poll(){const r=await api(`api/builds/${job}`);log.textContent=r.log||'';buildstatus.innerHTML='Status: <b class="'+(r.status==='success'?'ok':r.status==='failed'?'bad':'')+'">'+r.status+'</b>';log.scrollTop=log.scrollHeight;if(['success','failed','timeout'].includes(r.status)){clearInterval(timer);timer=null}}async function ota(p){try{const r=await api(`api/devices/${p}/ota`,{method:'POST'});alert('OTA-Auftrag gesendet. SHA256: '+r.sha256)}catch(e){alert('OTA nicht möglich: '+e.message)}}refresh();setInterval(refreshDevices,5000)</script></body></html>''')

@app.get('/api/projects')
def projects():
 out=[]
 for p in sorted(PROJECTS.iterdir()):
  f=p/'espmanager.yaml'
  if f.exists():
   m=yaml.safe_load(f.read_text());m.pop('ota_token',None);out.append(m)
 return out
@app.post('/api/projects')
async def create(payload:dict[str,Any]):
 name=clean_name(payload.get('name',''));board=payload.get('board','esp32dev');p=PROJECTS/name
 if p.exists():raise HTTPException(409,'Projekt existiert bereits')
 for d in ('src','include','lib','builds'):(p/d).mkdir(parents=True,exist_ok=True)
 m={'name':name,'display_name':name.replace('_',' ').title(),'board':board,'version':'0.1.0','mode':'wrapper','ota_token':secrets.token_urlsafe(32)}
 (p/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));write_pio(p,m);shutil.copytree(TEMPLATES/'src',p/'src',dirs_exist_ok=True);copy_agent(p);m.pop('ota_token');return m
@app.post('/api/projects/import')
async def import_project(name:str,board:str,archive:UploadFile=File(...)):
 name=clean_name(name);p=PROJECTS/name
 if p.exists():raise HTTPException(409,'Projekt existiert bereits')
 raw=await archive.read()
 try:z=zipfile.ZipFile(io.BytesIO(raw))
 except Exception:raise HTTPException(400,'Ungültiges ZIP')
 for d in ('src','include','lib','builds'):(p/d).mkdir(parents=True,exist_ok=True)
 for item in z.infolist():
  if item.is_dir():continue
  parts=Path(item.filename).parts
  if '..' in parts:continue
  filename=Path(item.filename).name
  target_dir='include' if filename.endswith(('.h','.hpp')) else 'src' if filename.endswith(('.ino','.cpp','.c','.cc')) else None
  if not target_dir:continue
  content=z.read(item)
  if filename.endswith('.ino'):
   text=content.decode(errors='replace')
   text=re.sub(r'\bvoid\s+setup\s*\(\s*\)', 'void setupDevice()', text, count=1)
   text=re.sub(r'\bvoid\s+loop\s*\(\s*\)', 'void loopDevice()', text, count=1)
   target_name='device.cpp';content=text.encode()
  else:target_name=filename
  (p/target_dir/target_name).write_bytes(content)
 m={'name':name,'display_name':name.replace('_',' ').title(),'board':board,'version':'0.1.0','mode':'wrapper','ota_token':secrets.token_urlsafe(32)}
 (p/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));write_pio(p,m);shutil.copy2(TEMPLATES/'src'/'main.cpp',p/'src'/'main.cpp');copy_agent(p);return {'ok':True,'note':'Bei .ino-Dateien wurden setup() und loop() automatisch nach setupDevice() und loopDevice() umbenannt. Import anschließend prüfen.'}
@app.get('/api/projects/{project}/files')
def files(project:str):return list_user_files(project)
@app.post('/api/projects/{project}/files')
async def create_file(project:str,payload:dict[str,Any]):
 p=user_file(project,payload.get('path',''),False);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise HTTPException(409,'Datei existiert')
 p.write_text('// Neue Projektdatei\n');return {'ok':True}
@app.get('/api/projects/{project}/file',response_class=PlainTextResponse)
def read_file(project:str,path:str):return user_file(project,path).read_text(errors='replace')
@app.put('/api/projects/{project}/file')
async def write_file(project:str,path:str,request:Request):user_file(project,path).write_bytes(await request.body());return {'ok':True}
@app.delete('/api/projects/{project}/file')
def delete_file(project:str,path:str):user_file(project,path).unlink();return {'ok':True}
@app.post('/api/projects/{project}/file-rename')
async def rename_file(project:str,payload:dict[str,Any]):
 old=user_file(project,payload.get('old_path',''));new=user_file(project,payload.get('new_path',''),False);new.parent.mkdir(parents=True,exist_ok=True)
 if new.exists():raise HTTPException(409,'Zieldatei existiert')
 old.rename(new);return {'ok':True}
@app.post('/api/projects/{project}/upload')
async def upload(project:str,files:list[UploadFile]=File(...)):
 for f in files:
  name=Path(f.filename or '').name
  if not name.endswith(('.cpp','.c','.cc','.h','.hpp','.ino')):continue
  folder='include' if name.endswith(('.h','.hpp')) else 'src';(project_path(project)/folder/name).write_bytes(await f.read())
 return {'ok':True}

def worker(jid):
 j=JOBS[jid];p=project_path(j['project']);m=load_meta(j['project']);write_pio(p,m);copy_agent(p);j['status']='running'
 try:
  proc=subprocess.Popen(['/opt/esp_manager/venv/bin/pio','run'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  for line in proc.stdout or []:j['log']=(j['log']+line)[-60000:]
  code=proc.wait()
  if code:j['status']='failed';return
  fw=p/'.pio'/'build'/m['board']/'firmware.bin';data=fw.read_bytes();out=FIRMWARE/j['project'];out.mkdir(parents=True,exist_ok=True);shutil.copy2(fw,out/'firmware.bin');manifest={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'version':m.get('version','0.1.0'),'built_at':int(time.time())};(out/'manifest.json').write_text(json.dumps(manifest,indent=2));j['status']='success';j['manifest']=manifest
 except Exception as e:j['status']='failed';j['log']+='\n'+repr(e)
@app.post('/api/projects/{project}/build-start')
def build_start(project:str):
 project=clean_name(project);project_path(project);jid=f'{project}-{time.time_ns()}';JOBS[jid]={'job_id':jid,'project':project,'status':'queued','log':''};threading.Thread(target=worker,args=(jid,),daemon=True).start();return {'job_id':jid}
@app.get('/api/builds/{jid}')
def build_get(jid:str):
 if jid not in JOBS:raise HTTPException(404,'Build nicht gefunden')
 return JOBS[jid]
@app.get('/api/devices')
def devices():return list(DEVICES.values())
@app.post('/api/devices/{device}/ota')
def ota(device:str):
 if MQTT is None:raise HTTPException(503,'MQTT nicht verbunden')
 d=clean_name(device);m=load_meta(d);mf=FIRMWARE/d/'manifest.json'
 if not mf.exists():raise HTTPException(404,'Zuerst Firmware kompilieren')
 man=json.loads(mf.read_text());url=f"{str(OPT['public_base_url']).rstrip('/')}/firmware/{d}/firmware.bin?token={m['ota_token']}";MQTT.publish(f'espmanager/{d}/cmd/ota',json.dumps({'token':m['ota_token'],'url':url,**man}));return {'ok':True,'sha256':man['sha256']}
@app.get('/webflash/{project}',response_class=HTMLResponse)
def usb_page(project:str):project_path(project);return HTMLResponse(f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><script type="module" src="https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module"></script></head><body><h1>USB-Erstinstallation: {project}</h1><p>ESP per USB an diesen Laptop anschließen. Diese Funktion ist für den ersten Flash oder eine Wiederherstellung. Spätere Updates erfolgen in der Geräteansicht über WLAN (OTA).</p><esp-web-install-button manifest="manifest.json"></esp-web-install-button><p><a href="../..">Zurück</a></p></body></html>''')
@app.get('/webflash/{project}/manifest.json')
def web_manifest(project:str):
 m=load_meta(project);f=FIRMWARE/clean_name(project)/'firmware.bin'
 if not f.exists():raise HTTPException(404,'Zuerst kompilieren')
 chip='ESP8266' if str(m['board']).startswith('esp12') else 'ESP32';return {'name':project,'version':m.get('version','0.1.0'),'builds':[{'chipFamily':chip,'parts':[{'path':f'../../firmware/{project}/firmware.bin?token={m["ota_token"]}','offset':0}]}]}
@app.get('/firmware/{project}/firmware.bin')
def firmware(project:str,token:str=Query(default='')):
 m=load_meta(project)
 if token!=m['ota_token']:raise HTTPException(403,'Token ungültig')
 f=FIRMWARE/clean_name(project)/'firmware.bin'
 if not f.exists():raise HTTPException(404,'Firmware fehlt')
 return FileResponse(f,media_type='application/octet-stream')
