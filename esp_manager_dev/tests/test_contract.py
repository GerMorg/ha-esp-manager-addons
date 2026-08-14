import sys,types
paho=types.ModuleType('paho');pm=types.ModuleType('paho.mqtt');pc=types.ModuleType('paho.mqtt.client')
class CV: VERSION2=2
class DummyClient:
 def __init__(self,*a,**k):pass
 def username_pw_set(self,*a,**k):pass
 def connect(self,*a,**k):raise RuntimeError('mock offline')
pc.CallbackAPIVersion=CV;pc.Client=DummyClient;pm.client=pc;paho.mqtt=pm
sys.modules.update({'paho':paho,'paho.mqtt':pm,'paho.mqtt.client':pc})
import os,tempfile,sys,types
os.environ['ESP_MANAGER_ROOT']=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_routes_and_ui():
 html=c.get('/').text
 for text in ['Projekt-ZIP importieren','Arduino-ZIP migrieren','Datei löschen','Umbenennen','Hochladen','Exportieren','Duplizieren','Buildhistorie','USB, OTA & Status']:assert text in html
 paths={x.path for x in app.routes}
 for path in ['/api/projects','/api/projects/import','/api/projects/{name}/files','/api/projects/{name}/files/upload','/api/projects/{name}/file/rename','/api/projects/{name}/export','/api/projects/{name}/duplicate','/api/projects/{name}/build-start','/api/devices','/api/projects/{name}/devices/{dev}/ota']:assert path in paths
def test_project_file_lifecycle():
 assert c.post('/api/projects',json={'name':'demo','board':'esp32dev'}).status_code==200
 assert c.post('/api/projects/demo/files',json={'path':'src/test.cpp','content':'one'}).status_code==200
 assert c.get('/api/projects/demo/file?path=src/test.cpp').text=='one'
 assert c.put('/api/projects/demo/file?path=src/test.cpp',content='two').status_code==200
 assert c.post('/api/projects/demo/file/rename',json={'source':'src/test.cpp','target':'src/new.cpp'}).status_code==200
 assert c.delete('/api/projects/demo/file?path=src/new.cpp').status_code==200
def test_system_protection():
 assert c.put('/api/projects/demo/file?path=src/main.cpp',content='bad').status_code==400
def test_duplicate_export_delete():
 assert c.post('/api/projects/demo/duplicate',json={'name':'copy'}).status_code==200
 assert c.get('/api/projects/demo/export').status_code==200
 assert c.delete('/api/projects/copy').status_code==200
