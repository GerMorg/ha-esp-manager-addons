import sys,types,os,tempfile
paho=types.ModuleType('paho');pm=types.ModuleType('paho.mqtt');pc=types.ModuleType('paho.mqtt.client')
class CV: VERSION2=2
class DummyClient:
 def __init__(self,*a,**k):pass
 def username_pw_set(self,*a,**k):pass
 def connect(self,*a,**k):raise RuntimeError('mock offline')
pc.CallbackAPIVersion=CV;pc.Client=DummyClient;pm.client=pc;paho.mqtt=pm;sys.modules.update({'paho':paho,'paho.mqtt':pm,'paho.mqtt.client':pc})
os.environ['ESP_MANAGER_ROOT']=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_ui_contract():
 h=c.get('/').text
 for x in ['Projekt-ZIP importieren','Arduino-ZIP migrieren','Datei löschen','Umbenennen','Hochladen','Exportieren','Duplizieren','Buildhistorie','USB, Serial & OTA','Details einklappen']:assert x in h
 assert 'white-space:pre-wrap' in h and 'overflow-wrap:anywhere' in h
def test_lifecycle():
 assert c.post('/api/projects',json={'name':'demo','board':'esp32dev'}).status_code==200
 assert c.post('/api/projects/demo/files',json={'path':'src/test.cpp','content':'one'}).status_code==200
 assert c.put('/api/projects/demo/file?path=src/test.cpp',content='two').status_code==200
 assert c.post('/api/projects/demo/file/rename',json={'source':'src/test.cpp','target':'src/new.cpp'}).status_code==200
 assert c.delete('/api/projects/demo/file?path=src/new.cpp').status_code==200
def test_hardware_page():
 for p in ['/usb/demo','/usb/demo/']:
  r=c.get(p);assert r.status_code==200;h=r.text
  for x in ['USB-Erstinstallation','Serieller Monitor','Gerät und MQTT','OTA-Aktualisierung','Erneut prüfen','HARDWARE_PROJECT']:assert x in h
  assert '../../static/hardware.js' not in h and "pageBase()+'manifest.json'" in h
  assert 'white-space:pre-wrap' in h and 'overflow-wrap:anywhere' in h
def test_protection_duplicate_export():
 assert c.put('/api/projects/demo/file?path=src/main.cpp',content='bad').status_code==400
 assert c.post('/api/projects/demo/duplicate',json={'name':'copy'}).status_code==200
 assert c.get('/api/projects/demo/export').status_code==200
