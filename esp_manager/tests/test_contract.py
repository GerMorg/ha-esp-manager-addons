import os,sys,tempfile,types
from pathlib import Path
paho=types.ModuleType("paho");pm=types.ModuleType("paho.mqtt");pc=types.ModuleType("paho.mqtt.client")
class CV: VERSION2=2
class DummyClient:
 def __init__(self,*a,**k):pass
 def username_pw_set(self,*a,**k):pass
 def connect(self,*a,**k):raise RuntimeError("mock offline")
pc.CallbackAPIVersion=CV;pc.Client=DummyClient;pm.client=pc;paho.mqtt=pm;sys.modules.update({"paho":paho,"paho.mqtt":pm,"paho.mqtt.client":pc})
os.environ["ESP_MANAGER_ROOT"]=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_project_and_file_lifecycle():
 assert c.post("/api/projects",json={"name":"demo","board":"esp32dev"}).status_code==200
 assert c.post("/api/projects/demo/files",json={"path":"src/test.cpp","content":"one"}).status_code==200
 assert c.put("/api/projects/demo/file?path=src/test.cpp",content="two").status_code==200
 assert c.delete("/api/projects/demo/file?path=src/test.cpp").status_code==200
def test_ui_and_hardware_routes():
 for word in ["Projekt-ZIP importieren","Buildhistorie","USB, Serial & OTA"]:assert word in c.get("/").text
 assert c.get("/usb/demo").status_code==200
def test_protected_system_file():assert c.put("/api/projects/demo/file?path=src/main.cpp",content="bad").status_code==400
