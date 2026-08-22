from pathlib import Path
import subprocess,tempfile
SCRIPT=Path(__file__).parents[1]/'tools/apply_mqtt_entity_ui_v0_13_0.py'
BASE='''import hashlib, io, json, secrets, shutil, subprocess, threading, time, zipfile\nfrom pathlib import Path\nfrom fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile\nimport yaml\nROOT=Path('/config/esp_manager_dev');PROJECTS=ROOT/'projects';app=FastAPI()\ndef clean(v):return v\ndef pdir(p):return PROJECTS/p\ndef meta(p):return yaml.safe_load((pdir(p)/'espmanager.yaml').read_text())\ndef save_meta(p,m):(pdir(p)/'espmanager.yaml').write_text(yaml.safe_dump(m))\ndef copy_agent (p): d=p/'lib'/'ESPManager'; shutil.copytree(Path('templates'),d)\n'''
def test_patch_contract():
 with tempfile.TemporaryDirectory() as d:
  r=Path(d);p=r/'esp_manager_dev/app';p.mkdir(parents=True);(p/'main.py').write_text(BASE);(r/'esp_manager_dev/config.yaml').write_text('name: X\nslug: x\n')
  subprocess.run(['python3',str(SCRIPT),d],check=True)
  s=(p/'main.py').read_text()
  for x in ['MQTT_ENTITY_UI_V0130','/mqtt-discovery','mqtt_entities','registerBinarySensor','registerSwitch','registerNumber','registerCover','ESPManagerEntities.h','espManagerRegisterConfiguredEntities(*this);']:assert x in s
  compile(s,str(p/'main.py'),'exec')
  assert 'version: 0.13.0-dev' in (r/'esp_manager_dev/config.yaml').read_text()
def test_patch_idempotent():
 with tempfile.TemporaryDirectory() as d:
  r=Path(d);p=r/'esp_manager_dev/app';p.mkdir(parents=True);(p/'main.py').write_text(BASE);(r/'esp_manager_dev/config.yaml').write_text('name: X\nslug: x\n')
  subprocess.run(['python3',str(SCRIPT),d],check=True);first=(p/'main.py').read_text();subprocess.run(['python3',str(SCRIPT),d],check=True);assert (p/'main.py').read_text()==first
