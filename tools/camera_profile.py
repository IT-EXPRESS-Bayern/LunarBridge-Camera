# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 IT-EXPRESS Bayern
"""Bounded metadata qualification. Does not open or operate a camera."""

import argparse
import json
from pathlib import Path
import re
import sys

MODEL = "Samsung Galaxy Book5 Pro 16 NP960XHA-KG3DE"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 512
MAX_IDS = 32
ROLES = {
    "ipu7": "Intel Lunar Lake IPU7",
    "sensor": "OmniVision OV02E10",
    "avstream": "Intel LNL AVStream camera interface",
    "control": "Intel camera control logic INT3472",
    "usb_storage": "USB mass storage; not a camera",
    "uvc_candidate": "USB video class candidate; separate device",
    "ir_sensor_candidate": "Himax HM1092 sensor metadata; transport unqualified",
}
PCI_ID = re.compile(r"PCI\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})(?:&SUBSYS_([0-9A-F]{8}))?(?:&REV_[0-9A-F]{2})?(?:&CC_[0-9A-F]{4,6})?")
VIDEO_ID = re.compile(r"VIDEO\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})(?:&SUBSYS_([0-9A-F]{8}))?(?:&REV_[0-9A-F]{2})?&INT3480")
USB_ID = re.compile(r"USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(?:&REV_[0-9A-F]{4})?(?:&MI_([0-9A-F]{2}))?")
USB_CLASS = re.compile(r"USB\\(?:COMPAT_VID_[0-9A-F]{4}&)?CLASS_([0-9A-F]{2})(?:&SUBCLASS_([0-9A-F]{2}))?(?:&PROT_([0-9A-F]{2}))?")
ACPI_ID = re.compile(r"(?:ACPI\\|\*)?(OVTI02E1|INT3472|INT3480|HIMX1092)")
ACPI_SPLIT = re.compile(r"ACPI\\VEN_(OVTI|INT)&DEV_(02E1|3472|3480)")
SERVICES = {"camera", "ov02e10", "iaisp64_lnl", "iactrllogic", "usbvideo", "usbstor"}
CLASSES = {"Camera", "Image", "System", "USB", "SoftwareComponent"}


def canonical_id(value):
    if not isinstance(value, str) or len(value) > 160:
        return None
    value = value.upper()
    match = PCI_ID.fullmatch(value)
    if match:
        vendor, device, subsystem = match.groups()
        return "PCI\\VEN_" + vendor + "&DEV_" + device + ("&SUBSYS_" + subsystem if subsystem else "")
    match = VIDEO_ID.fullmatch(value)
    if match:
        vendor, device, subsystem = match.groups()
        return "VIDEO\\VEN_" + vendor + "&DEV_" + device + ("&SUBSYS_" + subsystem if subsystem else "") + "&INT3480"
    match = USB_ID.fullmatch(value)
    if match:
        vendor, product, interface = match.groups()
        return "USB\\VID_" + vendor + "&PID_" + product + ("&MI_" + interface if interface else "")
    match = USB_CLASS.fullmatch(value)
    if match:
        kind, subclass, protocol = match.groups()
        return "USB\\CLASS_" + kind + ("&SUBCLASS_" + subclass if subclass else "") + ("&PROT_" + protocol if protocol else "")
    match = ACPI_ID.fullmatch(value)
    if match:
        return "ACPI\\" + match[1]
    match = ACPI_SPLIT.fullmatch(value)
    if match:
        combined = match[1] + match[2]
        if combined in {"OVTI02E1", "INT3472", "INT3480"}:
            return "ACPI\\" + combined
    return None


def clean_ids(values):
    if not isinstance(values, list) or len(values) > MAX_IDS:
        raise ValueError("invalid_id_list")
    return sorted({normalized for value in values if (normalized := canonical_id(value))})


def integer(value, limit):
    return value if type(value) is int and 0 <= value <= limit else None


def role_for(ids, compatible, service):
    joined = set(ids + compatible)
    # Storage identity wins over misleading caller-provided class labels.
    if "USB\\VID_0BDA&PID_9201" in joined or any(item.startswith("USB\\CLASS_08") for item in joined):
        return "usb_storage"
    if any(item.startswith("PCI\\VEN_8086&DEV_645D") for item in ids):
        return "ipu7"
    if "ACPI\\OVTI02E1" in joined:
        return "sensor"
    if any(item.startswith("VIDEO\\VEN_8086&DEV_64A0") and item.endswith("&INT3480") for item in ids):
        return "avstream"
    if "ACPI\\INT3472" in joined:
        return "control"
    if "ACPI\\HIMX1092" in joined:
        return "ir_sensor_candidate"
    if any(item.startswith("USB\\VID_") for item in ids) and (service == "usbvideo" or any(item.startswith("USB\\CLASS_0E") for item in compatible)):
        return "uvc_candidate"
    return None


def normalize_record(record):
    if not isinstance(record, dict):
        raise ValueError("invalid_record")
    ids = clean_ids(record.get("hardware_ids", []))
    compatible = clean_ids(record.get("compatible_ids", []))
    service = record.get("service")
    service = service.lower() if isinstance(service, str) and service.lower() in SERVICES else None
    role = role_for(ids, compatible, service)
    if role is None:
        return None
    driver = record.get("driver", {})
    driver = driver if isinstance(driver, dict) else {}
    version = driver.get("version")
    inf = driver.get("inf")
    result = {
        "role": role,
        "description": ROLES[role],
        "hardware_ids": ids,
        "compatible_ids": compatible,
        "service": service,
        "problem_code": integer(record.get("problem_code"), 0xFFFFFFFF),
        "driver_version": version if isinstance(version, str) and re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,8}){1,4}", version) else None,
        "driver_inf": inf.lower() if isinstance(inf, str) and re.fullmatch(r"(?:oem[0-9]{1,6}|usbvideo|usbstor)\.inf", inf, re.IGNORECASE) else None,
    }
    if role in {"ipu7", "avstream"}:
        result["samsung_subsystem_match"] = any("&SUBSYS_C1DD144D" in item for item in ids)
    return result


def qualify_windows(capture):
    if not isinstance(capture, dict) or type(capture.get("schema_version")) is not int or capture.get("schema_version") != 1 or capture.get("platform") != "windows":
        raise ValueError("invalid_windows_schema")
    records = capture.get("devices")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("invalid_device_list")
    normalized = [item for raw in records if (item := normalize_record(raw)) is not None]
    by_role = {role: [item for item in normalized if item["role"] == role] for role in ROLES}
    errors = capture.get("collection_errors", [])
    if not isinstance(errors, list) or len(errors) > 64:
        raise ValueError("invalid_error_list")
    allowed_errors = {"enumeration_failed", "property_read_failed", "inf_read_failed", "record_limit_reached"}
    errors = sorted({item if isinstance(item, str) and item in allowed_errors else "unknown_collection_error" for item in errors})
    match = all(by_role[role] for role in ("ipu7", "sensor", "avstream")) and all(any(item["samsung_subsystem_match"] for item in by_role[role]) for role in ("ipu7", "avstream"))
    driver_chain_ok = match and all(any(item["problem_code"] == 0 and item["service"] == service for item in by_role[role]) for role, service in (("ipu7", "iaisp64_lnl"), ("sensor", "ov02e10"), ("avstream", "camera"))) and not errors
    return {
        "schema_version": 1,
        "profile": MODEL,
        "observation_platform": "windows",
        "target_identity_observed": bool(match),
        "windows_driver_binding_observed": bool(driver_chain_ok),
        "integrated_camera_transport": "mipi_ipu7" if match else "unqualified",
        "native_macos_camera_support": "unimplemented" if match else "unqualified",
        "native_macos_capture_verified": False,
        "ir_camera": "sensor_metadata_present_transport_unqualified" if by_role["ir_sensor_candidate"] else "not_identified_by_this_profile",
        "uvc_candidates": len(by_role["uvc_candidate"]),
        "devices": normalized,
        "collection_errors": errors,
        "next_native_requirements": ["acpi_sensor_graph", "i2c_sensor_power_and_clock", "ipu7_dma_irq_iommu", "firmware_authentication", "csi2_raw_input", "isp_image_processing", "cmio_camera_extension", "target_capture_test"],
    }


def qualify_native(capture):
    if not isinstance(capture, dict) or type(capture.get("schema_version")) is not int or capture.get("schema_version") != 1 or capture.get("platform") != "macos":
        raise ValueError("invalid_macos_schema")
    pci = capture.get("pci_devices")
    acpi = capture.get("acpi_hids")
    if not isinstance(pci, list) or len(pci) > MAX_RECORDS or not isinstance(acpi, list) or len(acpi) > MAX_RECORDS:
        raise ValueError("invalid_native_records")
    safe_pci = []
    for item in pci:
        if not isinstance(item, dict):
            raise ValueError("invalid_native_pci")
        fields = {key: integer(item.get(key), limit) for key, limit in (("vendor_id", 0xFFFF), ("device_id", 0xFFFF), ("subsystem_vendor_id", 0xFFFF), ("subsystem_id", 0xFFFF), ("revision_id", 0xFF))}
        if fields["vendor_id"] == 0x8086 and fields["device_id"] == 0x645D:
            safe_pci.append(fields)
    safe_acpi = sorted({item for item in acpi if isinstance(item, str) and item in {"OVTI02E1", "INT3472", "INT3480"}})
    errors = capture.get("collection_errors", [])
    if not isinstance(errors, list) or len(errors) > 64:
        raise ValueError("invalid_error_list")
    allowed_errors = {"pci_enumeration_failed", "acpi_enumeration_failed", "metadata_read_failed", "record_limit_reached"}
    errors = sorted({item if isinstance(item, str) and item in allowed_errors else "unknown_collection_error" for item in errors})
    target = any(item["subsystem_vendor_id"] == 0x144D and item["subsystem_id"] == 0xC1DD for item in safe_pci) and "OVTI02E1" in safe_acpi
    return {"schema_version": 1, "profile": MODEL, "observation_platform": "macos", "target_identity_observed": target, "native_macos_camera_support": "unimplemented" if target else "unqualified", "native_macos_capture_verified": False, "pci_devices": safe_pci, "acpi_hids": safe_acpi, "collection_errors": errors}


def read_capture(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input_too_large")
    return json.loads(raw.decode("utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kamerametadaten qualifizieren; keine Kameraaufnahme.")
    parser.add_argument("capture", help="JSON aus collect_windows.ps1 oder camera_probe.swift")
    parser.add_argument("--output", type=Path, help="Datensparsamen Bericht schreiben")
    args = parser.parse_args(argv)
    try:
        capture = read_capture(args.capture)
        result = qualify_windows(capture) if capture.get("platform") == "windows" else qualify_native(capture)
        encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        else:
            print(encoded, end="")
    except (OSError, ValueError, TypeError, AttributeError):
        print("Kamerametadaten konnten nicht sicher gelesen werden.", file=sys.stderr)
        return 2
    # Identification is not driver support. This code never reports capture success.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
