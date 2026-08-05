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
static WiFiClient net; static PubSubClient mq(net); ESPManagerClass ESPManager;
static String base(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}
static void callback(char*t,byte*p,unsigned int l){String b;for(unsigned int i=0;i<l;i++)b+=(char)p[i];ESPManager.handleCommand(t,b);}
void ESPManagerClass::begin(){Serial.begin(115200);WiFi.mode(WIFI_STA);if(WiFi.status()!=WL_CONNECTED){WiFiManager wm;wm.setConfigPortalTimeout(180);String ap=String("ESPManager-")+ESPMANAGER_DEVICE_ID;if(!wm.autoConnect(ap.c_str()))ESP.restart();}mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mq.setCallback(callback);connectMqtt();status();}
void ESPManagerClass::loop(){if(WiFi.status()!=WL_CONNECTED)WiFi.reconnect();connectMqtt();mq.loop();if(millis()-lastStatus>30000)status();}
void ESPManagerClass::connectMqtt(){if(mq.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastRetry<5000)return;lastRetry=millis();String id=String("espmanager-")+ESPMANAGER_DEVICE_ID;bool ok=String(ESPMANAGER_MQTT_USER).length()?mq.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(base()+"/availability").c_str(),0,true,"offline"):mq.connect(id.c_str(),(base()+"/availability").c_str(),0,true,"offline");if(ok){mq.publish((base()+"/availability").c_str(),"online",true);mq.subscribe((base()+"/cmd/#").c_str());}}
void ESPManagerClass::status(){lastStatus=millis();if(!mq.connected())return;JsonDocument d;d["device_id"]=ESPMANAGER_DEVICE_ID;d["firmware_version"]=ESPMANAGER_FW_VERSION;d["ip"]=WiFi.localIP().toString();d["rssi"]=WiFi.RSSI();d["uptime"]=millis()/1000;String o;serializeJson(d,o);mq.publish((base()+"/status").c_str(),o.c_str(),true);}
void ESPManagerClass::log(const String&m){Serial.println(m);if(mq.connected())mq.publish((base()+"/log").c_str(),m.c_str());}
void ESPManagerClass::publishSensor(const char*k,double v){char b[32];snprintf(b,sizeof(b),"%.3f",v);if(mq.connected())mq.publish((base()+"/sensor/"+k).c_str(),b,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){JsonDocument d;if(deserializeJson(d,p))return;if(String((const char*)(d["token"]|""))!=String(ESPMANAGER_OTA_TOKEN)){log("Kommando abgelehnt");return;}if(t.endsWith("/restart"))ESP.restart();if(t.endsWith("/ota")){String u=d["url"]|"";if(!u.length())return;
#ifdef ESP8266
ESPhttpUpdate.update(net,u);
#else
httpUpdate.update(net,u);
#endif
}}
