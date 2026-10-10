# Konkreter Kamera-Befund

Am 10. Oktober 2026 wurden die folgenden **gegenwärtig vorhandenen** Windows-PnP-Geräte und Treiberbindungen nur lesend festgestellt. Es wurde kein Bild aufgenommen.

| Baustein | Generische Hardwarekennung | Gebundener Dienst | Windows-Version | Zuordnung |
|---|---|---|---|---|
| Intel Imaging Signal Processor | PCI `8086:645D`, Subsystem `C1DD144D`, Revision `04` | `iaisp64_lnl` | `70.26100.2.18321` | Lunar-Lake-IPU7-Bildprozessor |
| Samsung Camera Front | ACPI `OVTI02E1` | `OV02E10` | `70.26100.0.16` | OmniVision-OV02E10-Sensor |
| Intel LNL AVStream Camera | `VIDEO\VEN_8086&DEV_64A0&SUBSYS_C1DD144D&INT3480` | `camera` | `70.26100.2.18321` | Windows-Aufnahmeschnittstelle |
| Camera control logic | ACPI `INT3472` | `iactrllogic` | getrennt zu qualifizieren | Sensorversorgung/Steuerlogik als weiterer Baustein |
| Ugreen Storage Device | USB `0BDA:9201`, Klasse `08/06/50` | `USBSTOR` | Windows-Inbox-Treiber | Massenspeicher, keine Kamera |

Alle drei für die Profilzuordnung benötigten Geräte hatten Windows-PnP-Problemcode 0. Das ist ein Bindungsnachweis unter Windows und kein Test der Bildqualität oder des vollständigen Aufnahmepfads.

Die `64A0`-Kennung der AVStream-Schnittstelle steht im **VIDEO**-Enumerator. Die identische Zahl beim Grafik-PCI-Gerät darf nicht als Kamera-Profilbeweis verwendet werden. Der Prüfer fordert zusätzlich den passenden Enumerator, `INT3480` und beide Samsung-Subsystemkennungen.

Die Sensor-INF bindet tatsächlich `ACPI\OVTI02E1`, den Dienst `OV02E10`, den Kernel-Treiber `OV02E10.sys` und die Abhängigkeiten `SpbCx,inteli2c`. Sie nennt zudem die Bildpipeline-Dateien `OV02E10_KADC832_LNL.aiqb`, `.cpf` und `graph_settings_OV02E10_KADC832_LNL.bin`. Diese Dateien wurden nicht kopiert oder veröffentlicht. Abweichende Sensorkennungen in historischen INF-Kommentaren wurden nicht als Hardwarebeleg verwendet.

Der aktuelle Profilnachweis enthält keinen separat identifizierten IR-Sensor. Das beweist nicht die physische Abwesenheit jeder IR-Funktion. Windows Studio Effects ist eine Softwarekomponente; der Egis-Fingerabdrucksensor ist keine IR-Kamera. Face ID, Windows Hello und Camera-Extension-Funktionen sind hier nicht implementiert.

[Samsung nennt für genau NP960XHA-KG3DE eine 2,0-MP-Kamera](https://www.samsung.com/de/business/computers/galaxy-book/galaxy-book5-pro-16-inch-ultra-5-16gb-512gb-np960xha-kg3de/). Die Kameramodellzuordnung OV02E10 beruht auf dem oben genannten realen PnP-/Dienst-/INF-Befund.

## Noch nicht aus dem Zielgerät verifiziert

I2C-Adresse und Bus, ACPI-SSDB-/CRS-Daten, tatsächliche CSI-Lane-Zuordnung, MIPI-Linkfrequenz, Sensorclock, GPIO-Polaritäten, Verzögerungen, Kalibrierung und proprietäres ISP-Tuning müssen separat am Zielgerät qualifiziert werden. Die Linux-Referenz beschreibt für OV02E10 einen 2-Lane-/10-Bit-Bayer-Pfad mit 19,2-MHz-Clock und 360-MHz-Linkfrequenz. Diese Referenzwerte werden von den aktuellen Tools nicht programmiert und sind keine gemessenen Galaxy-Book-Betriebsparameter.

Der [gepinnten Sensorquelle](https://github.com/torvalds/linux/blob/e5f0a698b34ed76002dc5cff3804a61c80233a7a/drivers/media/i2c/ov02e10.c) und [Intel-IPU7-Projekt](https://github.com/intel/ipu7-drivers/tree/495acc90feb09d8008c0a6228fb8bb4c6415ca62) zufolge gehören Sensortreiber, Bildprozessor, Firmware und Bildverarbeitung zum vollständigen MIPI-Pfad. Ein neuer USB-VID/PID-Eintrag löst diesen Pfad nicht.

