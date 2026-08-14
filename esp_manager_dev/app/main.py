from __future__ import annotations
import hashlib,io,json,os,secrets,shutil,subprocess,sys,threading,time,zipfile
from pathlib import Path
from typing import Any
import paho.mqtt.client as mqtt
import yaml
from fastapi import FastAPI,File,Form,HTTPException,Request,UploadFile
from fastapi.responses import FileResponse,HTMLResponse,PlainTextResponse
ROOT=Path(os.getenv('ESP_MANAGER_ROOT','/config/esp_manager_dev'));PROJECTS=ROOT/'projects';FIRMWARE=ROOT/'firmware';BACKUPS=ROOT/'backups';T=Path(__file__).parent/'templates';OPTFILE=Path('/data/options.json')
for d in(PROJECTS,FIRMWARE,BACKUPS):d.mkdir(parents=True,exist_ok=True)
DEFAULTS={'mqtt_host':'core-mosquitto','mqtt_port':1883,'mqtt_username':'','mqtt_password':'','device_mqtt_host':'homeassistant.local','device_mqtt_port':1883,'device_mqtt_username':'','device_mqtt_password':'','public_base_url':'http://homeassistant.local:8100','build_retention':5,'device_offline_after':75,'wifi_reconnect_interval':15000,'wifi_recovery_restart_after':900000}
def options():
 d=dict(DEFAULTS)
 if OPTFILE.exists():
  try:d.update(json.loads(OPTFILE.read_text()))
  except Exception:pass
 return d
OPT=options();app=FastAPI(title='ESP Manager Dev 0.9.0.1');JOBS={};PROCS={};DEVICES={};MQTT=None
OTA_FILE=ROOT/'ota_jobs.json';HISTORY_FILE=ROOT/'device_history.jsonl'
def load_json(p,default):
 try:return json.loads(p.read_text()) if p.exists() else default
 except Exception:return default
OTA_JOBS=load_json(OTA_FILE,{})
def save_ota():tmp=OTA_FILE.with_suffix('.tmp');tmp.write_text(json.dumps(OTA_JOBS,indent=2));tmp.replace(OTA_FILE)
def history(dev,event,data):
 with HISTORY_FILE.open('a') as f:f.write(json.dumps({'ts':int(time.time()),'device_id':dev,'event':event,'data':data},separators=(',',':'))+'\n')
 lines=HISTORY_FILE.read_text().splitlines()
 if len(lines)>2000:HISTORY_FILE.write_text('\n'.join(lines[-2000:])+'\n')
BOARDS={'nodemcuv2':('NodeMCU ESP8266','ESP8266','esp8266',0),'esp32dev':('ESP32 DevKit/WROOM-32','ESP32','esp32',0x1000),'esp32-s2-saola-1':('ESP32-S2','ESP32-S2','esp32s2',0x1000),'esp32-s3-devkitc-1':('ESP32-S3','ESP32-S3','esp32s3',0),'esp32-c3-devkitm-1':('ESP32-C3','ESP32-C3','esp32c3',0),'esp32-c6-devkitc-1':('ESP32-C6','ESP32-C6','esp32c6',0)}
def clean(v):
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in str(v).strip()).split('_') if x)
 if not n:raise HTTPException(400,'Ungültiger Name')
 return n[:64]
def pdir(project):
 p=PROJECTS/clean(project)
 if not p.exists():raise HTTPException(404,'Projekt nicht gefunden')
 return p
def migrate(m):
 m.setdefault('display_name',m.get('name','').replace('_',' ').title());m.setdefault('board','esp32dev');m.setdefault('version','0.1.0');m.setdefault('monitor_speed',115200);m.setdefault('libraries',[]);m.setdefault('build_flags',[]);m.setdefault('device_id','');m.setdefault('ota_token',secrets.token_urlsafe(32));return m
def meta(project):return migrate(yaml.safe_load((pdir(project)/'espmanager.yaml').read_text()) or {})
def save_meta(project,m):(pdir(project)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False))
def public(m):r=dict(m);r.pop('ota_token',None);return r
def copy_system(p):shutil.copy2(T/'src/main.cpp',p/'src/main.cpp');dst=p/'lib/ESPManager';shutil.rmtree(dst,ignore_errors=True);shutil.copytree(T/'lib/ESPManager',dst)
def render_pio(p,m):
 platform='espressif8266' if m['board']=='nodemcuv2' else 'espressif32';libs=['tzapu/WiFiManager@^2.0.17','knolleary/PubSubClient@^2.8','bblanchon/ArduinoJson@^7.2.1']+[x for x in m['libraries'] if x not in ('tzapu/WiFiManager@^2.0.17','knolleary/PubSubClient@^2.8','bblanchon/ArduinoJson@^7.2.1')]
 flags=[f'-D ESPMANAGER_DEVICE_ID=\\"{m["name"]}\\"',f'-D ESPMANAGER_FW_VERSION=\\"{m["version"]}\\"',f'-D ESPMANAGER_MQTT_HOST=\\"{OPT["device_mqtt_host"]}\\"',f'-D ESPMANAGER_MQTT_PORT={int(OPT["device_mqtt_port"])}',f'-D ESPMANAGER_MQTT_USER=\\"{OPT["device_mqtt_username"]}\\"',f'-D ESPMANAGER_MQTT_PASS=\\"{OPT["device_mqtt_password"]}\\"',f'-D ESPMANAGER_OTA_TOKEN=\\"{m["ota_token"]}\\"',f'-D ESPMANAGER_WIFI_RECONNECT_INTERVAL={int(OPT["wifi_reconnect_interval"])}',f'-D ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER={int(OPT["wifi_recovery_restart_after"])}']+m['build_flags']
 (p/'platformio.ini').write_text(f'[env:{m["board"]}]\nplatform = {platform}\nboard = {m["board"]}\nframework = arduino\nmonitor_speed = {m["monitor_speed"]}\nlib_deps =\n'+'\n'.join('  '+x for x in libs)+'\nbuild_flags =\n'+'\n'.join('  '+x for x in flags)+'\n')
def safe_file(project,rel,exists=True):
 rel=str(rel).replace('\\','/').lstrip('/');f=pdir(project)/rel
 if '..' in Path(rel).parts or not rel.startswith(('src/','include/','lib/')) or rel=='src/main.cpp' or rel.startswith('lib/ESPManager/'):raise HTTPException(403,'Systemdatei oder Pfad gesperrt')
 if exists and not f.is_file():raise HTTPException(404,'Datei fehlt')
 return f
def backup(project,reason):
 out=BACKUPS/f'{clean(project)}-{time.strftime("%Y%m%d-%H%M%S")}-{reason}.zip';p=pdir(project)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 return out
def builds(project):
 out=[];root=FIRMWARE/clean(project)
 for f in root.glob('*/manifest.json') if root.exists() else []:
  try:d=json.loads(f.read_text());d['_dir']=f.parent;out.append(d)
  except Exception:pass
 return sorted(out,key=lambda x:x.get('built_at',0),reverse=True)
def prune(project,keep=None):
 keep=int(keep or OPT['build_retention']);n=0;removed=[]
 for b in builds(project):
  if b.get('pinned'):continue
  n+=1
  if n>keep:shutil.rmtree(b['_dir'],ignore_errors=True);removed.append(b['id'])
 return removed
def mqtt_connect(c,u,f,reason,properties=None):
 for t in('espmanager/+/status','espmanager/+/availability','espmanager/+/log','espmanager/+/ota/progress'):c.subscribe(t)
def mqtt_message(c,u,msg):
 parts=msg.topic.split('/');
 if len(parts)<3:return
 dev,kind=parts[1],parts[2];text=msg.payload.decode(errors='replace')
 if not msg.payload:
  DEVICES.pop(dev,None);return
 e=DEVICES.setdefault(dev,{'device_id':dev,'logs':[]});e['last_seen']=int(time.time())
 if kind=='status':
  try:
   d=json.loads(text);e.update(d);history(dev,'status',{k:d.get(k) for k in('firmware_version','ip','ssid','rssi','uptime','free_heap')})
   job=OTA_JOBS.get(dev)
   if job:
    e.update(ota_target_version=job['target_version'],ota_target_build=job['build_id'],ota_result=job['state'])
    if str(e.get('firmware_version'))==str(job['target_version']):job.update(state='confirmed',confirmed_at=int(time.time()));save_ota();e['ota_progress']=json.dumps({'state':'confirmed','percent':100,'message':'Neue Firmwareversion nach Neustart bestätigt'})
  except Exception:e['raw_status']=text
 elif kind=='availability':e['availability']=text
 elif kind=='log':e['logs']=(e['logs']+[{'ts':int(time.time()),'line':text}])[-200:]
 elif kind=='ota':e['ota_progress']=text
@app.on_event('startup')
def start_mqtt():
 global MQTT
 c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='esp-manager-dev-clean')
 if OPT['mqtt_username']:c.username_pw_set(OPT['mqtt_username'],OPT['mqtt_password'])
 c.on_connect=mqtt_connect;c.on_message=mqtt_message
 try:c.connect(OPT['mqtt_host'],int(OPT['mqtt_port']),60);c.loop_start();MQTT=c
 except Exception as exc:print('MQTT disabled:',exc)
def present(item):
 r=dict(item);r['last_seen_age']=max(0,int(time.time())-int(r.get('last_seen',0)));r['online']=r['last_seen_age']<=int(OPT['device_offline_after']);r['presence']='online' if r['online'] else 'offline';return r
@app.get('/api/projects')
def project_list():return[public(meta(p.name)) for p in sorted(PROJECTS.iterdir()) if(p/'espmanager.yaml').exists()]
@app.post('/api/projects')
async def project_create(data:dict[str,Any]):
 name=clean(data.get('name',''));board=data.get('board','esp32dev');p=PROJECTS/name
 if board not in BOARDS:raise HTTPException(400,'Board unbekannt')
 if p.exists():raise HTTPException(409,'Projekt existiert')
 for d in('src','include','lib'):(p/d).mkdir(parents=True,exist_ok=True)
 m=migrate({'name':name,'board':board});(p/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));shutil.copytree(T/'src',p/'src',dirs_exist_ok=True);copy_system(p);render_pio(p,m);return public(m)
@app.get('/api/projects/{project}')
def project_get(project):return public(meta(project))
@app.put('/api/projects/{project}')
async def project_put(project,data:dict[str,Any]):
 m=meta(project)
 for k in('display_name','board','version','monitor_speed','libraries','build_flags','device_id'):
  if k in data:m[k]=data[k]
 save_meta(project,m);render_pio(pdir(project),m);return public(m)
@app.delete('/api/projects/{project}')
def project_delete(project):backup(project,'before-delete');shutil.rmtree(pdir(project));return{'ok':True}
@app.get('/api/projects/{project}/files')
def files(project):
 p=pdir(project);return sorted(f.relative_to(p).as_posix() for root in('src','include','lib') for f in(p/root).rglob('*') if f.is_file() and f.relative_to(p).as_posix()!='src/main.cpp' and not f.relative_to(p).as_posix().startswith('lib/ESPManager/'))
@app.post('/api/projects/{project}/files')
async def file_create(project,data:dict[str,Any]):f=safe_file(project,data['path'],False);f.parent.mkdir(parents=True,exist_ok=True);f.write_text('// Neue Datei\n');return{'ok':True}
@app.get('/api/projects/{project}/file',response_class=PlainTextResponse)
def file_get(project,path):return safe_file(project,path).read_text(errors='replace')
@app.put('/api/projects/{project}/file')
async def file_put(project,path,request:Request):safe_file(project,path).write_bytes(await request.body());return{'ok':True}
@app.delete('/api/projects/{project}/file')
def file_delete(project,path):safe_file(project,path).unlink();return{'ok':True}
@app.post('/api/projects/{project}/backup')
def backup_api(project):return{'file':backup(project,'manual').name}
@app.get('/api/projects/{project}/export')
def export(project):return FileResponse(backup(project,'export'),filename=f'{clean(project)}.zip')
@app.post('/api/projects/import')
async def import_project(name:str=Form(...),archive:UploadFile=File(...)):
 name=clean(name);dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Projekt existiert')
 z=zipfile.ZipFile(io.BytesIO(await archive.read()));dst.mkdir()
 for i in z.infolist():
  if not i.is_dir() and '..' not in Path(i.filename).parts:
   f=dst/i.filename;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(i))
 if not(dst/'espmanager.yaml').exists():shutil.rmtree(dst);raise HTTPException(400,'espmanager.yaml fehlt')
 m=meta(name);m.update(name=name,ota_token=secrets.token_urlsafe(32));save_meta(name,m);copy_system(dst);render_pio(dst,m);return public(m)
def make_initial(p,m,out):
 build=p/'.pio/build'/m['board'];target=out/'initial_firmware.bin';family,chip,boot=BOARDS[m['board']][1:]
 if family=='ESP8266':shutil.copy2(build/'firmware.bin',target);return
 esptool=Path('/data/platformio/packages/tool-esptoolpy/esptool.py');parts=[hex(boot),str(build/'bootloader.bin'),hex(0x8000),str(build/'partitions.bin'),hex(0x10000),str(build/'firmware.bin')];bootapp=Path('/data/platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin')
 if bootapp.exists():parts[4:4]=[hex(0xE000),str(bootapp)]
 r=subprocess.run([sys.executable,str(esptool),'--chip',chip,'merge_bin','-o',str(target),'--flash_mode','dio','--flash_freq','40m','--flash_size','4MB']+parts,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
def build_worker(jid):
 j=JOBS[jid];p=pdir(j['project']);m=meta(j['project']);copy_system(p);render_pio(p,m);j['status']='running'
 try:
  proc=subprocess.Popen(['/opt/esp_manager/venv/bin/pio','run'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);PROCS[jid]=proc
  for line in proc.stdout or[]:j['log']=(j['log']+line)[-100000:]
  if proc.wait():j['status']='failed';return
  src=p/'.pio/build'/m['board']/'firmware.bin';bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/j['project']/bid;out.mkdir(parents=True);shutil.copy2(src,out/'firmware.bin');make_initial(p,m,out);data=src.read_bytes();rec={'id':bid,'version':m['version'],'board':m['board'],'chip_family':BOARDS[m['board']][1],'built_at':int(time.time()),'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'pinned':False};(out/'manifest.json').write_text(json.dumps(rec,indent=2));removed=prune(j['project']);j['log']+=f'\nBuild-Aufbewahrung: {len(removed)} alte Builds entfernt; Limit={OPT["build_retention"]}\n';j.update(status='success',build=rec)
 except Exception as exc:j['status']='failed';j['log']+='\n'+repr(exc)
@app.post('/api/projects/{project}/build-start')
def build_start(project):
 pdir(project);jid=f'{clean(project)}-{time.time_ns()}';JOBS[jid]={'project':clean(project),'status':'queued','log':''};threading.Thread(target=build_worker,args=(jid,),daemon=True).start();return{'job_id':jid}
@app.get('/api/builds/{jid}')
def build_status(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 return JOBS[jid]
@app.post('/api/builds/{jid}/cancel')
def build_cancel(jid):
 proc=PROCS.get(jid)
 if proc and proc.poll() is None:proc.terminate()
 JOBS[jid]['status']='cancelled';return{'ok':True}
@app.get('/api/projects/{project}/builds')
def build_list_api(project):return[{k:v for k,v in b.items() if k!='_dir'} for b in builds(project)]
@app.delete('/api/projects/{project}/builds/{bid}')
def build_delete(project,bid):
 b=next((x for x in builds(project) if x['id']==bid),None)
 if not b:raise HTTPException(404,'Build fehlt')
 if b.get('pinned'):raise HTTPException(409,'Build ist angeheftet')
 shutil.rmtree(b['_dir']);return{'ok':True}
@app.post('/api/projects/{project}/builds/{bid}/pin')
async def build_pin(project,bid,data:dict[str,Any]):
 b=next((x for x in builds(project) if x['id']==bid),None)
 if not b:raise HTTPException(404,'Build fehlt')
 d=json.loads((b['_dir']/'manifest.json').read_text());d['pinned']=bool(data.get('pinned',True));(b['_dir']/'manifest.json').write_text(json.dumps(d,indent=2));return{'pinned':d['pinned']}
@app.post('/api/projects/{project}/builds/prune')
async def build_prune(project,data:dict[str,Any]):return{'removed':prune(project,data.get('keep'))}
@app.get('/api/devices')
def devices():return sorted((present(x) for x in DEVICES.values()),key=lambda x:(not x['online'],x['device_id']))
@app.get('/api/devices/{device}')
def device(device):
 if clean(device) not in DEVICES:raise HTTPException(404,'Gerät unbekannt')
 return present(DEVICES[clean(device)])
@app.delete('/api/devices/{device}')
def device_delete(device):
 d=clean(device);DEVICES.pop(d,None);OTA_JOBS.pop(d,None);save_ota()
 if MQTT and MQTT.is_connected():
  for s in('status','availability','ota/progress'):MQTT.publish(f'espmanager/{d}/{s}','',qos=1,retain=True)
 return{'ok':True}
@app.get('/api/devices/{device}/history')
def device_history(device,limit:int=50):
 out=[]
 for line in HISTORY_FILE.read_text().splitlines() if HISTORY_FILE.exists() else[]:
  try:
   x=json.loads(line)
   if x.get('device_id')==clean(device):out.append(x)
  except Exception:pass
 return out[-max(1,min(limit,500)):]
def find_build(project,bid):
 b=next((x for x in builds(project) if x['id']==bid),None)
 if not b:raise HTTPException(404,'Build fehlt')
 return b
@app.post('/api/projects/{project}/devices/{device}/ota')
async def ota_start(project,device,data:dict[str,Any]):
 if not MQTT or not MQTT.is_connected():raise HTTPException(503,'MQTT nicht verbunden')
 m=meta(project);b=find_build(project,data.get('build_id') or builds(project)[0]['id']);fw=b['_dir']/'firmware.bin';sha=hashlib.sha256(fw.read_bytes()).hexdigest()
 if sha!=b['sha256']:raise HTTPException(409,'SHA256 stimmt nicht')
 url=f"{str(OPT['public_base_url']).rstrip('/')}/firmware/{clean(project)}/{b['id']}/firmware.bin?token={m['ota_token']}";cmd={'token':m['ota_token'],'url':url,'version':b['version'],'build_id':b['id'],'sha256':sha,'size':b['size']};payload=json.dumps(cmd,separators=(',',':'))
 MQTT.publish(f'espmanager/{clean(device)}/cmd/ota',payload,qos=1);OTA_JOBS[clean(device)]={'project':clean(project),'device_id':clean(device),'build_id':b['id'],'target_version':str(b['version']),'sha256':sha,'requested_at':int(time.time()),'state':'pending'};save_ota();return{'ok':True,'version':b['version'],'command_bytes':len(payload.encode()),'url':url}
@app.get('/firmware/{project}/{bid}/firmware.bin')
def ota_file(project,bid,token:str=''):
 m=meta(project)
 if token!=m['ota_token']:raise HTTPException(403,'Token falsch')
 b=find_build(project,bid);fw=b['_dir']/'firmware.bin';sha=hashlib.sha256(fw.read_bytes()).hexdigest()
 if sha!=b['sha256']:raise HTTPException(409,'SHA256 stimmt nicht')
 return FileResponse(fw,media_type='application/octet-stream',headers={'X-Firmware-SHA256':sha,'x-MD5':hashlib.md5(fw.read_bytes()).hexdigest(),'Cache-Control':'no-store'})
@app.get('/usb/{project}',response_class=HTMLResponse,include_in_schema=False)
@app.get('/usb/{project}/',response_class=HTMLResponse)
def hardware(project):pdir(project);return HTMLResponse(HARDWARE.replace('PROJECT',clean(project)))
@app.get('/usb/{project}/manifest.json')
def manifest(project):
 m=meta(project);bs=builds(project)
 if not bs:raise HTTPException(404,'Zuerst kompilieren')
 b=bs[0];return{'name':m['display_name'],'version':b['version'],'new_install_prompt_erase':True,'builds':[{'chipFamily':b['chip_family'],'parts':[{'path':'initial_firmware.bin','offset':0}]}]}
@app.get('/usb/{project}/initial_firmware.bin')
def initial(project):
 bs=builds(project)
 if not bs:raise HTTPException(404,'Zuerst kompilieren')
 return FileResponse(bs[0]['_dir']/'initial_firmware.bin')
UI='''<!doctype html><html><head><meta charset="utf-8"><title>ESP Manager Dev</title><style>body{font-family:system-ui;background:#111827;color:#e5e7eb;margin:20px}.card{background:#1f2937;padding:14px;margin:10px;border-radius:12px}.item{padding:8px;border-bottom:1px solid #374151}button,input,select,textarea{margin:3px;padding:7px}textarea,pre{background:#030712;color:#eee;width:100%;box-sizing:border-box}textarea{height:260px}</style></head><body><h1>ESP Manager Dev 0.9.0.1 clean</h1><div class="card"><input id="pn" placeholder="Projekt"><select id="pb"><option>esp32dev</option><option>nodemcuv2</option></select><button onclick="createP()">Anlegen</button></div><div class="card"><h2>Projekte</h2><div id="projects"></div></div><div class="card"><h2>Geräte</h2><div id="devices"></div><div id="detail"></div><pre id="hist"></pre></div><div class="card"><h2 id="title">Projekt</h2><input id="ver" placeholder="Version"><button onclick="saveP()">Speichern</button><button onclick="buildP()">Build</button><a id="usb">USB, OTA & Status</a><div id="files"></div><textarea id="editor"></textarea><button onclick="saveF()">Datei speichern</button><pre id="log"></pre></div><script src="app.js"></script></body></html>'''
@app.get('/',response_class=HTMLResponse)
def root():return HTMLResponse(UI)
@app.get('/app.js',response_class=PlainTextResponse)
def application_js():return PlainTextResponse(APP_JS,media_type='application/javascript')
APP_JS=r'''let project=null,file=null,job=null;async function api(p,o){let r=await fetch(p,o);if(!r.ok)throw Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}async function refresh(){let ps=await api('api/projects');projects.innerHTML=ps.map(x=>`<div class="item"><b>${x.name}</b> ${x.version} <button onclick="openP('${x.name}')">Öffnen</button></div>`).join('');let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class="item" onclick="showD('${x.device_id}')"><span style="color:${x.online?'#22c55e':'#ef4444'}">●</span> ${x.device_id} ${x.online?'Online':'Offline'} | ${x.ip||''} | RSSI ${x.rssi??'-'} | ${x.last_seen_age}s</div>`).join('')}async function createP(){await api('api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pn.value,board:pb.value})});refresh()}async function openP(p){project=p;let m=await api('api/projects/'+p);title.textContent=p;ver.value=m.version;usb.href='usb/'+p;let fs=await api(`api/projects/${p}/files`);files.innerHTML=fs.map(x=>`<div onclick="openF('${x}')">${x}</div>`).join('')}async function openF(f){file=f;editor.value=await api(`api/projects/${project}/file?path=${encodeURIComponent(f)}`)}async function saveF(){await api(`api/projects/${project}/file?path=${encodeURIComponent(file)}`,{method:'PUT',body:editor.value})}async function saveP(){await api('api/projects/'+project,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:ver.value})})}async function buildP(){let x=await api(`api/projects/${project}/build-start`,{method:'POST'});job=x.job_id;let t=setInterval(async()=>{let s=await api('api/builds/'+job);log.textContent=s.log;if(['success','failed','cancelled'].includes(s.status))clearInterval(t)},800)}async function showD(id){let d=await api('api/devices/'+id);detail.textContent=JSON.stringify(d,null,2);let h=await api(`api/devices/${id}/history`);hist.textContent=h.map(x=>new Date(x.ts*1000).toLocaleString()+' '+x.event+' '+JSON.stringify(x.data)).join('\n')}refresh();setInterval(refresh,5000)'''
HARDWARE=r'''<!doctype html><html><head><meta charset="utf-8"><script type="module" src="https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module"></script><style>body{font-family:system-ui;background:#111827;color:#eee;margin:20px}.card{background:#1f2937;padding:14px;margin:10px;border-radius:12px}pre{background:#030712;padding:10px}progress{width:100%}</style></head><body><h1>USB, OTA & Status: PROJECT</h1><div class="card"><div id="manifest">Prüfe Manifest...</div><esp-web-install-button id="installer"></esp-web-install-button></div><div class="card"><button onclick="connectS()">Seriell verbinden</button><button onclick="disconnectS()">Trennen</button><pre id="serial"></pre></div><div class="card"><select id="dev"></select><select id="build"></select><button onclick="ota()">OTA starten</button><button onclick="forget()">Gerät vergessen</button><progress id="prog" max="100" value="0"></progress><div id="state"></div><pre id="status"></pre></div><button onclick="location.href=base()">Zurück</button><script>let port=null,reader=null,reading=false,last='';const marker='/usb/';function base(){return location.pathname.slice(0,location.pathname.indexOf(marker)+1)}function api(p){return base()+p}async function init(){let u=(location.pathname.endsWith('/')?location.pathname:location.pathname+'/')+'manifest.json';installer.setAttribute('manifest',u);let r=await fetch(u);if(r.ok){let m=await r.json();manifest.textContent=`Bereit: ${m.name} ${m.version} / ${m.builds[0].chipFamily}`}await refresh()}async function refresh(){let ds=await(await fetch(api('api/devices'))).json();dev.innerHTML=ds.map(x=>`<option value="${x.device_id}">${x.online?'Online':'Offline'}: ${x.device_id}</option>`).join('');let bs=await(await fetch(api('api/projects/PROJECT/builds'))).json();build.innerHTML=bs.map(x=>`<option value="${x.id}">${x.version} ${x.id}</option>`).join('');if(dev.value){let d=await(await fetch(api('api/devices/'+dev.value))).json();status.textContent=JSON.stringify(d,null,2);if(d.ota_progress&&d.ota_progress!==last){last=d.ota_progress;let x=JSON.parse(last);prog.value=x.percent||0;state.textContent=x.state+' '+x.message}}}async function ota(){let r=await fetch(api(`api/projects/PROJECT/devices/${dev.value}/ota`),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({build_id:build.value})});state.textContent=await r.text()}async function forget(){await fetch(api('api/devices/'+dev.value),{method:'DELETE'});await refresh()}async function connectS(){port=await navigator.serial.requestPort();await port.open({baudRate:115200});reading=true;while(reading&&port.readable){reader=port.readable.getReader();try{while(reading){let x=await reader.read();if(x.done)break;serial.textContent+=new TextDecoder().decode(x.value)}}finally{reader.releaseLock();reader=null}}}async function disconnectS(){reading=false;if(reader)await reader.cancel();if(port)await port.close();port=null}init();setInterval(refresh,3000)</script></body></html>'''
