#!/usr/bin/env python3
"""Test 8 — line-tracking sensor (3 digital channels).

Continuously reads the left/middle/right line sensors and prints their state.
Pins come from config/robot.yaml (server/findline.py: L=20, M=16, R=19, BCM).

    python scripts/test_line_tracking.py          # read for a few seconds
    python scripts/test_line_tracking.py --seconds 20

Read-only sensor test — no motion. Ctrl-C to stop. gpiozero replaces RPi.GPIO.
Slide the robot over a line by hand and watch which channel changes.
"""
from __future__ import annotations

import argparse
import time

import robot_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Read line-tracking sensors.")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    cfg = robot_config.load_config()
    left = robot_config.get(cfg, "line_tracking", "left_pin")
    middle = robot_config.get(cfg, "line_tracking", "middle_pin")
    right = robot_config.get(cfg, "line_tracking", "right_pin")
    line_is_high = bool(robot_config.get(cfg, "line_tracking", "line_is_high", default=True))

    if None in (left, middle, right):
        print("Line-tracking pins not configured (line_tracking.left/middle/right_pin).")
        return 1

    print(f"Line tracking — L=GPIO{left}  M=GPIO{middle}  R=GPIO{right}")
    print(f"'line' == logic {'HIGH' if line_is_high else 'LOW'}. Reading for {args.seconds}s...")

    if robot_config.is_dry_run(cfg):
        print("[dry-run] would poll the three sensors.")
        return 0

    devices = []
    try:
        from gpiozero import DigitalInputDevice

        dev_l = DigitalInputDevice(left)
        dev_m = DigitalInputDevice(middle)
        dev_r = DigitalInputDevice(right)
        devices = [dev_l, dev_m, dev_r]

        def label(dev) -> str:
            on_line = (dev.value == 1) == line_is_high
            return "LINE" if on_line else " -- "

        end = args.seconds
        elapsed = 0.0
        while elapsed < end:
            print(f"  L:{label(dev_l)}  M:{label(dev_m)}  R:{label(dev_r)}   "
                  f"(raw {dev_l.value}{dev_m.value}{dev_r.value})")
            time.sleep(0.3)
            elapsed += 0.3
        print("OK: line-tracking test complete.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: line-tracking read failed: {exc}")
        return 1
    finally:
        for dev in devices:
            try:
                dev.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
