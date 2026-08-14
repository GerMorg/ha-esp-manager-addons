#include "ESPManager.h"
#ifdef ESP8266
#include <ESP8266WiFi.h>
#include <ESP8266httpUpdate.h>
#else
#include <WiFi.h>
#include <HTTPUpdate.h>
#endif
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
static WiFiClient mqttNet,otaNet; static PubSubClient mq(mqttNet); static WiFiManager wm; ESPManagerClass ESPManager;
static String base(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}
static void callback(char*t,byte*p,unsigned int n){String s;for(unsigned i=0;i<n;i++)s+=(char)p[i];ESPManager.handleCommand(t,s);}
static void otaReport(const String&s,int p,const String&m){JsonDocument d;d["state"]=s;d["percent"]=p;d["message"]=m;String o;serializeJson(d,o);if(mq.connected())mq.publish((base()+"/ota/progress").c_str(),o.c_str(),true);}
void ESPManagerClass::begin(){Serial.begin(115200);delay(50);WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(true);WiFi.persistent(true);wm.setConfigPortalBlocking(false);wm.setConfigPortalTimeout(0);bool ok=wm.autoConnect((String("ESPManager-")+ESPMANAGER_DEVICE_ID).c_str());portalActive=!ok;wifiState=ok?WIFI_OK:WIFI_PORTAL;if(!ok){wifiLostAt=millis();Serial.println("[ESPManager] WLAN nicht verbunden, Fallback-Portal aktiv");}mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mq.setBufferSize(2048);mq.setCallback(callback);mqttConnect();}
void ESPManagerClass::beginWifiRecovery(){if(!wifiLostAt)wifiLostAt=millis();wifiState=WIFI_RETRY;Serial.println("[ESPManager] WLAN verloren, Wiederherstellung gestartet");}
void ESPManagerClass::tryWifiReconnect(const char* reason){lastWifiRetry=millis();Serial.printf("[ESPManager] WLAN-Verbindungsversuch: %s\n",reason);WiFi.mode(WIFI_AP_STA);WiFi.disconnect(false,false);delay(50);WiFi.begin();}
void ESPManagerClass::startFallbackPortal(){if(portalActive)return;WiFi.mode(WIFI_AP_STA);wm.setConfigPortalBlocking(false);wm.startConfigPortal((String("ESPManager-")+ESPMANAGER_DEVICE_ID).c_str());portalActive=true;wifiState=WIFI_PORTAL;Serial.println("[ESPManager] Fallback-Portal einmalig gestartet; STA-Verbindungsversuche laufen weiter");}
void ESPManagerClass::stopFallbackPortal(){if(!portalActive)return;wm.stopConfigPortal();portalActive=false;WiFi.softAPdisconnect(true);Serial.println("[ESPManager] Fallback-Portal beendet");}
void ESPManagerClass::wifiRecovered(){stopFallbackPortal();WiFi.mode(WIFI_STA);wifiState=WIFI_OK;wifiLostAt=0;finalRetryAt=0;lastWifiRetry=0;Serial.print("[ESPManager] WLAN selbstständig wiederhergestellt, IP=");Serial.println(WiFi.localIP());mqttConnect();}
void ESPManagerClass::loop(){wm.process();unsigned long now=millis();if(WiFi.status()==WL_CONNECTED){if(wifiState!=WIFI_OK||portalActive)wifiRecovered();mqttConnect();mq.loop();if(now-lastStatus>30000UL)status();return;}if(wifiState==WIFI_OK)beginWifiRecovery();unsigned long outage=now-wifiLostAt;if(wifiState==WIFI_RETRY&&outage>=60000UL)startFallbackPortal();if((wifiState==WIFI_RETRY||wifiState==WIFI_PORTAL)&&now-lastWifiRetry>=ESPMANAGER_WIFI_RECONNECT_INTERVAL)tryWifiReconnect(wifiState==WIFI_PORTAL?"parallel zum Portal":"gespeicherte Zugangsdaten");const unsigned long finalWindow=60000UL;const unsigned long restartAfter=ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER;if(wifiState!=WIFI_FINAL_RETRY&&outage>=restartAfter-finalWindow){stopFallbackPortal();WiFi.mode(WIFI_STA);wifiState=WIFI_FINAL_RETRY;finalRetryAt=now;tryWifiReconnect("letzte reine STA-Phase vor Neustart");Serial.println("[ESPManager] Letzte WLAN-Wiederherstellungsphase: 60 Sekunden");}if(wifiState==WIFI_FINAL_RETRY&&now-lastWifiRetry>=ESPMANAGER_WIFI_RECONNECT_INTERVAL)tryWifiReconnect("letzte reine STA-Phase");if(outage>=restartAfter){Serial.println("[ESPManager] WLAN seit Wiederherstellungsgrenze nicht erreichbar, kontrollierter Neustart");delay(250);ESP.restart();}}
void ESPManagerClass::mqttConnect(){if(mq.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastMqtt<5000UL)return;lastMqtt=millis();String id=String("esp-")+ESPMANAGER_DEVICE_ID;bool ok=String(ESPMANAGER_MQTT_USER).length()?mq.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(base()+"/availability").c_str(),0,true,"offline"):mq.connect(id.c_str(),(base()+"/availability").c_str(),0,true,"offline");if(ok){mq.publish((base()+"/availability").c_str(),"online",true);mq.subscribe((base()+"/cmd/#").c_str());status();}}
void ESPManagerClass::status(){lastStatus=millis();JsonDocument d;d["device_id"]=ESPMANAGER_DEVICE_ID;d["firmware_version"]=ESPMANAGER_FW_VERSION;d["ip"]=WiFi.localIP().toString();d["ssid"]=WiFi.SSID();d["rssi"]=WiFi.RSSI();d["uptime"]=millis()/1000UL;d["free_heap"]=ESP.getFreeHeap();d["wifi_recovery_state"]=(int)wifiState;d["wifi_portal"]=portalActive;String o;serializeJson(d,o);mq.publish((base()+"/status").c_str(),o.c_str(),true);}
void ESPManagerClass::log(const String&s){Serial.println(String("[ESPManager] ")+s);if(mq.connected())mq.publish((base()+"/log").c_str(),s.c_str());}
void ESPManagerClass::publishSensor(const char*k,double v){char b[32];snprintf(b,sizeof(b),"%.3f",v);if(mq.connected())mq.publish((base()+"/sensor/"+k).c_str(),b,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){JsonDocument d;if(deserializeJson(d,p))return;if(String((const char*)(d["token"]|""))!=ESPMANAGER_OTA_TOKEN)return;if(t.endsWith("/cmd/restart"))ESP.restart();if(t.endsWith("/cmd/ota")){String u=d["url"]|"";otaReport("received",0,"Kommando empfangen");
#ifdef ESP8266
ESPhttpUpdate.rebootOnUpdate(false);auto r=ESPhttpUpdate.update(otaNet,u);
#else
httpUpdate.rebootOnUpdate(false);auto r=httpUpdate.update(otaNet,u);
#endif
if(r==HTTP_UPDATE_OK){otaReport("finished",100,"Update vollständig, Neustart folgt");for(int i=0;i<8;i++){mq.loop();delay(100);}ESP.restart();}else otaReport("failed",0,"Update fehlgeschlagen");}}
