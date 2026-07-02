# Hardware tests

Independent, safe test scripts for the PiCar-B on Trixie. Run them **one at a
time** from the repo root with the venv active. Every script reads hardware
settings from [`config/robot.yaml`](../config/robot.yaml).

```bash
source .venv/bin/activate
python scripts/<test>.py
```

## Safety first

- **Motor tests require the wheels to be OFF the ground.** You must type
  `LIFTED` to proceed. Speed is capped by `motors.speed_limit_percent`.
- Every movement test stops the hardware in a `finally` block and on Ctrl-C.
- Set `dry_run: true` in `config/robot.yaml` to rehearse any script with **no**
  hardware writes — it prints what it *would* do.
- Servo tests move slowly and stay within each servo's configured min/max.

## Recommended order

| # | Script | Moves? | Root? | What it checks |
|---|--------|--------|-------|----------------|
| 1 | `test_i2c.py` | no | no | `/dev/i2c-1`, bus scan, PCA9685 at `0x40` |
| 2 | `test_pca9685.py` | no | no | PCA9685 init + frequency (no servo motion) |
| 3 | `test_camera_picamera2.py` | no | no | Picamera2 captures one still |
| 4 | `test_ultrasonic.py` | no | no | HC-SR04 distance readings |
| 5 | `test_line_tracking.py` | no | no | 3 line-sensor digital states |
| 6 | `test_ws2812.py` | LEDs | **yes** | WS2812 colors + chase, then off |
| 7 | `test_servos.py` | **yes** | no | small bounded servo nudges around center |
| 8 | `test_motor.py` | **yes** | no | low-speed forward/backward per motor |

## Per-test notes

### 1. `test_i2c.py`
Confirms the I2C node exists, scans the bus (via `i2cdetect`, falling back to
`smbus`), and reports whether the configured PCA9685 address is present.

### 2. `test_pca9685.py`
Initializes the PCA9685 and sets the 50 Hz servo frequency. **No servo is
driven.** Add `--confirm` to also read back a channel register as a liveness check.

### 3. `test_camera_picamera2.py`
Uses Picamera2 (modern stack). Prints detected cameras and saves a JPEG to the
temp dir. Override the path with `--output /path/to.jpg`.

### 4. `test_ultrasonic.py`
Reads distance a few times via `gpiozero.DistanceSensor` (Trig=11, Echo=8).
`--samples N` to change count. If you get no readings, verify the ECHO line is
level-shifted to 3.3 V by the HAT.

### 5. `test_line_tracking.py`
Prints left/middle/right sensor state. Slide the robot over a line by hand and
watch which channel flips. `--seconds N` to change duration.

### 6. `test_ws2812.py`  — **needs root**
```bash
sudo .venv/bin/python scripts/test_ws2812.py
```
Cycles red/green/blue/white, runs a one-by-one chase, then turns all LEDs off.
Brightness defaults low (`ws2812.brightness`). **Does not work on Pi 5.**

### 7. `test_servos.py`  — **moves servos**
Prompts for confirmation, then nudges each servo `±servos.test_step_ticks`
around center and restores center. Make sure the head/pan/steering linkages can
move freely. Ctrl-C re-centers everything.

### 8. `test_motor.py`  — **moves wheels**
```bash
python scripts/test_motor.py            # both motors
python scripts/test_motor.py --side left
```
Requires the `LIFTED` confirmation. Runs each motor forward then backward at
`motors.test_speed_percent` for `motors.test_duration_s`. **If a wheel spins the
wrong way, set that side's `invert: true` in `config/robot.yaml`** and re-run —
this is the intended way to calibrate motor direction.
