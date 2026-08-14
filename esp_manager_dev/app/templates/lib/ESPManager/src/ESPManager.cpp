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
static WiFiClient mqttNet,otaNet;static PubSubClient mq(mqttNet);static WiFiManager wm;ESPManagerClass ESPManager;static String base(){return String("espmanager/")+ESPMANAGER_DEVICE_ID;}static void callback(char*t,byte*p,unsigned int n){String s;for(unsigned i=0;i<n;i++)s+=(char)p[i];ESPManager.handleCommand(t,s);}static void progress(const String&s,int p,const String&m){JsonDocument d;d["state"]=s;d["percent"]=p;d["message"]=m;String o;serializeJson(d,o);if(mq.connected())mq.publish((base()+"/ota/progress").c_str(),o.c_str(),true);}
void ESPManagerClass::begin(){Serial.begin(115200);WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(true);WiFi.persistent(true);wm.setConfigPortalBlocking(false);wm.autoConnect((String("ESPManager-")+ESPMANAGER_DEVICE_ID).c_str());mq.setServer(ESPMANAGER_MQTT_HOST,ESPMANAGER_MQTT_PORT);mq.setBufferSize(2048);mq.setCallback(callback);mqttConnect();}
void ESPManagerClass::loop(){wm.process();unsigned long now=millis();if(WiFi.status()==WL_CONNECTED){lostAt=0;mqttConnect();mq.loop();if(now-lastStatus>30000)status();}else{if(!lostAt)lostAt=now;if(now-lastWifi>ESPMANAGER_WIFI_RECONNECT_INTERVAL){lastWifi=now;WiFi.mode(WIFI_STA);WiFi.reconnect();}if(now-lostAt>60000)wm.startConfigPortal((String("ESPManager-")+ESPMANAGER_DEVICE_ID).c_str());if(now-lostAt>ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER)ESP.restart();}}
void ESPManagerClass::mqttConnect(){if(mq.connected()||WiFi.status()!=WL_CONNECTED||millis()-lastMqtt<5000)return;lastMqtt=millis();String id=String("esp-")+ESPMANAGER_DEVICE_ID;bool ok=String(ESPMANAGER_MQTT_USER).length()?mq.connect(id.c_str(),ESPMANAGER_MQTT_USER,ESPMANAGER_MQTT_PASS,(base()+"/availability").c_str(),0,true,"offline"):mq.connect(id.c_str(),(base()+"/availability").c_str(),0,true,"offline");if(ok){mq.publish((base()+"/availability").c_str(),"online",true);mq.subscribe((base()+"/cmd/#").c_str());status();}}
void ESPManagerClass::status(){lastStatus=millis();JsonDocument d;d["device_id"]=ESPMANAGER_DEVICE_ID;d["firmware_version"]=ESPMANAGER_FW_VERSION;d["ip"]=WiFi.localIP().toString();d["ssid"]=WiFi.SSID();d["rssi"]=WiFi.RSSI();d["uptime"]=millis()/1000;d["free_heap"]=ESP.getFreeHeap();String o;serializeJson(d,o);mq.publish((base()+"/status").c_str(),o.c_str(),true);}void ESPManagerClass::log(const String&s){Serial.println(s);if(mq.connected())mq.publish((base()+"/log").c_str(),s.c_str());}void ESPManagerClass::publishSensor(const char*k,double v){char b[32];snprintf(b,sizeof(b),"%.3f",v);if(mq.connected())mq.publish((base()+"/sensor/"+k).c_str(),b,true);}
void ESPManagerClass::handleCommand(const String&t,const String&p){JsonDocument d;if(deserializeJson(d,p))return;if(String((const char*)(d["token"]|""))!=ESPMANAGER_OTA_TOKEN)return;if(t.endsWith("/cmd/restart"))ESP.restart();if(t.endsWith("/cmd/ota")){String u=d["url"]|"";progress("received",0,"Kommando empfangen");
#ifdef ESP8266
 ESPhttpUpdate.rebootOnUpdate(false);auto r=ESPhttpUpdate.update(otaNet,u);
#else
 httpUpdate.rebootOnUpdate(false);auto r=httpUpdate.update(otaNet,u);
#endif
 if(r==HTTP_UPDATE_OK){progress("finished",100,"Update vollständig, Neustart folgt");for(int i=0;i<8;i++){mq.loop();delay(100);}ESP.restart();}else progress("failed",0,"Update fehlgeschlagen");}}
