#include <Arduino.h>
#include <ESPManager.h>
constexpr uint8_t LED_PIN = 2;
bool enabled = false;
uint32_t intervalMs = 1000, lastToggle = 0;
void command(const String& id, const String& value) {
  if (id == "led") {
    enabled = value == "ON";
    if (!enabled) digitalWrite(LED_PIN, LOW);
    ESPManager.publishState("led", enabled ? "ON" : "OFF");
  } else if (id == "blink_interval") {
    intervalMs = constrain(value.toInt(), 100L, 5000L);
    ESPManager.publishState("blink_interval", String(intervalMs));
  }
}
void setupDevice() {
  pinMode(LED_PIN, OUTPUT);
  ESPManager.registerSwitch("led", "Test LED", "led_number_test_led");
  ESPManager.registerNumber("blink_interval", "Blinkintervall", "led_number_test_interval", 100, 5000, 100, "ms");
  ESPManager.onCommand(command);
  ESPManager.publishState("led", "OFF");
  ESPManager.publishState("blink_interval", String(intervalMs));
}
void loopDevice() {
  if (enabled && millis() - lastToggle >= intervalMs) {
    lastToggle = millis();
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
  }
}
