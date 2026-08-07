#pragma once
#include <Arduino.h>
#ifndef ESPMANAGER_DEVICE_ID
#define ESPMANAGER_DEVICE_ID "espmanager_device"
#endif
#ifndef ESPMANAGER_FW_VERSION
#define ESPMANAGER_FW_VERSION "0.0.0"
#endif
#ifndef ESPMANAGER_MQTT_HOST
#define ESPMANAGER_MQTT_HOST "core-mosquitto"
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
#define ESPM_LOG(message) ESPManager.log(String(message))
class ESPManagerClass {
public:
  void begin();
  void loop();
  void log(const String &message);
  void publishSensor(const char *key, double value);
  void openWifiPortal();
  void handleCommand(const String &topic, const String &payload);
private:
  void ensureMqtt();
  void publishStatus();
  void startFallbackPortal();
  unsigned long lastStatus = 0;
  unsigned long lastMqttRetry = 0;
  unsigned long disconnectedSince = 0;
  unsigned long webPortalUntil = 0;
  bool configPortalActive = false;
  bool webPortalActive = false;
};
extern ESPManagerClass ESPManager;
