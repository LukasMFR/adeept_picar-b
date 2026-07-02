#!/usr/bin/env python3
"""Test 5 — WS2812 / NeoPixel strip.

Cycles the strip red -> green -> blue -> white, then lights each LED one by one,
then turns everything OFF. Uses rpi_ws281x on the configured GPIO pin.

    sudo .venv/bin/python scripts/test_ws2812.py

*** ROOT REQUIRED ***  rpi_ws281x needs root for DMA/PWM access.
*** Raspberry Pi 5 ***  rpi_ws281x does NOT work on Pi 5 — see MIGRATION_NOTES.
Brightness defaults low (config ws2812.brightness) for safe bench testing.
LEDs are reset to OFF in a finally block.
"""
from __future__ import annotations

import os
import time

import robot_config


def main() -> int:
    cfg = robot_config.load_config()
    w = robot_config.get(cfg, "ws2812", default={})
    pin = int(w.get("gpio_pin", 12))
    count = int(w.get("led_count", 16))
    brightness = int(w.get("brightness", 64))
    freq = int(w.get("freq_hz", 800000))
    dma = int(w.get("dma", 10))
    channel = int(w.get("channel", 0))
    invert = bool(w.get("invert", False))
    dry = robot_config.is_dry_run(cfg)

    print(f"WS2812 test — GPIO {pin}, {count} LEDs, brightness {brightness} "
          f"{'DRY-RUN' if dry else 'LIVE'}")

    if dry:
        print("[dry-run] would show red, green, blue, white, chase, then OFF.")
        return 0

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("FAIL: rpi_ws281x needs root. Run:")
        print("    sudo .venv/bin/python scripts/test_ws2812.py")
        return 1

    try:
        from rpi_ws281x import Color, PixelStrip
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: cannot import rpi_ws281x: {exc}")
        print("      On Pi 5 this library does not work — see docs/MIGRATION_NOTES.md")
        return 1

    strip = PixelStrip(count, pin, freq, dma, invert, brightness, channel)

    def fill(r, g, b, wait=0.5):
        for i in range(count):
            strip.setPixelColor(i, Color(r, g, b))
        strip.show()
        time.sleep(wait)

    def off():
        for i in range(count):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

    try:
        strip.begin()
        print("  red");   fill(255, 0, 0)
        print("  green"); fill(0, 255, 0)
        print("  blue");  fill(0, 0, 255)
        print("  white"); fill(255, 255, 255)
        off()
        print("  chase (one by one)")
        for i in range(count):
            strip.setPixelColor(i, Color(0, 0, 255))
            strip.show()
            time.sleep(0.08)
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        print("OK: WS2812 test complete.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 1
    finally:
        # Failsafe: always turn the strip off.
        try:
            off()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
