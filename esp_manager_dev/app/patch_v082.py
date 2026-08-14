from pathlib import Path
app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()

# A deleted device must not be recreated from retained empty payloads or old OTA jobs.
old="""parts=msg.topic.split('/');
 if len(parts)<3:return
 dev,kind=parts[1],parts[2];e=DEVICES.setdefault(dev,{'device_id':dev,'logs':[]});e['last_seen']=int(time.time());text=msg.payload.decode(errors='replace')"""
new="""parts=msg.topic.split('/')
 if len(parts)<3:return
 dev,kind=parts[1],parts[2];text=msg.payload.decode(errors='replace')
 if len(msg.payload)==0:
  if kind in ('status','availability','ota'):DEVICES.pop(dev,None)
  return
 e=DEVICES.setdefault(dev,{'device_id':dev,'logs':[]});e['last_seen']=int(time.time())"""
if old not in s:raise SystemExit('MQTT device creation block missing')
s=s.replace(old,new,1)

# Availability is explicit when present; computed presence protects against stale retained online.
old_devices="@app.get('/api/devices')\ndef devices():return list(DEVICES.values())"
new_devices="""@app.get('/api/devices')
def devices():
 now=int(time.time());timeout=max(35,min(int(OPT.get('device_offline_after',75)),600));out=[]
 for value in DEVICES.values():
  item=dict(value);age=max(0,now-int(item.get('last_seen',0)));explicit=str(item.get('availability','')).lower()
  item['last_seen_age']=age;item['online']=explicit=='online' and age<=timeout;item['presence']='online' if item['online'] else 'offline';out.append(item)
 return sorted(out,key=lambda x:(not x['online'],x.get('device_id','')))"""
if old_devices not in s:raise SystemExit('device list endpoint missing')
s=s.replace(old_devices,new_devices,1)

# Device details receive the same derived presence fields.
old_detail="""if clean(device) not in DEVICES:raise HTTPException(404,'Gerät hat sich noch nicht gemeldet')
 return DEVICES[clean(device)]"""
new_detail="""device_id=clean(device)
 if device_id not in DEVICES:raise HTTPException(404,'Gerät hat sich noch nicht gemeldet')
 item=dict(DEVICES[device_id]);timeout=max(35,min(int(OPT.get('device_offline_after',75)),600));age=max(0,int(time.time())-int(item.get('last_seen',0)));item['last_seen_age']=age;item['online']=str(item.get('availability','')).lower()=='online' and age<=timeout;item['presence']='online' if item['online'] else 'offline';return item"""
if old_detail not in s:raise SystemExit('device detail endpoint missing')
s=s.replace(old_detail,new_detail,1)

# Deletion clears memory, retained topics, persistent OTA job and saved project mappings.
old_forget="""device_id=clean(device_id);DEVICES.pop(device_id,None)
 if MQTT and MQTT.is_connected():
  for suffix in ('status','availability','ota/progress'):MQTT.publish(f'espmanager/{device_id}/{suffix}',payload='',qos=1,retain=True)
 return {'ok':True,'device_id':device_id,'note':'Ein aktives Gerät erscheint bei der nächsten Statusmeldung erneut.'}"""
new_forget="""device_id=clean(device_id);DEVICES.pop(device_id,None);removed_job=OTA_JOBS.pop(device_id,None)
 if removed_job is not None:_save_ota_jobs()
 if MQTT and MQTT.is_connected():
  for suffix in ('status','availability','ota/progress'):MQTT.publish(f'espmanager/{device_id}/{suffix}',payload='',qos=1,retain=True)
 for meta_file in PROJECTS.glob('*/espmanager.yaml'):
  try:
   meta=migrate(yaml.safe_load(meta_file.read_text()) or {})
   if meta.get('device_id')==device_id:meta['device_id']='';meta_file.write_text(yaml.safe_dump(meta,sort_keys=False))
  except Exception as exc:print('device mapping cleanup failed:',exc)
 return {'ok':True,'device_id':device_id,'removed_ota_job':removed_job is not None,'note':'Ein weiterhin aktives Gerät erscheint erst mit einer neuen echten Statusmeldung wieder.'}"""
if old_forget not in s:raise SystemExit('forget device block missing')
s=s.replace(old_forget,new_forget,1)

# Main overview: visible online/offline indicator.
old_card="""devices.innerHTML=ds.map(x=>`<div class=\"item\"><b>${x.device_id}</b> ${x.availability||''}<br>${x.ip||''} ${x.ssid||''} RSSI ${x.rssi||'-'}</div>`).join('')||'Noch keine Geräte'"""
new_card="""devices.innerHTML=ds.map(x=>`<div class=\"item\"><span style=\"color:${x.online?'#22c55e':'#ef4444'}\">●</span> <b>${x.device_id}</b> ${x.online?'Online':'Offline'}<br>${x.ip||''} ${x.ssid||''} RSSI ${x.rssi||'-'} | zuletzt vor ${x.last_seen_age}s</div>`).join('')||'Noch keine Geräte'"""
if old_card not in s:raise SystemExit('main device card renderer missing')
s=s.replace(old_card,new_card,1)

# Hardware selector also shows presence and drops the deleted name immediately.
old_option="""ds.map(d=>'<option value=\"'+d.device_id+'\">'+d.device_id+(d.ip?' - '+d.ip:'')+'</option>')"""
new_option="""ds.map(d=>'<option value=\"'+d.device_id+'\">'+(d.online?'Online: ':'Offline: ')+d.device_id+(d.ip?' - '+d.ip:'')+'</option>')"""
if old_option not in s:raise SystemExit('hardware device option renderer missing')
s=s.replace(old_option,new_option,1)
old_forget_js="selectedDevice='';await refreshDevices()"
new_forget_js="selectedDevice='';targetVersion=null;deviceSelect.innerHTML='<option value=\"\">Gerät auswählen</option>';deviceStatus.textContent='Gerät wurde aus der Übersicht entfernt.';await refreshDevices()"
if old_forget_js not in s:raise SystemExit('forget JS state missing')
s=s.replace(old_forget_js,new_forget_js,1)
s=s.replace('ESP Manager Dev 0.8.1-dev','ESP Manager Dev 0.8.2-dev').replace('ESP Manager Dev 0.8.1','ESP Manager Dev 0.8.2')
main.write_text(s)
