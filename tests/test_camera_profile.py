# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 IT-EXPRESS Bayern
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import camera_profile as camera


def target_capture():
    return {"schema_version": 1, "platform": "windows", "devices": [
        {"hardware_ids": ["PCI\\VEN_8086&DEV_645D&SUBSYS_C1DD144D&REV_04"], "service": "iaisp64_lnl", "problem_code": 0},
        {"hardware_ids": ["ACPI\\VEN_OVTI&DEV_02E1", "ACPI\\OVTI02E1"], "service": "OV02E10", "problem_code": 0},
        {"hardware_ids": ["VIDEO\\VEN_8086&DEV_64A0&SUBSYS_C1DD144D&REV_04&INT3480"], "service": "camera", "problem_code": 0},
    ], "collection_errors": []}


class CameraTests(unittest.TestCase):
    def test_exact_target_identified_without_capture_claim(self):
        report = camera.qualify_windows(target_capture())
        self.assertTrue(report["target_identity_observed"])
        self.assertTrue(report["windows_driver_binding_observed"])
        self.assertEqual(report["integrated_camera_transport"], "mipi_ipu7")
        self.assertEqual(report["native_macos_camera_support"], "unimplemented")
        self.assertFalse(report["native_macos_capture_verified"])

    def test_wrong_subsystem_rejected(self):
        capture = target_capture()
        capture["devices"][0]["hardware_ids"][0] = "PCI\\VEN_8086&DEV_645D&SUBSYS_12345678"
        self.assertFalse(camera.qualify_windows(capture)["target_identity_observed"])

    def test_sensor_missing_rejected(self):
        capture = target_capture()
        capture["devices"].pop(1)
        self.assertFalse(camera.qualify_windows(capture)["target_identity_observed"])

    def test_gpu_id_cannot_masquerade_as_camera(self):
        capture = target_capture()
        capture["devices"][2]["hardware_ids"] = ["PCI\\VEN_8086&DEV_64A0&SUBSYS_C1DD144D"]
        self.assertFalse(camera.qualify_windows(capture)["target_identity_observed"])

    def test_wrong_sensor_is_not_supported(self):
        capture = target_capture()
        capture["devices"][1]["hardware_ids"] = ["ACPI\\OVTI02C1"]
        self.assertFalse(camera.qualify_windows(capture)["target_identity_observed"])

    def test_wrong_driver_binding_does_not_pass(self):
        capture = target_capture()
        capture["devices"][0]["service"] = "usbvideo"
        self.assertFalse(camera.qualify_windows(capture)["windows_driver_binding_observed"])

    def test_problem_code_does_not_pass(self):
        capture = target_capture()
        capture["devices"][1]["problem_code"] = 31
        self.assertFalse(camera.qualify_windows(capture)["windows_driver_binding_observed"])

    def test_unknown_problem_not_success(self):
        capture = target_capture()
        capture["devices"][1]["problem_code"] = True
        self.assertFalse(camera.qualify_windows(capture)["windows_driver_binding_observed"])

    def test_collection_failure_retained(self):
        capture = target_capture()
        capture["collection_errors"] = ["property_read_failed"]
        self.assertFalse(camera.qualify_windows(capture)["windows_driver_binding_observed"])

    def test_unknown_error_retained_without_private_string(self):
        capture = target_capture()
        capture["collection_errors"] = ["PRIVATE_ERROR_PATH"]
        report = camera.qualify_windows(capture)
        self.assertFalse(report["windows_driver_binding_observed"])
        self.assertEqual(report["collection_errors"], ["unknown_collection_error"])
        self.assertNotIn("PRIVATE_ERROR_PATH", json.dumps(report))

    def test_storage_not_uvc_even_if_mislabelled(self):
        capture = target_capture()
        capture["devices"].append({"class": "Camera", "hardware_ids": ["USB\\VID_0BDA&PID_9201&REV_F200"], "compatible_ids": ["USB\\Class_08&SubClass_06&Prot_50"], "service": "usbvideo"})
        report = camera.qualify_windows(capture)
        self.assertEqual(report["uvc_candidates"], 0)
        self.assertEqual(report["devices"][-1]["role"], "usb_storage")

    def test_usb_storage_class_not_camera(self):
        item = camera.normalize_record({"hardware_ids": ["USB\\VID_1234&PID_5678"], "compatible_ids": ["USB\\Class_08"], "service": "usbvideo"})
        self.assertEqual(item["role"], "usb_storage")

    def test_separate_uvc_not_integrated_driver_support(self):
        capture = target_capture()
        capture["devices"].append({"hardware_ids": ["USB\\VID_1234&PID_5678&MI_00"], "compatible_ids": ["USB\\Class_0E&SubClass_01&Prot_00"], "service": "usbvideo"})
        report = camera.qualify_windows(capture)
        self.assertEqual(report["uvc_candidates"], 1)
        self.assertEqual(report["native_macos_camera_support"], "unimplemented")

    def test_usb_vid_only_does_not_imply_camera(self):
        self.assertIsNone(camera.normalize_record({"hardware_ids": ["USB\\VID_1234&PID_5678"]}))

    def test_fingerprint_not_ir_camera(self):
        self.assertIsNone(camera.normalize_record({"hardware_ids": ["USB\\VID_1C7A&PID_05A5"], "class": "Biometric", "service": "WUDFRd"}))

    def test_ir_candidate_does_not_claim_hello_support(self):
        capture = target_capture()
        capture["devices"].append({"hardware_ids": ["ACPI\\HIMX1092"]})
        self.assertEqual(camera.qualify_windows(capture)["ir_camera"], "sensor_metadata_present_transport_unqualified")

    def test_private_fields_removed(self):
        capture = target_capture()
        for item in capture["devices"]:
            item.update(instance_id="PRIVATE_SERIAL", friendly_name="PRIVATE_NAME", location_path="PRIVATE_PATH", arbitrary={"token": "PRIVATE_TOKEN"})
            item["hardware_ids"].append("PCI\\VEN_8086&DEV_645D\\PRIVATE_SERIAL")
            item["driver"] = {"version": "1.2.3.4", "inf": "oem112.inf", "path": "PRIVATE_PATH", "provider": "PRIVATE_NAME"}
        self.assertNotIn("PRIVATE_", json.dumps(camera.qualify_windows(capture)))

    def test_private_version_or_inf_removed(self):
        item = camera.normalize_record({"hardware_ids": ["ACPI\\OVTI02E1"], "driver": {"version": "PRIVATE_PATH", "inf": "PRIVATE_PATH"}})
        self.assertIsNone(item["driver_version"])
        self.assertIsNone(item["driver_inf"])

    def test_raw_instance_id_is_rejected(self):
        for value in ["USB\\VID_1234&PID_5678\\SERIAL", "ACPI\\OVTI02E1\\0", "PCI\\VEN_8086&DEV_645D&SUBSYS_C1DD144D\\INSTANCE", "ACPI\\OVTI02E1\nPRIVATE"]:
            self.assertIsNone(camera.canonical_id(value))

    def test_oversized_ids_and_devices_rejected(self):
        with self.assertRaises(ValueError):
            camera.clean_ids(["ACPI\\OVTI02E1"] * 33)
        capture = target_capture()
        capture["devices"] *= 200
        with self.assertRaises(ValueError):
            camera.qualify_windows(capture)

    def test_schema_and_record_types_rejected(self):
        for capture in [{}, [], {"schema_version": True, "platform": "windows", "devices": []}, {"schema_version": 1, "platform": "windows", "devices": [42]}]:
            with self.assertRaises(ValueError):
                camera.qualify_windows(capture)

    def test_native_metadata_does_not_claim_capture(self):
        report = camera.qualify_native({"schema_version": 1, "platform": "macos", "pci_devices": [{"vendor_id": 0x8086, "device_id": 0x645D, "subsystem_vendor_id": 0x144D, "subsystem_id": 0xC1DD}], "acpi_hids": ["OVTI02E1", "INT3472"]})
        self.assertTrue(report["target_identity_observed"])
        self.assertFalse(report["native_macos_capture_verified"])
        self.assertEqual(report["native_macos_camera_support"], "unimplemented")

    def test_native_unrelated_device_and_private_fields_removed(self):
        report = camera.qualify_native({"schema_version": 1, "platform": "macos", "pci_devices": [{"vendor_id": 0x1234, "device_id": 0x645D, "serial": "PRIVATE"}], "acpi_hids": ["PRIVATE", "OVTI02E1"], "private": "PRIVATE"})
        self.assertFalse(report["target_identity_observed"])
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_native_invalid_error_list_rejected(self):
        with self.assertRaises(ValueError):
            camera.qualify_native({"schema_version": 1, "platform": "macos", "pci_devices": [], "acpi_hids": [], "collection_errors": "PRIVATE"})

    def test_utf8_bom_and_input_size_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(target_capture()), encoding="utf-8-sig")
            self.assertEqual(camera.read_capture(path)["platform"], "windows")
            with path.open("wb") as stream:
                stream.truncate(camera.MAX_INPUT_BYTES + 1)
            with self.assertRaises(ValueError):
                camera.read_capture(path)

    def test_cli_output_and_private_failure_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "capture.json"
            output = Path(directory) / "report.json"
            source.write_text(json.dumps(target_capture()), encoding="utf-8")
            run = subprocess.run([sys.executable, str(Path(camera.__file__)), str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["native_macos_capture_verified"])
            source.write_text("PRIVATE_MALFORMED_JSON", encoding="utf-8")
            run = subprocess.run([sys.executable, str(Path(camera.__file__)), str(source)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn("PRIVATE", run.stderr)
            self.assertEqual(run.stdout, "")


if __name__ == "__main__":
    unittest.main()
