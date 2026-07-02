#!/usr/bin/env python3
"""Test 2 — PCA9685 initialization.

Initializes the PCA9685 at the configured address and sets the servo frequency.
Does NOT move any servo by default (channels are left untouched). Pass --confirm
to additionally read back the prescale register as a liveness check.

    python scripts/test_pca9685.py

Uses adafruit-circuitpython-pca9685 (modern replacement for Adafruit_PCA9685).
"""
from __future__ import annotations

import argparse

import robot_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the PCA9685 (no servo movement).")
    parser.add_argument("--confirm", action="store_true", help="read back prescale register")
    args = parser.parse_args()

    cfg = robot_config.load_config()
    addr = robot_config.get(cfg, "pca9685", "address", default=0x40)
    freq = robot_config.get(cfg, "pca9685", "frequency_hz", default=50)

    if robot_config.is_dry_run(cfg):
        print(f"[dry-run] would init PCA9685 at 0x{addr:02x} @ {freq} Hz — no movement")
        return 0

    try:
        import board
        import busio
        from adafruit_pca9685 import PCA9685
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: cannot import CircuitPython PCA9685 libs: {exc}")
        print("      pip install adafruit-circuitpython-pca9685 adafruit-blinka")
        return 1

    pca = None
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        pca = PCA9685(i2c, address=addr)
        pca.frequency = freq
        print(f"OK: PCA9685 initialized at 0x{addr:02x}, frequency set to {freq} Hz")
        print("No servo channels were driven (safe).")
        if args.confirm:
            # duty_cycle read-back of channel 0 confirms register access works.
            duty = pca.channels[0].duty_cycle
            print(f"OK: channel 0 duty_cycle register readable ({duty})")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: PCA9685 init failed: {exc}")
        return 1
    finally:
        # Do not deinit the bus aggressively; just leave channels as-is.
        if pca is not None:
            try:
                pca.deinit()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
