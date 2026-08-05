#include "ESPManager.h"
#ifdef ESP8266
#include <ESP8266WiFi.h>
#else
#include <WiFi.h>
#endif
#include <WiFiManager.h>
ESPManagerClass ESPManager;
void ESPManagerClass::begin(){Serial.begin(115200);WiFi.mode(WIFI_STA);if(WiFi.status()!=WL_CONNECTED){WiFiManager wm;String ap=String("ESPManager-")+ESPMANAGER_DEVICE_ID;wm.autoConnect(ap.c_str());}}
void ESPManagerClass::loop(){if(WiFi.status()!=WL_CONNECTED)WiFi.reconnect();}
void ESPManagerClass::log(const String&m){Serial.println(m);}
