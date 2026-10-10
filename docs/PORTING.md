# Nächster nativer Kamera-Port

Das konkrete Ziel ist ein OV02E10-Sensor am Lunar-Lake-IPU7 (`8086:645D`). Der vorhandene Windows-Treiber kann nicht als macOS-Treiber geladen werden. Intel veröffentlicht Linux-Referenzen, die die Bausteine nachvollziehbar machen; die Betriebssystem-APIs und die Lizenzen müssen pro Datei beachtet werden.

## Verknüpfbare Stellen in vorhandenen Quellen

| Referenz | Konkrete Stellen | Zweck beim macOS-Port | Aktueller Stand |
|---|---|---|---|
| Linux `ov02e10.c` | `ov02e10_check_hwcfg`, `ov02e10_identify_module` | Bus-/Clock-/Lane-Konfiguration und Chip-ID qualifizieren | Quelle geprüft; keine Sensortransaktion |
| Linux `ov02e10.c` | `ov02e10_power_on`, `ov02e10_set_stream_mode` | Getrennte Versorgung, Reset, Clock und Streamingzustände | Noch nicht nativ implementiert |
| Linux `ipu-bridge.c` | Sensorkonfiguration für `OVTI02E1`, ACPI-Graph-Aufbau | ACPI-Sensorgraph und Endpunkte nachvollziehen | Referenzwerte sind keine Zielgerätmessung |
| Intel `ipu7.c` | `ipu7_pci_probe`, `request_firmware`, `ipu_buttress_authenticate` | PCI-Ressourcen, Firmwaredatei und Authentifizierung zuordnen | Keine DMA-/IRQ-/Firmwarefunktion implementiert |
| Intel IPU7 HAL und Camera Bins | HAL-/ISP- und Firmwareabhängigkeiten | Raw-Bayer-Bilder zu einem benutzbaren Videoformat verarbeiten | Linux-Bibliotheken sind kein macOS-Buildnachweis |
| Apple Core Media I/O | Camera-Extension-API | Eine echte Framequelle mit Formaten und Zeitstempeln in Kamera-Apps anbieten | Bisher nur separater IORegistry-Metadatenprüfer |

Die exakten Commits und gelesenen Dateien stehen in [REFERENCES.json](REFERENCES.json). Die Quelle für den ähnlichen OV02C10 ist kein Ersatz für OV02E10: Register, Chip-ID und Konfiguration unterscheiden sich.

## Reihenfolge mit überprüfbaren Ergebnissen

1. **Native Enumeration:** IPU7 und den passenden ACPI-Sensor mit dem bereitgestellten Metadatenprüfer suchen. Fehlende IORegistry-HID-Exposition wird als unbekannt behandelt.
2. **Sensorgraph:** ACPI-Ressourcen, SSDB-Daten, Power-/Reset-Steuerung und die reale I2C-Zuordnung dokumentieren. Der separate I2C-/GPIO-Treiber muss seine Busfunktion am Zielgerät belegt haben.
3. **Sensorprotokoll:** Ein eigener OV02E10-Baustein darf erst nach bestätigtem Power-/Clock-Pfad die Chip-ID qualifizieren. Sensorinitialisierung und Streaming brauchen gezielte native Tests.
4. **IPU7-Input:** PCI-Mapping, IOMMU/DMA, Interrupts, Firmwareformat, sichere Authentifizierung und CSI-2-Input getrennt implementieren. Ein angelegter Benutzerpuffer ersetzt keine DMA-Funktion.
5. **Bildverarbeitung:** Bayer-Format, Stride, Crop, Belichtung, Farbkorrektur, Kalibrierung und Formatkonvertierung qualifizieren. Eine reine Raw-Quelle ist noch keine normale Webcam für Videoanrufe.
6. **macOS-Ausgabe:** Erst echte Frames an eine separate CMIO-Camera-Extension mit korrekten Formaten, Zeitstempeln und Freigaben liefern. Sichtbare virtuelle Kameranamen ohne Bildquelle wären kein Erfolg.
7. **Zielgerätprüfung:** Aufnahme, Neustart, Sleep/Wake und mehrere Anwendungen auf dem Galaxy Book prüfen. Die jetzige Metadatendiagnose führt keine Aufnahme durch; dieser spätere Schritt benötigt eine ausdrücklich gewünschte Kameranutzung.

Die obige Reihenfolge ist der öffentlich dokumentierte technische Portierungsstand; interne Arbeitslisten gehören nicht zum Repository oder Paket.

## USB und Apple Camera Extensions

Die [Windows-UVC-Dokumentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/stream/usb-video-class-driver-overview) beschreibt den Inbox-Treiber `usbvideo.sys` für USB-Video-Klassenhardware. Dieses Zielgerät bindet stattdessen die Intel-IPU-/Sensor-/AVStream-Dienste. Die native [Apple-UVC-Camera-Extension](https://developer.apple.com/videos/play/wwdc2022/10022/) unterstützt Klassenhardware und lässt sich für besondere USB-Protokolle erweitern. Sie enthält dadurch keinen Intel-MIPI/IPU7-Transport. Eine zusätzliche externe UVC-Kamera wäre ein separates Gerät und würde die interne Kamera nicht implementieren.

## Eigenständige Komponenten und Lizenzen

Dieser Kamerabaustein ist ein eigenes Repository. Der spätere Sensoradapter, IPU7-Baustein und CMIO-Ausgabebaustein bleiben getrennte Komponenten für den Kamerapfad. I2C-Controller, GPIO, GPU und weitere Hardware werden nicht zu einem gemeinsamen All-in-one-Kext zusammengelegt.

Eigener Code steht unter GPL-3.0-only. Die geprüfte Linux-Sensor-/IPU7-Implementierung trägt GPL-2.0-Kennzeichnungen. Sie wurde nicht in den eigenen Code kopiert oder als GPLv3 umetikettiert. Der Intel-HAL-Lizenztext nennt Apache 2.0; die gesonderte Camera-Bins-Lizenz erlaubt bestimmte unveränderte Binärweitergaben unter eigenen Bedingungen. Dieses Repository enthält keine dieser Binärdateien. Vor einer konkreten Übernahme werden die Datei- und Unterkomponentenlizenzen geprüft und passende Notices erhalten.

UEFI Secure Boot, macOS-Bootrichtlinien, Kernel-/System-Extension-Freigaben und die IPU-interne Firmwareauthentifizierung sind unterschiedliche Prüfungen. Keine dieser Prüfungen wird durch die aktuelle Metadatendiagnose umgestellt, umgangen oder als erfüllt behauptet.
