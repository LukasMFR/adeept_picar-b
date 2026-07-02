#!/usr/bin/env python3
"""Test 1 — I2C bus scan.

Read-only. Confirms /dev/i2c-<bus> exists, scans the bus, and reports whether
the PCA9685 address from the config is present.

    python scripts/test_i2c.py
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import robot_config


def scan_with_smbus(bus: int) -> list[int]:
    """Probe every 7-bit address using smbus. Returns list of responders."""
    import smbus  # type: ignore

    found: list[int] = []
    b = smbus.SMBus(bus)
    for addr in range(0x03, 0x78):
        try:
            b.read_byte(addr)
            found.append(addr)
        except OSError:
            continue
    return found


def main() -> int:
    cfg = robot_config.load_config()
    bus = robot_config.get(cfg, "i2c", "bus", default=1)
    target = robot_config.get(cfg, "pca9685", "address", default=0x40)

    dev = Path(f"/dev/i2c-{bus}")
    print(f"I2C bus: {bus}  ({dev})")
    if not dev.exists():
        print(f"FAIL: {dev} not found. Enable I2C (dtparam=i2c_arm=on) and reboot.")
        return 1
    print(f"OK: {dev} exists")

    found: list[int] = []
    if shutil.which("i2cdetect"):
        proc = subprocess.run(["i2cdetect", "-y", str(bus)], capture_output=True, text=True)
        print("\ni2cdetect output:")
        print(proc.stdout)
        for token in proc.stdout.split():
            try:
                found.append(int(token, 16))
            except ValueError:
                continue
    else:
        print("i2c-tools not found; scanning via smbus...")
        try:
            found = scan_with_smbus(bus)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: smbus scan failed: {exc}")
            return 1
        print("Addresses:", ", ".join(f"0x{a:02x}" for a in found) or "(none)")

    if target in found:
        print(f"\nOK: PCA9685 found at 0x{target:02x}")
        return 0
    print(f"\nWARN: expected PCA9685 at 0x{target:02x} but it was not detected.")
    print("      Check HAT power and ribbon/pin seating.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
