from pathlib import Path
C=Path('app/templates/lib/ESPManager/src/ESPManager.cpp').read_text();H=Path('app/templates/lib/ESPManager/src/ESPManager.h').read_text()
def test_api():
 for x in ['registerSensor','registerBinarySensor','registerSwitch','registerNumber','registerCover','publishState','onCommand']:assert x in H and x in C
def test_topics():
 for x in ['homeassistant/','/cmd/entity/','/state/','/availability']:assert x in C
 assert 'mq.publish(t.c_str(),p.c_str(),true)' in C
def test_compatibility():
 for x in ['publishSensor','cmd/ota','cmd/restart','WIFI_AP_STA','stopConfigPortal','ESP.restart()']:assert x in C
def test_late_registration():assert C.count('if(mq.connected())discovery();')>=5
