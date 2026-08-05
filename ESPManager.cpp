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
static WiFiClient wifiClient; static PubSubClient mqttClient(wifiClient); ESPManagerClass ESPManager;
static String baseTopic(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}
static void cb(char*t, byte*p, unsigned int l){String b; for(unsigned int i=0;i<l;i++) b+=(char)p[i]; ESPManager.handleCommand(String(t),b);}
void ESPManagerClass::begin(){Serial.begin(115200); WiFi.mode(WIFI_STA); if(WiFi.status()!=WL_CONNECTED){WiFiManager wm; wm.setConfigPortalTimeout(180); String ap=String("ESPManager-")+ESPMANAGER_DEVICE_ID; if(!wm.autoConnect(ap.c_str())) ESP.restart();} mqttClient.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT); mqttClient.setCallback(cb); ensureMqtt(); publishStatus();}
void ESPManagerClass::loop(){ if(WiFi.status()!=WL_CONNECTED) WiFi.reconnect(); ensureMqtt(); mqttClient.loop(); if(millis()-lastStatus>30000) publishStatus();}
void ESPManagerClass::ensureMqtt(){ if(mqttClient.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastReconnect<5000)return; lastReconnect=millis(); String id=String("espmanager-")+ESPMANAGER_DEVICE_ID; bool ok=String(ESPMANAGER_MQTT_USER).length()?mqttClient.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(baseTopic()+"/availability").c_str(),0,true,"offline"):mqttClient.connect(id.c_str(),(baseTopic()+"/availability").c_str(),0,true,"offline"); if(ok){mqttClient.publish((baseTopic()+"/availability").c_str(),"online",true); mqttClient.subscribe((baseTopic()+"/cmd/#").c_str()); log("MQTT verbunden");}}
void ESPManagerClass::publishStatus(){lastStatus=millis(); if(!mqttClient.connected())return; JsonDocument d; d["device_id"]=ESPMANAGER_DEVICE_ID; d["firmware_version"]=ESPMANAGER_FW_VERSION; d["ip"]=WiFi.localIP().toString(); d["rssi"]=WiFi.RSSI(); d["uptime"]=millis()/1000; String out; serializeJson(d,out); mqttClient.publish((baseTopic()+"/status").c_str(),out.c_str(),true);}
void ESPManagerClass::log(const String&m){Serial.println(m); if(mqttClient.connected()) mqttClient.publish((baseTopic()+"/log").c_str(),m.c_str());}
void ESPManagerClass::publishSensor(const char*key,double value){ if(!mqttClient.connected())return; char buf[32]; snprintf(buf,sizeof(buf),"%.3f",value); mqttClient.publish((baseTopic()+"/sensor/"+key).c_str(),buf,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){
  JsonDocument d; if(deserializeJson(d,p))return;
  if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Command rejected: invalid token"); return;}
  if(t.endsWith("/cmd/restart")){ESP.restart();}
  if(t.endsWith("/cmd/ota")){
    String url=d["url"]|""; if(!url.length())return; log(String("OTA: ")+url);
#ifdef ESP8266
    ESPhttpUpdate.update(wifiClient,url);
#else
    httpUpdate.update(wifiClient,url);
#endif
  }
}
