from fastapi import FastAPI,HTTPException,Request,UploadFile,File,Form
from fastapi.responses import FileResponse,HTMLResponse,PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Any
import io,json,time,threading,subprocess,shutil,zipfile,hashlib,secrets,re
import paho.mqtt.client as mqtt
from .core import *
app=FastAPI(title='ESP Manager Dev 0.13.1-dev');STATIC=Path(__file__).parent/'static';app.mount('/static',StaticFiles(directory=STATIC),name='static');JOBS={};PROCS={};DEVICES={};MQTT=None;OTA_FILE=ROOT/'ota_jobs.json';HISTORY=ROOT/'device_history.jsonl'
def fail(e):
 if isinstance(e,HTTPException):raise e
 if isinstance(e,FileNotFoundError):raise HTTPException(404,str(e))
 if isinstance(e,(PermissionError,ValueError,zipfile.BadZipFile)):raise HTTPException(400,str(e))
 raise e
def load_json(p,default):
 try:return json.loads(p.read_text())
 except Exception:return default
OTA=load_json(OTA_FILE,{})
def save_ota():OTA_FILE.write_text(json.dumps(OTA,indent=2))
def hist(dev,event,data):
 with HISTORY.open('a') as f:f.write(json.dumps({'ts':int(time.time()),'device_id':dev,'event':event,'data':data})+'\n')
def on_connect(c,u,f,reason,properties=None):
 for t in ('espmanager/+/status','espmanager/+/availability','espmanager/+/log','espmanager/+/ota/progress'):c.subscribe(t)
def on_message(c,u,msg):
 parts=msg.topic.split('/')
 if len(parts)<3:return
 dev,kind=parts[1],parts[2];text=msg.payload.decode(errors='replace')
 if not msg.payload:DEVICES.pop(dev,None);return
 e=DEVICES.setdefault(dev,{'device_id':dev,'logs':[]});e['last_seen']=int(time.time())
 if kind=='status':
  try:
   d=json.loads(text);e.update(d);hist(dev,'status',{k:d.get(k) for k in('firmware_version','ip','rssi','uptime','free_heap')});job=OTA.get(dev)
   if job:
    e.update(ota_target_version=job['target_version'],ota_result=job['state'])
    if str(d.get('firmware_version'))==str(job['target_version']):job['state']='confirmed';save_ota();e['ota_progress']=json.dumps({'state':'confirmed','percent':100,'message':'Neue Firmwareversion nach Neustart bestätigt'})
  except Exception:e['raw_status']=text
 elif kind=='availability':e['availability']=text
 elif kind=='log':e['logs']=(e['logs']+[{'ts':int(time.time()),'line':text}])[-200:]
 elif kind=='ota':e['ota_progress']=text
@app.on_event('startup')
def startup():
 global MQTT
 c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='esp-manager-dev-0101')
 if OPT['mqtt_username']:c.username_pw_set(OPT['mqtt_username'],OPT['mqtt_password'])
 c.on_connect=on_connect;c.on_message=on_message
 try:c.connect(OPT['mqtt_host'],int(OPT['mqtt_port']),60);c.loop_start();MQTT=c
 except Exception as e:print('MQTT disabled',e)
@app.get('/',response_class=HTMLResponse)
def home():return FileResponse(STATIC/'index.html')
@app.get('/api/projects')
def projects():return[public(meta(p.name)) for p in sorted(PROJECTS.iterdir()) if(p/'espmanager.yaml').exists()]
@app.post('/api/projects')
async def create(data:dict[str,Any]):
 try:
  name=clean(data['name']);p=pdir(name,False)
  if p.exists():raise HTTPException(409,'Projekt existiert')
  for d in('src','include','lib'):(p/d).mkdir(parents=True,exist_ok=True)
  m=migrate({'name':name,'board':data.get('board','esp32dev')});(p/'espmanager.yaml').write_text(__import__('yaml').safe_dump(m,sort_keys=False));shutil.copytree(T/'src',p/'src',dirs_exist_ok=True);system_copy(p);render_pio(p,m);return public(m)
 except Exception as e:fail(e)
@app.get('/api/projects/{name}/mqtt-entities')
def mqtt_entities_get(name):
 try:return {'project':clean(name),'entities':meta(name).get('mqtt_entities',[])}
 except Exception as e:fail(e)
@app.put('/api/projects/{name}/mqtt-entities')
async def mqtt_entities_put(name,data:dict[str,Any]):
 try:
  items=data.get('entities',data) if isinstance(data,dict) else data;m=meta(name);m['mqtt_entities']=validate_entities(items);backup(name,'before-mqtt-entities');save_meta(name,m);render_entities(pdir(name),m);return {'ok':True,'count':len(m['mqtt_entities']),'entities':m['mqtt_entities']}
 except Exception as e:fail(e)
@app.get('/api/projects/{name}')
def get_project(name):
 try:return public(meta(name))
 except Exception as e:fail(e)
@app.put('/api/projects/{name}')
async def update_project(name,data:dict[str,Any]):
 try:
  m=meta(name)
  for k in ('display_name','board','version','monitor_speed','libraries','build_flags','device_id'):
   if k in data:m[k]=data[k]
  backup(name,'before-settings');save_meta(name,m);render_pio(pdir(name),m);return public(m)
 except Exception as e:fail(e)
@app.post('/api/projects/{name}/duplicate')
async def duplicate(name,data:dict[str,Any]):
 try:
  new=clean(data['name']);dst=pdir(new,False)
  if dst.exists():raise HTTPException(409,'Ziel existiert')
  shutil.copytree(pdir(name),dst,ignore=shutil.ignore_patterns('.pio'));m=meta(new);m.update(name=new,display_name=new.replace('_',' ').title(),ota_token=secrets.token_urlsafe(32),device_id='');save_meta(new,m);system_copy(dst);render_pio(dst,m);return public(m)
 except Exception as e:fail(e)
@app.delete('/api/projects/{name}')
def delete_project(name):
 try:backup(name,'before-delete');shutil.rmtree(pdir(name));return{'ok':True}
 except Exception as e:fail(e)
@app.post('/api/projects/{name}/backup')
def manual_backup(name):return{'file':backup(name,'manual').name}
@app.get('/api/projects/{name}/export')
def export_project(name):return FileResponse(backup(name,'export'),filename=f'{clean(name)}.zip')
@app.post('/api/projects/import')
async def import_project(name:str=Form(...),archive:UploadFile=File(...)):
 try:
  n=clean(name);dst=pdir(n,False)
  if dst.exists():raise HTTPException(409,'Projekt existiert')
  z=zipfile.ZipFile(io.BytesIO(await archive.read()));tmp=ROOT/f'.import-{secrets.token_hex(5)}';tmp.mkdir()
  for i in z.infolist():
   if not i.is_dir() and '..' not in Path(i.filename).parts:
    f=tmp/i.filename;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(i))
  roots=list(tmp.rglob('espmanager.yaml'))
  if not roots:raise ValueError('espmanager.yaml fehlt')
  shutil.move(str(roots[0].parent),dst);shutil.rmtree(tmp,ignore_errors=True);m=meta(n);m.update(name=n,ota_token=secrets.token_urlsafe(32),device_id='');save_meta(n,m);system_copy(dst);render_pio(dst,m);return public(m)
 except Exception as e:fail(e)
@app.post('/api/projects/{name}/import-arduino')
async def import_arduino(name,archive:UploadFile=File(...)):
 try:
  backup(name,'before-arduino-import');z=zipfile.ZipFile(io.BytesIO(await archive.read()))
  for i in z.infolist():
   if i.is_dir() or '..' in Path(i.filename).parts:continue
   ext=Path(i.filename).suffix.lower()
   if ext not in('.ino','.cpp','.c','.h','.hpp'):continue
   target=('include/' if ext in('.h','.hpp') else 'src/')+Path(i.filename).name;data=z.read(i).decode(errors='replace')
   if ext=='.ino':data=re.sub(r'\bvoid\s+setup\s*\(','void setupDevice(',data,count=1);data=re.sub(r'\bvoid\s+loop\s*\(','void loopDevice(',data,count=1);target='src/'+Path(i.filename).stem+'.cpp'
   f=safe(name,target,False);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
  return{'ok':True}
 except Exception as e:fail(e)
@app.post('/api/projects/{name}/platformio-import')
async def pio_import(name,ini:UploadFile=File(...)):backup(name,'before-platformio-import');(pdir(name)/'platformio.imported.ini').write_bytes(await ini.read());return{'ok':True}
@app.get('/api/projects/{name}/files')
def file_list(name):
 p=pdir(name);return sorted(f.relative_to(p).as_posix() for r in('src','include','lib') for f in(p/r).rglob('*') if f.is_file() and f.relative_to(p).as_posix()!='src/main.cpp' and not f.relative_to(p).as_posix().startswith('lib/ESPManager/'))
@app.post('/api/projects/{name}/files')
async def file_create(name,data:dict[str,Any]):
 try:f=safe(name,data['path'],False);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data.get('content','// Neue Datei\n'));return{'ok':True}
 except Exception as e:fail(e)
@app.post('/api/projects/{name}/files/upload')
async def file_upload(name,path:str=Form('src'),files:list[UploadFile]=File(...)):
 try:
  out=[]
  for up in files:
   f=safe(name,f'{path}/{Path(up.filename).name}',False);f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(await up.read());out.append(f.name)
  return{'files':out}
 except Exception as e:fail(e)
@app.get('/api/projects/{name}/file',response_class=PlainTextResponse)
def file_open(name,path):
 try:return safe(name,path).read_text(errors='replace')
 except Exception as e:fail(e)
@app.put('/api/projects/{name}/file')
async def file_save(name,path,request:Request):
 try:safe(name,path).write_bytes(await request.body());return{'ok':True}
 except Exception as e:fail(e)
@app.post('/api/projects/{name}/file/rename')
async def file_rename(name,data:dict[str,Any]):
 try:backup(name,'before-file-rename');src=safe(name,data['source']);dst=safe(name,data['target'],False);dst.parent.mkdir(parents=True,exist_ok=True);src.rename(dst);return{'ok':True}
 except Exception as e:fail(e)
@app.delete('/api/projects/{name}/file')
def file_delete(name,path):
 try:backup(name,'before-file-delete');safe(name,path).unlink();return{'ok':True}
 except Exception as e:fail(e)
def worker(jid):
 j=JOBS[jid];name=j['project'];p=pdir(name);m=meta(name);system_copy(p);render_pio(p,m);j['status']='running'
 try:
  proc=subprocess.Popen(['/opt/esp_manager/venv/bin/pio','run'],cwd=p,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);PROCS[jid]=proc
  for line in proc.stdout or[]:j['log']=(j['log']+line)[-150000:]
  if proc.wait():j['status']='failed';return
  src=p/'.pio/build'/m['board']/'firmware.bin';bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/name/bid;out.mkdir(parents=True);shutil.copy2(src,out/'firmware.bin');initial_image(p,m,out);blob=src.read_bytes();rec={'id':bid,'version':m['version'],'board':m['board'],'chip_family':BOARDS[m['board']][0],'built_at':int(time.time()),'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'pinned':False};(out/'manifest.json').write_text(json.dumps(rec,indent=2));removed=prune(name);j['log']+=f'\nAufbewahrung: {len(removed)} entfernt\n';j.update(status='success',build=rec)
 except Exception as e:j['status']='failed';j['log']+='\n'+repr(e)
@app.post('/api/projects/{name}/build-start')
def build_start(name):
 if any(j['project']==clean(name) and j['status'] in('queued','running') for j in JOBS.values()):raise HTTPException(409,'Build läuft bereits')
 jid=f'{clean(name)}-{time.time_ns()}';JOBS[jid]={'project':clean(name),'status':'queued','log':''};threading.Thread(target=worker,args=(jid,),daemon=True).start();return{'job_id':jid}
@app.get('/api/builds/{jid}')
def build_status(jid):
 if jid not in JOBS:raise HTTPException(404,'Build fehlt')
 return JOBS[jid]
@app.post('/api/builds/{jid}/cancel')
def build_cancel(jid):
 p=PROCS.get(jid)
 if p and p.poll() is None:p.terminate()
 JOBS[jid]['status']='cancelled';return{'ok':True}
@app.get('/api/projects/{name}/builds')
def build_list(name):return[{k:v for k,v in b.items() if k!='_dir'} for b in builds(name)]
@app.get('/api/projects/{name}/builds/{bid}/firmware')
def build_download(name,bid):return FileResponse(next(b for b in builds(name) if b['id']==bid)['_dir']/'firmware.bin')
@app.post('/api/projects/{name}/builds/{bid}/pin')
async def build_pin(name,bid,data:dict[str,Any]):
 b=next((x for x in builds(name) if x['id']==bid),None)
 if not b:raise HTTPException(404,'Build fehlt')
 d=json.loads((b['_dir']/'manifest.json').read_text());d['pinned']=bool(data.get('pinned',True));(b['_dir']/'manifest.json').write_text(json.dumps(d,indent=2));return{'pinned':d['pinned']}
@app.delete('/api/projects/{name}/builds/{bid}')
def build_delete(name,bid):
 b=next((x for x in builds(name) if x['id']==bid),None)
 if not b:raise HTTPException(404,'Build fehlt')
 if b.get('pinned'):raise HTTPException(409,'Angeheftet')
 shutil.rmtree(b['_dir']);return{'ok':True}
@app.post('/api/projects/{name}/builds/prune')
async def build_prune(name,data:dict[str,Any]):return{'removed':prune(name,data.get('keep'))}
def presence(e):r=dict(e);r['last_seen_age']=max(0,int(time.time())-int(r.get('last_seen',0)));r['online']=r['last_seen_age']<=int(OPT['device_offline_after']);return r
@app.get('/api/devices')
def devices():return sorted((presence(x) for x in DEVICES.values()),key=lambda x:(not x['online'],x['device_id']))
@app.get('/api/devices/{dev}')
def device(dev):
 if clean(dev) not in DEVICES:raise HTTPException(404,'Gerät fehlt')
 return presence(DEVICES[clean(dev)])
@app.delete('/api/devices/{dev}')
def device_delete(dev):
 d=clean(dev);DEVICES.pop(d,None);OTA.pop(d,None);save_ota()
 if MQTT and MQTT.is_connected():
  for s in('status','availability','ota/progress'):MQTT.publish(f'espmanager/{d}/{s}','',qos=1,retain=True)
 return{'ok':True}
@app.get('/api/devices/{dev}/history')
def device_history(dev,limit:int=100):
 out=[]
 for line in HISTORY.read_text().splitlines() if HISTORY.exists() else[]:
  try:
   x=json.loads(line)
   if x.get('device_id')==clean(dev):out.append(x)
  except Exception:pass
 return out[-min(max(limit,1),500):]
@app.get('/api/mqtt/status')
def mqtt_status():return{'connected':bool(MQTT and MQTT.is_connected()),'devices':len(DEVICES),'host':OPT['mqtt_host'],'port':OPT['mqtt_port']}
def find_build(name,bid):
 b=next((x for x in builds(name) if x['id']==bid),None)
 if not b:raise HTTPException(404,'Build fehlt')
 return b
@app.post('/api/projects/{name}/devices/{dev}/ota')
async def ota(name,dev,data:dict[str,Any]):
 if not MQTT or not MQTT.is_connected():raise HTTPException(503,'MQTT offline')
 m=meta(name);b=find_build(name,data['build_id']);fw=b['_dir']/'firmware.bin';sha=hashlib.sha256(fw.read_bytes()).hexdigest()
 if sha!=b['sha256']:raise HTTPException(409,'SHA256 falsch')
 url=f"{str(OPT['public_base_url']).rstrip('/')}/firmware/{clean(name)}/{b['id']}/firmware.bin?token={m['ota_token']}";cmd={'token':m['ota_token'],'url':url,'version':b['version'],'build_id':b['id'],'sha256':sha,'size':b['size']};payload=json.dumps(cmd,separators=(',',':'))
 if len(payload.encode())>1536:raise HTTPException(413,'OTA-Kommando zu groß')
 MQTT.publish(f'espmanager/{clean(dev)}/cmd/ota',payload,qos=1);OTA[clean(dev)]={'project':clean(name),'build_id':b['id'],'target_version':str(b['version']),'requested_at':int(time.time()),'state':'pending'};save_ota();return{'ok':True,'url':url,'command_bytes':len(payload.encode())}
@app.get('/firmware/{name}/{bid}/firmware.bin')
def firmware(name,bid,token:str):
 m=meta(name)
 if token!=m['ota_token']:raise HTTPException(403,'Token falsch')
 b=find_build(name,bid);fw=b['_dir']/'firmware.bin';blob=fw.read_bytes()
 if hashlib.sha256(blob).hexdigest()!=b['sha256']:raise HTTPException(409,'SHA256 falsch')
 return FileResponse(fw,headers={'x-MD5':hashlib.md5(blob).hexdigest(),'X-Firmware-SHA256':b['sha256'],'Cache-Control':'no-store'})
@app.get('/usb/{name}',response_class=HTMLResponse,include_in_schema=False)
@app.get('/usb/{name}/',response_class=HTMLResponse)
def hardware(name):
 pdir(name);html=(STATIC/'hardware.html').read_text();js=(STATIC/'hardware.js').read_text();return HTMLResponse(html.replace('__PROJECT__',clean(name)).replace('__HARDWARE_JS__',js))
@app.get('/usb/{name}/manifest.json')
def manifest(name):
 bs=builds(name)
 if not bs:raise HTTPException(404,'Kein erfolgreicher Build vorhanden')
 b=bs[0];return{'name':meta(name)['display_name'],'version':b['version'],'new_install_prompt_erase':True,'builds':[{'chipFamily':b['chip_family'],'parts':[{'path':'initial_firmware.bin','offset':0}]}]}
@app.get('/usb/{name}/initial_firmware.bin')
def initial(name):
 bs=builds(name)
 if not bs:raise HTTPException(404,'Kein erfolgreicher Build vorhanden')
 return FileResponse(bs[0]['_dir']/'initial_firmware.bin')



