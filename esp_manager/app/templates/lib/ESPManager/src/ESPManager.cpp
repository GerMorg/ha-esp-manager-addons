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
static WiFiClient networkClient;static PubSubClient mqttClient(networkClient);static WiFiManager wifiManager;ESPManagerClass ESPManager;
static String baseTopic(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}static String portalName(){return String("ESPManager-")+ESPMANAGER_DEVICE_ID;}
static void mqttCallback(char*topic,byte*payload,unsigned int length){String body;for(unsigned int i=0;i<length;i++)body+=(char)payload[i];ESPManager.handleCommand(String(topic),body);}
void ESPManagerClass::begin(){Serial.begin(115200);delay(150);Serial.println();Serial.println("[ESPManager] Agent startet");WiFi.mode(WIFI_STA);wifiManager.setConfigPortalBlocking(false);wifiManager.setConfigPortalTimeout(0);wifiManager.setConnectTimeout(20);bool connected=wifiManager.autoConnect(portalName().c_str());configPortalActive=!connected;if(connected){wifiManager.startWebPortal();webPortalActive=true;webPortalUntil=millis()+600000UL;log(String("WLAN verbunden: ")+WiFi.SSID()+" IP="+WiFi.localIP().toString());}else{log(String("Fallback-WLAN aktiv: ")+portalName()+" IP=192.168.4.1");}mqttClient.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mqttClient.setCallback(mqttCallback);ensureMqtt();}
void ESPManagerClass::loop(){wifiManager.process();if(WiFi.status()==WL_CONNECTED){disconnectedSince=0;if(configPortalActive){wifiManager.stopConfigPortal();configPortalActive=false;}ensureMqtt();mqttClient.loop();if(millis()-lastStatus>30000UL)publishStatus();if(webPortalActive&&webPortalUntil&&(long)(millis()-webPortalUntil)>=0){wifiManager.stopWebPortal();webPortalActive=false;}}else{if(!disconnectedSince)disconnectedSince=millis();if(!configPortalActive&&millis()-disconnectedSince>60000UL)startFallbackPortal();}}
void ESPManagerClass::startFallbackPortal(){wifiManager.setConfigPortalBlocking(false);wifiManager.startConfigPortal(portalName().c_str());configPortalActive=true;log(String("Router nicht erreichbar. Fallback-WLAN: ")+portalName());}
void ESPManagerClass::openWifiPortal(){if(WiFi.status()==WL_CONNECTED){if(!webPortalActive)wifiManager.startWebPortal();webPortalActive=true;webPortalUntil=millis()+600000UL;log(String("WLAN-Maske: http://")+WiFi.localIP().toString());}else if(!configPortalActive)startFallbackPortal();}
void ESPManagerClass::ensureMqtt(){if(mqttClient.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastMqttRetry<5000UL)return;lastMqttRetry=millis();String id=String("espmanager-")+ESPMANAGER_DEVICE_ID;bool ok=String(ESPMANAGER_MQTT_USER).length()?mqttClient.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(baseTopic()+"/availability").c_str(),0,true,"offline"):mqttClient.connect(id.c_str(),(baseTopic()+"/availability").c_str(),0,true,"offline");if(ok){mqttClient.publish((baseTopic()+"/availability").c_str(),"online",true);mqttClient.subscribe((baseTopic()+"/cmd/#").c_str());log("MQTT verbunden");publishStatus();}}
void ESPManagerClass::publishStatus(){lastStatus=millis();if(!mqttClient.connected())return;JsonDocument d;d["device_id"]=ESPMANAGER_DEVICE_ID;d["firmware_version"]=ESPMANAGER_FW_VERSION;d["ip"]=WiFi.localIP().toString();d["ssid"]=WiFi.SSID();d["rssi"]=WiFi.RSSI();d["uptime"]=millis()/1000UL;d["free_heap"]=ESP.getFreeHeap();d["wifi_portal"]=configPortalActive||webPortalActive;String out;serializeJson(d,out);mqttClient.publish((baseTopic()+"/status").c_str(),out.c_str(),true);}
void ESPManagerClass::log(const String&m){Serial.println(String("[ESPManager] ")+m);if(mqttClient.connected())mqttClient.publish((baseTopic()+"/log").c_str(),m.c_str());}
void ESPManagerClass::publishSensor(const char*k,double v){char b[32];snprintf(b,sizeof(b),"%.3f",v);if(mqttClient.connected())mqttClient.publish((baseTopic()+"/sensor/"+k).c_str(),b,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){JsonDocument d;if(deserializeJson(d,p))return;if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Kommando abgelehnt");return;}if(t.endsWith("/cmd/restart"))ESP.restart();if(t.endsWith("/cmd/wifi_portal"))openWifiPortal();if(t.endsWith("/cmd/ota")){String u=d["url"]|"";if(!u.length())return;
#ifdef ESP8266
ESPhttpUpdate.update(networkClient,u);
#else
httpUpdate.update(networkClient,u);
#endif
}}
