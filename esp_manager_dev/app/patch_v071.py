from pathlib import Path

app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()

# Report command size for diagnostics and refuse unexpectedly huge commands.
old="""command={'token':m['ota_token'],'url':url,'version':build['version'],'build_id':build['id'],'sha256':actual,'size':build['size']}
 info=MQTT.publish(f'espmanager/{device_id}/cmd/ota',json.dumps(command),qos=1)"""
new="""command={'token':m['ota_token'],'url':url,'version':build['version'],'build_id':build['id'],'sha256':actual,'size':build['size']}
 command_json=json.dumps(command,separators=(',',':'))
 command_bytes=len(command_json.encode('utf-8'))
 if command_bytes>1536:raise HTTPException(413,f'OTA-Kommando zu groß: {command_bytes} Bytes')
 info=MQTT.publish(f'espmanager/{device_id}/cmd/ota',command_json,qos=1)"""
if old not in s:raise SystemExit('OTA command block not found')
s=s.replace(old,new,1)
old_return="return {'ok':True,'device_id':device_id,'build_id':build['id'],'version':build['version'],'sha256':actual,'url':url}"
new_return="return {'ok':True,'device_id':device_id,'build_id':build['id'],'version':build['version'],'sha256':actual,'url':url,'command_bytes':command_bytes}"
if old_return not in s:raise SystemExit('OTA response block not found')
s=s.replace(old_return,new_return,1)
s=s.replace('ESP Manager Dev 0.7.0-dev','ESP Manager Dev 0.7.1-dev').replace('ESP Manager 0.7.0','ESP Manager 0.7.1')
main.write_text(s)

cpp=app_dir/'templates/lib/ESPManager/src/ESPManager.cpp'
c=cpp.read_text()
old_setup='mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mq.setCallback(callback);ensureMqtt();'
new_setup='mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);if(!mq.setBufferSize(2048))Serial.println("[ESPManager] WARNUNG: MQTT-Puffer konnte nicht auf 2048 Bytes gesetzt werden");mq.setCallback(callback);ensureMqtt();'
if old_setup not in c:raise SystemExit('MQTT setup block not found')
c=c.replace(old_setup,new_setup,1)
# Emit an immediate acknowledgement once token and JSON were accepted.
old_token='if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Kommando abgelehnt");return;}if(t.endsWith("/cmd/restart"))'
new_token='if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Kommando abgelehnt");return;}if(t.endsWith("/cmd/ota"))otaState("received",0,String("MQTT-Kommando empfangen, Bytes=")+String(p.length()));if(t.endsWith("/cmd/restart"))'
if old_token not in c:raise SystemExit('Token command block not found')
c=c.replace(old_token,new_token,1)
cpp.write_text(c)
