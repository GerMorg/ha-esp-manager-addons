from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()

s=s.replace('import yaml\n', 'import yaml\nimport paho.mqtt.client as mqtt\n')
old_app="app=FastAPI(title='ESP Manager'); JOBS={}; PROCESSES={}"
new_app="app=FastAPI(title='ESP Manager'); JOBS={}; PROCESSES={}; DEVICES={}; MQTT_CLIENT=None"
if old_app not in s: raise SystemExit('app globals block not found')
s=s.replace(old_app,new_app)

startup_code="""
def _mqtt_connect(client,userdata,flags,reason_code,properties=None):
    client.subscribe('espmanager/+/status')
    client.subscribe('espmanager/+/availability')
    client.subscribe('espmanager/+/log')
    client.subscribe('espmanager/+/ota/progress')

def _mqtt_message(client,userdata,msg):
    parts=msg.topic.split('/')
    if len(parts)<3:return
    device,kind=parts[1],parts[2]
    entry=DEVICES.setdefault(device,{'device_id':device,'logs':[]})
    entry['last_seen']=int(time.time())
    text=msg.payload.decode(errors='replace')
    if kind=='status':
        try:entry.update(json.loads(text))
        except Exception:entry['raw_status']=text
    elif kind=='availability':entry['availability']=text
    elif kind=='log':entry['logs']=(entry.get('logs',[])+[{'ts':int(time.time()),'line':text}])[-200:]
    elif kind=='ota':entry['ota_progress']=text

@app.on_event('startup')
def _start_mqtt_status():
    global MQTT_CLIENT
    options={'mqtt_host':'core-mosquitto','mqtt_port':1883,'mqtt_username':'','mqtt_password':''}
    options_file=Path('/data/options.json')
    if options_file.exists():
        try:options.update(json.loads(options_file.read_text()))
        except Exception:pass
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='esp-manager-status')
    if options.get('mqtt_username'):client.username_pw_set(options['mqtt_username'],options.get('mqtt_password'))
    client.on_connect=_mqtt_connect;client.on_message=_mqtt_message
    try:client.connect(options['mqtt_host'],int(options['mqtt_port']),60);client.loop_start();MQTT_CLIENT=client
    except Exception as exc:print('MQTT status disabled:',exc)

"""
anchor='def clean(v):'
if anchor not in s: raise SystemExit('clean anchor not found')
s=s.replace(anchor,startup_code+anchor,1)

s=s.replace('<option value="esp12e">ESP8266 ESP-12E</option>', '<option value="nodemcuv2">NodeMCU 1.0 ESP8266MOD</option><option value="esp12e">ESP8266 ESP-12E</option>')
old="<button onclick=\"openP('${x.name}')\">Öffnen</button><button onclick=\"quickBuild('${x.name}')\">Build</button>"
new="<button onclick=\"openP('${x.name}')\">Öffnen</button><button onclick=\"quickBuild('${x.name}')\">Build</button><a href=\"usb/${x.name}\" style=\"color:#93c5fd;margin-left:8px\">USB & Status</a>"
if old not in s: raise SystemExit('project card block not found')
s=s.replace(old,new)

hardware_code='''

def latest_successful_build(project):
    root=FIRMWARE/clean(project);builds=[]
    if root.exists():
        for mf in root.glob('*/manifest.json'):
            try:
                data=json.loads(mf.read_text());data['_dir']=mf.parent
                if (mf.parent/'firmware.bin').exists():builds.append(data)
            except Exception:pass
    if not builds:raise HTTPException(404,'Noch keine erfolgreiche Firmware vorhanden. Bitte zuerst kompilieren.')
    return sorted(builds,key=lambda x:x.get('built_at',0),reverse=True)[0]

@app.get('/usb/{project}',response_class=HTMLResponse)
def usb_test_page(project):
    m=ensure_defaults(meta(project))
    page="""<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Hardwaretest PROJECT</title><script type='module' src='https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module'></script><style>body{font-family:system-ui;margin:20px;background:#111827;color:#e5e7eb}.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:16px;margin:12px 0}button{padding:9px;margin:4px;background:#2563eb;color:white;border:0;border-radius:8px}pre{background:#030712;padding:12px;min-height:220px;max-height:430px;overflow:auto;white-space:pre-wrap}a{color:#93c5fd}.warn{color:#fbbf24}</style></head><body><h1>Hardwaretest: PROJECT</h1><section class='card'><h2>1. USB-Erstinstallation</h2><p>NodeMCU per USB an diesen Laptop anschließen. Diese Installation überschreibt die vorhandene Firmware.</p><p class='warn'>Web Serial benötigt einen unterstützten Browser und HTTPS.</p><esp-web-install-button manifest='manifest.json'></esp-web-install-button></section><section class='card'><h2>2. Serieller Statusmonitor</h2><button onclick='connectSerial()'>Seriell verbinden</button><button onclick='disconnectSerial()'>Trennen</button><button onclick='clearLog()'>Leeren</button><span id='serialState'>Nicht verbunden</span><pre id='serialLog'></pre></section><section class='card'><h2>3. WLAN-Ersteinrichtung</h2><ol><li>Nach dem Neustart nach <b>ESPManager-PROJECT</b> suchen.</li><li>Verbinden und das Portal öffnen.</li><li>Falls nötig <b>192.168.4.1</b> aufrufen.</li><li>Heim-WLAN auswählen und Passwort speichern.</li></ol></section><section class='card'><h2>4. MQTT-Gerätestatus</h2><button onclick='refreshStatus()'>Status aktualisieren</button><pre id='deviceStatus'>Noch kein Status</pre></section><p><a href='../..'>Zurück</a></p><script>let port=null,reader=null,reading=false;async function connectSerial(){try{if(!navigator.serial)throw Error('Web Serial wird in diesem Browser oder Kontext nicht unterstützt.');port=await navigator.serial.requestPort();await port.open({baudRate:115200});serialState.textContent='Verbunden';reading=true;const decoder=new TextDecoderStream();port.readable.pipeTo(decoder.writable);reader=decoder.readable.getReader();while(reading){const r=await reader.read();if(r.done)break;serialLog.textContent+=r.value;serialLog.scrollTop=serialLog.scrollHeight}}catch(e){serialState.textContent='Fehler: '+e.message}}async function disconnectSerial(){reading=false;try{if(reader){await reader.cancel();reader.releaseLock()}if(port)await port.close()}catch(e){}reader=null;port=null;serialState.textContent='Nicht verbunden'}function clearLog(){serialLog.textContent=''}async function refreshStatus(){try{let r=await fetch('../../api/devices/PROJECT');if(!r.ok)throw Error(await r.text());deviceStatus.textContent=JSON.stringify(await r.json(),null,2)}catch(e){deviceStatus.textContent='Noch kein MQTT-Status: '+e.message}}setInterval(refreshStatus,5000);refreshStatus();</script></body></html>"""
    return HTMLResponse(page.replaceAll('PROJECT',clean(project)))

@app.get('/usb/{project}/manifest.json')
def usb_manifest(project):
    m=ensure_defaults(meta(project));b=latest_successful_build(project)
    chip='ESP8266' if m['board'] in ('esp12e','nodemcuv2') else 'ESP32'
    return {'name':m.get('display_name',project),'version':b.get('version',m.get('version','0.1.0')),'new_install_prompt_erase':True,'builds':[{'chipFamily':chip,'parts':[{'path':'firmware.bin','offset':0}]}]}

@app.get('/usb/{project}/firmware.bin')
def usb_firmware(project):
    b=latest_successful_build(project);return FileResponse(b['_dir']/'firmware.bin',media_type='application/octet-stream',filename=f'{clean(project)}.bin')

@app.get('/api/devices/{device}')
def device_status(device):
    d=clean(device)
    if d not in DEVICES:raise HTTPException(404,'Gerät hat sich noch nicht über MQTT gemeldet.')
    return DEVICES[d]
'''
s += hardware_code
p.write_text(s)
