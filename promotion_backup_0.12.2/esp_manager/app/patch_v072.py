from pathlib import Path
app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()
anchor='def hardware_page(project):'
backend="""
def _remove_build_dir(project,build_id):
 build=_build_by_id(project,build_id);shutil.rmtree(build['_dir']);return build

def prune_builds(project,keep=5):
 keep=max(1,min(int(keep),50));items=build_list(project);kept=0;removed=[]
 for item in items:
  if item.get('pinned'):continue
  kept+=1
  if kept>keep:shutil.rmtree(item['_dir'],ignore_errors=True);removed.append(item['id'])
 return removed

@app.delete('/api/devices/{device_id}')
def forget_device(device_id):
 device_id=clean(device_id);DEVICES.pop(device_id,None)
 if MQTT and MQTT.is_connected():
  for suffix in ('status','availability','ota/progress'):MQTT.publish(f'espmanager/{device_id}/{suffix}',payload='',qos=1,retain=True)
 return {'ok':True,'device_id':device_id,'note':'Ein aktives Gerät erscheint bei der nächsten Statusmeldung erneut.'}

@app.delete('/api/projects/{project}/builds/{build_id}')
def delete_build(project,build_id):
 item=_build_by_id(project,build_id)
 if item.get('pinned'):raise HTTPException(409,'Angehefteter Build kann nicht gelöscht werden')
 _remove_build_dir(project,build_id);return {'ok':True,'build_id':build_id}

@app.post('/api/projects/{project}/builds/{build_id}/pin')
async def pin_build(project,build_id,payload:dict[str,Any]):
 item=_build_by_id(project,build_id);manifest=item['_dir']/'manifest.json';data=json.loads(manifest.read_text());data['pinned']=bool(payload.get('pinned',True));manifest.write_text(json.dumps(data,indent=2));return {'build_id':build_id,'pinned':data['pinned']}

@app.post('/api/projects/{project}/builds/prune')
async def prune_project_builds(project,payload:dict[str,Any]):return {'removed':prune_builds(project,payload.get('keep',5))}

"""
if anchor not in s:raise SystemExit('hardware page anchor missing')
s=s.replace(anchor,backend+anchor,1)
old="(out/'manifest.json').write_text(json.dumps(rec,indent=2));j['status']='success';j['build']=rec"
new="rec['pinned']=False;(out/'manifest.json').write_text(json.dumps(rec,indent=2));prune_builds(j['project'],5);j['status']='success';j['build']=rec"
if old not in s:raise SystemExit('build success block missing')
s=s.replace(old,new,1)
s=s.replace("<button onclick='refreshDevices()'>Aktualisieren</button><pre id='deviceStatus'>","<button onclick='refreshDevices()'>Aktualisieren</button><button onclick='forgetSelectedDevice()'>Gerät vergessen</button><pre id='deviceStatus'>",1)
s=s.replace("<label>Firmware-Build: <select id='buildSelect'></select></label><button id='otaButton'","<label>Firmware-Build: <select id='buildSelect'></select></label><button onclick='togglePin()'>Anheften/Lösen</button><button onclick='deleteSelectedBuild()'>Build löschen</button><button onclick='pruneBuilds()'>Nur letzte 5 behalten</button><button id='otaButton'",1)
marker='async function startOta()'
funcs="""async function forgetSelectedDevice(){if(!selectedDevice||!confirm('Gerät aus der Übersicht entfernen? Ein aktives Gerät kann wieder erscheinen.'))return;let r=await fetch(apiUrl('api/devices/'+encodeURIComponent(selectedDevice)),{method:'DELETE'});if(!r.ok)throw Error(await r.text());selectedDevice='';await refreshDevices()}async function deleteSelectedBuild(){if(!buildSelect.value||!confirm('Diesen Build endgültig löschen?'))return;let r=await fetch(apiUrl('api/projects/PROJECT/builds/'+buildSelect.value),{method:'DELETE'});if(!r.ok)throw Error(await r.text());await loadBuilds()}async function togglePin(){if(!buildSelect.value)return;let option=buildSelect.selectedOptions[0];let pinned=option.dataset.pinned!=='true';let r=await fetch(apiUrl('api/projects/PROJECT/builds/'+buildSelect.value+'/pin'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned})});if(!r.ok)throw Error(await r.text());await loadBuilds()}async function pruneBuilds(){let r=await fetch(apiUrl('api/projects/PROJECT/builds/prune'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keep:5})});if(!r.ok)throw Error(await r.text());let x=await r.json();alert(x.removed.length+' alte Builds entfernt');await loadBuilds()}"""
if marker not in s:raise SystemExit('startOta marker missing')
s=s.replace(marker,funcs+marker,1)
old_opts="""buildSelect.innerHTML=builds.map(b=>'<option value="'+b.id+'">'+b.version+' | '+new Date(b.built_at*1000).toLocaleString()+' | '+b.size+' B</option>').join('')"""
new_opts="""buildSelect.innerHTML=builds.map(b=>'<option data-pinned="'+(b.pinned?'true':'false')+'" value="'+b.id+'">'+(b.pinned?'[PIN] ':'')+b.version+' | '+new Date(b.built_at*1000).toLocaleString()+' | '+b.size+' B</option>').join('')"""
if old_opts not in s:raise SystemExit('build option renderer missing')
s=s.replace(old_opts,new_opts,1)
s=s.replace('ESP Manager Dev 0.7.1-dev','ESP Manager Dev 0.7.2-dev').replace('ESP Manager 0.7.1','ESP Manager 0.7.2')
main.write_text(s)
cpp=app_dir/'templates/lib/ESPManager/src/ESPManager.cpp';c=cpp.read_text()
old_client='static WiFiClient net; static PubSubClient mq(net);';new_client='static WiFiClient net; static WiFiClient otaNet; static PubSubClient mq(net);'
if old_client not in c:raise SystemExit('MQTT client declaration missing')
c=c.replace(old_client,new_client,1).replace('ESPhttpUpdate.update(net,u)','ESPhttpUpdate.update(otaNet,u)').replace('httpUpdate.update(net,u)','httpUpdate.update(otaNet,u)')
cpp.write_text(c)
