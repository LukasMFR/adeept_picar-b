#!/usr/bin/env python3
"""Test 6 — camera (Picamera2).

Uses the modern Picamera2 stack (not the legacy PiCamera). Prints camera info
and captures a single still to the scratch/temp directory, then exits cleanly.

    python scripts/test_camera_picamera2.py
    python scripts/test_camera_picamera2.py --output /tmp/picar_test.jpg

Picamera2 comes from apt (python3-picamera2) and is visible inside a
--system-site-packages venv.
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import robot_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one still via Picamera2.")
    parser.add_argument("--output", help="path for the captured JPEG")
    args = parser.parse_args()

    cfg = robot_config.load_config()
    width = int(robot_config.get(cfg, "camera", "width", default=640))
    height = int(robot_config.get(cfg, "camera", "height", default=480))

    out = Path(args.output) if args.output else Path(tempfile.gettempdir()) / "picar_camera_test.jpg"

    if robot_config.is_dry_run(cfg):
        print(f"[dry-run] would capture {width}x{height} still to {out}")
        return 0

    try:
        from picamera2 import Picamera2
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: cannot import picamera2: {exc}")
        print("      sudo apt install -y python3-picamera2  (venv must use --system-site-packages)")
        return 1

    picam = None
    try:
        picam = Picamera2()
        cameras = Picamera2.global_camera_info()
        print(f"Cameras detected: {len(cameras)}")
        for i, cam in enumerate(cameras):
            print(f"  [{i}] {cam.get('Model', 'unknown')}  {cam.get('Location', '')}")

        config = picam.create_still_configuration(main={"size": (width, height)})
        picam.configure(config)
        picam.start()
        # A short warm-up lets auto-exposure/white-balance settle.
        import time
        time.sleep(1.0)
        picam.capture_file(str(out))
        print(f"OK: captured {width}x{height} still to {out}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: camera capture failed: {exc}")
        return 1
    finally:
        if picam is not None:
            try:
                picam.stop()
            except Exception:  # noqa: BLE001
                pass
            try:
                picam.close()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
