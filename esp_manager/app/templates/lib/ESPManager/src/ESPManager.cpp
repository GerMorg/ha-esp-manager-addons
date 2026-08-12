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
static WiFiClient net; static PubSubClient mq(net); static WiFiManager wm; ESPManagerClass ESPManager;
static String base(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}
static String portal(){return String("ESPManager-")+ESPMANAGER_DEVICE_ID;}
static void callback(char*t,byte*p,unsigned int l){String b;for(unsigned int i=0;i<l;i++)b+=(char)p[i];ESPManager.handleCommand(String(t),b);}
void ESPManagerClass::begin(){Serial.begin(115200);delay(120);Serial.println();Serial.println("[ESPManager] Agent startet");Serial.println(String("[ESPManager] MQTT-Ziel: ")+ESPMANAGER_MQTT_HOST+":"+String(ESPMANAGER_MQTT_PORT));WiFi.mode(WIFI_STA);wm.setConfigPortalBlocking(false);wm.setConfigPortalTimeout(0);wm.setConnectTimeout(20);bool ok=wm.autoConnect(portal().c_str());configPortalActive=!ok;if(ok){wm.startWebPortal();webPortalActive=true;webPortalUntil=millis()+600000UL;log(String("WLAN verbunden: ")+WiFi.SSID()+" IP="+WiFi.localIP().toString());}else log(String("Fallback-WLAN aktiv: ")+portal()+" IP=192.168.4.1");mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mq.setCallback(callback);ensureMqtt();}
void ESPManagerClass::loop(){wm.process();if(WiFi.status()==WL_CONNECTED){disconnectedSince=0;if(configPortalActive){wm.stopConfigPortal();configPortalActive=false;}ensureMqtt();mq.loop();if(millis()-lastStatus>30000UL)publishStatus();if(webPortalActive&&webPortalUntil&&(long)(millis()-webPortalUntil)>=0){wm.stopWebPortal();webPortalActive=false;}}else{if(!disconnectedSince)disconnectedSince=millis();if(!configPortalActive&&millis()-disconnectedSince>60000UL)startFallbackPortal();}}
void ESPManagerClass::startFallbackPortal(){wm.setConfigPortalBlocking(false);wm.startConfigPortal(portal().c_str());configPortalActive=true;log(String("Router nicht erreichbar. Fallback-WLAN: ")+portal());}
void ESPManagerClass::openWifiPortal(){if(WiFi.status()==WL_CONNECTED){if(!webPortalActive)wm.startWebPortal();webPortalActive=true;webPortalUntil=millis()+600000UL;log(String("WLAN-Maske: http://")+WiFi.localIP().toString());}else if(!configPortalActive)startFallbackPortal();}
void ESPManagerClass::ensureMqtt(){if(mq.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastMqttRetry<5000UL)return;lastMqttRetry=millis();String id=String("espmanager-")+ESPMANAGER_DEVICE_ID;bool ok=String(ESPMANAGER_MQTT_USER).length()?mq.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(base()+"/availability").c_str(),0,true,"offline"):mq.connect(id.c_str(),(base()+"/availability").c_str(),0,true,"offline");if(ok){mq.publish((base()+"/availability").c_str(),"online",true);mq.subscribe((base()+"/cmd/#").c_str());log("MQTT verbunden");publishStatus();}else log(String("MQTT-Verbindung fehlgeschlagen, Status=")+String(mq.state()));}
void ESPManagerClass::publishStatus(){lastStatus=millis();if(!mq.connected())return;JsonDocument d;d["device_id"]=ESPMANAGER_DEVICE_ID;d["firmware_version"]=ESPMANAGER_FW_VERSION;d["ip"]=WiFi.localIP().toString();d["ssid"]=WiFi.SSID();d["rssi"]=WiFi.RSSI();d["uptime"]=millis()/1000UL;d["free_heap"]=ESP.getFreeHeap();d["wifi_portal"]=configPortalActive||webPortalActive;String o;serializeJson(d,o);mq.publish((base()+"/status").c_str(),o.c_str(),true);}
void ESPManagerClass::log(const String&m){Serial.println(String("[ESPManager] ")+m);if(mq.connected())mq.publish((base()+"/log").c_str(),m.c_str());}
void ESPManagerClass::publishSensor(const char*k,double v){char b[32];snprintf(b,sizeof(b),"%.3f",v);if(mq.connected())mq.publish((base()+"/sensor/"+k).c_str(),b,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){JsonDocument d;if(deserializeJson(d,p))return;if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Kommando abgelehnt");return;}if(t.endsWith("/cmd/restart"))ESP.restart();if(t.endsWith("/cmd/wifi_portal"))openWifiPortal();if(t.endsWith("/cmd/ota")){String u=d["url"]|"";if(!u.length())return;
#ifdef ESP8266
ESPhttpUpdate.update(net,u);
#else
httpUpdate.update(net,u);
#endif
}}
