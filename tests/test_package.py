# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 IT-EXPRESS Bayern
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package


def header(kind=2, cpu=0x1000007, count=0, size=0):
    return struct.pack("<IiiIIIII", 0xFEEDFACF, cpu, 3, kind, count, size, 0, 0)


class PackageTests(unittest.TestCase):
    def test_object_and_kext_not_executable(self):
        for kind in [1, 11]:
            with self.assertRaises(ValueError):
                package.validate_binary(header(kind=kind))

    def test_wrong_architecture_and_windows_binary_rejected(self):
        for data in [header(cpu=0x100000C), b"MZ" + b"\0" * 64]:
            with self.assertRaises(ValueError):
                package.validate_binary(data)

    def test_truncated_load_commands_rejected(self):
        for data in [header(count=1, size=16), header(count=1, size=8) + struct.pack("<II", 1, 0), header(count=0, size=8) + b"\0" * 8]:
            with self.assertRaises(ValueError):
                package.validate_binary(data)

    def test_fake_signature_bounds_rejected(self):
        data = header(count=1, size=16) + struct.pack("<IIII", 0x1D, 16, 48, 99)
        with self.assertRaises(ValueError):
            package.validate_binary(data)

    def test_corresponding_source_and_executable_bit_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in package.SOURCES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"public source\n")
            (root / "TASKS.md").write_text("private plan", encoding="utf-8")
            (root / "reports").mkdir()
            (root / "reports" / "private.json").write_text("private serial", encoding="utf-8")
            binary = root / "observer"
            binary.write_bytes(header())
            output = root / "package.zip"
            proof = package.create_package(root, binary, output)
            self.assertFalse(proof["native_camera_capture_verified"])
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertFalse(any("tasks.md" in name.lower() or "reports/" in name for name in archive.namelist()))
                self.assertEqual(len(archive.namelist()), len(package.SOURCES) + 2)
                self.assertEqual((archive.getinfo("bin/lb-camera-probe").external_attr >> 16) & 0o777, 0o755)
                manifest = json.loads(archive.read("build-manifest.json"))
                for name, expected in manifest["source_sha256"].items():
                    self.assertEqual(hashlib.sha256(archive.read("source/" + name)).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
