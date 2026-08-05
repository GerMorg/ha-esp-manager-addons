#include <Arduino.h>
#include <ESPManager.h>
void setupDevice(){ ESPM_LOG("setupDevice gestartet"); }
void loopDevice(){ static unsigned long last=0; if(millis()-last>10000){ last=millis(); ESPM_LOG("Heartbeat"); ESPManager.publishSensor("example_value", millis()/1000.0); } }
