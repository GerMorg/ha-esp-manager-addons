# MQTT Discovery in ESP Manager 0.11.0

## Allgemeines Projekt

Sensoren einmalig in `setupDevice()` registrieren:

```cpp
void setupDevice() {
  ESPManager.registerSensor(
    "temperature",
    "Gartentemperatur",
    "garten_temperatur",
    "°C",
    "temperature",
    "measurement"
  );
}
```

Messwerte anschließend wie bisher veröffentlichen:

```cpp
void loopDevice() {
  ESPManager.publishSensor("temperature", temperatur);
}
```

Daraus entstehen:

- Zustand: `espmanager/<device_id>/sensor/temperature`
- Discovery: `homeassistant/sensor/<device_id>/garten_temperatur/config`
- Verfügbarkeit: `espmanager/<device_id>/availability`

Signatur:

```cpp
bool registerSensor(
  const char* key,
  const char* name,
  const char* uniqueId,
  const char* unit = "",
  const char* deviceClass = "",
  const char* stateClass = "measurement",
  const char* valueTemplate = "",
  bool forceUpdate = false
);
```

Maximal 24 Sensoren können pro Firmware registriert werden. Die Discovery-Konfiguration wird retained veröffentlicht und nach jeder MQTT-Neuverbindung erneut gesendet.

## Smartmeter-Kompatibilität

Bei `device_id=smartmeter` registriert der Agent automatisch die elf bisherigen Sensoren mit unveränderten `unique_id`-Werten. Der funktionierende Decoder bleibt unverändert und verwendet weiterhin `publishSensor()`.

Die manuelle MQTT-YAML erst entfernen, nachdem in Home Assistant geprüft wurde, dass die bisherigen Entity-IDs weiterverwendet werden. Bei Duplikaten die neuen Discovery-Entitäten deaktivieren und die YAML vorerst behalten.
