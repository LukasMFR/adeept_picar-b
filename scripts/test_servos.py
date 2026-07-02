#!/usr/bin/env python3
"""Test 3 — servos (PCA9685).

Moves each configured servo a small, bounded amount around its center and then
restores center. Requires explicit confirmation before moving. Motion is slow
(micro-stepped) and clamped to the per-servo min/max from config/robot.yaml.

Servos are driven with RAW 12-bit ticks (duty_cycle = ticks << 4), identical to
the original servo.py, so existing calibration values remain valid.

    python scripts/test_servos.py

SAFETY: make sure the head/pan/steering linkages can move freely without
binding. Keep fingers clear. Ctrl-C returns every servo to center.
"""
from __future__ import annotations

import time

import robot_config

TICKS_MAX = 4095


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def set_ticks(pca, channel: int, ticks: int) -> None:
    """Drive a PCA9685 channel with a 12-bit tick value (matches Adafruit_PCA9685.set_pwm)."""
    ticks = clamp(int(ticks), 0, TICKS_MAX)
    pca.channels[channel].duty_cycle = ticks << 4  # 12-bit -> 16-bit


def glide(pca, channel: int, start: int, end: int, low: int, high: int, delay: float) -> None:
    """Move slowly from start to end in single-tick steps, clamped to [low, high]."""
    step = 1 if end >= start else -1
    for tick in range(start, end + step, step):
        set_ticks(pca, channel, clamp(tick, low, high))
        time.sleep(delay)


def main() -> int:
    cfg = robot_config.load_config()
    servos = robot_config.get(cfg, "servos", "channels", default={})
    if not servos:
        print("FAIL: no servos configured under servos.channels")
        return 1

    step = int(robot_config.get(cfg, "servos", "test_step_ticks", default=20))
    delay = float(robot_config.get(cfg, "servos", "move_delay_s", default=0.02))
    addr = robot_config.get(cfg, "pca9685", "address", default=0x40)
    freq = robot_config.get(cfg, "pca9685", "frequency_hz", default=50)
    dry = robot_config.is_dry_run(cfg)

    print("Servo test — small, bounded movements around center.")
    print(f"Step: +/-{step} ticks   delay: {delay}s   {'DRY-RUN' if dry else 'LIVE'}")
    for name, s in servos.items():
        print(f"  {name}: ch{s['channel']} center={s['center']} "
              f"range=[{s['min']},{s['max']}] invert={s.get('invert', False)}")

    if not robot_config.confirm("\nServos will move a little. Linkages free to move?"):
        print("Aborted — no movement.")
        return 0

    pca = None
    if not dry:
        try:
            import board
            import busio
            from adafruit_pca9685 import PCA9685

            i2c = busio.I2C(board.SCL, board.SDA)
            pca = PCA9685(i2c, address=addr)
            pca.frequency = freq
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: PCA9685 init failed: {exc}")
            return 1

    def move_to(channel: int, frm: int, to: int, low: int, high: int) -> None:
        if dry:
            print(f"    [dry-run] ch{channel}: {frm} -> {clamp(to, low, high)}")
            return
        glide(pca, channel, frm, clamp(to, low, high), low, high, delay)

    try:
        for name, s in servos.items():
            ch = int(s["channel"])
            center = int(s["center"])
            low = int(s["min"])
            high = int(s["max"])
            direction = -1 if s.get("invert", False) else 1
            offset = step * direction

            print(f"\n{name} (ch{ch}): center -> +step -> -step -> center")
            move_to(ch, center, center, low, high)          # ensure at center
            time.sleep(0.2)
            move_to(ch, center, center + offset, low, high)  # nudge one way
            time.sleep(0.3)
            move_to(ch, center + offset, center - offset, low, high)  # other way
            time.sleep(0.3)
            move_to(ch, center - offset, center, low, high)  # back to center
            time.sleep(0.2)
        print("\nOK: all servos returned to center.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted — restoring centers...")
        return 1
    finally:
        # Failsafe: always try to return every servo to its center.
        if pca is not None:
            for s in servos.values():
                try:
                    set_ticks(pca, int(s["channel"]), int(s["center"]))
                except Exception:  # noqa: BLE001
                    pass
            try:
                pca.deinit()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
