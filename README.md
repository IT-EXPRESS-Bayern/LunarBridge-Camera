# LunarBridge-Camera

Eigenes Kameramodul für **Samsung Galaxy Book5 Pro 16 NP960XHA-KG3DE** und die native macOS-Tahoe-Entwicklung.

Die integrierte Kamera dieses Rechners verwendet **OmniVision OV02E10 + Intel IPU7**. Unter Windows wurden `ACPI\OVTI02E1`, IPU7 `PCI 8086:645D / Samsung C1DD144D` und die Intel-LNL-AVStream-Schnittstelle mit passenden Treiberbindungen festgestellt. Das Modul enthält derzeit eine getestete Metadatenqualifikation und einen macOS-IORegistry-Prüfer. **Der native Sensor-/IPU7-Kameratreiber und die Aufnahme unter macOS sind noch nicht implementiert oder bestätigt.**

## Windows: konkretes Geräteprofil prüfen

Python 3.9 oder neuer und Windows PowerShell mit den PnP-Cmdlets:

```powershell
powershell -NoProfile -File tools/collect_windows.ps1 -OutputPath reports/windows-capture.json
python tools/camera_profile.py reports/windows-capture.json --output reports/windows-qualification.json
python -m unittest discover -s tests -v
```

Der Collector liest PnP-Metadaten. Geräteinstanzpfade, Seriennummern, Benutzerpfade, Kamerabilder und freie Gerätenamen werden verworfen. Der Bericht unterscheidet das konkrete MIPI/IPU7-Profil, separate USB-Videokandidaten und den Ugreen-Speicheradapter `0BDA:9201`. Windows-Treiberbindung wird nur bei passender Gerätekennung, passendem Dienst, Fehlercode 0 und fehlerfreier Erfassung bestätigt.

## macOS: Geräte-Metadaten prüfen

Auf einem macOS-System mit Apple Command Line Tools:

```sh
mkdir -p build reports
swiftc -O -warnings-as-errors tools/camera_probe.swift -framework IOKit -o build/lb-camera-probe
build/lb-camera-probe > reports/macos-capture.json
python3 tools/camera_profile.py reports/macos-capture.json --output reports/macos-qualification.json
```

Der native Prüfer liest ausschließlich die passenden PCI-Kennzahlen und ausgewählte bekannte ACPI-HIDs aus IORegistry. Er öffnet keine Kamera und schreibt weder Sensorregister noch Firmware. ACPI-HIDs müssen im IORegistry sichtbar sein; fehlen sie dort, bleibt die Identifikation unqualifiziert. Ein sichtbares Gerät beweist weder einen geladenen Kameratreiber noch eine funktionierende Aufnahme.

Die eigene GitHub-CI kompiliert den Prüfer auf Intel-macOS und verpackt ihn mit den zugehörigen Quellen. CI-Geräte sind keine Galaxy-Book-Testgeräte. Das Paket ist ein **Metadatenprüfer**, kein Kernel-Treiber-Installer. Ein Signatur-Eintrag beweist keine von macOS anerkannte Signaturvertrauenskette.

## Hardware und Portierung

- [Hardwarebefund und Zuordnungsgrenzen](docs/HARDWARE.md)
- [Konkrete Bausteine für den nativen Port](docs/PORTING.md)
- [Gepinnte Primärquellen und SHA-256](docs/REFERENCES.json)
- [Getrennte lokale und native Validierung](docs/VALIDATION.json)

Kamera, Grafik, I2C-Controller und andere Hardware bleiben eigenständige Module. Der zukünftige Kamera-Port darf auf einen separat qualifizierten I2C-/GPIO-Dienst zugreifen; dieses Repository ersetzt diesen Dienst nicht. Firmware-Secure-Boot und macOS-Treiberfreigaben bleiben gesonderte Anforderungen. Die aktuellen Prüfwerkzeuge ändern diese Einstellungen nicht.

Eigene Beiträge: **GPL-3.0-only**, Copyright IT-EXPRESS Bayern. Externe Referenzen behalten ihre Lizenzen; Linux-, Windows-, Apple- und Intel-Firmwareimplementierungen sind nicht enthalten. Siehe [NOTICE](NOTICE) und [LICENSE](LICENSE).

