#!/usr/bin/env python3
"""Test 4 — DC motors.

Spins each motor forward then backward at a very low speed for a very short
time, respecting per-motor inversion from config/robot.yaml. Uses gpiozero
(lgpio backend), the preferred modern GPIO path on Trixie for Pi 3/4/5.

    python scripts/test_motor.py            # both motors
    python scripts/test_motor.py --side left

*** SAFETY ***
The WHEELS MUST BE LIFTED OFF THE GROUND. You must type LIFTED to proceed.
Speed is capped by motors.speed_limit_percent. Motors are ALWAYS stopped in a
finally block and on any exception / Ctrl-C.
"""
from __future__ import annotations

import argparse
import time

import robot_config


class Motor:
    """One motor: PWM enable pin + two direction pins (gpiozero)."""

    def __init__(self, name, enable_pin, in1_pin, in2_pin, invert, pwm_hz):
        from gpiozero import DigitalOutputDevice, PWMOutputDevice

        self.name = name
        self.invert = invert
        self.enable = PWMOutputDevice(enable_pin, frequency=pwm_hz, initial_value=0)
        self.in1 = DigitalOutputDevice(in1_pin)
        self.in2 = DigitalOutputDevice(in2_pin)

    def _drive(self, forward: bool, speed_fraction: float) -> None:
        if self.invert:
            forward = not forward
        self.in1.value = 1 if forward else 0
        self.in2.value = 0 if forward else 1
        self.enable.value = max(0.0, min(1.0, speed_fraction))

    def forward(self, speed_fraction: float) -> None:
        self._drive(True, speed_fraction)

    def backward(self, speed_fraction: float) -> None:
        self._drive(False, speed_fraction)

    def stop(self) -> None:
        try:
            self.enable.value = 0
            self.in1.off()
            self.in2.off()
        except Exception:  # noqa: BLE001
            pass

    def close(self) -> None:
        self.stop()
        for dev in (self.enable, self.in1, self.in2):
            try:
                dev.close()
            except Exception:  # noqa: BLE001
                pass


def build_motors(cfg, sides, pwm_hz):
    motors = []
    for side in sides:
        m = robot_config.get(cfg, "motors", side)
        if not m:
            print(f"WARN: no config for motor '{side}', skipping")
            continue
        motors.append(
            Motor(
                name=side,
                enable_pin=m["enable_pin"],
                in1_pin=m["in1_pin"],
                in2_pin=m["in2_pin"],
                invert=bool(m.get("invert", False)),
                pwm_hz=pwm_hz,
            )
        )
    return motors


def main() -> int:
    parser = argparse.ArgumentParser(description="Low-speed, short motor test.")
    parser.add_argument("--side", choices=["left", "right", "both"], default="both")
    args = parser.parse_args()

    cfg = robot_config.load_config()
    speed_limit = int(robot_config.get(cfg, "motors", "speed_limit_percent", default=40))
    speed_pct = int(robot_config.get(cfg, "motors", "test_speed_percent", default=25))
    speed_pct = min(speed_pct, speed_limit)
    duration = float(robot_config.get(cfg, "motors", "test_duration_s", default=0.6))
    pwm_hz = int(robot_config.get(cfg, "motors", "pwm_frequency_hz", default=1000))
    speed = speed_pct / 100.0
    dry = robot_config.is_dry_run(cfg)
    sides = ["left", "right"] if args.side == "both" else [args.side]

    print("=" * 60)
    print("  MOTOR TEST — WHEELS MUST BE OFF THE GROUND")
    print("=" * 60)
    print(f"Sides: {sides}   speed: {speed_pct}% (cap {speed_limit}%)   "
          f"duration: {duration}s each   {'DRY-RUN' if dry else 'LIVE'}")

    if not robot_config.confirm(
        "\nAre the wheels LIFTED off the ground and clear?", expected="LIFTED"
    ):
        print("Aborted — motors not started.")
        return 0

    if dry:
        for side in sides:
            print(f"[dry-run] {side}: forward {speed_pct}% {duration}s, "
                  f"backward {speed_pct}% {duration}s, stop")
        return 0

    motors = []
    try:
        motors = build_motors(cfg, sides, pwm_hz)
        if not motors:
            print("FAIL: no motors to test.")
            return 1
        for m in motors:
            print(f"\n{m.name}: forward {speed_pct}% for {duration}s")
            m.forward(speed)
            time.sleep(duration)
            m.stop()
            time.sleep(0.4)
            print(f"{m.name}: backward {speed_pct}% for {duration}s")
            m.backward(speed)
            time.sleep(duration)
            m.stop()
            time.sleep(0.4)
        print("\nOK: motor test complete.")
        print("If a wheel spun the wrong way, set that side's 'invert: true' in config/robot.yaml.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted — stopping motors.")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL: {exc} — stopping motors.")
        return 1
    finally:
        # Failsafe: motors are never left running.
        for m in motors:
            m.close()


if __name__ == "__main__":
    raise SystemExit(main())
