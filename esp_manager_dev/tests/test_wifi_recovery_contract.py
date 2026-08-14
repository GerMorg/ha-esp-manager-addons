from pathlib import Path
CPP=Path('app/templates/lib/ESPManager/src/ESPManager.cpp').read_text()
HDR=Path('app/templates/lib/ESPManager/src/ESPManager.h').read_text()
def test_state_machine_and_single_portal_start():
 for token in ['WIFI_RETRY','WIFI_PORTAL','WIFI_FINAL_RETRY','portalActive','startFallbackPortal','stopFallbackPortal','wifiRecovered']:assert token in HDR+CPP
 assert 'if(portalActive)return' in CPP
 assert 'wm.startConfigPortal' in CPP
def test_parallel_reconnect_and_clean_recovery():
 for token in ['WiFi.mode(WIFI_AP_STA)','WiFi.begin()','wm.process()','wm.stopConfigPortal()','WiFi.softAPdisconnect(true)','WiFi.mode(WIFI_STA)']:assert token in CPP
def test_restart_timing():
 assert 'const unsigned long finalWindow=60000UL' in CPP
 assert 'outage>=restartAfter-finalWindow' in CPP
 assert 'outage>=restartAfter' in CPP
 assert 'ESP.restart()' in CPP
