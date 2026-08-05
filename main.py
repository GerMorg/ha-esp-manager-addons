from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
import yaml
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

ROOT = Path('/config/esp_manager')
PROJECT_ROOT = ROOT / 'projects'
FIRMWARE_ROOT = ROOT / 'firmware'
OPTIONS_FILE = Path('/data/options.json')
TEMPLATE_ROOT = Path(__file__).parent / 'templates'
for d in [PROJECT_ROOT, FIRMWARE_ROOT]:
    d.mkdir(parents=True, exist_ok=True)


def read_options() -> dict[str, Any]:
    defaults = {
        'mqtt_host': 'core-mosquitto',
        'mqtt_port': 1883,
        'mqtt_username': '',
        'mqtt_password': '',
        'discovery_prefix': 'homeassistant',
        'public_base_url': 'http://homeassistant.local:8099',
    }
    if OPTIONS_FILE.exists():
        try:
            defaults.update(json.loads(OPTIONS_FILE.read_text()))
        except Exception:
            pass
    return defaults


OPTIONS = read_options()
app = FastAPI(title='ESP Manager')
DEVICES: dict[str, dict[str, Any]] = {}
BUILD_JOBS: dict[str, dict[str, Any]] = {}
MQTT_CLIENT: mqtt.Client | None = None


def safe_name(name: str) -> str:
    cleaned = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name.strip())
    cleaned = '_'.join(part for part in cleaned.split('_') if part)
    if not cleaned:
        raise HTTPException(400, 'Invalid name')
    return cleaned[:64]


def project_dir(project: str) -> Path:
    p = PROJECT_ROOT / safe_name(project)
    if not p.exists():
        raise HTTPException(404, 'Project not found')
    return p


def load_meta(project: str) -> dict[str, Any]:
    return yaml.safe_load((project_dir(project) / 'espmanager.yaml').read_text())


def save_meta(project: str, meta: dict[str, Any]) -> None:
    (project_dir(project) / 'espmanager.yaml').write_text(yaml.safe_dump(meta, sort_keys=False))


def public_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(meta)
    out.pop('ota_token', None)
    return out


def copy_agent_library(target: Path) -> None:
    dst = target / 'lib' / 'ESPManager'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(TEMPLATE_ROOT / 'lib' / 'ESPManager', dst)


def write_platformio(project_path: Path, meta: dict[str, Any]) -> None:
    board = meta['board']
    platform = 'espressif8266' if board in {'esp12e', 'nodemcuv2'} else 'espressif32'
    name = meta['name']
    version = meta.get('version', '0.1.0')
    token = meta['ota_token']
    project_path.joinpath('platformio.ini').write_text(f'''[env:{board}]
platform = {platform}
board = {board}
framework = arduino
monitor_speed = 115200
lib_deps =
  knolleary/PubSubClient@^2.8
  bblanchon/ArduinoJson@^7.2.1
  tzapu/WiFiManager@^2.0.17
build_flags =
  -D ESPMANAGER_DEVICE_ID=\\"{name}\\"
  -D ESPMANAGER_FW_VERSION=\\"{version}\\"
  -D ESPMANAGER_MQTT_HOST=\\"{OPTIONS.get('mqtt_host', 'core-mosquitto')}\\"
  -D ESPMANAGER_MQTT_PORT={int(OPTIONS.get('mqtt_port', 1883))}
  -D ESPMANAGER_MQTT_USER=\\"{OPTIONS.get('mqtt_username', '')}\\"
  -D ESPMANAGER_MQTT_PASS=\\"{OPTIONS.get('mqtt_password', '')}\\"
  -D ESPMANAGER_DISCOVERY_PREFIX=\\"{OPTIONS.get('discovery_prefix', 'homeassistant')}\\"
  -D ESPMANAGER_OTA_TOKEN=\\"{token}\\"
''')


def safe_project_file(project: str, rel_path: str) -> Path:
    allowed_prefixes = ('src/', 'include/', 'lib/')
    if rel_path.startswith('/') or '..' in Path(rel_path).parts or not rel_path.startswith(allowed_prefixes):
        raise HTTPException(400, 'File path not allowed')
    p = project_dir(project) / rel_path
    if not p.exists():
        raise HTTPException(404, 'File not found')
    return p


def mqtt_on_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe('espmanager/+/status')
    client.subscribe('espmanager/+/availability')
    client.subscribe('espmanager/+/ota/progress')
    client.subscribe('espmanager/+/log')


def mqtt_on_message(client, userdata, msg):
    parts = msg.topic.split('/')
    if len(parts) < 3:
        return
    device_id, kind = parts[1], parts[2]
    entry = DEVICES.setdefault(device_id, {'device_id': device_id, 'logs': []})
    entry['last_seen'] = int(time.time())
    payload = msg.payload.decode(errors='replace')
    if kind == 'status':
        try:
            entry.update(json.loads(payload))
        except Exception:
            entry['status_payload'] = payload
    elif kind == 'availability':
        entry['availability'] = payload
    elif kind == 'ota' and len(parts) > 3:
        entry['ota_progress'] = payload
    elif kind == 'log':
        entry['logs'].append({'ts': int(time.time()), 'line': payload})
        del entry['logs'][:-300]


@app.on_event('startup')
def startup() -> None:
    global MQTT_CLIENT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='esp-manager-addon')
    if OPTIONS.get('mqtt_username'):
        client.username_pw_set(OPTIONS.get('mqtt_username'), OPTIONS.get('mqtt_password'))
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message
    try:
        client.connect(OPTIONS.get('mqtt_host', 'core-mosquitto'), int(OPTIONS.get('mqtt_port', 1883)), 60)
        client.loop_start()
        MQTT_CLIENT = client
    except Exception as exc:
        print(f'MQTT disabled: {exc}')


@app.get('/', response_class=HTMLResponse)
def ui() -> HTMLResponse:
    return HTMLResponse("""
<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ESP Manager</title>
<style>
body{font-family:system-ui;margin:24px;background:#111827;color:#e5e7eb}h1,h2{color:white}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}.card{background:#1f2937;border:1px solid #374151;border-radius:14px;padding:16px;margin:12px 0}button,input,select,textarea{font:inherit;padding:8px;margin:4px;border-radius:8px;border:1px solid #374151}button{background:#2563eb;color:white;cursor:pointer}textarea{width:100%;height:360px;background:#030712;color:#e5e7eb;font-family:ui-monospace,Consolas,monospace}pre{background:#030712;padding:12px;white-space:pre-wrap;max-height:440px;overflow:auto;border-radius:10px}a{color:#93c5fd;margin-left:8px}.muted{color:#9ca3af}.ok{color:#86efac}.bad{color:#fca5a5}
</style></head><body>
<h1>ESP Manager 0.3.0</h1>
<div class='grid'>
<section class='card'><h2>Neues Projekt</h2><input id='project_name' placeholder='stromzaehler_sagemcom'><select id='project_board'><option value='esp32dev'>ESP32 DevKit</option><option value='esp12e'>ESP8266 ESP-12E</option><option value='esp32-s3-devkitc-1'>ESP32-S3</option><option value='esp32-c3-devkitm-1'>ESP32-C3</option><option value='esp32-s2-saola-1'>ESP32-S2</option></select><button onclick='createProject()'>Anlegen</button></section>
<section class='card'><h2>Projekte</h2><div id='projects'>Lade ...</div></section>
<section class='card'><h2>Geräte</h2><div id='devices'>Lade ...</div></section>
</div>
<section class='card'><h2>Editor <span class='muted' id='editor_title'></span></h2><select id='file_select' onchange='loadFile()'><option value='src/device.cpp'>src/device.cpp</option><option value='src/main.cpp'>src/main.cpp</option></select><button onclick='saveFile()'>Speichern</button><textarea id='editor'></textarea></section>
<section class='card'><h2>Live Build Log</h2><div id='build_status' class='muted'>Bereit.</div><pre id='log'>Noch kein Build gestartet.</pre></section>
<script>
let selectedProject=null; let currentJob=null; let pollTimer=null;
async function api(path,opts){const r=await fetch(path,opts);if(!r.ok){throw new Error(await r.text())}return await r.json()}
async function textApi(path,opts){const r=await fetch(path,opts);if(!r.ok){throw new Error(await r.text())}return await r.text()}
async function refresh(){await refreshProjects(); await refreshDevices();}
async function refreshProjects(){const ps=await api('api/projects'); projects.innerHTML=ps.map(p=>`<div class='card'><b>${p.name}</b><br>Board: ${p.board}<br>Version: ${p.version||'-'}<br><button onclick="selectProject('${p.name}')">Öffnen</button><button onclick="startBuild('${p.name}')">Kompilieren</button><a href='webflash/${p.name}'>Initial flashen</a><a href='api/projects/${p.name}/download'>Firmware</a></div>`).join('')||'Keine Projekte'}
async function refreshDevices(){const ds=await api('api/devices'); devices.innerHTML=ds.map(d=>`<div class='card'><b>${d.device_id}</b><br>Status: ${d.availability||'unbekannt'}<br>IP: ${d.ip||'-'}<br>FW: ${d.firmware_version||'-'}<br>RSSI: ${d.rssi||'-'}<br><button onclick="restartDevice('${d.device_id}')">Neustart</button><button onclick="otaDevice('${d.device_id}')">OTA</button></div>`).join('')||'Noch keine Geräte erkannt'}
async function createProject(){try{await api('api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:project_name.value,board:project_board.value})});project_name.value='';await refreshProjects()}catch(e){alert('Anlegen fehlgeschlagen: '+e.message)}}
async function selectProject(p){selectedProject=p; editor_title.textContent='- '+p; await loadFile()}
async function loadFile(){if(!selectedProject)return; try{editor.value=await textApi(`api/projects/${selectedProject}/file?path=${encodeURIComponent(file_select.value)}`)}catch(e){alert('Laden fehlgeschlagen: '+e.message)}}
async function saveFile(){if(!selectedProject)return; try{await fetch(`api/projects/${selectedProject}/file?path=${encodeURIComponent(file_select.value)}`,{method:'PUT',headers:{'Content-Type':'text/plain'},body:editor.value}); alert('Gespeichert')}catch(e){alert('Speichern fehlgeschlagen: '+e.message)}}
async function startBuild(p){try{const r=await api(`api/projects/${p}/build-start`,{method:'POST'});currentJob=r.job_id;log.textContent='';build_status.textContent='Build gestartet: '+currentJob;if(pollTimer)clearInterval(pollTimer);pollTimer=setInterval(pollBuild,1000);pollBuild()}catch(e){alert('Build Start fehlgeschlagen: '+e.message)}}
async function pollBuild(){if(!currentJob)return; const r=await api(`api/builds/${currentJob}`);log.textContent=r.log||'';build_status.innerHTML=`Status: <b class='${r.status==='success'?'ok':r.status==='failed'?'bad':''}'>${r.status}</b>`;log.scrollTop=log.scrollHeight;if(['success','failed','timeout'].includes(r.status)){clearInterval(pollTimer);pollTimer=null;await refreshProjects();}}
async function restartDevice(id){try{await api(`api/devices/${id}/restart`,{method:'POST'})}catch(e){alert('Neustart fehlgeschlagen: '+e.message)}}
async function otaDevice(id){try{const r=await api(`api/devices/${id}/ota`,{method:'POST'});alert('OTA gesendet: '+r.sha256)}catch(e){alert('OTA fehlgeschlagen: '+e.message)}}
refresh(); setInterval(refreshDevices,5000);
</script></body></html>
""")


@app.get('/api/projects')
def list_projects():
    out = []
    for p in sorted(PROJECT_ROOT.iterdir()):
        f = p / 'espmanager.yaml'
        if f.exists():
            out.append(public_meta(yaml.safe_load(f.read_text())))
    return out


@app.post('/api/projects')
async def create_project(payload: dict[str, Any]):
    name = safe_name(payload.get('name', ''))
    board = payload.get('board', 'esp32dev')
    p = PROJECT_ROOT / name
    if p.exists():
        raise HTTPException(409, 'Project already exists')
    for sub in ['src', 'include', 'lib', 'builds']:
        (p / sub).mkdir(parents=True, exist_ok=True)
    meta = {'name': name, 'display_name': name.replace('_', ' ').title(), 'board': board, 'version': '0.1.0', 'mode': 'wrapper', 'ota_token': secrets.token_urlsafe(32)}
    save_meta(name, meta)
    write_platformio(p, meta)
    shutil.copytree(TEMPLATE_ROOT / 'src', p / 'src', dirs_exist_ok=True)
    copy_agent_library(p)
    return public_meta(meta)


@app.get('/api/projects/{project}/file', response_class=PlainTextResponse)
def get_project_file(project: str, path: str):
    return safe_project_file(project, path).read_text(errors='replace')


@app.put('/api/projects/{project}/file')
async def put_project_file(project: str, path: str, request: Request):
    body = (await request.body()).decode(errors='replace')
    safe_project_file(project, path).write_text(body)
    return {'ok': True}


@app.post('/api/projects/{project}/build-start')
def build_start(project: str):
    project = safe_name(project)
    _ = project_dir(project)
    job_id = f'{project}-{int(time.time())}'
    BUILD_JOBS[job_id] = {'job_id': job_id, 'project': project, 'status': 'queued', 'log': '', 'started_at': int(time.time())}
    threading.Thread(target=build_worker, args=(job_id,), daemon=True).start()
    return {'job_id': job_id}


def append_job(job_id: str, text: str) -> None:
    job = BUILD_JOBS[job_id]
    job['log'] = (job.get('log', '') + text)[-40000:]


def build_worker(job_id: str) -> None:
    job = BUILD_JOBS[job_id]
    project = job['project']
    p = project_dir(project)
    meta = load_meta(project)
    if 'ota_token' not in meta:
        meta['ota_token'] = secrets.token_urlsafe(32)
        save_meta(project, meta)
    write_platformio(p, meta)
    copy_agent_library(p)
    job['status'] = 'running'
    try:
        proc = subprocess.Popen(['/opt/esp_manager/venv/bin/pio', 'run'], cwd=p, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            append_job(job_id, line)
        code = proc.wait(timeout=30)
        (p / 'builds' / 'last_build_log.txt').write_text(job['log'], errors='replace')
        if code != 0:
            job['status'] = 'failed'
            return
        fw = p / '.pio' / 'build' / meta['board'] / 'firmware.bin'
        data = fw.read_bytes()
        out = FIRMWARE_ROOT / project
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fw, out / 'firmware.bin')
        manifest = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'version': meta.get('version', '0.1.0'), 'built_at': int(time.time())}
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        job['manifest'] = manifest
        job['status'] = 'success'
    except subprocess.TimeoutExpired:
        job['status'] = 'timeout'
        append_job(job_id, '\nBuild timeout.\n')
    except Exception as exc:
        job['status'] = 'failed'
        append_job(job_id, f'\nBuild exception: {exc}\n')


@app.get('/api/builds/{job_id}')
def build_status(job_id: str):
    if job_id not in BUILD_JOBS:
        raise HTTPException(404, 'Build job not found')
    return BUILD_JOBS[job_id]


@app.get('/api/projects/{project}/download')
def download(project: str):
    f = FIRMWARE_ROOT / safe_name(project) / 'firmware.bin'
    if not f.exists():
        raise HTTPException(404, 'Firmware not built yet')
    return FileResponse(f, filename=f'{safe_name(project)}.bin')


@app.get('/api/devices')
def devices():
    return sorted(DEVICES.values(), key=lambda d: d.get('device_id', ''))


@app.post('/api/devices/{device_id}/restart')
def restart_device(device_id: str):
    if MQTT_CLIENT is None:
        raise HTTPException(503, 'MQTT not connected')
    project = safe_name(device_id)
    meta = load_meta(project)
    MQTT_CLIENT.publish(f'espmanager/{project}/cmd/restart', json.dumps({'cmd': 'restart', 'token': meta.get('ota_token', '')}))
    return {'ok': True}


@app.post('/api/devices/{device_id}/ota')
def ota_device(device_id: str):
    if MQTT_CLIENT is None:
        raise HTTPException(503, 'MQTT not connected')
    project = safe_name(device_id)
    meta = load_meta(project)
    manifest_file = FIRMWARE_ROOT / project / 'manifest.json'
    if not manifest_file.exists():
        raise HTTPException(404, 'Build firmware first')
    manifest = json.loads(manifest_file.read_text())
    base_url = str(OPTIONS.get('public_base_url', 'http://homeassistant.local:8099')).rstrip('/')
    token = meta.get('ota_token', '')
    url = f'{base_url}/firmware/{project}/firmware.bin?token={token}'
    payload = {'cmd': 'ota', 'token': token, 'url': url, 'sha256': manifest['sha256'], 'size': manifest['size'], 'version': manifest['version']}
    MQTT_CLIENT.publish(f'espmanager/{project}/cmd/ota', json.dumps(payload))
    return {'ok': True, 'sha256': manifest['sha256']}


@app.get('/webflash/{project}', response_class=HTMLResponse)
def webflash(project: str):
    project_dir(project)
    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><script type='module' src='https://unpkg.com/esp-web-tools@10/dist/web/install-button.js?module'></script></head><body><h1>Initial Flash {project}</h1><p>Erst kompilieren, dann ESP per USB an diesen Laptop anschliessen.</p><esp-web-install-button manifest='manifest.json'></esp-web-install-button><p><a href='../..'>Zurück</a></p></body></html>""")


@app.get('/webflash/{project}/manifest.json')
def web_manifest(project: str):
    meta = load_meta(project)
    f = FIRMWARE_ROOT / safe_name(project) / 'firmware.bin'
    if not f.exists():
        raise HTTPException(404, 'Build first')
    chip = 'ESP8266' if str(meta['board']).startswith('esp12') else 'ESP32'
    return {'name': project, 'version': meta.get('version', '0.1.0'), 'builds': [{'chipFamily': chip, 'parts': [{'path': f'../../firmware/{project}/firmware.bin?token={meta["ota_token"]}', 'offset': 0}]}]}


@app.get('/firmware/{project}/firmware.bin')
def firmware(project: str, token: str = Query(default='')):
    meta = load_meta(project)
    if token != meta.get('ota_token'):
        raise HTTPException(403, 'Invalid token')
    f = FIRMWARE_ROOT / safe_name(project) / 'firmware.bin'
    if not f.exists():
        raise HTTPException(404, 'Firmware not built yet')
    return FileResponse(f, media_type='application/octet-stream')
