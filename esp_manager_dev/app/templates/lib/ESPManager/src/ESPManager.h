#pragma once
#include <Arduino.h>
#ifndef ESPMANAGER_DEVICE_ID
#define ESPMANAGER_DEVICE_ID "device"
#endif
#ifndef ESPMANAGER_FW_VERSION
#define ESPMANAGER_FW_VERSION "0.0.0"
#endif
#ifndef ESPMANAGER_MQTT_HOST
#define ESPMANAGER_MQTT_HOST "homeassistant.local"
#endif
#ifndef ESPMANAGER_MQTT_PORT
#define ESPMANAGER_MQTT_PORT 1883
#endif
#ifndef ESPMANAGER_MQTT_USER
#define ESPMANAGER_MQTT_USER ""
#endif
#ifndef ESPMANAGER_MQTT_PASS
#define ESPMANAGER_MQTT_PASS ""
#endif
#ifndef ESPMANAGER_OTA_TOKEN
#define ESPMANAGER_OTA_TOKEN ""
#endif
class ESPManagerClass{public:typedef void(*Handler)(const String&,const String&);struct E{String t,id,n,u,unit,dc,sc,vt;float lo=0,hi=100,step=1;bool pos=true;};void begin();void loop();void log(const String&);void publishSensor(const char*,double);bool publishState(const char*,const String&,bool=true);void onCommand(Handler);void registerSensor(const char*,const char*,const char*,const char*="",const char*="",const char*="measurement",const char*="");void registerBinarySensor(const char*,const char*,const char*,const char*="");void registerSwitch(const char*,const char*,const char*);void registerNumber(const char*,const char*,const char*,float,float,float,const char*="");void registerCover(const char*,const char*,const char*,bool=true);void command(const String&,const String&);private:E es[48];uint8_t ec=0;Handler handler=nullptr;unsigned long lastMqtt=0,lostAt=0,lastRetry=0;bool portal=false;void connectMqtt();void discover();void add(E);};extern ESPManagerClass ESPManager;
