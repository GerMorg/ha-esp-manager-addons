# Changelog

## 0.5.5
- Mehrchip-USB-Erstinstallation für ESP8266, klassischen ESP32, ESP32-S2, ESP32-S3, ESP32-C3 und ESP32-C6 vorbereitet.
- Boardauswahl um WROOM-32/ESP32 DevKit, S2 Saola, S3 DevKitC, C3 DevKitM und C6 DevKitC erweitert.
- ESP8266 verwendet weiterhin seine einzelne Firmwaredatei ab Offset 0.
- ESP32-Familien erhalten nach dem Build automatisch ein vollständiges `initial_firmware.bin`.
- Bootloader, Partitionstabelle, Boot-App und Anwendung werden mit PlatformIO-esptool zusammengeführt.
- USB-Manifest verwendet das zum Projekt gespeicherte Chipprofil und das vollständige Initial-Image ab Offset 0.
- OTA-Firmware bleibt separat als reine Anwendungsfirmware erhalten.
- Build-Historie speichert Board, Chipfamilie und Größe des Initial-Images.
