from pathlib import Path
app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()

# Persistent OTA jobs and bounded device history.
anchor="OPT=options();app=FastAPI(title='ESP Manager');JOBS={};PROCS={};DEVICES={};MQTT=None"
replacement="""OPT=options();app=FastAPI(title='ESP Manager');JOBS={};PROCS={};DEVICES={};MQTT=None
OTA_JOBS_FILE=ROOT/'ota_jobs.json';DEVICE_HISTORY_FILE=ROOT/'device_history.jsonl'
def _load_ota_jobs():
 try:return json.loads(OTA_JOBS_FILE.read_text()) if OTA_JOBS_FILE.exists() else {}
 except Exception:return {}
OTA_JOBS=_load_ota_jobs()
def _save_ota_jobs():
 tmp=OTA_JOBS_FILE.with_suffix('.tmp');tmp.write_text(json.dumps(OTA_JOBS,indent=2));tmp.replace(OTA_JOBS_FILE)
def _history(device,event,data):
 record={'ts':int(time.time()),'device_id':device,'event':event,'data':data}
 with DEVICE_HISTORY_FILE.open('a') as f:f.write(json.dumps(record,separators=(',',':'))+'\\n')
 try:
  lines=DEVICE_HISTORY_FILE.read_text().splitlines()
  if len(lines)>2000:DEVICE_HISTORY_FILE.write_text('\\n'.join(lines[-2000:])+'\\n')
 except Exception:pass"""
if anchor not in s:raise SystemExit('global anchor missing')
s=s.replace(anchor,replacement,1)

# Persist status snapshots and reconcile OTA jobs.
old="""if kind=='status':
  try:
   e.update(json.loads(text))
   target=e.get('ota_target_version')
   if target and str(e.get('firmware_version'))==str(target):
    e['ota_result']='success';e['ota_progress']=json.dumps({'state':'confirmed','percent':100,'message':'Neue Firmwareversion nach Neustart bestätigt'})
  except Exception:e['raw_status']=text"""
new="""if kind=='status':
  try:
   status=json.loads(text);e.update(status);_history(device,'status',{k:status.get(k) for k in ('firmware_version','ip','ssid','rssi','uptime','free_heap')})
   target=e.get('ota_target_version')
   if target and str(e.get('firmware_version'))==str(target):
    e['ota_result']='success';e['ota_progress']=json.dumps({'state':'confirmed','percent':100,'message':'Neue Firmwareversion nach Neustart bestätigt'})
    job=OTA_JOBS.get(device)
    if job:job.update(state='confirmed',confirmed_at=int(time.time()),reported_version=str(e.get('firmware_version')));_save_ota_jobs();_history(device,'ota_confirmed',job)
  except Exception:e['raw_status']=text"""
if old not in s:raise SystemExit('status reconcile block missing')
s=s.replace(old,new,1)

# Persist OTA target immediately.
old="""entry['ota_target_version']=build['version'];entry['ota_target_build']=build['id'];entry['ota_requested_at']=int(time.time());entry['ota_result']='pending'"""
new="""entry['ota_target_version']=build['version'];entry['ota_target_build']=build['id'];entry['ota_requested_at']=int(time.time());entry['ota_result']='pending'
 OTA_JOBS[device_id]={'project':clean(project),'device_id':device_id,'build_id':build['id'],'target_version':str(build['version']),'sha256':actual,'requested_at':int(time.time()),'state':'pending'};_save_ota_jobs();_history(device_id,'ota_requested',OTA_JOBS[device_id])"""
if old not in s:raise SystemExit('OTA cache block missing')
s=s.replace(old,new,1)

# APIs for OTA persistence and device history.
api_anchor='def hardware_page(project):'
api_code="""@app.get('/api/ota/jobs')
def ota_jobs():return OTA_JOBS
@app.get('/api/devices/{device_id}/history')
def device_history(device_id,limit:int=100):
 device_id=clean(device_id);out=[]
 if DEVICE_HISTORY_FILE.exists():
  for line in DEVICE_HISTORY_FILE.read_text().splitlines():
   try:
    item=json.loads(line)
    if item.get('device_id')==device_id:out.append(item)
   except Exception:pass
 return out[-max(1,min(limit,500)):]

"""
if api_anchor not in s:raise SystemExit('hardware anchor missing')
s=s.replace(api_anchor,api_code+api_anchor,1)

# Retention setting from add-on options instead of fixed count.
s=s.replace("prune_builds(j['project'],5)","prune_builds(j['project'],int(OPT.get('build_retention',5)))")
s=s.replace('ESP Manager Dev 0.7.3-dev','ESP Manager Dev 0.8.0-dev').replace('ESP Manager 0.7.3','ESP Manager 0.8.0-dev')
main.write_text(s)

# ESP32 boot confirmation hook. Effective when the board/bootloader exposes a pending-verify OTA image.
cpp=app_dir/'templates/lib/ESPManager/src/ESPManager.cpp';c=cpp.read_text()
include='#include <ArduinoJson.h>'
extra='''#include <ArduinoJson.h>\n#ifndef ESP8266\n#include <esp_ota_ops.h>\n#endif'''
if include not in c:raise SystemExit('ArduinoJson include missing')
c=c.replace(include,extra,1)
helper='''\nstatic void confirmRunningFirmware(){\n#ifndef ESP8266\n const esp_partition_t* running=esp_ota_get_running_partition();esp_ota_img_states_t state;\n if(running&&esp_ota_get_state_partition(running,&state)==ESP_OK&&state==ESP_OTA_IMG_PENDING_VERIFY){\n  if(esp_ota_mark_app_valid_cancel_rollback()==ESP_OK)Serial.println("[ESPManager] OTA-Boot bestätigt");\n }\n#endif\n}\n'''
callback='static void callback(char*t,byte*p,unsigned int l){String b;for(unsigned int i=0;i<l;i++)b+=(char)p[i];ESPManager.handleCommand(String(t),b);}'
if callback not in c:raise SystemExit('callback missing')
c=c.replace(callback,callback+helper,1)
needle='log("MQTT verbunden");publishStatus();'
if needle not in c:raise SystemExit('MQTT success missing')
c=c.replace(needle,'log("MQTT verbunden");confirmRunningFirmware();publishStatus();',1)
cpp.write_text(c)
