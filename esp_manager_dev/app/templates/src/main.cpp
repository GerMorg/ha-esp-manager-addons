// AUTOMATISCH VOM ESP MANAGER VERWALTET. NICHT BEARBEITEN.
#include <Arduino.h>
#include <ESPManager.h>
extern void setupDevice();
extern void loopDevice();
void setup(){ ESPManager.begin(); setupDevice(); }
void loop(){ ESPManager.loop(); loopDevice(); }
