# PiCar-B Modern Web UI

A modernized, mobile-first control console for the Adeept PiCar-B, built on the
existing Flask + WebSocket backend. This branch (`picar-b-modern-ui`) changes
**only the web interface and the minimum backend needed to support it and make it
safe**. It does not touch the OS, `setup.py`, `rc.local`, autorun, or hardware pins.

## What it looks like

- A dark-tech "FPV cockpit": the live camera is prominent, controls sit in a
  glass dock beside it (desktop) or below it (mobile).
- Light and dark themes follow `prefers-color-scheme`, plus a manual toggle in the
  top bar (auto -> light -> dark, remembered in `localStorage`).
- Large, touch-friendly, hold-to-drive controls tuned for iPhone Safari.
- A full-width **STOP** button that is always visible on every tab.

## How to run

Nothing about starting the robot changes. Start the server exactly as before:

```bash
cd server
sudo python3 webServer.py
```

`webServer.py` launches the Flask app (`app.py`) in a thread. Then open a browser
on the same network:

```
http://<raspberry-pi-ip>:5000/
```

- `http://<ip>:5000/`        -> the new console (default)
- `http://<ip>:5000/legacy`  -> the original Vue interface (kept as a fallback)

The console talks to the two services the robot already exposes:

| Purpose        | Endpoint                          |
| -------------- | --------------------------------- |
| Camera (MJPEG) | `http://<ip>:5000/video_feed`     |
| Control socket | `ws://<ip>:8888` (auth `admin:123456`) |

No build step, no framework, no internet access required. The whole UI is one
self-contained file (`server/ui/index.html`) so it works when the robot is in
offline AP mode. Fonts use the system stack (SF Pro on iPhone) and icons are
inline SVG for the same reason.

## Controls

| Section  | Controls |
| -------- | -------- |
| Drive    | Speed slider, hold-to-steer (left/right), hold-to-throttle (forward/reverse) |
| Camera   | Hold-to-pan/tilt (up/down/left/right), center, ultrasonic scan |
| Lights   | Robot HAT switch ports 1-3; autonomous modes (obstacle avoidance, line tracking, motion watch) |
| System   | Live temperature / CPU / RAM, connection details, latency, collapsible debug console, link to legacy UI |

Movement controls are **momentary**: the robot moves only while a control is held
and stops the instant you release, lose focus, switch tabs, or background the page.

### Keyboard controls (desktop)

The on-screen buttons show their key hints, and pressing a key drives the same
button (it lights up "pressed" while the key is held). Keys are hidden on
touch-only devices.

| Keys | Action |
| ---- | ------ |
| `W` / `Up`  | Forward (hold) |
| `S` / `Down` | Reverse (hold) |
| `A` / `Left` | Steer left (hold) |
| `D` / `Right` | Steer right (hold) |
| `I` `K` `J` `L` | Camera tilt up / down, pan left / right (hold) |
| `H` | Center camera |
| `Esc` | Emergency stop (works anywhere) |
| `Space` | Emergency stop (when no control is focused) |

Hold `W` and `A` together to drive forward while steering, and so on. Releasing a
key sends the matching stop, exactly like lifting a finger. On a touch screen you
can hold two buttons at once the same way (for example steer + throttle) — each
finger is tracked independently.

### Joystick control

The System tab has a **Joystick control** toggle (under "Controls"). When on, the
Drive tab shows a drag joystick instead of the direction buttons: vertical drag is
forward/reverse, horizontal is steering, both released the instant you let go. The
keyboard still drives while the joystick is shown. This is a per-device display
preference (stored in `localStorage["picar-prefs"]`), not a robot setting, since a
joystick suits a phone but not a desktop.

With buttons (the default), the Drive tab keeps STEER on the left and THROTTLE on
the right, below the camera.

### Settings

The System tab has a Settings section (under "Robot behaviour"):

- **Invert forward / reverse** — swaps the throttle direction if the robot drives
  the opposite way to the buttons (for example if the motors are wired reversed).
  - **Also invert the direction lights** (sub-option) — swaps the white (forward)
    and red (reverse) LEDs so they match the button you pressed.
- **Invert steering** — swaps left and right.
  - **Also invert the turn signals** (sub-option) — swaps the left/right indicator
    LEDs to match.

Throttle/steer inversion is applied to the on-screen buttons, the keyboard, and the
joystick. The two light inversions are applied on the robot itself (`webServer.py`
reads the shared config); they are independent toggles, so you can enable a light
swap on its own if only the LEDs are wired the wrong way round.

These are **shared, server-side settings** so every phone and computer sees the
same configuration. The robot keeps the authoritative copy in
`server/robot_settings.json` and exposes a small JSON API on the Flask server:

| Method | Endpoint | Behaviour |
| ------ | -------- | --------- |
| `GET`  | `/api/settings` | Returns the current settings (defaults if none saved). |
| `POST` | `/api/settings` | Accepts a JSON object; only the known boolean keys are read, everything else is ignored; writes atomically and returns the saved settings. |

The API validates input safely: a non-object body or malformed JSON returns
`400`, an oversized body returns `413`, unknown keys are dropped, and values are
coerced to booleans, so a bad or hostile request cannot inject state.

`localStorage["picar-settings"]` is kept only as a **cache/fallback**: the UI
shows the cached values instantly on load, then refreshes them from the robot;
if the robot's API is unreachable it keeps working from the cache. The settings
file is per-robot and is not tracked in git.

### Servo calibration

The System tab has a **Servo calibration** section (under "Robot behaviour").
The PiCar-B has three servos on PCA9685 channels 0, 1, 2:

| Channel | Servo | Controller |
| ------- | ----- | ---------- |
| 0 | Camera tilt (up / down) | `T_sc` |
| 1 | Camera pan (left / right) | `P_sc` |
| 2 | Steering (front wheels) | `scGear` |

Each servo has a **center** (its resting PWM) plus a **min** and **max** travel
limit. The center is what the camera **Center** button and the steering neutral
resolve to; `300` is the official Adeept safe default. Adjust a center with the
`−5 / −1 / +1 / +5` steppers or by typing a value; min/max are typed fields. Every
value is clamped to the driver's safe PWM range (`100`–`560`), `min ≤ max` is
enforced, and the center is kept inside `[min, max]`, on both the client and the
server, so a bad or hostile value can never push a servo past its limits.

Calibration is a **shared, server-side** config, like the behaviour settings. The
robot keeps the authoritative copy in `server/robot_servo_calibration.json` and
exposes a JSON API:

| Method | Endpoint | Behaviour |
| ------ | -------- | --------- |
| `GET`  | `/api/servo_calibration` | Returns the calibration (defaults if none saved). |
| `POST` | `/api/servo_calibration` | Accepts `{ "servos": { "0": { "center", "min", "max" }, ... } }` (partial updates allowed); validates and clamps every value, writes atomically, applies it to the live servos, and returns the saved calibration. |

Saving **applies live** without a restart: `webServer.py` registers a callback on
the Flask app (they share one process), so a save updates each servo's center and
limits immediately and gently eases the servo to its new center, letting you see
where "straight" really is while you calibrate. On startup the calibration is
loaded **before** the first init move, so the robot settles on the calibrated
centers rather than the hard-coded `300`.

The single source of truth is `server/robot_servo_calibration.json` (per-robot,
not tracked in git). If that file does not exist yet, every servo defaults to
**center 300** (the official Adeept value); the file is created only when you
first save from the UI. Nothing is read from the user's home folder.
`localStorage["picar-servo-cal"]` is only a cache/fallback, exactly like the
behaviour settings.

The legacy Vue interface's own servo-tuning commands (`SiLeft`/`SiRight`/`PWMMS`/
`PWMD`, which rewrite `RPIservo.py`) are left untouched and still work.

## Safety model

The UI and backend cooperate so the robot never keeps moving unattended:

- **Hold-to-move only.** Press-and-hold sends the move command; releasing sends the
  matching stop (`DS` for drive, `TS` for steer, `UDstop`/`LRstop` for the camera).
- **Release backstops.** `pointerup`, confirmed touch release/cancel, lost pointer
  capture, window `blur`, and `visibilitychange` (tab hidden) all release every
  held control. Tab hidden also fires an `E_STOP`.
- **Always-visible STOP.** Sends `E_STOP`, plus `DS`/`TS`, and clears any held
  controls and autonomous-mode toggles. `Esc` on desktop does the same.
- **Heartbeat + WebSocket liveness.** The client sends an idle `heartbeat` every
  500ms, or re-sends the held drive/steer command at the same cadence while a
  control is pressed. Connection safety is handled by server-side WebSocket
  ping/pong, so mobile timer delays during a long touch hold do not trigger a
  false motor stop. If the link really dies (phone sleeps, Wi-Fi drops),
  `main_logic` stops the motors in its disconnect `finally` block; the close
  timeout is kept short so silent radio loss is cut off promptly.
- **Stop on disconnect.** `main_logic` stops the motors in a `finally` block when the
  client disconnects for any reason.
- **Clear disconnected state.** The top-bar dot turns red, controls report "Not
  connected", and the client auto-reconnects with backoff.

No autonomous or movement test is ever triggered automatically. Autonomous modes
(obstacle avoidance, line tracking) are opt-in toggles that warn before engaging.

## Changed files

| File | Change |
| ---- | ------ |
| `server/ui/index.html` | **New.** The entire modern console (HTML + CSS + JS, self-contained). |
| `server/app.py` | Serve the new console at `/`; keep the original Vue app at `/legacy`; add the `GET`/`POST` `/api/settings` config API and the `GET`/`POST` `/api/servo_calibration` API. |
| `server/webServer.py` | **Safety:** added `emergency_stop()` + `E_STOP` command, WebSocket ping/pong liveness, a `heartbeat` no-op, and stop-on-disconnect in `main_logic`. Also reads the shared config to swap the forward/reverse LED colour when "Invert direction lights" is on. **Servo calibration:** loads the calibration into the live controllers at start-up and on save, and fixes the `home`/Center command (it referenced an undefined `G_sc` and passed PWM values as channel IDs). |
| `server/robot_settings.json` | Runtime, per-robot config written by the settings API (git-ignored, created on first save). |
| `server/robot_servo_calibration.json` | Runtime, per-robot servo calibration written by the calibration API (git-ignored, created on first save). |
| `.gitignore` | Ignore `server/robot_settings.json`. |
| `WEB_UI.md` | **New.** This document. |

The command protocol, hardware drivers, camera pipeline, and existing endpoints are
unchanged. The original UI and desktop `client/GUI.py` still work.

## Safe manual tests

Do these with the **wheels lifted off the ground** for anything involving motors.

1. **Load & serve** — open `http://<ip>:5000/`. The console loads; the top-bar dot
   goes green ("Connected"); the camera feed appears. Open `/legacy` and confirm the
   old UI still loads.
2. **Camera** — confirm live video. Kill nothing; then temporarily block the feed and
   confirm the "Camera offline" state and auto-retry, then recovery.
3. **Telemetry** — the System tab and top-bar chips show temperature / CPU / RAM and
   update every few seconds. Latency shows a millisecond value.
4. **Theme** — tap the theme button; confirm auto -> light -> dark and that it
   survives a reload. Toggle your OS dark mode with the theme on "auto".
5. **Camera pan/tilt (no wheels needed)** — on the Camera tab, hold each arrow and
   confirm the camera servos move only while held, and "Center" recenters.
6. **Lights** — toggle Light 1-3 and confirm the corresponding Robot HAT ports switch.
7. **Steering only (wheels can stay down)** — on Drive, hold Left/Right and confirm the
   steering servo turns and recenters on release.
8. **Drive (WHEELS LIFTED)** — hold Forward, confirm motors run; release, confirm they
   stop immediately. Repeat for Reverse. Drag your finger off the button and confirm it
   stops. Switch tabs mid-hold and confirm it stops.
9. **STOP (WHEELS LIFTED)** — hold Forward, tap STOP; motors stop at once. Press `Esc`
   on desktop for the same effect.
10. **Watchdog (WHEELS LIFTED)** — hold Forward, then put the phone to sleep / turn off
    Wi-Fi. Within ~2.5s the motors stop on their own. Reconnect and confirm the UI shows
    "Reconnecting" then "Connected".
11. **Disconnect (WHEELS LIFTED)** — hold Forward, then close the browser tab. The
    motors stop immediately (server `finally`).
12. **Shared settings** — on phone A, System tab, turn on "Invert forward / reverse".
    Open the console on phone B (or another browser) and confirm the switch is already
    on. Check `curl http://<ip>:5000/api/settings` returns the same values. With the
    server reachable the setting survives a full reload on a device with cleared site
    data; if the robot is unreachable the UI still loads from its local cache.
13. **Joystick (WHEELS LIFTED)** — System tab, turn on "Joystick control". On the Drive
    tab, drag the joystick up/down/left/right and confirm the robot responds; release
    and confirm it stops. Toggle it back off and confirm the buttons return. Confirm the
    setting sticks after a reload on that device.
14. **Direction lights (WHEELS LIFTED)** — with "Invert forward / reverse" on, hold
    Forward and note the LED colour. Turn on "Also invert the direction lights"; hold
    Forward again and confirm the colour is now the white/headlight colour (and Reverse
    shows red). No robot restart is needed; the change applies on the next command.
15. **Turn signals (WHEELS LIFTED)** — with "Invert steering" on, hold Left and note
    which indicator lights. Turn on "Also invert the turn signals"; hold Left again and
    confirm the opposite indicator now lights (matching the button).
16. **Servo calibration (no wheels needed)** — System tab, Servo calibration. Nudge the
    Camera tilt center with `+5`/`−1`; the tilt servo eases to the new center each time
    and the status reads "Saved to robot". On the Camera tab tap **Center** and confirm
    the camera returns to the calibrated center, not `300`. Open the console on another
    device and confirm the values match, and that `curl http://<ip>:5000/api/servo_calibration`
    returns the same JSON. Tap **Reset all to 300** to restore the official defaults.

## Rollback

To restore the original interface as the default, revert the `index()` route in
`server/app.py` to serve `dist/index.html`. The safety additions in `webServer.py`
are independent and can stay.
