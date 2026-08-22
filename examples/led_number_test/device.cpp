#include <Arduino.h>
#include <ESPManager.h>
constexpr int LED_PIN=2;bool enabled=false,state=false;uint32_t interval=1000,last=0;
void command(const String&id,const String&v){if(id=="led"){enabled=v=="ON";ESPManager.publishState("led",enabled?"ON":"OFF");}else if(id=="interval"){interval=constrain(v.toInt(),100L,5000L);ESPManager.publishState("interval",String(interval));}}
void setupDevice(){pinMode(LED_PIN,OUTPUT);ESPManager.onCommand(command);}void loopDevice(){if(enabled&&millis()-last>=interval){last=millis();state=!state;digitalWrite(LED_PIN,state);}}
