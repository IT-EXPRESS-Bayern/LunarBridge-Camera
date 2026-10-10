// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 IT-EXPRESS Bayern
import Foundation
import IOKit

// Only IORegistry metadata. No AVFoundation session, device open, I2C transfer,
// DMA, MMIO, firmware upload, register writes or camera frame collection.
let recordLimit = 512
var errors = Set<String>()
var pci: [[String: Any]] = []
var hids = Set<String>()

func property(_ entry: io_registry_entry_t, _ key: String) -> Any? {
    IORegistryEntryCreateCFProperty(entry, key as CFString, kCFAllocatorDefault, 0)?.takeRetainedValue()
}

func number(_ entry: io_registry_entry_t, _ key: String, _ maximum: UInt32) -> UInt32? {
    guard let value = property(entry, key) else { return nil }
    if let bytes = value as? Data, bytes.count == 4 {
        let raw = bytes.enumerated().reduce(UInt32(0)) { sum, item in sum | (UInt32(item.element) << (8 * item.offset)) }
        return raw <= maximum ? raw : nil
    }
    if let raw = value as? NSNumber {
        let signed = raw.int64Value
        return signed >= 0 && signed <= Int64(maximum) ? UInt32(signed) : nil
    }
    return nil
}

func publicHIDs(_ value: Any?) -> [String] {
    var candidates: [String] = []
    if let text = value as? String, text.utf8.count <= 256 {
        candidates = text.components(separatedBy: "\0")
    } else if let bytes = value as? Data, bytes.count <= 256,
              let text = String(data: bytes, encoding: .utf8) {
        candidates = text.components(separatedBy: "\0")
    } else if let values = value as? [String], values.count <= 16 {
        candidates = values.filter { $0.utf8.count <= 32 }
    }
    return candidates.map { $0.uppercased() }.filter { ["OVTI02E1", "INT3472", "INT3480"].contains($0) }
}

func enumerate(_ name: String, _ error: String, _ inspect: (io_registry_entry_t) -> Void) {
    var iterator: io_iterator_t = 0
    guard let matching = IOServiceMatching(name), IOServiceGetMatchingServices(kIOMainPortDefault, matching, &iterator) == KERN_SUCCESS else {
        errors.insert(error)
        return
    }
    defer { IOObjectRelease(iterator) }
    var count = 0
    while true {
        let entry = IOIteratorNext(iterator)
        if entry == 0 { break }
        count += 1
        if count > recordLimit {
            IOObjectRelease(entry)
            errors.insert("record_limit_reached")
            break
        }
        inspect(entry)
        IOObjectRelease(entry)
    }
}

enumerate("IOPCIDevice", "pci_enumeration_failed") { entry in
    guard number(entry, "vendor-id", 0xFFFF) == 0x8086,
          number(entry, "device-id", 0xFFFF) == 0x645D else { return }
    var item: [String: Any] = ["vendor_id": 0x8086, "device_id": 0x645D]
    for (output, input, maximum) in [("subsystem_vendor_id", "subsystem-vendor-id", UInt32(0xFFFF)),
                                      ("subsystem_id", "subsystem-id", UInt32(0xFFFF)),
                                      ("revision_id", "revision-id", UInt32(0xFF))] {
        if let value = number(entry, input, maximum) {
            item[output] = NSNumber(value: value)
        } else {
            item[output] = NSNull()
        }
    }
    pci.append(item)
}

enumerate("IOACPIPlatformDevice", "acpi_enumeration_failed") { entry in
    for key in ["name", "_HID", "acpi-hid", "IONameMatched", "compatible"] {
        for hid in publicHIDs(property(entry, key)) { hids.insert(hid) }
    }
}

let result: [String: Any] = ["schema_version": 1, "platform": "macos", "pci_devices": pci,
                             "acpi_hids": hids.sorted(), "collection_errors": errors.sorted()]
do {
    let json = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
    FileHandle.standardOutput.write(json)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    FileHandle.standardError.write(Data("Kamerametadaten konnten nicht serialisiert werden.\n".utf8))
    exit(2)
}
