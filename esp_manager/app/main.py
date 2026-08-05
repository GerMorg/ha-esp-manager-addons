from __future__ import annotations
import hashlib, io, json, secrets, shutil, subprocess, threading, time, zipfile
from configparser import ConfigParser
from pathlib import Path
from typing import Any
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

ROOT=Path('/config/esp_manager'); PROJECTS=ROOT/'projects'; FIRMWARE=ROOT/'firmware'; BACKUPS=ROOT/'backups'; OPTIONS=Path('/data/options.json'); TEMPLATES=Path(__file__).parent/'templates'
for d in (PROJECTS,FIRMWARE,BACKUPS):d.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='ESP Manager'); JOBS:dict[str,dict[str,Any]]={}; PROCESSES:dict[str,subprocess.Popen]={}

def clean(v:str)->str:
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in v.strip()).split('_') if x)
 if not n:raise HTTPException(400,'Ungültiger Name')
 return n[:64]
def pdir(project:str)->Path:
 p=PROJECTS/clean(project)
 if not p.exists():raise HTTPException(404,'Projekt nicht gefunden')
 return p
def meta(project):return yaml.safe_load((pdir(project)/'espmanager.yaml').read_text())
def save_meta(project,m):(pdir(project)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False))
def public(m):
 r=dict(m);r.pop('ota_token',None);return r
def backup(project,reason='manual'):
 p=pdir(project);stamp=time.strftime('%Y%m%d-%H%M%S');out=BACKUPS/f'{clean(project)}-{stamp}-{reason}.zip'
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 return out
def copy_agent(p):
 d=p/'lib'/'ESPManager'
 if d.exists():shutil.rmtree(d)
 shutil.copytree(TEMPLATES/'lib'/'ESPManager',d)
def render_pio(p,m):
 platform='espressif8266' if m['board'] in ('esp12e','nodemcuv2') else 'espressif32'; libs=m.get('libraries',[]); flags=m.get('build_flags',[])
 text=f"[env:{m['board']}]\nplatform = {platform}\nboard = {m['board']}\nframework = arduino\nmonitor_speed = {int(m.get('monitor_speed',115200))}\n"
 if libs:text+='lib_deps =\n'+'\n'.join('  '+x for x in libs)+'\n'
 defaults=[f'-D ESPMANAGER_DEVICE_ID=\\"{m["name"]}\\"',f'-D ESPMANAGER_FW_VERSION=\\"{m.get("version","0.1.0")}\\"',f'-D ESPMANAGER_OTA_TOKEN=\\"{m["ota_token"]}\\"']
 allflags=defaults+flags
 if allflags:text+='build_flags =\n'+'\n'.join('  '+x for x in allflags)+'\n'
 (p/'platformio.ini').write_text(text)
def safe_file(project,rel,exists=True):
 rel=rel.replace('\\','/').lstrip('/')
 if '..' in Path(rel).parts or not rel.startswith(('src/','include/','lib/')) or rel=='src/main.cpp' or rel.startswith('lib/ESPManager/'):raise HTTPException(403,'Dateipfad nicht erlaubt')
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
def parse_pio(text):
 cp=ConfigParser(strict=False);cp.read_string(text);sections=[s for s in cp.sections() if s.startswith('env:')]
 if not sections:raise HTTPException(400,'Keine [env:...] Sektion gefunden')
 s=sections[0];get=lambda k,d='':cp.get(s,k,fallback=d)
 split=lambda v:[x.strip() for x in v.replace('\n',',').split(',') if x.strip()]
 return {'board':get('board','esp32dev'),'monitor_speed':int(get('monitor_speed','115200')),'libraries':split(get('lib_deps')),'build_flags':split(get('build_flags'))}

def project_zip(project):
 p=pdir(project);buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 buf.seek(0);return buf

@app.get('/',response_class=HTMLResponse)
def ui():return HTMLResponse(r'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP Manager</title><style>body{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:15px;margin:12px 0}button,input,select,textarea{font:inherit;padding:8px;margin:4px;border-radius:8px;border:1px solid #475569}button{background:#2563eb;color:white}.danger{background:#991b1b}.secondary{background:#475569}textarea{box-sizing:border-box;width:100%;height:300px;background:#030712;color:#e5e7eb;font-family:monospace}pre{background:#030712;padding:12px;white-space:pre-wrap;max-height:420px;overflow:auto}.row{display:flex;gap:8px;flex-wrap:wrap}.item{padding:8px;border-bottom:1px solid #374151}.ok{color:#86efac}.bad{color:#fca5a5}.muted{color:#9ca3af}</style></head><body><h1>ESP Manager 0.5.0</h1><div class="grid"><section class="card"><h2>Neues Projekt</h2><input id="pname" placeholder="Projektname"><select id="pboard"><option value="esp32dev">ESP32 DevKit</option><option value="esp12e">ESP8266 ESP-12E</option><option value="esp32-s3-devkitc-1">ESP32-S3</option><option value="esp32-c3-devkitm-1">ESP32-C3</option></select><button onclick="createP()">Anlegen</button><h3>Projekt-ZIP importieren</h3><input id="importfile" type="file" accept=".zip"><button onclick="importP()">Importieren</button></section><section class="card"><h2>Projekte</h2><div id="projects"></div></section><section class="card"><h2>Build-Historie</h2><div id="history">Projekt öffnen</div></section></div><section class="card"><h2>Projekt <span id="title" class="muted"></span></h2><div class="row"><button onclick="duplicateP()">Duplizieren</button><button onclick="backupP()">Backup erstellen</button><button onclick="exportP()">Projekt exportieren</button><button class="danger" onclick="deleteP()">Projekt löschen</button></div><h3>Einstellungen</h3><div class="row"><label>Anzeigename <input id="display"></label><label>Board <input id="board"></label><label>Firmwareversion <input id="version"></label><label>Monitor Baud <input id="speed" type="number"></label></div><label>Bibliotheken, eine pro Zeile<textarea id="libraries"></textarea></label><label>Zusätzliche Build-Flags, eine pro Zeile<textarea id="flags"></textarea></label><button onclick="saveSettings()">Einstellungen speichern</button><label>platformio.ini importieren <input id="piofile" type="file" accept=".ini"></label><button onclick="importPio()">Übernehmen</button><h3>Programmdateien</h3><div class="row"><input id="newfile" placeholder="src/datei.cpp"><button onclick="newF()">Datei anlegen</button></div><div id="files"></div><h4 id="filename"></h4><button onclick="saveF()">Datei speichern</button><textarea id="editor"></textarea></section><section class="card"><h2>Build</h2><button onclick="startBuild()">Kompilieren</button><button class="danger" onclick="cancelBuild()">Build abbrechen</button><div id="status">Bereit</div><pre id="log"></pre></section><script>
let project=null,file=null,job=null,timer=null;async function api(p,o){let r=await fetch(p,o);if(!r.ok)throw Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}async function refresh(){let ps=await api('api/projects');projects.innerHTML=ps.map(x=>`<div class="item"><b>${x.name}</b> ${x.version}<br><button onclick="openP('${x.name}')">Öffnen</button><button onclick="quickBuild('${x.name}')">Build</button></div>`).join('')||'Keine Projekte'}async function createP(){await api('api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pname.value,board:pboard.value})});pname.value='';refresh()}async function openP(p){project=p;title.textContent='- '+p;let m=await api(`api/projects/${p}`);display.value=m.display_name||'';board.value=m.board;version.value=m.version;speed.value=m.monitor_speed||115200;libraries.value=(m.libraries||[]).join('\n');flags.value=(m.build_flags||[]).join('\n');await refreshFiles();await refreshHistory()}async function saveSettings(){await api(`api/projects/${project}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({display_name:display.value,board:board.value,version:version.value,monitor_speed:+speed.value,libraries:libraries.value.split('\n').filter(Boolean),build_flags:flags.value.split('\n').filter(Boolean)})});alert('Gespeichert')}async function importPio(){let fd=new FormData();fd.append('file',piofile.files[0]);let m=await api(`api/projects/${project}/platformio-import`,{method:'POST',body:fd});await openP(project);alert('platformio.ini übernommen')}async function refreshFiles(){let fs=await api(`api/projects/${project}/files`);files.innerHTML=fs.map(x=>`<div class="item" onclick="openF('${x}')">${x}</div>`).join('')}async function openF(f){file=f;filename.textContent=f;editor.value=await api(`api/projects/${project}/file?path=${encodeURIComponent(f)}`)}async function saveF(){await api(`api/projects/${project}/file?path=${encodeURIComponent(file)}`,{method:'PUT',body:editor.value});alert('Gespeichert')}async function newF(){await api(`api/projects/${project}/files`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:newfile.value})});newfile.value='';refreshFiles()}async function quickBuild(p){project=p;startBuild()}async function startBuild(){let r=await api(`api/projects/${project}/build-start`,{method:'POST'});job=r.job_id;log.textContent='';if(timer)clearInterval(timer);timer=setInterval(poll,700)}async function poll(){let r=await api(`api/builds/${job}`);status.innerHTML='Status: '+r.status;log.textContent=r.log||'';log.scrollTop=log.scrollHeight;if(['success','failed','cancelled'].includes(r.status)){clearInterval(timer);timer=null;refreshHistory()}}async function cancelBuild(){if(job)await api(`api/builds/${job}/cancel`,{method:'POST'})}async function refreshHistory(){let hs=await api(`api/projects/${project}/builds`);history.innerHTML=hs.map(x=>`<div class="item">${x.version} | ${new Date(x.built_at*1000).toLocaleString()} | ${x.size} B<br><a href="api/projects/${project}/builds/${x.id}/firmware">Firmware</a></div>`).join('')||'Noch keine Builds'}async function duplicateP(){let n=prompt('Name der Kopie');if(n){await api(`api/projects/${project}/duplicate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})});refresh()}}async function backupP(){await api(`api/projects/${project}/backup`,{method:'POST'});alert('Backup erstellt')}function exportP(){location.href=`api/projects/${project}/export`}async function deleteP(){if(confirm('Projekt wirklich löschen?')){await api(`api/projects/${project}`,{method:'DELETE'});project=null;refresh()}}async function importP(){let n=prompt('Projektname');if(!n)return;let fd=new FormData();fd.append('name',n);fd.append('archive',importfile.files[0]);await api('api/projects/import',{method:'POST',body:fd});refresh()}refresh()</script></body></html>''')

@app.get('/api/projects')
def projects():return [public(yaml.safe_load(f.read_text())) for f in sorted(PROJECTS.glob('*/espmanager.yaml'))]
@app.post('/api/projects')
async def create(payload:dict[str,Any]):
 name=clean(payload.get('name',''));p=PROJECTS/name
 if p.exists():raise HTTPException(409,'Projekt existiert')
 for d in ('src','include','lib','builds'):(p/d).mkdir(parents=True,exist_ok=True)
 m={'name':name,'display_name':name.replace('_',' ').title(),'board':payload.get('board','esp32dev'),'version':'0.1.0','monitor_speed':115200,'libraries':['tzapu/WiFiManager@^2.0.17'],'build_flags':[],'ota_token':secrets.token_urlsafe(32)}
 (p/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));shutil.copytree(TEMPLATES/'src',p/'src',dirs_exist_ok=True);copy_agent(p);render_pio(p,m);return public(m)
@app.get('/api/projects/{project}')
def project_get(project):return public(meta(project))
@app.put('/api/projects/{project}')
async def project_put(project,payload:dict[str,Any]):
 backup(project,'before-settings');m=meta(project)
 for k in ('display_name','board','version','monitor_speed','libraries','build_flags'):
  if k in payload:m[k]=payload[k]
 save_meta(project,m);render_pio(pdir(project),m);return public(m)
@app.delete('/api/projects/{project}')
def project_delete(project):backup(project,'before-delete');shutil.rmtree(pdir(project));shutil.rmtree(FIRMWARE/clean(project),ignore_errors=True);return {'ok':True}
@app.post('/api/projects/{project}/duplicate')
async def duplicate(project,payload:dict[str,Any]):
 src=pdir(project);name=clean(payload.get('name',''));dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Ziel existiert')
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.pio'));m=yaml.safe_load((dst/'espmanager.yaml').read_text());m['name']=name;m['display_name']=name.replace('_',' ').title();m['ota_token']=secrets.token_urlsafe(32);(dst/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));render_pio(dst,m);return public(m)
@app.post('/api/projects/{project}/backup')
def project_backup(project):return {'file':backup(project).name}
@app.get('/api/projects/{project}/export')
def project_export(project):
 buf=project_zip(project);tmp=BACKUPS/f'{clean(project)}-export.zip';tmp.write_bytes(buf.read());return FileResponse(tmp,filename=tmp.name)
@app.post('/api/projects/import')
async def project_import(name:str=Form(...),archive:UploadFile=File(...)):
 name=clean(name);dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Projekt existiert')
 raw=await archive.read()
 try:z=zipfile.ZipFile(io.BytesIO(raw))
 except Exception:raise HTTPException(400,'Ungültiges ZIP')
 dst.mkdir(parents=True)
 for it in z.infolist():
  if it.is_dir() or '..' in Path(it.filename).parts:continue
  out=dst/it.filename;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(it))
 if not (dst/'espmanager.yaml').exists():shutil.rmtree(dst);raise HTTPException(400,'Kein ESP-Manager-Projekt')
 m=yaml.safe_load((dst/'espmanager.yaml').read_text());m['name']=name;m['ota_token']=secrets.token_urlsafe(32);(dst/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));copy_agent(dst);render_pio(dst,m);return public(m)
@app.post('/api/projects/{project}/platformio-import')
async def pio_import(project,file:UploadFile=File(...)):
 backup(project,'before-pio-import');parsed=parse_pio((await file.read()).decode(errors='replace'));m=meta(project);m.update(parsed);save_meta(project,m);render_pio(pdir(project),m);return public(m)
@app.get('/api/projects/{project}/files')
def files(project):return list_files(project)
@app.post('/api/projects/{project}/files')
async def file_create(project,payload:dict[str,Any]):
 f=safe_file(project,payload.get('path',''),False);f.parent.mkdir(parents=True,exist_ok=True)
 if f.exists():raise HTTPException(409,'Datei existiert')
 f.write_text('// Neue Datei\n');return {'ok':True}
@app.get('/api/projects/{project}/file',response_class=PlainTextResponse)
def file_get(project,path):return safe_file(project,path).read_text(errors='replace')
@app.put('/api/projects/{project}/file')
async def file_put(project,path,request:Request):safe_file(project,path).write_bytes(await request.body());return {'ok':True}

def build_worker(jid):
 j=JOBS[jid];project=j['project'];p=pdir(project);m=meta(project);render_pio(p,m);copy_agent(p);j['status']='running'
 try:
  proc=subprocess.Popen(['/opt/esp_manager/venv/bin/pio','run'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True);PROCESSES[jid]=proc
  for line in proc.stdout or []:j['log']=(j['log']+line)[-80000:]
  code=proc.wait();PROCESSES.pop(jid,None)
  if j.get('cancel_requested'):j['status']='cancelled';return
  if code:j['status']='failed';return
  src=p/'.pio'/'build'/m['board']/'firmware.bin';data=src.read_bytes();bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/project/bid;out.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out/'firmware.bin')
  rec={'id':bid,'version':m.get('version','0.1.0'),'built_at':int(time.time()),'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'status':'success'};(out/'manifest.json').write_text(json.dumps(rec,indent=2));j['status']='success';j['build']=rec
 except Exception as e:PROCESSES.pop(jid,None);j['status']='failed';j['log']+='\n'+repr(e)
@app.post('/api/projects/{project}/build-start')
def build_start(project):
 pdir(project)
 if any(x['project']==clean(project) and x['status'] in ('queued','running') for x in JOBS.values()):raise HTTPException(409,'Für dieses Projekt läuft bereits ein Build')
 jid=f'{clean(project)}-{time.time_ns()}';JOBS[jid]={'job_id':jid,'project':clean(project),'status':'queued','log':''};threading.Thread(target=build_worker,args=(jid,),daemon=True).start();return {'job_id':jid}
@app.get('/api/builds/{jid}')
def build_get(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 return JOBS[jid]
@app.post('/api/builds/{jid}/cancel')
def build_cancel(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 JOBS[jid]['cancel_requested']=True;proc=PROCESSES.get(jid)
 if proc and proc.poll() is None:proc.terminate()
 JOBS[jid]['status']='cancelled';return {'ok':True}
@app.get('/api/projects/{project}/builds')
def builds(project):
 root=FIRMWARE/clean(project);out=[]
 if root.exists():
  for f in root.glob('*/manifest.json'):
   try:out.append(json.loads(f.read_text()))
   except Exception:pass
 return sorted(out,key=lambda x:x.get('built_at',0),reverse=True)
@app.get('/api/projects/{project}/builds/{bid}/firmware')
def build_firmware(project,bid):
 f=FIRMWARE/clean(project)/clean(bid)/'firmware.bin'
 if not f.is_file():raise HTTPException(404,'Firmware fehlt')
 return FileResponse(f,filename=f'{clean(project)}-{bid}.bin')
