from pathlib import Path
app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()

# Remember the OTA target in the device status cache so completion can be
# recognized after the ESP reboots and publishes its new firmware_version.
old="""m['device_id']=device_id;save_meta(project,m)
 return {'ok':True,'device_id':device_id,'build_id':build['id'],'version':build['version'],'sha256':actual,'url':url,'command_bytes':command_bytes}"""
new="""m['device_id']=device_id;save_meta(project,m)
 entry=DEVICES.setdefault(device_id,{'device_id':device_id,'logs':[]})
 entry['ota_target_version']=build['version'];entry['ota_target_build']=build['id'];entry['ota_requested_at']=int(time.time());entry['ota_result']='pending'
 return {'ok':True,'device_id':device_id,'build_id':build['id'],'version':build['version'],'sha256':actual,'url':url,'command_bytes':command_bytes}"""
if old not in s:raise SystemExit('OTA response block not found')
s=s.replace(old,new,1)

# Reconcile a rebooted device with the requested target version whenever status arrives.
old_status="""if kind=='status':
  try:e.update(json.loads(text))
  except Exception:e['raw_status']=text"""
new_status="""if kind=='status':
  try:
   e.update(json.loads(text))
   target=e.get('ota_target_version')
   if target and str(e.get('firmware_version'))==str(target):
    e['ota_result']='success';e['ota_progress']=json.dumps({'state':'confirmed','percent':100,'message':'Neue Firmwareversion nach Neustart bestätigt'})
  except Exception:e['raw_status']=text"""
if old_status not in s:raise SystemExit('MQTT status block not found')
s=s.replace(old_status,new_status,1)

# UI: target version returned by OTA request and definitive 100% on version confirmation.
script_anchor="let port=null,reader=null,readLoopPromise=null,keepReading=false,selectedDevice='PREFERRED';"
script_new="let port=null,reader=null,readLoopPromise=null,keepReading=false,selectedDevice='PREFERRED',targetVersion=null,otaStartedAt=0;"
if script_anchor not in s:raise SystemExit('hardware script state missing')
s=s.replace(script_anchor,script_new,1)
old_refresh="""let d=await r.json();deviceStatus.textContent=JSON.stringify(d,null,2);let o=d.ota_progress;if(o){try{let x=JSON.parse(o);otaState.textContent=x.state+(x.message?' - '+x.message:'');if(Number.isFinite(x.percent))otaProgress.value=x.percent;otaLog.textContent=o+'\\\\n'+otaLog.textContent}catch(e){otaState.textContent=o}}"""
new_refresh="""let d=await r.json();deviceStatus.textContent=JSON.stringify(d,null,2);if(!targetVersion&&d.ota_target_version)targetVersion=String(d.ota_target_version);if(targetVersion&&String(d.firmware_version)===targetVersion){otaProgress.value=100;otaState.className='ok';otaState.textContent='Update erfolgreich: Firmware '+targetVersion+' nach Neustart bestätigt';otaButton.disabled=false}let o=d.ota_progress;if(o){try{let x=JSON.parse(o);if(x.state==='confirmed'||x.state==='finished'){otaProgress.value=100;otaState.className='ok'}else if(x.state==='failed'){otaState.className='bad'}otaState.textContent=x.state+(x.message?' - '+x.message:'');if(Number.isFinite(x.percent))otaProgress.value=x.percent;otaLog.textContent=o+'\\\\n'+otaLog.textContent}catch(e){otaState.textContent=o}}if(otaStartedAt&&Date.now()-otaStartedAt>180000&&otaProgress.value<100){otaState.className='bad';otaState.textContent='OTA-Zeitüberschreitung: Gerätestatus und serielle Ausgabe prüfen';otaButton.disabled=false}"""
if old_refresh not in s:raise SystemExit('hardware status refresh block not found')
s=s.replace(old_refresh,new_refresh,1)
old_sent="""let x=await r.json();otaState.textContent='Auftrag gesendet: '+x.version;otaLog.textContent=JSON.stringify(x,null,2)"""
new_sent="""let x=await r.json();targetVersion=String(x.version);otaStartedAt=Date.now();otaState.className='';otaState.textContent='Auftrag gesendet: '+x.version;otaLog.textContent=JSON.stringify(x,null,2)"""
if old_sent not in s:raise SystemExit('OTA sent UI block not found')
s=s.replace(old_sent,new_sent,1)
s=s.replace('ESP Manager Dev 0.7.2-dev','ESP Manager Dev 0.7.3-dev').replace('ESP Manager 0.7.2','ESP Manager 0.7.3')
main.write_text(s)

# Agent: disable immediate library reboot, publish final state, flush MQTT briefly,
# then restart explicitly. This makes finished much more likely to reach the broker.
cpp=app_dir/'templates/lib/ESPManager/src/ESPManager.cpp'
c=cpp.read_text()
old_8266="ESPhttpUpdate.onStart(otaStart);ESPhttpUpdate.onEnd(otaEnd);ESPhttpUpdate.onProgress(otaProgress);ESPhttpUpdate.onError(otaError);t_httpUpdate_return result=ESPhttpUpdate.update(otaNet,u);if(result==HTTP_UPDATE_NO_UPDATES)otaState(\"no_update\",100,\"Keine Aktualisierung\");else if(result==HTTP_UPDATE_FAILED)otaState(\"failed\",0,ESPhttpUpdate.getLastErrorString());"
new_8266="ESPhttpUpdate.rebootOnUpdate(false);ESPhttpUpdate.onStart(otaStart);ESPhttpUpdate.onEnd(otaEnd);ESPhttpUpdate.onProgress(otaProgress);ESPhttpUpdate.onError(otaError);t_httpUpdate_return result=ESPhttpUpdate.update(otaNet,u);if(result==HTTP_UPDATE_OK){otaState(\"finished\",100,\"Update vollständig, Neustart folgt\");for(int i=0;i<8;i++){mq.loop();delay(100);}ESP.restart();}else if(result==HTTP_UPDATE_NO_UPDATES)otaState(\"no_update\",100,\"Keine Aktualisierung\");else otaState(\"failed\",0,ESPhttpUpdate.getLastErrorString());"
old_32="httpUpdate.onStart(otaStart);httpUpdate.onEnd(otaEnd);httpUpdate.onProgress(otaProgress);httpUpdate.onError(otaError);t_httpUpdate_return result=httpUpdate.update(otaNet,u);if(result==HTTP_UPDATE_NO_UPDATES)otaState(\"no_update\",100,\"Keine Aktualisierung\");else if(result==HTTP_UPDATE_FAILED)otaState(\"failed\",0,httpUpdate.getLastErrorString());"
new_32="httpUpdate.rebootOnUpdate(false);httpUpdate.onStart(otaStart);httpUpdate.onEnd(otaEnd);httpUpdate.onProgress(otaProgress);httpUpdate.onError(otaError);t_httpUpdate_return result=httpUpdate.update(otaNet,u);if(result==HTTP_UPDATE_OK){otaState(\"finished\",100,\"Update vollständig, Neustart folgt\");for(int i=0;i<8;i++){mq.loop();delay(100);}ESP.restart();}else if(result==HTTP_UPDATE_NO_UPDATES)otaState(\"no_update\",100,\"Keine Aktualisierung\");else otaState(\"failed\",0,httpUpdate.getLastErrorString());"
if old_8266 not in c or old_32 not in c:raise SystemExit('HTTPUpdate branches not found')
c=c.replace(old_8266,new_8266,1).replace(old_32,new_32,1)
cpp.write_text(c)
