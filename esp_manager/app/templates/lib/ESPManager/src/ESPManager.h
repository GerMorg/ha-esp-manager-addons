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
#ifndef ESPMANAGER_WIFI_RECONNECT_INTERVAL
#define ESPMANAGER_WIFI_RECONNECT_INTERVAL 15000UL
#endif
#ifndef ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER
#define ESPMANAGER_WIFI_RECOVERY_RESTART_AFTER 900000UL
#endif
#define ESPM_LOG(x) ESPManager.log(String(x))
class ESPManagerClass{public:typedef void(*CommandHandler)(const String&,const String&);struct E{String type,id,name,uid,unit,dc,sc,vt;float lo=0,hi=100,step=1;bool pos=true;};void begin();void loop();void log(const String&);void publishSensor(const char*,double);void handleCommand(const String&,const String&);void onCommand(CommandHandler);void registerSensor(const char*,const char*,const char*,const char* ="",const char* ="",const char* ="measurement",const char* ="");void registerBinarySensor(const char*,const char*,const char*,const char* ="");void registerSwitch(const char*,const char*,const char*);void registerNumber(const char*,const char*,const char*,float,float,float,const char* ="");void registerCover(const char*,const char*,const char*,bool=true);bool publishState(const char*,const String&,bool=true);private:E es[32];uint8_t ec=0;CommandHandler cb=nullptr;enum W:uint8_t{OK,RETRY,PORTAL,FINAL};W ws=RETRY;unsigned long lastStatus=0,lastMqtt=0,lost=0,lastRetry=0;bool portal=false;void mqttConnect();void status();void discovery();void entityCommand(const String&,const String&);void startPortal();void stopPortal();void reconnect();void recovered();};extern ESPManagerClass ESPManager;
