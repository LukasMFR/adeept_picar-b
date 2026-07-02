#!/usr/bin/env python3
"""Test 7 — ultrasonic distance sensor (HC-SR04 style).

Reads distance a few times using gpiozero's DistanceSensor on the configured
trigger/echo pins (from server/ultra.py: Trig=11, Echo=8, BCM).

    python scripts/test_ultrasonic.py
    python scripts/test_ultrasonic.py --samples 10

Read-only sensor test — no motion. Uses gpiozero (preferred on Trixie for Pi 3/4/5).

WIRING NOTE: HC-SR04 ECHO is 5V; the Robot HAT is expected to level-shift/divide
it to 3.3V. If you see no readings, verify ECHO reaches the Pi at 3.3V logic.
"""
from __future__ import annotations

import argparse
import time

import robot_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Read ultrasonic distance.")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    cfg = robot_config.load_config()
    trig = robot_config.get(cfg, "ultrasonic", "trigger_pin")
    echo = robot_config.get(cfg, "ultrasonic", "echo_pin")
    max_dist = float(robot_config.get(cfg, "ultrasonic", "max_distance_m", default=2.0))

    if trig is None or echo is None:
        print("Ultrasonic pins not configured (ultrasonic.trigger_pin / echo_pin).")
        return 1

    print(f"Ultrasonic — trigger GPIO {trig}, echo GPIO {echo}, max {max_dist} m")

    if robot_config.is_dry_run(cfg):
        print(f"[dry-run] would take {args.samples} distance samples.")
        return 0

    sensor = None
    try:
        from gpiozero import DistanceSensor

        sensor = DistanceSensor(echo=echo, trigger=trig, max_distance=max_dist)
        for i in range(args.samples):
            time.sleep(0.2)
            print(f"  sample {i + 1}: {sensor.distance * 100:.1f} cm")
        print("OK: ultrasonic test complete.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: ultrasonic read failed: {exc}")
        return 1
    finally:
        if sensor is not None:
            try:
                sensor.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
