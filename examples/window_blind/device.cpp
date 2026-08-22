#include <Arduino.h>
#include <ESPManager.h>
void command(const String&id,const String&value){if(id=="blind")ESPManager.publishState("blind",value);else if(id=="blind_position")ESPManager.publishState("blind_position",String(constrain(value.toInt(),0,100)));}
void setupDevice(){ESPManager.registerCover("blind","Fensterverdunkelung","bedroom_blind",true);ESPManager.registerSwitch("automatic","Automatik","bedroom_blind_automatic");ESPManager.registerNumber("sun_threshold","Helligkeitsschwelle","bedroom_blind_sun_threshold",0,100000,100,"lx");ESPManager.registerBinarySensor("window_open","Fenster offen","bedroom_window_open","window");ESPManager.registerSensor("illuminance","Helligkeit","bedroom_illuminance","lx","illuminance","measurement","");ESPManager.onCommand(command);}void loopDevice(){}



