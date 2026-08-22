#include <Arduino.h>
#include <ESPManager.h>
#include <ESPManagerEntities.h>
extern void setupDevice();extern void loopDevice();
void setup(){ESPManager.begin();registerManagedEntities();setupDevice();}
void loop(){ESPManager.loop();loopDevice();}
