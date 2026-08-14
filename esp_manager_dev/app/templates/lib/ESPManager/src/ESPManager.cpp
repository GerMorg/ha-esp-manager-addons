#include "ESPManager.h"
#ifdef ESP8266
#include <ESP8266WiFi.h>
#include <ESP8266httpUpdate.h>
#else
#include <WiFi.h>
#include <HTTPUpdate.h>
#include <esp_ota_ops.h>
#endif
#include <WiFiManager.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
static WiFiClient mqttNet,otaNet; static PubSubClient mq(mqttNet); static WiFiManager wm; ESPManagerClass ESPManager;
static String base(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}
static String portal(){return String("ESPManager-")+ESPMANAGER_DEVICE_ID;}
static void otaState(const String&s,int p,const String&m){JsonDocument d;d["state"]=s;d["percent"]=p;d["message"]=m;String o;serializeJson(d,o);Serial.println(String("[ESPManager] OTA ")+o);if(mq.connected())mq.publish((base()+"/ota/progress").c_str(),o.c_str(),true);}
static void otaStart(){otaState("started",0,"Download gestartet");} static void otaEnd(){otaState("finished",100,"Update vollständig");}
static void otaProgress(int cur,int total){otaState("progress",total?cur*100/total:0,String(cur)+"/"+String(total));} static void otaError(int e){otaState("failed",0,String("Fehlercode ")+e);}
static void callback(char*t,byte*p,unsigned int n){String b;for(unsigned int i=0;i<n;i++)b+=(char)p[i];ESPManager.handleCommand(String(t),b);}
static void confirmFirmware(){
#ifndef ESP8266
 const esp_partition_t*r=esp_ota_get_running_partition();esp_ota_img_states_t s;if(r&&esp_ota_get_state_partition(r,&s)==ESP_OK&&s==ESP_OTA_IMG_PENDING_VERIFY)esp_ota_mark_app_valid_cancel_rollback();
#endif
}
void ESPManagerClass::begin(){Serial.begin(115200);delay(100);Serial.println("[ESPManager] Agent startet");WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(true);WiFi.persistent(true);wm.setConfigPortalBlocking(false);wm.setConnectTimeout(20);bool ok=wm.autoConnect(portal().c_str());configPortalActive=!ok;if(ok){wm.startWebPortal();webPortalActive=true;webPortalUntil=millis()+600000UL;}mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mq.setBufferSize(2048);mq.setCallback(callback);ensureMqtt();}
void ESPManagerClass::loop(){wm.process();unsigned long now=millis();if(WiFi.status()==WL_CONNECTED){disconnectedSince=0;if(configPortalActive){wm.stopConfigPortal();configPortalActive=false;}ensureMqtt();mq.loop();if(now-lastStatus>30000UL)publishStatus();if(webPortalActive&&webPortalUntil&&(long)(now-webPortalUntil)>=0){wm.stopWebPortal();webPortalActive=false;}}else{if(!disconnectedSince)disconnectedSince=now;if(now-lastWifiRetry>=ESPMANAGER_WIFI_RECONNECT_INTERVAL){lastWifiRetry=now;Serial.println("[ESPManager] WLAN getrennt, erneuter Verbindungsversuch");WiFi.mode(WIFI_STA);WiFi.reconnect();}if(!configPortalActive&&now-disconnectedSince>60000UL)startFallbackPortal();if(now-disconnectedSince>=ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER){Serial.println("[ESPManager] WLAN-Wiederherstellung ohne Erfolg, Neustart");delay(200);ESP.restart();}}}
void ESPManagerClass::startFallbackPortal(){wm.setConfigPortalBlocking(false);wm.startConfigPortal(portal().c_str());configPortalActive=true;}
void ESPManagerClass::openWifiPortal(){if(WiFi.status()==WL_CONNECTED){if(!webPortalActive)wm.startWebPortal();webPortalActive=true;webPortalUntil=millis()+600000UL;}else if(!configPortalActive)startFallbackPortal();}
void ESPManagerClass::ensureMqtt(){if(mq.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastMqttRetry<5000UL)return;lastMqttRetry=millis();String id=String("espmanager-")+ESPMANAGER_DEVICE_ID;bool ok=String(ESPMANAGER_MQTT_USER).length()?mq.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(base()+"/availability").c_str(),0,true,"offline"):mq.connect(id.c_str(),(base()+"/availability").c_str(),0,true,"offline");if(ok){mq.publish((base()+"/availability").c_str(),"online",true);mq.subscribe((base()+"/cmd/#").c_str());confirmFirmware();log("MQTT verbunden");publishStatus();}else Serial.printf("[ESPManager] MQTT Fehler %d\n",mq.state());}
void ESPManagerClass::publishStatus(){lastStatus=millis();if(!mq.connected())return;JsonDocument d;d["device_id"]=ESPMANAGER_DEVICE_ID;d["firmware_version"]=ESPMANAGER_FW_VERSION;d["ip"]=WiFi.localIP().toString();d["ssid"]=WiFi.SSID();d["rssi"]=WiFi.RSSI();d["uptime"]=millis()/1000UL;d["free_heap"]=ESP.getFreeHeap();d["wifi_portal"]=configPortalActive||webPortalActive;String o;serializeJson(d,o);mq.publish((base()+"/status").c_str(),o.c_str(),true);}
void ESPManagerClass::log(const String&m){Serial.println(String("[ESPManager] ")+m);if(mq.connected())mq.publish((base()+"/log").c_str(),m.c_str());}
void ESPManagerClass::publishSensor(const char*k,double v){char b[40];snprintf(b,sizeof(b),"%.3f",v);if(mq.connected())mq.publish((base()+"/sensor/"+k).c_str(),b,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){JsonDocument d;if(deserializeJson(d,p))return;if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Kommando abgelehnt");return;}if(t.endsWith("/cmd/restart"))ESP.restart();if(t.endsWith("/cmd/wifi_portal"))openWifiPortal();if(t.endsWith("/cmd/ota")){String u=d["url"]|"";if(!u.length()){otaState("failed",0,"URL fehlt");return;}
#ifdef ESP8266
 ESPhttpUpdate.rebootOnUpdate(false);ESPhttpUpdate.onStart(otaStart);ESPhttpUpdate.onEnd(otaEnd);ESPhttpUpdate.onProgress(otaProgress);ESPhttpUpdate.onError(otaError);auto r=ESPhttpUpdate.update(otaNet,u);
#else
 httpUpdate.rebootOnUpdate(false);httpUpdate.onStart(otaStart);httpUpdate.onEnd(otaEnd);httpUpdate.onProgress(otaProgress);httpUpdate.onError(otaError);auto r=httpUpdate.update(otaNet,u);
#endif
 if(r==HTTP_UPDATE_OK){otaState("finished",100,"Update vollständig, Neustart folgt");for(int i=0;i<8;i++){mq.loop();delay(100);}ESP.restart();}else if(r==HTTP_UPDATE_NO_UPDATES)otaState("no_update",100,"Keine Aktualisierung");}}
