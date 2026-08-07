from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()

# Imports used for initial-install image generation.
s=s.replace('import hashlib, io, json, secrets, shutil, subprocess, threading, time, zipfile',
            'import hashlib, io, json, secrets, shutil, subprocess, sys, threading, time, zipfile')

# Expand the board selector. Existing choices are kept.
anchor='<option value="nodemcuv2">NodeMCU 1.0 ESP8266MOD</option>'
extra='''<option value="nodemcuv2">NodeMCU 1.0 ESP8266MOD</option><option value="esp32dev">ESP32 DevKit / WROOM-32</option><option value="esp32-s2-saola-1">ESP32-S2 Saola</option><option value="esp32-s3-devkitc-1">ESP32-S3 DevKitC-1</option><option value="esp32-c3-devkitm-1">ESP32-C3 DevKitM-1</option><option value="esp32-c6-devkitc-1">ESP32-C6 DevKitC-1</option>'''
if anchor in s:s=s.replace(anchor,extra,1)

# Platform and chip profile helpers. These profiles cover Wi-Fi capable families
# currently supported by this Arduino agent and ESP Web Tools.
helpers='''
CHIP_PROFILES={
 'nodemcuv2':{'family':'ESP8266','chip':'esp8266','boot':0x0},
 'esp12e':{'family':'ESP8266','chip':'esp8266','boot':0x0},
 'esp32dev':{'family':'ESP32','chip':'esp32','boot':0x1000},
 'esp32-s2-saola-1':{'family':'ESP32-S2','chip':'esp32s2','boot':0x1000},
 'esp32-s3-devkitc-1':{'family':'ESP32-S3','chip':'esp32s3','boot':0x0},
 'esp32-c3-devkitm-1':{'family':'ESP32-C3','chip':'esp32c3','boot':0x0},
 'esp32-c6-devkitc-1':{'family':'ESP32-C6','chip':'esp32c6','boot':0x0},
}

def chip_profile(board):
 return CHIP_PROFILES.get(board,{'family':'ESP32','chip':'esp32','boot':0x1000})

def create_initial_image(project_path,m,output_dir):
 build=project_path/'.pio'/'build'/m['board'];profile=chip_profile(m['board']);app_bin=build/'firmware.bin';target=output_dir/'initial_firmware.bin'
 if profile['family']=='ESP8266':
  shutil.copy2(app_bin,target);return target,profile
 bootloader=build/'bootloader.bin';partitions=build/'partitions.bin'
 if not bootloader.exists() or not partitions.exists():raise RuntimeError('Bootloader oder Partitionstabelle fehlt für den Initial-Flash')
 esptools=list(Path('/data/platformio/packages').glob('tool-esptoolpy/esptool.py'))
 if not esptools:esptools=list(Path('/data/platformio/packages').glob('tool-esptoolpy/esptool/__main__.py'))
 if not esptools:raise RuntimeError('PlatformIO esptool wurde nicht gefunden')
 parts=[hex(profile['boot']),str(bootloader),hex(0x8000),str(partitions),hex(0x10000),str(app_bin)]
 boot_app=Path('/data/platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin')
 if boot_app.exists():parts[4:4]=[hex(0xE000),str(boot_app)]
 cmd=[sys.executable,str(esptools[0]),'--chip',profile['chip'],'merge_bin','-o',str(target),'--flash_mode','dio','--flash_freq','40m','--flash_size','4MB']+parts
 result=subprocess.run(cmd,text=True,capture_output=True)
 if result.returncode:raise RuntimeError('Factory-Image konnte nicht erstellt werden: '+result.stdout+result.stderr)
 return target,profile
'''
worker_anchor='def worker(jid):'
if worker_anchor not in s:raise SystemExit('build worker anchor not found')
s=s.replace(worker_anchor,helpers+'\n'+worker_anchor,1)

old="""src=p/'.pio'/'build'/m['board']/'firmware.bin';data=src.read_bytes();bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/j['project']/bid;out.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out/'firmware.bin');rec={'id':bid,'version':m['version'],'built_at':int(time.time()),'size':len(data),'sha256':hashlib.sha256(data).hexdigest()};(out/'manifest.json').write_text(json.dumps(rec,indent=2));j['status']='success'"""
new="""src=p/'.pio'/'build'/m['board']/'firmware.bin';data=src.read_bytes();bid=time.strftime('%Y%m%d-%H%M%S');out=FIRMWARE/j['project']/bid;out.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out/'firmware.bin');initial,profile=create_initial_image(p,m,out);rec={'id':bid,'version':m['version'],'built_at':int(time.time()),'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'initial_size':initial.stat().st_size,'chip_family':profile['family'],'board':m['board']};(out/'manifest.json').write_text(json.dumps(rec,indent=2));j['status']='success'"""
if old not in s:raise SystemExit('successful build artifact block not found')
s=s.replace(old,new,1)

# Hardware page now consumes the merged/full initial image for ESP32 families.
s=s.replace("if (mf.parent/'firmware.bin').exists():builds.append(data)","if (mf.parent/'initial_firmware.bin').exists():builds.append(data)")
s=s.replace("'parts':[{'path':'firmware.bin','offset':0}]","'parts':[{'path':'initial_firmware.bin','offset':0}]")
s=s.replace("@app.get('/usb/{project}/firmware.bin')\ndef usb_firmware(project):\n    b=latest_successful_build(project);return FileResponse(b['_dir']/'firmware.bin',media_type='application/octet-stream',filename=f'{clean(project)}.bin')",
"@app.get('/usb/{project}/initial_firmware.bin')\ndef usb_firmware(project):\n    b=latest_successful_build(project);return FileResponse(b['_dir']/'initial_firmware.bin',media_type='application/octet-stream',filename=f'{clean(project)}-initial.bin')")

p.write_text(s)
