import sys,types
paho=types.ModuleType('paho');pm=types.ModuleType('paho.mqtt');pc=types.ModuleType('paho.mqtt.client')
class CV: VERSION2=2
pc.CallbackAPIVersion=CV;pc.Client=object;pc.MQTT_ERR_SUCCESS=0;pm.client=pc;paho.mqtt=pm
sys.modules.update({'paho':paho,'paho.mqtt':pm,'paho.mqtt.client':pc})
import os,tempfile
os.environ['ESP_MANAGER_ROOT']=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.main import app,APP_JS,HARDWARE
client=TestClient(app)
def test_root_and_js():
 assert client.get('/').status_code==200
 assert client.get('/app.js').status_code==200
 assert 'refreshDevices' if False else 'refresh()' in APP_JS
def test_project_workflow():
 r=client.post('/api/projects',json={'name':'test','board':'esp32dev'});assert r.status_code==200
 assert client.get('/api/projects').json()[0]['name']=='test'
 assert client.get('/api/projects/test/files').status_code==200
 assert client.put('/api/projects/test/file?path=src/device.cpp',content='void setupDevice(){}\nvoid loopDevice(){}').status_code==200
def test_device_presence():
 from app import main
 main.DEVICES['x']={'device_id':'x','last_seen':int(__import__('time').time()),'ip':'1.2.3.4'}
 assert client.get('/api/devices').json()[0]['online'] is True
 assert client.delete('/api/devices/x').status_code==200
 assert client.get('/api/devices').json()==[]
def test_hardware_template():
 assert 'manifest.json' in HARDWARE and 'disconnectS' in HARDWARE and 'OTA starten' in HARDWARE
