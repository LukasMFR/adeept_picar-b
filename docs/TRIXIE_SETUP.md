# PiCar-B on Raspberry Pi OS Lite 64-bit (Debian 13 "Trixie")

Modern, venv-based setup for the Adeept PiCar-B / Robot HAT. This replaces the
legacy `setup.py` flow (which uses `sudo pip`, `/etc/rc.local`, `create_ap`, and
apt packages that no longer exist on Trixie).

> **Step 1 scope:** this adds a clean hardware foundation only — config, a
> requirements file, and independent test scripts. It does **not** modify the old
> `server/` code, install autorun, or create services. See
> [MIGRATION_NOTES.md](MIGRATION_NOTES.md) for the reasoning and roadmap.

## 0. Start from a fresh install

Flash **Raspberry Pi OS Lite 64-bit (Trixie)**, boot, then:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

## 1. Enable interfaces

Enable I2C (for the PCA9685) and the camera. Easiest via `raspi-config`:

```bash
sudo raspi-config    # Interface Options -> I2C -> Enable
```

Confirm the I2C device node exists after a reboot:

```bash
ls /dev/i2c-1
```

## 2. Install system packages (apt)

These are installed via apt (not pip) so they match the system Python, kernel,
and camera stack:

```bash
sudo apt install -y \
  git build-essential pkg-config \
  python3-full python3-venv python3-pip python3-dev \
  python3-opencv python3-smbus i2c-tools \
  python3-picamera2 \
  libopenblas-dev
```

## 3. Create the virtual environment

`--system-site-packages` lets the venv see the apt-installed `cv2`, `picamera2`,
and `smbus` modules while still isolating project pip installs.

```bash
cd ~/adeept_picar-b        # repo root
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-trixie.txt
```

> Do **not** use `sudo pip`, and do not install project packages globally.

## 4. Verify the environment

```bash
python scripts/check_environment.py
```

Resolve any `[FAIL]` lines (missing I2C node, missing required imports) before
running hardware tests. `[WARN]` lines are informational.

## 5. Run the hardware tests

See [HARDWARE_TESTS.md](HARDWARE_TESTS.md). Run them one at a time, in order.
The safe read-only tests first (`test_i2c`, `test_pca9685`, camera, sensors),
then the movement tests (`test_servos`, `test_motor`) only when the robot is
safely supported.

## Supported hardware

This foundation targets **Raspberry Pi 3 and Raspberry Pi 4** by default, running
Raspberry Pi OS Lite 64-bit (Trixie). The Pi 5 uses a different GPIO controller
(RP1) and has its own limitations, documented separately in
[MIGRATION_NOTES.md](MIGRATION_NOTES.md#raspberry-pi-5-specific-notes). Those Pi 5
caveats do **not** apply to Pi 3/4.

## Notes / gotchas on Trixie

- **GPIO backend:** the test scripts use **`gpiozero`** with the `lgpio` backend,
  which is the preferred modern path on Trixie for Pi 3/4/5. Classic `RPi.GPIO`
  is deprecated on recent images (and does not work on the Pi 5), so it is not
  used here; on Pi 3/4 it may still function but `gpiozero`/`lgpio` is preferred.
- **WS2812 needs root.** Run its test with
  `sudo .venv/bin/python scripts/test_ws2812.py`. `rpi_ws281x` works on Pi 3/4;
  it does **not** work on the Pi 5 (see MIGRATION_NOTES for the Pi 5 alternative).
- **PCA9685** uses the maintained `adafruit-circuitpython-pca9685` library, but
  the servo scripts drive it with the same raw 12-bit tick values as the old
  code, so your existing calibration in `server/config.txt` stays valid.
- The venv Python for a `sudo` run is `.venv/bin/python` — plain `sudo python`
  would use the system interpreter and miss the venv packages.
