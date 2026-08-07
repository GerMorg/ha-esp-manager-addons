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

static WiFiClient networkClient;
static PubSubClient mqttClient(networkClient);
static WiFiManager wifiManager;
ESPManagerClass ESPManager;

static String baseTopic() { return String("espmanager/") + ESPMANAGER_DEVICE_ID; }
static String portalName() { return String("ESPManager-") + ESPMANAGER_DEVICE_ID; }
static void mqttCallback(char *topic, byte *payload, unsigned int length) {
  String body;
  for (unsigned int i = 0; i < length; i++) body += (char)payload[i];
  ESPManager.handleCommand(String(topic), body);
}

void ESPManagerClass::begin() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  wifiManager.setConfigPortalBlocking(false);
  wifiManager.setConfigPortalTimeout(0);
  wifiManager.setConnectTimeout(20);
  bool connected = wifiManager.autoConnect(portalName().c_str());
  configPortalActive = !connected;
  if (connected) {
    wifiManager.startWebPortal();
    webPortalActive = true;
    webPortalUntil = millis() + 600000UL;
    log(String("WLAN verbunden: ") + WiFi.SSID() + " / " + WiFi.localIP().toString());
    log("WLAN-Konfigurationsmaske ist nach dem Start 10 Minuten über die Geräte-IP erreichbar.");
  } else {
    log(String("WLAN-Fallback aktiv: ") + portalName() + " / 192.168.4.1");
  }
  mqttClient.setServer(ESPMANAGER_MQTT_HOST, ESPMANAGER_MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  ensureMqtt();
}

void ESPManagerClass::loop() {
  wifiManager.process();
  if (WiFi.status() == WL_CONNECTED) {
    disconnectedSince = 0;
    if (configPortalActive) {
      wifiManager.stopConfigPortal();
      configPortalActive = false;
    }
    ensureMqtt();
    mqttClient.loop();
    if (millis() - lastStatus > 30000UL) publishStatus();
    if (webPortalActive && webPortalUntil && (long)(millis() - webPortalUntil) >= 0) {
      wifiManager.stopWebPortal();
      webPortalActive = false;
    }
  } else {
    if (!disconnectedSince) disconnectedSince = millis();
    if (!configPortalActive && millis() - disconnectedSince > 60000UL) startFallbackPortal();
  }
}

void ESPManagerClass::startFallbackPortal() {
  wifiManager.setConfigPortalBlocking(false);
  wifiManager.startConfigPortal(portalName().c_str());
  configPortalActive = true;
  log(String("Router länger nicht erreichbar. Fallback-WLAN aktiv: ") + portalName());
}

void ESPManagerClass::openWifiPortal() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!webPortalActive) wifiManager.startWebPortal();
    webPortalActive = true;
    webPortalUntil = millis() + 600000UL;
    log(String("WLAN-Maske 10 Minuten erreichbar: http://") + WiFi.localIP().toString());
  } else if (!configPortalActive) {
    startFallbackPortal();
  }
}

void ESPManagerClass::ensureMqtt() {
  if (mqttClient.connected() || WiFi.status() != WL_CONNECTED || millis() - lastMqttRetry < 5000UL) return;
  lastMqttRetry = millis();
  String clientId = String("espmanager-") + ESPMANAGER_DEVICE_ID;
  bool ok;
  if (String(ESPMANAGER_MQTT_USER).length()) {
    ok = mqttClient.connect(clientId.c_str(), ESPMANAGER_MQTT_USER, ESPMANAGER_MQTT_PASS,
      (baseTopic()+"/availability").c_str(), 0, true, "offline");
  } else {
    ok = mqttClient.connect(clientId.c_str(), (baseTopic()+"/availability").c_str(), 0, true, "offline");
  }
  if (ok) {
    mqttClient.publish((baseTopic()+"/availability").c_str(), "online", true);
    mqttClient.subscribe((baseTopic()+"/cmd/#").c_str());
    publishStatus();
  }
}

void ESPManagerClass::publishStatus() {
  lastStatus = millis();
  if (!mqttClient.connected()) return;
  JsonDocument doc;
  doc["device_id"] = ESPMANAGER_DEVICE_ID;
  doc["firmware_version"] = ESPMANAGER_FW_VERSION;
  doc["ip"] = WiFi.localIP().toString();
  doc["ssid"] = WiFi.SSID();
  doc["rssi"] = WiFi.RSSI();
  doc["uptime"] = millis() / 1000UL;
  doc["wifi_portal"] = configPortalActive || webPortalActive;
  String out; serializeJson(doc, out);
  mqttClient.publish((baseTopic()+"/status").c_str(), out.c_str(), true);
}

void ESPManagerClass::log(const String &message) {
  Serial.println(message);
  if (mqttClient.connected()) mqttClient.publish((baseTopic()+"/log").c_str(), message.c_str());
}

void ESPManagerClass::publishSensor(const char *key, double value) {
  char valueText[32];
  snprintf(valueText, sizeof(valueText), "%.3f", value);
  if (mqttClient.connected()) mqttClient.publish((baseTopic()+"/sensor/"+key).c_str(), valueText, true);
}

void ESPManagerClass::handleCommand(const String &topic, const String &payload) {
  JsonDocument doc;
  if (deserializeJson(doc, payload)) return;
  if (String((const char*)(doc["token"] | "")) != String(ESPMANAGER_OTA_TOKEN)) {
    log("Kommando abgelehnt: ungültiger Token");
    return;
  }
  if (topic.endsWith("/cmd/restart")) ESP.restart();
  if (topic.endsWith("/cmd/wifi_portal")) openWifiPortal();
  if (topic.endsWith("/cmd/ota")) {
    String url = doc["url"] | "";
    if (!url.length()) return;
#ifdef ESP8266
    ESPhttpUpdate.update(networkClient, url);
#else
    httpUpdate.update(networkClient, url);
#endif
  }
}
