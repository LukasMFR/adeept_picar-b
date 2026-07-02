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

## Safety model

The UI and backend cooperate so the robot never keeps moving unattended:

- **Hold-to-move only.** Press-and-hold sends the move command; releasing sends the
  matching stop (`DS` for drive, `TS` for steer, `UDstop`/`LRstop` for the camera).
- **Release backstops.** `pointerup`, `pointercancel`, lost pointer capture, window
  `blur`, and `visibilitychange` (tab hidden) all release every held control. Tab
  hidden also fires an `E_STOP`.
- **Always-visible STOP.** Sends `E_STOP`, plus `DS`/`TS`, and clears any held
  controls and autonomous-mode toggles. `Esc` on desktop does the same.
- **Heartbeat + server watchdog.** The client sends a `heartbeat` every second.
  `webServer.py` waits at most `COMMAND_TIMEOUT` (2.5s) for any message; if the link
  goes silent (phone sleeps, Wi-Fi drops) it stops the motors.
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
| `server/app.py` | Serve the new console at `/`; keep the original Vue app at `/legacy`. |
| `server/webServer.py` | **Safety:** added `emergency_stop()` + `E_STOP` command, a receive-timeout watchdog in `recv_msg`, a `heartbeat` no-op, and stop-on-disconnect in `main_logic`. |
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

## Rollback

To restore the original interface as the default, revert the `index()` route in
`server/app.py` to serve `dist/index.html`. The safety additions in `webServer.py`
are independent and can stay.
