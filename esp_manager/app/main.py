from __future__ import annotations
import hashlib, io, json, secrets, shutil, subprocess, threading, time, zipfile
from configparser import ConfigParser
from pathlib import Path
from typing import Any
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse

DEV='dev' in __file__
ROOT=Path('/config/esp_manager_dev' if DEV else '/config/esp_manager')
PROJECTS=ROOT/'projects'; FIRMWARE=ROOT/'firmware'; BACKUPS=ROOT/'backups'; TEMPLATES=Path(__file__).parent/'templates'
for d in (PROJECTS,FIRMWARE,BACKUPS): d.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='ESP Manager'); JOBS={}; PROCESSES={}

def clean(v):
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in str(v).strip()).split('_') if x)
 if not n: raise HTTPException(400,'Ungültiger Name')
 return n[:64]
def pdir(project):
 p=PROJECTS/clean(project)
 if not p.exists(): raise HTTPException(404,'Projekt nicht gefunden')
 return p
def meta(project): return yaml.safe_load((pdir(project)/'espmanager.yaml').read_text())
def save_meta(project,m): (pdir(project)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False))
def public(m):
 r=dict(m); r.pop('ota_token',None); return r
def ensure_defaults(m):
 m.setdefault('display_name',m.get('name','').replace('_',' ').title());m.setdefault('version','0.1.0');m.setdefault('monitor_speed',115200);m.setdefault('libraries',['tzapu/WiFiManager@^2.0.17']);m.setdefault('build_flags',[]);m.setdefault('ota_token',secrets.token_urlsafe(32));return m
def backup(project,reason='manual'):
 p=pdir(project);out=BACKUPS/f'{clean(project)}-{time.strftime("%Y%m%d-%H%M%S")}-{reason}.zip'
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 return out
def copy_agent(p):
 d=p/'lib'/'ESPManager'
 if d.exists(): shutil.rmtree(d)
 shutil.copytree(TEMPLATES/'lib'/'ESPManager',d)
def render_pio(p,m):
 m=ensure_defaults(m);platform='espressif8266' if m['board'] in ('esp12e','nodemcuv2') else 'espressif32'
 text=f"[env:{m['board']}]\nplatform = {platform}\nboard = {m['board']}\nframework = arduino\nmonitor_speed = {int(m['monitor_speed'])}\n"
 if m['libraries']:text+='lib_deps =\n'+'\n'.join('  '+x for x in m['libraries'])+'\n'
 flags=[f'-D ESPMANAGER_DEVICE_ID=\\"{m["name"]}\\"',f'-D ESPMANAGER_FW_VERSION=\\"{m["version"]}\\"',f'-D ESPMANAGER_OTA_TOKEN=\\"{m["ota_token"]}\\"']+m['build_flags']
 text+='build_flags =\n'+'\n'.join('  '+x for x in flags)+'\n';(p/'platformio.ini').write_text(text)
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
def parse_pio(text):
 cp=ConfigParser(strict=False);cp.read_string(text);ss=[s for s in cp.sections() if s.startswith('env:')]
 if not ss:raise HTTPException(400,'Keine [env:...] Sektion')
 s=ss[0]
 def lines(k):return [x.strip() for x in cp.get(s,k,fallback='').splitlines() if x.strip()]
 return {'board':cp.get(s,'board',fallback='esp32dev'),'monitor_speed':cp.getint(s,'monitor_speed',fallback=115200),'libraries':lines('lib_deps'),'build_flags':[x for x in lines('build_flags') if not x.startswith('-D ESPMANAGER_')]}

def ui_html():return r'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ESP Manager</title><style>body{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:15px;margin:12px 0}button,input,select,textarea{font:inherit;padding:8px;margin:4px;border-radius:8px;border:1px solid #475569}button{background:#2563eb;color:white}.danger{background:#991b1b}.muted{color:#9ca3af}textarea{box-sizing:border-box;width:100%;height:280px;background:#030712;color:#e5e7eb;font-family:monospace}pre{background:#030712;padding:12px;white-space:pre-wrap;max-height:420px;overflow:auto}.item{padding:8px;border-bottom:1px solid #374151}details{margin-top:12px}</style></head><body><h1>ESP Manager 0.5.1</h1><div class="grid"><section class="card"><h2>Neues Projekt</h2><input id="pn"><select id="pb"><option value="esp32dev">ESP32 DevKit</option><option value="esp12e">ESP8266 ESP-12E</option><option value="esp32-s3-devkitc-1">ESP32-S3</option><option value="esp32-c3-devkitm-1">ESP32-C3</option></select><button onclick="createP()">Anlegen</button><h3>ESP-Manager-Projekt importieren</h3><input id="imp" type="file" accept=".zip"><button onclick="importP()">Importieren</button></section><section class="card"><h2>Projekte</h2><div id="projects"></div></section><section class="card"><h2>Build-Historie</h2><div id="history">Projekt öffnen</div></section></div><section class="card"><h2>Projekt <span id="title" class="muted"></span></h2><button onclick="duplicateP()">Duplizieren</button><button onclick="backupP()">Backup</button><button onclick="exportP()">Exportieren</button><button class="danger" onclick="deleteP()">Projekt löschen</button><h3>Grundeinstellungen</h3><label>Anzeigename <input id="display"></label><label>Board <input id="board"></label><label>Firmwareversion <input id="version"></label><button onclick="saveSettings()">Speichern</button><details><summary>Erweiterte PlatformIO-Einstellungen</summary><p class="muted">Normalerweise leer lassen. Bibliotheken sind externe Codepakete, z. B. <code>knolleary/PubSubClient@^2.8</code>. Build-Flags sind Compileroptionen, z. B. <code>-D DEBUG=1</code>.</p><label>Monitor-Baudrate <input id="speed" type="number"></label><label>Bibliotheken, eine pro Zeile<textarea id="libraries"></textarea></label><label>Build-Flags, eine pro Zeile<textarea id="flags"></textarea></label><label>Bestehende platformio.ini übernehmen <input id="pio" type="file" accept=".ini"></label><button onclick="importPio()">platformio.ini einlesen</button></details><h3>Programmdateien</h3><input id="newfile" placeholder="src/datei.cpp"><button onclick="newF()">Anlegen</button><div id="files"></div><h4 id="filename"></h4><button onclick="saveF()">Speichern</button><button class="danger" onclick="deleteF()">Datei löschen</button><textarea id="editor"></textarea></section><section class="card"><h2>Build</h2><button onclick="startBuild()">Kompilieren</button><button class="danger" onclick="cancelBuild()">Abbrechen</button><div id="status">Bereit</div><pre id="log"></pre></section><script>let project=null,file=null,job=null,timer=null;async function api(p,o){let r=await fetch(p,o);if(!r.ok)throw Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}async function refresh(){let ps=await api('api/projects');projects.innerHTML=ps.map(x=>`<div class="item"><b>${x.name}</b> ${x.version}<br><button onclick="openP('${x.name}')">Öffnen</button><button onclick="quickBuild('${x.name}')">Build</button></div>`).join('')||'Keine Projekte'}async function createP(){await api('api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:pn.value,board:pb.value})});pn.value='';refresh()}async function openP(p){project=p;file=null;title.textContent='- '+p;let m=await api(`api/projects/${p}`);display.value=m.display_name;board.value=m.board;version.value=m.version;speed.value=m.monitor_speed;libraries.value=(m.libraries||[]).join('\n');flags.value=(m.build_flags||[]).join('\n');refreshFiles();refreshHistory()}async function saveSettings(){await api(`api/projects/${project}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({display_name:display.value,board:board.value,version:version.value,monitor_speed:+speed.value,libraries:libraries.value.split('\n').filter(Boolean),build_flags:flags.value.split('\n').filter(Boolean)})});alert('Gespeichert')}async function importPio(){if(!pio.files[0])return;let fd=new FormData();fd.append('file',pio.files[0]);await api(`api/projects/${project}/platformio-import`,{method:'POST',body:fd});openP(project)}async function refreshFiles(){let fs=await api(`api/projects/${project}/files`);files.innerHTML=fs.map(x=>`<div class="item"><span onclick="openF('${x}')" style="cursor:pointer">${x}</span></div>`).join('')}async function openF(f){file=f;filename.textContent=f;editor.value=await api(`api/projects/${project}/file?path=${encodeURIComponent(f)}`)}async function saveF(){if(!file)return alert('Datei auswählen');await api(`api/projects/${project}/file?path=${encodeURIComponent(file)}`,{method:'PUT',body:editor.value});alert('Gespeichert')}async function deleteF(){if(!file||!confirm(file+' löschen?'))return;await api(`api/projects/${project}/file?path=${encodeURIComponent(file)}`,{method:'DELETE'});file=null;filename.textContent='';editor.value='';refreshFiles()}async function newF(){await api(`api/projects/${project}/files`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:newfile.value})});newfile.value='';refreshFiles()}async function quickBuild(p){project=p;startBuild()}async function startBuild(){let r=await api(`api/projects/${project}/build-start`,{method:'POST'});job=r.job_id;log.textContent='';timer=setInterval(poll,700)}async function poll(){let r=await api(`api/builds/${job}`);status.textContent='Status: '+r.status;log.textContent=r.log||'';log.scrollTop=log.scrollHeight;if(['success','failed','cancelled'].includes(r.status)){clearInterval(timer);refreshHistory()}}async function cancelBuild(){if(job)await api(`api/builds/${job}/cancel`,{method:'POST'})}async function refreshHistory(){let hs=await api(`api/projects/${project}/builds`);history.innerHTML=hs.map(x=>`<div class="item">${x.version} | ${new Date(x.built_at*1000).toLocaleString()} | ${x.size} B<br><a href="api/projects/${project}/builds/${x.id}/firmware">Firmware</a></div>`).join('')||'Noch keine Builds'}async function duplicateP(){let n=prompt('Name der Kopie');if(n){await api(`api/projects/${project}/duplicate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})});refresh()}}async function backupP(){await api(`api/projects/${project}/backup`,{method:'POST'});alert('Backup erstellt')}function exportP(){location.href=`api/projects/${project}/export`}async function deleteP(){if(confirm('Projekt wirklich löschen?')){await api(`api/projects/${project}`,{method:'DELETE'});project=null;refresh()}}async function importP(){let n=prompt('Projektname');if(!n)return;let fd=new FormData();fd.append('name',n);fd.append('archive',imp.files[0]);await api('api/projects/import',{method:'POST',body:fd});refresh()}refresh()</script></body></html>'''
@app.get('/',response_class=HTMLResponse)
def ui():return HTMLResponse(ui_html())

@app.get('/api/projects')
def projects():
 out=[]
 for f in sorted(PROJECTS.glob('*/espmanager.yaml')):
  m=ensure_defaults(yaml.safe_load(f.read_text()));save_meta(m['name'],m);out.append(public(m))
 return out
@app.post('/api/projects')
async def create(payload:dict[str,Any]):
 name=clean(payload.get('name',''));p=PROJECTS/name
 if p.exists():raise HTTPException(409,'Projekt existiert')
 for d in ('src','include','lib','builds'):(p/d).mkdir(parents=True,exist_ok=True)
 m=ensure_defaults({'name':name,'board':payload.get('board','esp32dev')});(p/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));shutil.copytree(TEMPLATES/'src',p/'src',dirs_exist_ok=True);copy_agent(p);render_pio(p,m);return public(m)
@app.get('/api/projects/{project}')
def get_project(project):m=ensure_defaults(meta(project));save_meta(project,m);return public(m)
@app.put('/api/projects/{project}')
async def put_project(project,payload:dict[str,Any]):
 backup(project,'before-settings');m=ensure_defaults(meta(project))
 for k in ('display_name','board','version','monitor_speed','libraries','build_flags'):
  if k in payload:m[k]=payload[k]
 save_meta(project,m);render_pio(pdir(project),m);return public(m)
@app.delete('/api/projects/{project}')
def delete_project(project):backup(project,'before-delete');shutil.rmtree(pdir(project));shutil.rmtree(FIRMWARE/clean(project),ignore_errors=True);return {'ok':True}
@app.post('/api/projects/{project}/duplicate')
async def duplicate(project,payload:dict[str,Any]):
 src=pdir(project);name=clean(payload.get('name',''));dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Ziel existiert')
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('.pio'));m=ensure_defaults(yaml.safe_load((dst/'espmanager.yaml').read_text()));m['name']=name;m['display_name']=name.replace('_',' ').title();m['ota_token']=secrets.token_urlsafe(32);(dst/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));render_pio(dst,m);return public(m)
@app.post('/api/projects/{project}/backup')
def make_backup(project):return {'file':backup(project).name}
@app.get('/api/projects/{project}/export')
def export_project(project):
 out=BACKUPS/f'{clean(project)}-export.zip';p=pdir(project)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 return FileResponse(out,filename=out.name)
@app.post('/api/projects/import')
async def import_project(name:str=Form(...),archive:UploadFile=File(...)):
 name=clean(name);dst=PROJECTS/name
 if dst.exists():raise HTTPException(409,'Projekt existiert')
 try:z=zipfile.ZipFile(io.BytesIO(await archive.read()))
 except Exception:raise HTTPException(400,'Ungültiges ZIP')
 dst.mkdir(parents=True)
 for it in z.infolist():
  if not it.is_dir() and '..' not in Path(it.filename).parts:
   out=dst/it.filename;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(it))
 if not (dst/'espmanager.yaml').exists():shutil.rmtree(dst);raise HTTPException(400,'Kein ESP-Manager-Projekt')
 m=ensure_defaults(yaml.safe_load((dst/'espmanager.yaml').read_text()));m['name']=name;m['ota_token']=secrets.token_urlsafe(32);(dst/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False));copy_agent(dst);render_pio(dst,m);return public(m)
@app.post('/api/projects/{project}/platformio-import')
async def import_pio(project,file:UploadFile=File(...)):
 backup(project,'before-pio-import');m=ensure_defaults(meta(project));m.update(parse_pio((await file.read()).decode(errors='replace')));save_meta(project,m);render_pio(pdir(project),m);return public(m)
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

def worker(jid):
 j=JOBS[jid];p=pdir(j['project']);m=ensure_defaults(meta(j['project']));render_pio(p,m);copy_agent(p);j['status']='running'
 try:
  proc=subprocess.Popen(['/opt/esp_manager/venv/bin/pio','run'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1);PROCESSES[jid]=proc
  for line in proc.stdout or []:j['log']=(j['log']+line)[-80000:]
  code=proc.wait();PROCESSES.pop(jid,None)
  if j.get('cancel_requested'):j['status']='cancelled';return
  if code:j['status']='failed';return
  src=p/'.pio'/'build'/m['board']/'firmware.bin';data=src.read_bytes();bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/j['project']/bid;out.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out/'firmware.bin');rec={'id':bid,'version':m['version'],'built_at':int(time.time()),'size':len(data),'sha256':hashlib.sha256(data).hexdigest()};(out/'manifest.json').write_text(json.dumps(rec,indent=2));j['status']='success'
 except Exception as e:j['status']='failed';j['log']+='\n'+repr(e)
@app.post('/api/projects/{project}/build-start')
def start_build(project):
 pdir(project);jid=f'{clean(project)}-{time.time_ns()}';JOBS[jid]={'project':clean(project),'status':'queued','log':''};threading.Thread(target=worker,args=(jid,),daemon=True).start();return {'job_id':jid}
@app.get('/api/builds/{jid}')
def get_build(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 return JOBS[jid]
@app.post('/api/builds/{jid}/cancel')
def cancel_build(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 JOBS[jid]['cancel_requested']=True;proc=PROCESSES.get(jid)
 if proc and proc.poll() is None:proc.terminate()
 JOBS[jid]['status']='cancelled';return {'ok':True}
@app.get('/api/projects/{project}/builds')
def build_history(project):
 root=FIRMWARE/clean(project);out=[]
 if root.exists():
  for f in root.glob('*/manifest.json'):
   try:out.append(json.loads(f.read_text()))
   except Exception:pass
 return sorted(out,key=lambda x:x.get('built_at',0),reverse=True)
@app.get('/api/projects/{project}/builds/{bid}/firmware')
def get_firmware(project,bid):
 f=FIRMWARE/clean(project)/clean(bid)/'firmware.bin'
 if not f.exists():raise HTTPException(404,'Firmware fehlt')
 return FileResponse(f,filename=f'{clean(project)}-{bid}.bin')
