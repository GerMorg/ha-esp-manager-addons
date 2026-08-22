from pathlib import Path
def test_agent_api_and_topics():
 h=Path("app/templates/lib/ESPManager/src/ESPManager.h").read_text();c=Path("app/templates/lib/ESPManager/src/ESPManager.cpp").read_text()
 for x in ["publishSensor","publishState","onCommand","registerSensor","registerBinarySensor","registerSwitch","registerNumber","registerCover"]:assert x in h and x in c
 for x in ["homeassistant/","/cmd/entity/","/state/","/availability"]:assert x in c
 assert "mq.publish(t.c_str(),p.c_str(),true)" in c
def test_wifi_and_ota_preserved():
 c=Path("app/templates/lib/ESPManager/src/ESPManager.cpp").read_text()
 for x in ["WiFi.setAutoReconnect(true)","startConfigPortal","softAPdisconnect","ESP.restart()","otaNet"]:assert x in c
