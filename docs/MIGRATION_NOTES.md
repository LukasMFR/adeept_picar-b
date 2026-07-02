# Migration notes — PiCar-B to Raspberry Pi OS Trixie

Why the modern setup differs from the official Adeept code, what stayed the same,
and the roadmap. The robot is confirmed working on the old Buster image; the goal
is a clean, testable Trixie foundation **without** changing hardware behaviour.

## Target hardware

**Default target: Raspberry Pi 3 and Raspberry Pi 4** on Raspberry Pi OS Lite
64-bit (Trixie). The Step 1 foundation (config, tests, docs) is safe to run on
Pi 3/4. The Raspberry Pi 5 introduces a different GPIO controller (RP1) with its
own constraints; those are documented separately in
[Raspberry Pi 5-specific notes](#raspberry-pi-5-specific-notes) and do **not**
apply to Pi 3/4.

## Hardware inventory (extracted from the working Buster sources)

All pins are **BCM**, copied verbatim into [`config/robot.yaml`](../config/robot.yaml).

| Subsystem | Source file | Pins / address | Notes |
|-----------|-------------|----------------|-------|
| Right motor (`Motor_A`) | `server/move.py` | EN=4, IN1=14, IN2=15 | 1 kHz PWM on EN |
| Left motor (`Motor_B`) | `server/move.py` | EN=17, IN1=27, IN2=18 | forward polarity mirrors the right side in the original code |
| Servos (PCA9685) | `server/servo.py`, `server/RPIservo.py` | I2C `0x40` @ 50 Hz | ch0 head-tilt (dir −1, 100–500), ch1 head-pan/radar (150–450), ch2 steering (150–450); all center 300 |
| Ultrasonic | `server/ultra.py` | Trig=11, Echo=8 | HC-SR04 style |
| Line tracking | `server/findline.py` | L=20, M=16, R=19 | digital; `1` = line |
| WS2812 | `server/robotLight.py`, `server/LED.py` | GPIO 12, 16 LEDs | 800 kHz, DMA 10, channel 0 |
| HAT switch outputs / lights | `server/switch.py`, `server/robotLight.py` | 5, 6, 13 | high-side ports 1/2/3 |
| Camera | `server/camera_opencv.py` | `cv2.VideoCapture(0)` | legacy stack |

### Values intentionally reconciled
- **WS2812 LED count:** `robotLight.py` uses **16**, `LED.py` module-level uses
  12 (its class uses 16). Config defaults to **16** (matches the class the web
  server uses). Adjust `ws2812.led_count` to your actual strip.
- **WS2812 brightness:** lowered from `255` to `64` in config for safe bench
  testing. Raise as desired.
- **Servo direction / min / max:** taken from `servo.py` (ch0 inverted, ch0
  range 100–500, ch1/ch2 range 150–450). `RPIservo.py` uses a wider 100–560
  generic range; the per-servo values in config follow the more specific
  `servo.py`. Existing tick calibration in `server/config.txt` remains valid.

## Dependency changes and why

| Legacy (Buster) | Problem on Trixie | Modern replacement |
|-----------------|-------------------|--------------------|
| `RPi.GPIO` | Deprecated on recent images; unsupported on Pi 5 (RP1 GPIO). On Pi 3/4 it may still work but is no longer the recommended path | **`gpiozero`** + `lgpio` backend (preferred on Pi 3/4/5) |
| `Adafruit_PCA9685` | Abandoned, not on PyPI for 3.11+ | **`adafruit-circuitpython-pca9685`** (driven with the same raw 12-bit ticks) |
| `picamera` (legacy) | Removed; libcamera is the stack now | **`picamera2`** (apt `python3-picamera2`) |
| `rpi_ws281x` | Works on Pi 3/4 (needs root); not supported on Pi 5 (RP1) | Kept for Pi 3/4; Pi 5 needs an SPI/PIO-based approach (future) |
| `sudo pip3 install ...` | Externally-managed env (PEP 668); pollutes system | **venv** (`--system-site-packages`) + `requirements-trixie.txt` |
| `python3-opencv` via mixed pip/apt | Version/ABI drift | apt `python3-opencv`, visible through the venv |
| `create_ap`, `/etc/rc.local`, `startup.sh`, audio blacklist + reboot | Deprecated / out of scope for a hardware foundation | **dropped** from Step 1 |

### PCA9685 tick compatibility (important)
The old code calls `pwm.set_pwm(channel, 0, ticks)` with 12-bit `ticks`
(0–4095). The scripts reproduce this exactly:
`pca.channels[ch].duty_cycle = ticks << 4` (12-bit → 16-bit). So every
calibration value in `server/config.txt` and `servo.py` carries over unchanged.

## Things deliberately **not** done in Step 1
- No edits to `server/webServer.py` or any existing runtime code.
- No systemd services, no autorun, no `/etc/rc.local`.
- No Wi-Fi AP / `create_ap`.
- No UI changes.
- The direct-GPIO RGB pins in `robotLight.py` (22/23/24, 10/9/25) are **not**
  wired into the config/tests — they belong to a legacy LED path superseded by
  the WS2812 strip. Left untouched pending confirmation of the actual board.

## Raspberry Pi 5-specific notes

These apply **only** to the Pi 5 and are **not** limitations on Pi 3/4. The Pi 5
moves GPIO onto a separate RP1 I/O controller, which changes what works:

- **`RPi.GPIO` (classic):** does not work on the Pi 5. This is a Pi 5 issue, not
  a general Trixie issue — on Pi 3/4 the classic library still functions (though
  `gpiozero`/`lgpio`, which this project uses, is preferred everywhere).
- **`gpiozero` + `lgpio`:** works on Pi 5 as well, so the motor/servo/sensor
  scripts here are expected to run on Pi 5 unchanged. (Pin factories/backends may
  differ under the hood, but the scripts don't depend on that.)
- **`rpi_ws281x` (WS2812):** not supported on the Pi 5 — the PWM/DMA path it
  relies on is not available through RP1. A Pi 5 WS2812 story (e.g. SPI- or
  PIO-based drive) is deferred to a later step. On Pi 3/4 it works (as root).

## Roadmap

- **Step 1 (this change):** docs, `config/robot.yaml`, `requirements-trixie.txt`,
  environment check, independent hardware test scripts. Additive only.
- **Step 2:** once tests pass on real hardware, build a clean hardware
  abstraction layer (motors/servos/LEDs/sensors) on top of the config — no UI
  changes.
- **Step 3:** modern Flask (or FastAPI) backend on top of the abstraction layer.
- **Step 4:** modernize the mobile UI.

## Open items to confirm on real hardware
- Motor `invert` flags per side (use `scripts/test_motor.py` with wheels lifted).
- Actual WS2812 LED count: `robotLight.py` uses **16**, `LED.py` uses **12**
  (config defaults to 16). Confirm against your physical strip.
- Whether the direct-GPIO RGB LEDs exist on this board or only the WS2812 strip.
- Ultrasonic ECHO level-shifting (3.3 V at the Pi) on the current HAT revision.
