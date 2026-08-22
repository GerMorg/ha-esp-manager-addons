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
class ESPManagerClass {
public:
  void begin(); void loop(); void log(const String&); void publishSensor(const char*,double); void handleCommand(const String&,const String&);
  bool registerSensor(const char* key,const char* name,const char* uniqueId,const char* unit="",const char* deviceClass="",const char* stateClass="measurement",const char* valueTemplate="",bool forceUpdate=false);
private:
  enum WifiRecoveryState:uint8_t{WIFI_OK,WIFI_RETRY,WIFI_PORTAL,WIFI_FINAL_RETRY};
  struct SensorDef{String key,name,uniqueId,unit,deviceClass,stateClass,valueTemplate;bool forceUpdate=false;};
  static const uint8_t MAX_DISCOVERY_SENSORS=24; SensorDef sensors[MAX_DISCOVERY_SENSORS]; uint8_t sensorCount=0;
  WifiRecoveryState wifiState=WIFI_RETRY; unsigned long lastStatus=0,lastMqtt=0,wifiLostAt=0,lastWifiRetry=0; bool portalActive=false;
  void mqttConnect(); void status(); void beginWifiRecovery(); void startFallbackPortal(); void stopFallbackPortal(); void tryWifiReconnect(const char*); void wifiRecovered();
  void registerLegacySmartmeter(); void publishDiscovery(); void publishDiscovery(const SensorDef&); String slug(const String&)const;
};
extern ESPManagerClass ESPManager;
