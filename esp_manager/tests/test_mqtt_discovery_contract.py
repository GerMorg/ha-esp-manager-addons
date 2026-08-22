from pathlib import Path
H=Path('app/templates/lib/ESPManager/src/ESPManager.h').read_text();C=Path('app/templates/lib/ESPManager/src/ESPManager.cpp').read_text()
def test_generic_api():
 for x in ['registerSensor','MAX_DISCOVERY_SENSORS','publishDiscovery','homeassistant/sensor/','availability_topic']:assert x in H+C
def test_legacy_ids():
 ids=['smartmeter_kWh_bezug','smartmeter_kWh_einspeisung','smartmeter_leistung_bezug','smartmeter_leistung_einspeisung','smartmeter_leistungsfaktor']+[f'smartmeter_spannung_l{i}' for i in range(1,4)]+[f'smartmeter_strom_l{i}' for i in range(1,4)]
 for x in ids:assert C.count(x)==1
def test_compatibility_and_retain():
 assert 'void ESPManagerClass::publishSensor(const char*k,double v)' in C
 assert 'mq.publish(topic.c_str(),payload.c_str(),true)' in C
 assert 'publishDiscovery();status();' in C
def test_wifi_recovery_kept():
 for x in ['WIFI_PORTAL','WIFI_FINAL_RETRY','WiFi.softAPdisconnect(true)','ESP.restart()']:assert x in H+C
