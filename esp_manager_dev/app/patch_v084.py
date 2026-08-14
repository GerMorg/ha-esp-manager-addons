from pathlib import Path
p=Path(__file__).with_name('main.py')
s=p.read_text()

# Add firmware build flags for reconnect policy, configurable in Dev options.
needle="f'-D ESPMANAGER_OTA_TOKEN=\\\"{m[\"ota_token\"]}\\\"']+m['build_flags']"
replacement="f'-D ESPMANAGER_OTA_TOKEN=\\\"{m[\"ota_token\"]}\\\"',f'-D ESPMANAGER_WIFI_RECONNECT_INTERVAL={int(OPT.get(\"wifi_reconnect_interval\",15000))}',f'-D ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER={int(OPT.get(\"wifi_recovery_restart_after\",900000))}']+m['build_flags']"
if needle not in s:raise SystemExit('render_pio OTA flag anchor missing')
s=s.replace(needle,replacement,1)

# Visible device detail/history panel on main page.
s=s.replace("<section class=\"card\"><h2>Geräte</h2><div id=\"devices\"></div></section>","<section class=\"card\"><h2>Geräte</h2><div id=\"devices\"></div></section><section class=\"card\"><h2>Geräte-Details</h2><div id=\"deviceDetail\">Gerät auswählen</div><pre id=\"deviceHistory\"></pre></section>",1)
old_refresh="""async function refreshDevices(){let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class=\"item\"><span style=\"color:${x.online?'#22c55e':'#ef4444'};font-size:18px\">●</span> <b>${x.device_id}</b> <b>${x.online?'Online':'Offline'}</b><br>${x.ip||''} ${x.ssid||''} RSSI ${x.rssi??'-'} | zuletzt vor ${x.last_seen_age}s</div>`).join('')||'Noch keine Geräte'}"""
new_refresh="""async function refreshDevices(){let ds=await api('api/devices');devices.innerHTML=ds.map(x=>`<div class=\"item\" style=\"cursor:pointer\" onclick=\"showDevice('${x.device_id}')\"><span style=\"color:${x.online?'#22c55e':'#ef4444'};font-size:18px\">●</span> <b>${x.device_id}</b> <b>${x.online?'Online':'Offline'}</b><br>${x.ip||''} ${x.ssid||''} RSSI ${x.rssi??'-'} | zuletzt vor ${x.last_seen_age}s</div>`).join('')||'Noch keine Geräte'}async function showDevice(id){let d=await api('api/devices/'+encodeURIComponent(id));deviceDetail.innerHTML=`<b>${d.device_id}</b><br>Status: ${d.online?'Online':'Offline'}<br>Firmware: ${d.firmware_version||'-'}<br>IP: ${d.ip||'-'}<br>RSSI: ${d.rssi??'-'}<br>Uptime: ${d.uptime??'-'} s<br>Heap: ${d.free_heap??'-'}`;let h=await api('api/devices/'+encodeURIComponent(id)+'/history?limit=50');deviceHistory.textContent=h.map(x=>new Date(x.ts*1000).toLocaleString()+' | '+x.event+' | '+JSON.stringify(x.data)).join('\\n')}"""
if old_refresh not in s:raise SystemExit('main refreshDevices from 0.8.3 missing')
s=s.replace(old_refresh,new_refresh,1)
s=s.replace('ESP Manager Dev 0.8.3-dev','ESP Manager Dev 0.8.4-dev').replace('ESP Manager Dev 0.8.3','ESP Manager Dev 0.8.4')
p.write_text(s)

# Agent header: configurable recovery constants and state.
h=Path(__file__).parent/'templates/lib/ESPManager/src/ESPManager.h';hs=h.read_text()
insert='''\n#ifndef ESPMANAGER_WIFI_RECONNECT_INTERVAL\n#define ESPMANAGER_WIFI_RECONNECT_INTERVAL 15000UL\n#endif\n#ifndef ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER\n#define ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER 900000UL\n#endif\n'''
anchor='#define ESPM_LOG(message) ESPManager.log(String(message))'
if anchor not in hs:raise SystemExit('ESPManager header anchor missing')
hs=hs.replace(anchor,insert+'\n'+anchor,1)
old_state='unsigned long lastStatus=0,lastMqttRetry=0,disconnectedSince=0,webPortalUntil=0;'
new_state='unsigned long lastStatus=0,lastMqttRetry=0,disconnectedSince=0,lastWifiRetry=0,webPortalUntil=0;'
if old_state not in hs:raise SystemExit('ESPManager timing state missing')
h.write_text(hs.replace(old_state,new_state,1))

# Agent implementation: periodic reconnect, AP fallback, and final recovery restart.
cpp=Path(__file__).parent/'templates/lib/ESPManager/src/ESPManager.cpp';c=cpp.read_text()
setup='WiFi.mode(WIFI_STA);wm.setConfigPortalBlocking(false);'
setup_new='WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(true);WiFi.persistent(true);wm.setConfigPortalBlocking(false);'
if setup not in c:raise SystemExit('WiFi setup anchor missing')
c=c.replace(setup,setup_new,1)
old_else='''}else{if(!disconnectedSince)disconnectedSince=millis();if(!configPortalActive&&millis()-disconnectedSince>60000UL)startFallbackPortal();}}'''
new_else='''}else{unsigned long now=millis();if(!disconnectedSince)disconnectedSince=now;if(now-lastWifiRetry>=ESPMANAGER_WIFI_RECONNECT_INTERVAL){lastWifiRetry=now;Serial.println("[ESPManager] WLAN getrennt, erneuter Verbindungsversuch");WiFi.mode(WIFI_STA);WiFi.reconnect();}if(!configPortalActive&&now-disconnectedSince>60000UL)startFallbackPortal();if(now-disconnectedSince>=ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER){Serial.println("[ESPManager] WLAN-Wiederherstellung ohne Erfolg, kontrollierter Neustart");delay(200);ESP.restart();}}}'''
if old_else not in c:raise SystemExit('WiFi disconnect loop branch missing')
c=c.replace(old_else,new_else,1)
cpp.write_text(c)
