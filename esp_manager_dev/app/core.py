from pathlib import Path
import os,json,yaml,secrets,shutil,zipfile,time,hashlib,subprocess,sys
ROOT=Path(os.getenv('ESP_MANAGER_ROOT','/config/esp_manager_dev'));PROJECTS=ROOT/'projects';FIRMWARE=ROOT/'firmware';BACKUPS=ROOT/'backups';OPTFILE=Path('/data/options.json');T=Path(__file__).parent/'templates'
for d in(PROJECTS,FIRMWARE,BACKUPS):d.mkdir(parents=True,exist_ok=True)
DEFAULTS={'mqtt_host':'core-mosquitto','mqtt_port':1883,'mqtt_username':'','mqtt_password':'','device_mqtt_host':'homeassistant.local','device_mqtt_port':1883,'device_mqtt_username':'','device_mqtt_password':'','public_base_url':'http://homeassistant.local:8100','build_retention':5,'device_offline_after':75,'wifi_reconnect_interval':15000,'wifi_recovery_restart_after':900000}
def options():
 d=dict(DEFAULTS)
 try:d.update(json.loads(OPTFILE.read_text()))
 except Exception:pass
 return d
OPT=options();BOARDS={'nodemcuv2':('ESP8266','esp8266',0),'esp12e':('ESP8266','esp8266',0),'esp32dev':('ESP32','esp32',0x1000),'esp32-s2-saola-1':('ESP32-S2','esp32s2',0x1000),'esp32-s3-devkitc-1':('ESP32-S3','esp32s3',0),'esp32-c3-devkitm-1':('ESP32-C3','esp32c3',0),'esp32-c6-devkitc-1':('ESP32-C6','esp32c6',0)}
def clean(v):
 n='_'.join(x for x in ''.join(c.lower() if c.isalnum() else '_' for c in str(v).strip()).split('_') if x)
 if not n:raise ValueError('Ungültiger Name')
 return n[:64]
def pdir(name,must=True):
 p=PROJECTS/clean(name)
 if must and not p.exists():raise FileNotFoundError(name)
 return p
def migrate(m):
 m.setdefault('display_name',m.get('name','').replace('_',' ').title());m.setdefault('board','esp32dev');m.setdefault('version','0.1.0');m.setdefault('monitor_speed',115200);m.setdefault('libraries',[]);m.setdefault('build_flags',[]);m.setdefault('device_id','');m.setdefault('ota_token',secrets.token_urlsafe(32));return m
def meta(name):return migrate(yaml.safe_load((pdir(name)/'espmanager.yaml').read_text()) or {})
def save_meta(name,m):(pdir(name)/'espmanager.yaml').write_text(yaml.safe_dump(m,sort_keys=False))
def public(m):r=dict(m);r.pop('ota_token',None);return r
def system_copy(p):
 shutil.copy2(T/'src/main.cpp',p/'src/main.cpp');dst=p/'lib/ESPManager';shutil.rmtree(dst,ignore_errors=True);shutil.copytree(T/'lib/ESPManager',dst)
def render_pio(p,m):
 platform='espressif8266' if m['board'] in ('nodemcuv2','esp12e') else 'espressif32';libs=['tzapu/WiFiManager@^2.0.17','knolleary/PubSubClient@^2.8','bblanchon/ArduinoJson@^7.2.1']+m['libraries'];flags=[f'-D ESPMANAGER_DEVICE_ID=\\"{m["name"]}\\"',f'-D ESPMANAGER_FW_VERSION=\\"{m["version"]}\\"',f'-D ESPMANAGER_MQTT_HOST=\\"{OPT["device_mqtt_host"]}\\"',f'-D ESPMANAGER_MQTT_PORT={OPT["device_mqtt_port"]}',f'-D ESPMANAGER_MQTT_USER=\\"{OPT["device_mqtt_username"]}\\"',f'-D ESPMANAGER_MQTT_PASS=\\"{OPT["device_mqtt_password"]}\\"',f'-D ESPMANAGER_OTA_TOKEN=\\"{m["ota_token"]}\\"',f'-D ESPMANAGER_WIFI_RECONNECT_INTERVAL={OPT["wifi_reconnect_interval"]}',f'-D ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER={OPT["wifi_recovery_restart_after"]}']+m['build_flags'];(p/'platformio.ini').write_text(f'[env:{m["board"]}]\nplatform={platform}\nboard={m["board"]}\nframework=arduino\nmonitor_speed={m["monitor_speed"]}\nlib_deps=\n'+'\n'.join('  '+x for x in libs)+'\nbuild_flags=\n'+'\n'.join('  '+x for x in flags)+'\n')
def safe(name,rel,exists=True):
 rel=str(rel).replace('\\','/').lstrip('/');f=pdir(name)/rel
 if '..' in Path(rel).parts or not rel.startswith(('src/','include/','lib/')) or rel=='src/main.cpp' or rel.startswith('lib/ESPManager/'):raise PermissionError(rel)
 if exists and not f.is_file():raise FileNotFoundError(rel)
 return f
def backup(name,reason):
 out=BACKUPS/f'{clean(name)}-{time.strftime("%Y%m%d-%H%M%S")}-{reason}.zip';p=pdir(name)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for f in p.rglob('*'):
   if f.is_file() and '.pio' not in f.parts:z.write(f,f.relative_to(p))
 return out
def builds(name):
 out=[];root=FIRMWARE/clean(name)
 for f in root.glob('*/manifest.json') if root.exists() else []:
  try:d=json.loads(f.read_text());d['_dir']=f.parent;out.append(d)
  except Exception:pass
 return sorted(out,key=lambda x:x.get('built_at',0),reverse=True)
def prune(name,keep=None):
 keep=int(keep or OPT['build_retention']);n=0;removed=[]
 for b in builds(name):
  if b.get('pinned'):continue
  n+=1
  if n>keep:shutil.rmtree(b['_dir'],ignore_errors=True);removed.append(b['id'])
 return removed
def initial_image(p,m,out):
 b=p/'.pio/build'/m['board'];target=out/'initial_firmware.bin'
 if m['board'] in ('nodemcuv2','esp12e'):shutil.copy2(b/'firmware.bin',target);return
 family,chip,boot=BOARDS[m['board']];tool=Path('/data/platformio/packages/tool-esptoolpy/esptool.py');parts=[hex(boot),str(b/'bootloader.bin'),'0x8000',str(b/'partitions.bin'),'0x10000',str(b/'firmware.bin')];bootapp=Path('/data/platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin')
 if bootapp.exists():parts[4:4]=['0xe000',str(bootapp)]
 r=subprocess.run([sys.executable,str(tool),'--chip',chip,'merge_bin','-o',str(target),'--flash_mode','dio','--flash_freq','40m','--flash_size','4MB']+parts,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
