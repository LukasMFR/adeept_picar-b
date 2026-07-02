#!/usr/bin/env python3
"""Environment check for the PiCar-B modern (Trixie) setup.

Read-only. Touches no hardware output; only reads/reports. Run this first after
setting up the venv to confirm the system is ready for the hardware tests.

    python scripts/check_environment.py
"""
from __future__ import annotations

import importlib
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import robot_config

OK = "[ OK ]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def line(status: str, msg: str) -> None:
    print(f"{status} {msg}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def run(cmd: list[str]) -> tuple[int, str]:
    """Run a command, returning (returncode, combined_output). Never raises."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def check_os() -> None:
    section("Operating system")
    line(OK, f"Platform: {platform.platform()}")
    os_release = Path("/etc/os-release")
    if os_release.exists():
        info = {}
        for entry in os_release.read_text().splitlines():
            if "=" in entry:
                key, _, val = entry.partition("=")
                info[key] = val.strip().strip('"')
        pretty = info.get("PRETTY_NAME", "unknown")
        line(OK, f"OS: {pretty}")
        if "trixie" in pretty.lower() or info.get("VERSION_CODENAME") == "trixie":
            line(OK, "Debian 13 'Trixie' detected")
        else:
            line(WARN, "Not detected as Trixie — scripts target Trixie")
    else:
        line(WARN, "/etc/os-release not found (not a Linux/Pi host?)")


def check_python() -> None:
    section("Python")
    line(OK, f"Python {sys.version.split()[0]} ({sys.executable})")
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        line(OK, f"Running inside a virtual environment: {sys.prefix}")
    else:
        line(WARN, "NOT running inside a venv — see docs/TRIXIE_SETUP.md")


def check_imports() -> None:
    section("Python imports")
    # (module, friendly name, required?)
    modules = [
        ("yaml", "PyYAML", True),
        ("gpiozero", "gpiozero", True),
        ("lgpio", "lgpio", False),
        ("board", "Adafruit Blinka (board)", False),
        ("adafruit_pca9685", "adafruit-circuitpython-pca9685", False),
        ("cv2", "OpenCV (python3-opencv)", False),
        ("picamera2", "Picamera2 (python3-picamera2)", False),
        ("smbus", "smbus (python3-smbus)", False),
        ("rpi_ws281x", "rpi_ws281x", False),
        ("flask", "Flask", False),
    ]
    for module, name, required in modules:
        try:
            importlib.import_module(module)
            line(OK, f"import {module}  ({name})")
        except Exception as exc:  # noqa: BLE001 - report any import failure
            status = FAIL if required else WARN
            line(status, f"import {module} failed ({name}): {exc}")


def check_i2c(cfg: dict) -> None:
    section("I2C / PCA9685")
    bus = robot_config.get(cfg, "i2c", "bus", default=1)
    dev = Path(f"/dev/i2c-{bus}")
    if dev.exists():
        line(OK, f"{dev} exists")
    else:
        line(FAIL, f"{dev} missing — enable I2C (dtparam=i2c_arm=on) and reboot")
        return

    addr = robot_config.get(cfg, "pca9685", "address", default=0x40)
    addr_hex = f"0x{addr:02x}"

    if shutil.which("i2cdetect"):
        code, out = run(["i2cdetect", "-y", str(bus)])
        if code == 0:
            found = addr_hex[2:] in out.replace(" ", " ").split()
            if found:
                line(OK, f"PCA9685 visible at {addr_hex} via i2cdetect")
            else:
                line(WARN, f"{addr_hex} not seen by i2cdetect (HAT powered/connected?)")
            if robot_config.is_debug(cfg):
                print(out)
        else:
            line(WARN, f"i2cdetect failed: {out}")
    else:
        line(WARN, "i2c-tools not installed (apt install i2c-tools) — trying smbus")
        try:
            import smbus  # type: ignore

            b = smbus.SMBus(bus)
            b.read_byte(addr)
            line(OK, f"PCA9685 responded at {addr_hex} via smbus")
        except Exception as exc:  # noqa: BLE001
            line(WARN, f"smbus probe of {addr_hex} failed: {exc}")


def check_camera() -> None:
    section("Camera")
    code, out = run(["rpicam-hello", "--list-cameras"])
    if code == 127:
        code, out = run(["libcamera-hello", "--list-cameras"])
    if code == 0 and out:
        line(OK, "Camera detected via libcamera stack")
        if out:
            first = out.splitlines()[0]
            line(OK, f"  {first}")
    else:
        line(WARN, "No camera reported by libcamera (check ribbon/enable)")


def check_network() -> None:
    section("Network")
    hostname = socket.gethostname()
    line(OK, f"Hostname: {hostname}")
    code, out = run(["hostname", "-I"])
    if code == 0 and out:
        line(OK, f"IP address(es): {out}")
    else:
        line(WARN, "Could not determine IP address")


def check_thermal() -> None:
    section("Temperature / throttling")
    temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_file.exists():
        try:
            millideg = int(temp_file.read_text().strip())
            line(OK, f"CPU temperature: {millideg / 1000:.1f} C")
        except ValueError:
            line(WARN, "Could not read CPU temperature")
    if shutil.which("vcgencmd"):
        code, out = run(["vcgencmd", "get_throttled"])
        if code == 0:
            throttled = out.strip()
            status = OK if throttled.endswith("0x0") else WARN
            line(status, f"vcgencmd {throttled}")
    else:
        line(WARN, "vcgencmd not available")


def check_config() -> None:
    section("Project config")
    try:
        cfg = robot_config.load_config()
    except SystemExit as exc:
        line(FAIL, str(exc))
        return None
    line(OK, f"Loaded {robot_config.DEFAULT_CONFIG_PATH}")
    for key in ("motors", "servos", "ws2812", "ultrasonic", "line_tracking", "pca9685"):
        present = key in cfg
        line(OK if present else FAIL, f"section '{key}': {'present' if present else 'MISSING'}")
    if robot_config.is_dry_run(cfg):
        line(WARN, "dry_run is ENABLED — hardware writes will be simulated")
    return cfg


def main() -> int:
    print("PiCar-B Trixie environment check")
    print("=" * 40)
    check_os()
    check_python()
    check_imports()
    cfg = check_config()
    if cfg is not None:
        check_i2c(cfg)
    check_camera()
    check_network()
    check_thermal()
    print("\nDone. Review any [WARN]/[FAIL] lines above before running hardware tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
