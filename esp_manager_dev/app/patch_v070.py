from pathlib import Path

app_dir=Path(__file__).parent
main=app_dir/'main.py'
s=main.read_text()

# Persist an optional project-to-device association.
s=s.replace("m.setdefault('build_flags',[]);m.setdefault('ota_token'", "m.setdefault('build_flags',[]);m.setdefault('device_id','');m.setdefault('ota_token'")
s=s.replace("for k in ('display_name','board','version','monitor_speed','libraries','build_flags'):", "for k in ('display_name','board','version','monitor_speed','libraries','build_flags','device_id'):")

# Add OTA APIs before the hardware page function.
anchor='def hardware_page(project):'
ota_backend=r'''
def _build_by_id(project,build_id):
 for item in build_list(project):
  if item.get('id')==build_id:return item
 raise HTTPException(404,'Build nicht gefunden')

@app.post('/api/projects/{project}/device')
async def associate_device(project,payload:dict[str,Any]):
 device_id=clean(payload.get('device_id',''));m=load_meta(project);m['device_id']=device_id;save_meta(project,m);return {'project':clean(project),'device_id':device_id}

@app.post('/api/projects/{project}/devices/{device_id}/ota')
async def start_ota(project,device_id,payload:dict[str,Any]):
 if MQTT is None or not MQTT.is_connected():raise HTTPException(503,'ESP Manager ist nicht mit MQTT verbunden')
 m=load_meta(project);device_id=clean(device_id);build_id=payload.get('build_id')
 builds=build_list(project)
 if not builds:raise HTTPException(404,'Kein erfolgreicher Build vorhanden')
 build=_build_by_id(project,build_id) if build_id else builds[0]
 firmware=build['_dir']/'firmware.bin'
 if not firmware.exists():raise HTTPException(404,'OTA-Firmware fehlt')
 actual=hashlib.sha256(firmware.read_bytes()).hexdigest()
 if actual!=build.get('sha256'):raise HTTPException(409,'SHA256-Prüfung des Build-Artefakts fehlgeschlagen')
 base=str(OPT['public_base_url']).rstrip('/')
 url=f"{base}/firmware/{clean(project)}/{build['id']}/firmware.bin?token={m['ota_token']}"
 command={'token':m['ota_token'],'url':url,'version':build['version'],'build_id':build['id'],'sha256':actual,'size':build['size']}
 info=MQTT.publish(f'espmanager/{device_id}/cmd/ota',json.dumps(command),qos=1)
 if info.rc!=mqtt.MQTT_ERR_SUCCESS:raise HTTPException(503,f'MQTT-Publish fehlgeschlagen: {info.rc}')
 m['device_id']=device_id;save_meta(project,m)
 return {'ok':True,'device_id':device_id,'build_id':build['id'],'version':build['version'],'sha256':actual,'url':url}

@app.get('/firmware/{project}/{build_id}/firmware.bin')
def ota_firmware(project,build_id,token:str=''):
 m=load_meta(project)
 if token!=m['ota_token']:raise HTTPException(403,'Firmware-Token ungültig')
 build=_build_by_id(project,build_id);firmware=build['_dir']/'firmware.bin'
 if not firmware.exists():raise HTTPException(404,'Firmware fehlt')
 actual=hashlib.sha256(firmware.read_bytes()).hexdigest()
 if actual!=build.get('sha256'):raise HTTPException(409,'SHA256-Prüfung fehlgeschlagen')
 md5=hashlib.md5(firmware.read_bytes()).hexdigest();return FileResponse(firmware,media_type='application/octet-stream',headers={'X-Firmware-SHA256':actual,'X-Firmware-Version':str(build['version']),'x-MD5':md5,'Cache-Control':'no-store'})

'''
if anchor not in s:raise SystemExit('hardware page anchor missing')
s=s.replace(anchor,ota_backend+anchor,1)

# Replace hardware page with device association, selectable build and OTA flow.
start=s.index('def hardware_page(project):')
end=s.index("@app.get('/usb/{project}'",start)
page=r'''def hardware_page(project):
 m=load_meta(project);preferred=m.get('device_id') or clean(project)
 return """<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><script type='module' src='https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module'></script><style>body{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}.card{background:#1f2937;padding:16px;border-radius:14px;margin:12px 0}button,select{padding:8px;margin:3px}pre{background:#030712;padding:12px;min-height:150px;white-space:pre-wrap}a{color:#93c5fd}.ok{color:#86efac}.warn{color:#fbbf24}.bad{color:#fca5a5}progress{width:100%;height:24px}</style></head><body><h1>USB, OTA & Status: PROJECT</h1><div class='card'><h2>USB-Erstinstallation</h2><div id='manifestState'>Prüfe Manifest ...</div><esp-web-install-button id='installer'></esp-web-install-button></div><div class='card'><h2>Serieller Monitor</h2><button id='connectButton' onclick='connectSerial()'>Verbinden</button><button id='disconnectButton' onclick='disconnectSerial()' disabled>Trennen</button><button onclick='document.getElementById("serialLog").textContent=""'>Leeren</button><span id='serialState'>Nicht verbunden</span><pre id='serialLog'></pre></div><div class='card'><h2>Gerät und MQTT</h2><div id='mqttConnection'>Prüfe MQTT ...</div><label>Gerät: <select id='deviceSelect' onchange='selectDevice()'></select></label><button onclick='refreshDevices()'>Aktualisieren</button><pre id='deviceStatus'>Noch kein Status</pre></div><div class='card'><h2>OTA-Testaktualisierung</h2><p class='warn'>Nur verwenden, wenn das gewählte Gerät online ist. Der ESP lädt die reine Anwendungsfirmware und startet nach Erfolg neu.</p><label>Firmware-Build: <select id='buildSelect'></select></label><button id='otaButton' onclick='startOta()'>Über WLAN aktualisieren</button><progress id='otaProgress' max='100' value='0'></progress><div id='otaState'>Bereit</div><pre id='otaLog'></pre></div><button onclick='goBack()'>Zurück zum ESP Manager</button><script>const manifestState=document.getElementById('manifestState'),serialLog=document.getElementById('serialLog'),serialState=document.getElementById('serialState'),connectButton=document.getElementById('connectButton'),disconnectButton=document.getElementById('disconnectButton'),mqttConnection=document.getElementById('mqttConnection'),deviceSelect=document.getElementById('deviceSelect'),deviceStatus=document.getElementById('deviceStatus'),buildSelect=document.getElementById('buildSelect'),otaButton=document.getElementById('otaButton'),otaProgress=document.getElementById('otaProgress'),otaState=document.getElementById('otaState'),otaLog=document.getElementById('otaLog');let port=null,reader=null,readLoopPromise=null,keepReading=false,selectedDevice='PREFERRED';const decoder=new TextDecoder();const marker='/usb/';function appBase(){const i=location.pathname.indexOf(marker);if(i<0)throw Error('Ingress-Basispfad fehlt');return location.pathname.slice(0,i+1)}function apiUrl(path){return appBase()+path.replace(/^\//,'')}function goBack(){location.href=appBase()}async function checkManifest(){try{let base=location.pathname.endsWith('/')?location.pathname:location.pathname+'/';let url=base+'manifest.json';document.getElementById('installer').setAttribute('manifest',url);let r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(await r.text());let m=await r.json();manifestState.className='ok';manifestState.textContent='Bereit: '+m.name+' '+m.version+' / '+m.builds[0].chipFamily}catch(e){manifestState.className='bad';manifestState.textContent='Manifest-Fehler: '+e.message}}async function readSerial(){try{while(keepReading&&port&&port.readable){reader=port.readable.getReader();try{while(keepReading){let r=await reader.read();if(r.done)break;if(r.value){serialLog.textContent+=decoder.decode(r.value,{stream:true});serialLog.scrollTop=serialLog.scrollHeight}}}finally{try{reader.releaseLock()}catch(e){}reader=null}}}catch(e){if(keepReading)serialLog.textContent+='\\nLesefehler: '+e.message}}async function connectSerial(){if(port)return;try{port=await navigator.serial.requestPort();await port.open({baudRate:115200});keepReading=true;serialState.textContent='Verbunden';connectButton.disabled=true;disconnectButton.disabled=false;readLoopPromise=readSerial()}catch(e){port=null;serialState.textContent='Fehler: '+e.message}}async function disconnectSerial(){if(!port)return;keepReading=false;disconnectButton.disabled=true;try{if(reader)await reader.cancel();if(readLoopPromise)await readLoopPromise;await port.close();serialState.textContent='Getrennt'}catch(e){serialState.textContent='Trennfehler: '+e.message}finally{reader=null;readLoopPromise=null;port=null;connectButton.disabled=false}}async function loadBuilds(){let r=await fetch(apiUrl('api/projects/PROJECT/builds'),{cache:'no-store'});if(!r.ok)throw Error(await r.text());let builds=await r.json();buildSelect.innerHTML=builds.map(b=>'<option value="'+b.id+'">'+b.version+' | '+new Date(b.built_at*1000).toLocaleString()+' | '+b.size+' B</option>').join('');otaButton.disabled=!builds.length}async function refreshDevices(){try{let mr=await fetch(apiUrl('api/mqtt/status'),{cache:'no-store'});if(!mr.ok)throw Error(await mr.text());let ms=await mr.json();mqttConnection.className=ms.connected?'ok':'bad';mqttConnection.textContent=ms.connected?'Add-on mit MQTT verbunden. Geräte: '+ms.device_count:'Add-on nicht mit MQTT verbunden';let r=await fetch(apiUrl('api/devices'),{cache:'no-store'});if(!r.ok)throw Error(await r.text());let ds=await r.json();deviceSelect.innerHTML='<option value="">Gerät auswählen</option>'+ds.map(d=>'<option value="'+d.device_id+'">'+d.device_id+(d.ip?' - '+d.ip:'')+'</option>').join('');if(ds.some(d=>d.device_id===selectedDevice))deviceSelect.value=selectedDevice;else if(ds.length===1){selectedDevice=ds[0].device_id;deviceSelect.value=selectedDevice}await refreshSelected()}catch(e){mqttConnection.className='bad';mqttConnection.textContent='MQTT/API-Fehler: '+e.message}}function selectDevice(){selectedDevice=deviceSelect.value;associateDevice();refreshSelected()}async function associateDevice(){if(!selectedDevice)return;await fetch(apiUrl('api/projects/PROJECT/device'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:selectedDevice})})}async function refreshSelected(){if(!selectedDevice){deviceStatus.textContent='Gerät auswählen';return}try{let r=await fetch(apiUrl('api/devices/'+encodeURIComponent(selectedDevice)),{cache:'no-store'});if(!r.ok)throw Error(await r.text());let d=await r.json();deviceStatus.textContent=JSON.stringify(d,null,2);let o=d.ota_progress;if(o){try{let x=JSON.parse(o);otaState.textContent=x.state+(x.message?' - '+x.message:'');if(Number.isFinite(x.percent))otaProgress.value=x.percent;otaLog.textContent=o+'\\n'+otaLog.textContent}catch(e){otaState.textContent=o}}}catch(e){deviceStatus.textContent='Kein Status: '+e.message}}async function startOta(){if(!selectedDevice)return alert('Gerät auswählen');if(!buildSelect.value)return alert('Build auswählen');if(!confirm('OTA-Test für '+selectedDevice+' starten?'))return;otaButton.disabled=true;otaProgress.value=0;otaState.textContent='OTA-Auftrag wird gesendet';try{let r=await fetch(apiUrl('api/projects/PROJECT/devices/'+encodeURIComponent(selectedDevice)+'/ota'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({build_id:buildSelect.value})});if(!r.ok)throw Error(await r.text());let x=await r.json();otaState.textContent='Auftrag gesendet: '+x.version;otaLog.textContent=JSON.stringify(x,null,2)}catch(e){otaState.textContent='OTA-Fehler: '+e.message}finally{otaButton.disabled=false}}checkManifest();loadBuilds().catch(e=>otaState.textContent='Buildfehler: '+e.message);refreshDevices();setInterval(refreshDevices,3000)</script></body></html>""".replace('PROJECT',clean(project)).replace('PREFERRED',preferred)
'''
s=s[:start]+page+s[end:]
s=s.replace('ESP Manager Dev 0.6.4-dev','ESP Manager Dev 0.7.0-dev').replace('ESP Manager 0.6.4','ESP Manager 0.7.0')
main.write_text(s)

cpp=app_dir/'templates/lib/ESPManager/src/ESPManager.cpp'
c=cpp.read_text()
callback_anchor='static void callback(char*t,byte*p,unsigned int l){String b;for(unsigned int i=0;i<l;i++)b+=(char)p[i];ESPManager.handleCommand(String(t),b);}'
ota_helpers=r'''
static void otaState(const String&state,int percent,const String&message){JsonDocument d;d["state"]=state;d["percent"]=percent;d["message"]=message;String out;serializeJson(d,out);Serial.println(String("[ESPManager] OTA ")+out);if(mq.connected())mq.publish((base()+"/ota/progress").c_str(),out.c_str(),true);}
static void otaStart(){otaState("started",0,"Download gestartet");}
static void otaEnd(){otaState("finished",100,"Update vollständig, Neustart folgt");}
static void otaProgress(int current,int total){int percent=total>0?(current*100/total):0;otaState("progress",percent,String(current)+"/"+String(total));}
static void otaError(int error){otaState("failed",0,String("Fehlercode ")+String(error));}
'''
if ota_helpers.strip() not in c:
 if callback_anchor not in c:raise SystemExit('MQTT callback anchor missing')
 c=c.replace(callback_anchor,callback_anchor+ota_helpers,1)
old='''if(t.endsWith("/cmd/ota")){String u=d["url"]|"";if(!u.length())return;
#ifdef ESP8266
ESPhttpUpdate.update(net,u);
#else
httpUpdate.update(net,u);
#endif
}'''
new='''if(t.endsWith("/cmd/ota")){String u=d["url"]|"";String expected=d["sha256"]|"";if(!u.length()){otaState("failed",0,"URL fehlt");return;}otaState("validating",0,String("Server-SHA256 ")+expected);
#ifdef ESP8266
ESPhttpUpdate.onStart(otaStart);ESPhttpUpdate.onEnd(otaEnd);ESPhttpUpdate.onProgress(otaProgress);ESPhttpUpdate.onError(otaError);t_httpUpdate_return result=ESPhttpUpdate.update(net,u);if(result==HTTP_UPDATE_NO_UPDATES)otaState("no_update",100,"Keine Aktualisierung");else if(result==HTTP_UPDATE_FAILED)otaState("failed",0,ESPhttpUpdate.getLastErrorString());
#else
httpUpdate.onStart(otaStart);httpUpdate.onEnd(otaEnd);httpUpdate.onProgress(otaProgress);httpUpdate.onError(otaError);t_httpUpdate_return result=httpUpdate.update(net,u);if(result==HTTP_UPDATE_NO_UPDATES)otaState("no_update",100,"Keine Aktualisierung");else if(result==HTTP_UPDATE_FAILED)otaState("failed",0,httpUpdate.getLastErrorString());
#endif
}'''
if old not in c:raise SystemExit('OTA branch missing')
c=c.replace(old,new,1)
cpp.write_text(c)
