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
class ESPManagerClass{public:void begin();void loop();void log(const String&);void publishSensor(const char*,double);void handleCommand(const String&,const String&);private:unsigned long lastStatus=0,lastMqtt=0,lostAt=0,lastWifi=0;void mqttConnect();void status();};extern ESPManagerClass ESPManager;
