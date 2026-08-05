#pragma once
#include <Arduino.h>
#ifndef ESPMANAGER_DEVICE_ID
#define ESPMANAGER_DEVICE_ID "espmanager_device"
#endif
#define ESPM_LOG(message) ESPManager.log(String(message))
class ESPManagerClass{public:void begin();void loop();void log(const String&);void publishSensor(const char*,double);};
extern ESPManagerClass ESPManager;
