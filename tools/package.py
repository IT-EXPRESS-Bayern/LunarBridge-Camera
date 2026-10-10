# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 IT-EXPRESS Bayern
"""Package an actual x86_64 metadata observer with its corresponding source."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

SOURCES = ["README.md", "LICENSE", "NOTICE", ".gitignore", "tools/camera_profile.py", "tools/collect_windows.ps1", "tools/camera_probe.swift", "tools/package.py", "tests/test_camera_profile.py", "tests/test_package.py", "docs/HARDWARE.md", "docs/PORTING.md", "docs/REFERENCES.json", "docs/VALIDATION.json"]


def read_regular(path, maximum):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("regular_file_required")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("file_too_large")
    return data


def validate_binary(data):
    if len(data) < 32:
        raise ValueError("truncated_macho")
    magic, cpu, subtype, kind, count, command_size, flags, reserved = struct.unpack_from("<IiiIIIII", data)
    if magic != 0xFEEDFACF or cpu != 0x1000007 or kind != 2 or reserved != 0:
        raise ValueError("x86_64_macos_executable_required")
    if count > 4096 or command_size > len(data) - 32:
        raise ValueError("invalid_load_command_bounds")
    cursor = 32
    signature = False
    for _ in range(count):
        if cursor + 8 > 32 + command_size:
            raise ValueError("truncated_load_command")
        command, length = struct.unpack_from("<II", data, cursor)
        if length < 8 or length % 8 or cursor + length > 32 + command_size:
            raise ValueError("invalid_load_command")
        if command == 0x1D:
            if length != 16:
                raise ValueError("invalid_code_signature_command")
            _, _, offset, size = struct.unpack_from("<IIII", data, cursor)
            if offset > len(data) or size > len(data) - offset:
                raise ValueError("invalid_code_signature_bounds")
            signature = size > 0
        cursor += length
    if cursor != 32 + command_size:
        raise ValueError("inconsistent_load_commands")
    return {"architecture": "x86_64", "filetype": "MH_EXECUTE", "code_signature_command_present": signature, "signature_trust_verified": False, "native_camera_capture_verified": False}


def create_package(root, binary, output):
    root = Path(root).resolve()
    data = read_regular(binary, 64 * 1024 * 1024)
    proof = validate_binary(data)
    entries = {"bin/lb-camera-probe": data}
    hashes = {}
    for relative in SOURCES:
        path = root / relative
        if any(part.lower() in {"tasks.md", "plan.md"} for part in path.parts):
            raise ValueError("private_work_list_forbidden")
        source = read_regular(path, 4 * 1024 * 1024)
        entries["source/" + relative] = source
        hashes[relative] = hashlib.sha256(source).hexdigest()
    proof["binary_sha256"] = hashlib.sha256(data).hexdigest()
    proof["source_sha256"] = hashes
    proof["purpose"] = "read_only_camera_metadata_observer"
    entries["build-manifest.json"] = (json.dumps(proof, indent=2) + "\n").encode("utf-8")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = ((0o100755 if name.startswith("bin/") else 0o100644) << 16)
            archive.writestr(entry, content)
    return proof


def main():
    parser = argparse.ArgumentParser(description="macOS-Kamerametadatenprüfer samt Quellen verpacken")
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        proof = create_package(Path(__file__).resolve().parents[1], args.binary, args.output)
    except (OSError, ValueError):
        print("Paketprüfung fehlgeschlagen; kein bestätigter Kameratreiber.")
        return 2
    print(json.dumps({"source_files": len(proof["source_sha256"]), "architecture": proof["architecture"], "native_camera_capture_verified": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
