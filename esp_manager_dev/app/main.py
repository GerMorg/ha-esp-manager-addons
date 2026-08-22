from __future__ import annotations
import hashlib,json,re,secrets,shutil,subprocess,threading,time,zipfile
from pathlib import Path
from typing import Any
import yaml
from fastapi import FastAPI,HTTPException,Request,UploadFile,File
from fastapi.responses import HTMLResponse,FileResponse

CHANNEL='Dev'; ROOT=Path('/config/esp_manager_dev'); PROJECTS=ROOT/'projects'; FIRMWARE=ROOT/'firmware'; BACKUPS=ROOT/'backups'; TEMPLATES=Path(__file__).parent/'templates'
for p in (PROJECTS,FIRMWARE,BACKUPS):p.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='ESP Manager');JOBS={};PROCESSES={}
def clean(v):
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in str(v).strip()).split('_') if x)
 if not n:raise HTTPException(400,'Ungültiger Name')
 return n[:64]
def pdir(name):
 p=PROJECTS/clean(name)
 if not p.exists():raise HTTPException(404,'Projekt nicht gefunden')
 return p
def load_meta(name):return yaml.safe_load((pdir(name)/'espmanager.yaml').read_text()) or {}
def save_meta(name,m):(pdir(name)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False,allow_unicode=True))
def entities_path(p):return p/'entities.yaml'
def validate_entities(items):
 allowed={'sensor','binary_sensor','switch','number','cover'};seen=set();out=[]
 for raw in items:
  x=dict(raw);t=x.get('type');i=clean(x.get('id',''));u=x.get('unique_id') or f"{clean(x.get('project','device'))}_{i}"
  if t not in allowed:raise HTTPException(400,f'Ungültiger Typ: {t}')
  if u in seen:raise HTTPException(400,f'Doppelte unique_id: {u}')
  seen.add(u);x['id']=i;x['unique_id']=u;x['name']=x.get('name') or i.replace('_',' ').title()
  if t=='number':x.setdefault('min',0);x.setdefault('max',100);x.setdefault('step',1)
  out.append(x)
 return out
def load_entities(p):
 if not entities_path(p).exists():return []
 return validate_entities(yaml.safe_load(entities_path(p).read_text()) or [])
def save_entities(p,items):entities_path(p).write_text(yaml.safe_dump(validate_entities(items),sort_keys=False,allow_unicode=True))
def generate_entities(p):
 items=load_entities(p);lines=['#pragma once','#include <ESPManager.h>','inline void registerManagedEntities(){']
 q=lambda v:json.dumps(str(v),ensure_ascii=False)
 for x in items:
  a=f'{q(x["id"])},{q(x["name"])},{q(x["unique_id"])}';t=x['type']
  if t=='sensor':lines.append(f' ESPManager.registerSensor({a},{q(x.get("unit",""))},{q(x.get("device_class",""))},{q(x.get("state_class","measurement"))},{q(x.get("value_template",""))});')
  elif t=='binary_sensor':lines.append(f' ESPManager.registerBinarySensor({a},{q(x.get("device_class",""))});')
  elif t=='switch':lines.append(f' ESPManager.registerSwitch({a});')
  elif t=='number':lines.append(f' ESPManager.registerNumber({a},{float(x["min"])},{float(x["max"])},{float(x["step"])},{q(x.get("unit",""))});')
  elif t=='cover':lines.append(f' ESPManager.registerCover({a},{str(bool(x.get("position",True))).lower()});')
 lines+=['}',''];(p/'include').mkdir(exist_ok=True);(p/'include/ESPManagerEntities.h').write_text('\n'.join(lines))
def prepare(p,m):
 generate_entities(p);shutil.copytree(TEMPLATES/'lib/ESPManager',p/'lib/ESPManager',dirs_exist_ok=True);shutil.copy2(TEMPLATES/'src/main.cpp',p/'src/main.cpp')
 libs=['tzapu/WiFiManager@^2.0.17','knolleary/PubSubClient@^2.8','bblanchon/ArduinoJson@^7.0.0']+m.get('libraries',[])
 platform='espressif8266' if m['board'] in ('esp12e','nodemcuv2') else 'espressif32'
 flags=[f'-D ESPMANAGER_DEVICE_ID=\\"{m["name"]}\\"',f'-D ESPMANAGER_FW_VERSION=\\"{m["version"]}\\"',f'-D ESPMANAGER_MQTT_HOST=\\"{m.get("mqtt_host","homeassistant.local")}\\"',f'-D ESPMANAGER_MQTT_PORT={int(m.get("mqtt_port",1883))}',f'-D ESPMANAGER_MQTT_USER=\\"{m.get("mqtt_user","")}\\"',f'-D ESPMANAGER_MQTT_PASS=\\"{m.get("mqtt_password","")}\\"',f'-D ESPMANAGER_OTA_TOKEN=\\"{m["ota_token"]}\\"']+m.get('build_flags',[])
 text=f'[env:{m["board"]}]\nplatform = {platform}\nboard = {m["board"]}\nframework = arduino\nmonitor_speed = {m.get("monitor_speed",115200)}\nlib_deps =\n'+'\n'.join('  '+x for x in dict.fromkeys(libs))+'\nbuild_flags =\n'+'\n'.join('  '+x for x in flags)+'\n'
 (p/'platformio.ini').write_text(text)
def build_worker(name,jid):
 p=pdir(name);m=load_meta(name);prepare(p,m);cmd=['pio','run','-d',str(p)];proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);PROCESSES[jid]=proc;log=[]
 for line in proc.stdout:log.append(line);JOBS[jid]['log']=''.join(log)[-60000:]
 rc=proc.wait();JOBS[jid]['done']=True;JOBS[jid]['ok']=rc==0
 if rc==0:
  src=p/'.pio/build'/m['board']/'firmware.bin';dst=FIRMWARE/clean(name)/m['version'];dst.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst/'firmware.bin');sha=hashlib.sha256(src.read_bytes()).hexdigest();(dst/'manifest.json').write_text(json.dumps({'name':m['display_name'],'version':m['version'],'sha256':sha},indent=2))

@app.get('/',response_class=HTMLResponse)
def index():return HTML
@app.get('/api/projects')
def projects():return [yaml.safe_load((p/'espmanager.yaml').read_text()) for p in PROJECTS.iterdir() if (p/'espmanager.yaml').exists()]
@app.post('/api/projects')
async def create(req:Request):
 d=await req.json();name=clean(d['name']);p=PROJECTS/name
 if p.exists():raise HTTPException(409,'Projekt existiert')
 (p/'src').mkdir(parents=True);(p/'include').mkdir();(p/'lib').mkdir();m={'name':name,'display_name':d.get('display_name',name),'board':d.get('board','esp32dev'),'version':'0.1.0','monitor_speed':115200,'libraries':[],'build_flags':[],'mqtt_host':'homeassistant.local','mqtt_port':1883,'mqtt_user':'','mqtt_password':'','ota_token':secrets.token_urlsafe(24)};save_meta(name,m);(p/'src/device.cpp').write_text('#include <Arduino.h>\n#include <ESPManager.h>\nvoid setupDevice(){}\nvoid loopDevice(){}\n');save_entities(p,[]);return m
@app.get('/api/projects/{name}')
def get_project(name):return load_meta(name)
@app.put('/api/projects/{name}')
async def put_project(name,req:Request):m=load_meta(name);m.update(await req.json());save_meta(name,m);return m
@app.get('/api/projects/{name}/entities')
def get_entities(name):return load_entities(pdir(name))
@app.put('/api/projects/{name}/entities')
async def put_entities(name,req:Request):items=await req.json();save_entities(pdir(name),items);generate_entities(pdir(name));return load_entities(pdir(name))
@app.get('/api/projects/{name}/file')
def get_file(name,path:str='src/device.cpp'):
 p=(pdir(name)/path).resolve();base=pdir(name).resolve()
 if base not in p.parents or not p.exists():raise HTTPException(404,'Datei fehlt')
 return {'path':path,'content':p.read_text()}
@app.put('/api/projects/{name}/file')
async def put_file(name,req:Request):
 d=await req.json();p=(pdir(name)/d['path']).resolve();base=pdir(name).resolve()
 if base not in p.parents:raise HTTPException(400,'Pfad ungültig')
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(d['content']);return {'ok':True}
@app.post('/api/projects/{name}/build')
def build(name):jid=secrets.token_hex(6);JOBS[jid]={'done':False,'ok':False,'log':''};threading.Thread(target=build_worker,args=(name,jid),daemon=True).start();return {'job':jid}
@app.get('/api/jobs/{jid}')
def job(jid):return JOBS.get(jid) or {'done':True,'ok':False,'log':'Job fehlt'}
@app.post('/api/jobs/{jid}/cancel')
def cancel(jid):
 p=PROCESSES.get(jid)
 if p:p.terminate()
 return {'ok':True}

HTML='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ESP Manager</title><style>body{font-family:system-ui;margin:0;background:#f4f6f8;color:#17212b}header{background:#0866c6;color:white;padding:16px 24px}main{max-width:1200px;margin:auto;padding:20px}.grid{display:grid;grid-template-columns:280px 1fr;gap:16px}.card{background:white;border-radius:14px;padding:16px;box-shadow:0 2px 10px #0001}button{background:#0866c6;color:white;border:0;border-radius:8px;padding:9px 13px;margin:3px}input,select,textarea{width:100%;box-sizing:border-box;padding:9px;margin:4px 0 10px;border:1px solid #ccd3da;border-radius:8px}textarea{min-height:360px;font-family:monospace}.entity{display:grid;grid-template-columns:110px 1fr 1fr 1fr auto;gap:7px;align-items:center;border-bottom:1px solid #eee;padding:8px 0}.tabs button{background:#506070}.hidden{display:none}pre{white-space:pre-wrap;background:#111;color:#ddd;padding:12px;max-height:350px;overflow:auto}@media(max-width:800px){.grid{grid-template-columns:1fr}.entity{grid-template-columns:1fr}}</style></head><body><header><h2>ESP Manager – Dev</h2></header><main><div class="grid"><aside class="card"><h3>Projekte</h3><div id="projects"></div><hr><input id="newName" placeholder="Projektname"><select id="newBoard"><option>esp32dev</option><option>nodemcuv2</option></select><button onclick="createProject()">Anlegen</button></aside><section class="card"><h2 id="title">Projekt wählen</h2><div id="work" class="hidden"><div class="tabs"><button onclick="tab('settings')">Einstellungen</button><button onclick="tab('code')">Code</button><button onclick="tab('entities')">HA-Entitäten</button><button onclick="tab('build')">Build</button></div><div id="settings"><label>Anzeigename</label><input id="display"><label>Version</label><input id="version"><label>Board</label><input id="board"><label>MQTT Host</label><input id="mqtt"><label>Bibliotheken, eine pro Zeile</label><textarea id="libs" style="min-height:100px"></textarea><button onclick="saveSettings()">Speichern</button></div><div id="code" class="hidden"><textarea id="editor"></textarea><button onclick="saveCode()">Code speichern</button></div><div id="entities" class="hidden"><p>Die unique_id nach der ersten Veröffentlichung nicht mehr ändern.</p><div id="elist"></div><button onclick="addEntity()">Entität hinzufügen</button><button onclick="saveEntities()">Entitäten speichern</button></div><div id="build" class="hidden"><button onclick="startBuild()">Kompilieren</button><pre id="log"></pre></div></div></section></div></main><script>let current=null,ents=[];const $=x=>document.getElementById(x);async function api(u,o){let r=await fetch(u,o);if(!r.ok)throw Error(await r.text());return r.json()}async function loadProjects(){let p=await api('api/projects');$('projects').innerHTML=p.map(x=>`<button onclick="openProject('${x.name}')">${x.display_name}</button>`).join('')}async function createProject(){await api('api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:$('newName').value,board:$('newBoard').value})});loadProjects()}async function openProject(n){current=n;let m=await api(`api/projects/${n}`);$('title').textContent=m.display_name;$('work').classList.remove('hidden');$('display').value=m.display_name;$('version').value=m.version;$('board').value=m.board;$('mqtt').value=m.mqtt_host;$('libs').value=(m.libraries||[]).join('\n');let f=await api(`api/projects/${n}/file?path=src/device.cpp`);$('editor').value=f.content;ents=await api(`api/projects/${n}/entities`);renderEntities()}function tab(n){for(let x of ['settings','code','entities','build'])$(x).classList.toggle('hidden',x!==n)}async function saveSettings(){await api(`api/projects/${current}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({display_name:$('display').value,version:$('version').value,board:$('board').value,mqtt_host:$('mqtt').value,libraries:$('libs').value.split('\n').map(x=>x.trim()).filter(Boolean)})});loadProjects()}async function saveCode(){await api(`api/projects/${current}/file`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:'src/device.cpp',content:$('editor').value})})}function addEntity(){ents.push({type:'sensor',id:'new_entity',name:'Neue Entität',unique_id:`${current}_new_entity`,unit:'',device_class:'',state_class:'measurement'});renderEntities()}function renderEntities(){$('elist').innerHTML=ents.map((e,i)=>`<div class="entity"><select onchange="ents[${i}].type=this.value">${['sensor','binary_sensor','switch','number','cover'].map(t=>`<option ${e.type===t?'selected':''}>${t}</option>`).join('')}</select><input value="${e.id}" onchange="ents[${i}].id=this.value" placeholder="ID"><input value="${e.name}" onchange="ents[${i}].name=this.value" placeholder="Name"><input value="${e.unique_id}" onchange="ents[${i}].unique_id=this.value" placeholder="unique_id"><button onclick="ents.splice(${i},1);renderEntities()">Löschen</button><input value="${e.unit||''}" onchange="ents[${i}].unit=this.value" placeholder="Einheit"><input value="${e.device_class||''}" onchange="ents[${i}].device_class=this.value" placeholder="Geräteklasse"><input value="${e.state_class||''}" onchange="ents[${i}].state_class=this.value" placeholder="Zustandsklasse"><input value="${e.min??''}" onchange="ents[${i}].min=Number(this.value)" placeholder="Minimum"><input value="${e.max??''}" onchange="ents[${i}].max=Number(this.value)" placeholder="Maximum"></div>`).join('')}async function saveEntities(){ents=await api(`api/projects/${current}/entities`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(ents)});renderEntities()}async function startBuild(){let j=await api(`api/projects/${current}/build`,{method:'POST'});let t=setInterval(async()=>{let x=await api(`api/jobs/${j.job}`);$('log').textContent=x.log;if(x.done)clearInterval(t)},700)}loadProjects();</script></body></html>'''.replace('Dev',CHANNEL)
