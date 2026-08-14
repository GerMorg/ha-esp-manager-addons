from pathlib import Path
app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()

# Replace status processing with failure-isolated persistence and restoration
# of OTA targets from the persistent job store after an add-on restart.
start=s.index("if kind=='status':",s.index('def on_message'))
end=s.index(" elif kind=='availability':",start)
new="""if kind=='status':
  try:status=json.loads(text)
  except Exception:
   e['raw_status']=text;return
  e.update(status);e.pop('raw_status',None)
  job=OTA_JOBS.get(device)
  if job:
   e['ota_target_version']=job.get('target_version');e['ota_target_build']=job.get('build_id');e['ota_requested_at']=job.get('requested_at');e['ota_result']=job.get('state','pending')
  try:_history(device,'status',{k:status.get(k) for k in ('firmware_version','ip','ssid','rssi','uptime','free_heap')})
  except Exception as exc:print('device history write failed:',exc)
  target=e.get('ota_target_version')
  if target and str(e.get('firmware_version'))==str(target):
   e['ota_result']='success';e['ota_progress']=json.dumps({'state':'confirmed','percent':100,'message':'Neue Firmwareversion nach Neustart bestätigt'})
   if job:
    job.update(state='confirmed',confirmed_at=int(time.time()),reported_version=str(e.get('firmware_version')))
    try:_save_ota_jobs();_history(device,'ota_confirmed',job)
    except Exception as exc:print('OTA confirmation persistence failed:',exc)
 """
s=s[:start]+new+s[end:]

# Build-retention diagnostics and an explicit status endpoint.
anchor="@app.post('/api/projects/{project}/builds/prune')"
pos=s.index(anchor)
insert="""@app.get('/api/projects/{project}/builds/retention')
def build_retention_status(project):
 items=build_list(project);configured=max(1,min(int(OPT.get('build_retention',5)),50))
 return {'configured':configured,'total':len(items),'pinned':sum(1 for x in items if x.get('pinned')),'normal':sum(1 for x in items if not x.get('pinned')),'builds':[{'id':x.get('id'),'version':x.get('version'),'pinned':bool(x.get('pinned'))} for x in items]}

"""
s=s[:pos]+insert+s[pos:]

# Make automatic pruning visible in the build log and enforce the current
# add-on option after every successful build.
old="prune_builds(j['project'],int(OPT.get('build_retention',5)));j['status']='success';j['build']=rec"
new="removed=prune_builds(j['project'],int(OPT.get('build_retention',5)));j['log']+=f'\\nBuild-Aufbewahrung: {len(removed)} alte Builds entfernt; Limit={int(OPT.get(\"build_retention\",5))}\\n';j['status']='success';j['build']=rec"
if old not in s:raise SystemExit('automatic retention call not found')
s=s.replace(old,new,1)

# Deduplicate retained OTA progress messages in the UI and stop polling the
# completed message into the log forever.
state="let port=null,reader=null,readLoopPromise=null,keepReading=false,selectedDevice='PREFERRED',targetVersion=null,otaStartedAt=0;"
state_new="let port=null,reader=null,readLoopPromise=null,keepReading=false,selectedDevice='PREFERRED',targetVersion=null,otaStartedAt=0,lastOtaProgress='';"
if state not in s:raise SystemExit('UI state anchor not found')
s=s.replace(state,state_new,1)
old_log="otaLog.textContent=o+'\\\\n'+otaLog.textContent"
new_log="if(o!==lastOtaProgress){otaLog.textContent=o+'\\\\n'+otaLog.textContent;lastOtaProgress=o}"
if old_log not in s:raise SystemExit('OTA log append not found')
s=s.replace(old_log,new_log,1)
# Once completion is confirmed, clear timeout tracking.
s=s.replace("otaButton.disabled=false}let o=d.ota_progress", "otaButton.disabled=false;otaStartedAt=0}let o=d.ota_progress",1)
s=s.replace("ESP Manager Dev 0.8.0-dev","ESP Manager Dev 0.8.1-dev").replace("ESP Manager 0.8.0-dev","ESP Manager Dev 0.8.1-dev")
main.write_text(s)
