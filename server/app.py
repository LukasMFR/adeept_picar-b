#!/usr/bin/env python
from importlib import import_module
import os
import json
from flask import Flask, render_template, Response, send_from_directory, request, jsonify
from flask_cors import *
# import camera driver

from camera_opencv import Camera
import threading

# Raspberry Pi camera module (requires picamera package)
# from camera_pi import Camera

app = Flask(__name__)
CORS(app, supports_credentials=True)
camera = Camera()

def gen(camera):
    """Video streaming generator function."""
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

dir_path = os.path.dirname(os.path.realpath(__file__))

# ---------------------------------------------------------------------------
# Shared UI settings (server-side JSON config so every phone/computer agrees).
# Only these keys are accepted from clients and are always coerced to booleans;
# unknown keys are ignored, so a malformed or hostile body cannot inject state.
# ---------------------------------------------------------------------------
SETTINGS_FILE = os.path.join(dir_path, 'robot_settings.json')
SETTINGS_MAX_BODY = 4096                      # bytes; the payload is tiny
DEFAULT_SETTINGS = {
    'version': 1,
    'invertThrottle': False,
    'invertSteering': False,
    'invertLEDs': False,           # swap forward/reverse LED colour
    'invertTurnSignals': False,    # swap left/right turn-signal LEDs
}
_ALLOWED_BOOL_KEYS = ('invertThrottle', 'invertSteering', 'invertLEDs', 'invertTurnSignals')
_settings_lock = threading.Lock()
_settings_cache = None                         # in-process cache; webServer.py reads this


def read_settings():
    """Return the stored settings merged over defaults (safe if file missing)."""
    data = {}
    try:
        with open(SETTINGS_FILE, 'r') as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data = loaded
    except (FileNotFoundError, ValueError, OSError):
        data = {}
    merged = dict(DEFAULT_SETTINGS)
    for key in _ALLOWED_BOOL_KEYS:
        if key in data:
            merged[key] = bool(data[key])
    return merged


def get_current_settings():
    """Fast, cached access for the control loop (avoids a file read per command)."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = read_settings()
    return _settings_cache


def write_settings(new_values):
    """Validate, merge and atomically persist settings; returns the saved dict."""
    global _settings_cache
    with _settings_lock:
        current = read_settings()
        for key in _ALLOWED_BOOL_KEYS:
            if key in new_values:
                current[key] = bool(new_values[key])
        tmp = SETTINGS_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(current, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)        # atomic swap, no partial writes
        _settings_cache = current             # keep the cache in sync for the control loop
    return current


@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(read_settings())


@app.route('/api/settings', methods=['POST'])
def post_settings():
    if request.content_length is not None and request.content_length > SETTINGS_MAX_BODY:
        return jsonify({'error': 'payload too large'}), 413
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'expected a JSON object'}), 400
    return jsonify(write_settings(data))


# ---------------------------------------------------------------------------
# Servo calibration (server-side JSON so the centre / min / max are shared by
# every device and applied on the robot itself). Only channels 0, 1, 2 are
# physical servos; each has a centre plus a safe travel range. Every value is
# clamped to the PCA9685 range the drivers use, so a malformed or hostile
# request can never push a servo past its mechanical limits. webServer.py reads
# get_current_servo_calibration() at start-up and registers a callback via
# register_servo_apply() so a save from the UI is applied to the live servos.
# ---------------------------------------------------------------------------
SERVO_CAL_FILE = os.path.join(dir_path, 'robot_servo_calibration.json')
SERVO_CAL_MAX_BODY = 4096                      # bytes; the payload is tiny
SERVO_CAL_VERSION = 1
SERVO_CHANNELS = (0, 1, 2)
SERVO_BOUND_MIN = 100                          # matches RPIservo ctrlRangeMin
SERVO_BOUND_MAX = 560                          # matches RPIservo ctrlRangeMax
SERVO_DEFAULT_CENTER = 300                     # the official Adeept safe centre
DEFAULT_SERVO = {'center': SERVO_DEFAULT_CENTER, 'min': SERVO_BOUND_MIN, 'max': SERVO_BOUND_MAX}

_servo_cal_lock = threading.Lock()
_servo_cal_cache = None                         # in-process cache; webServer.py reads this
_servo_apply_cb = None                          # webServer.py registers a live-apply hook


def _clamp_int(value, lo, hi, fallback):
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return fallback
    return max(lo, min(hi, n))


def _coerce_servo(raw, base):
    """Merge raw {center, min, max} over base, clamped to hardware-safe bounds.

    Accepts a dict, or a bare number treated as the centre. Guarantees
    min <= max and min <= center <= max on the way out.
    """
    out = dict(base)
    if isinstance(raw, (int, float)):
        raw = {'center': raw}
    if isinstance(raw, dict):
        for key in ('center', 'min', 'max'):
            if key in raw:
                out[key] = _clamp_int(raw[key], SERVO_BOUND_MIN, SERVO_BOUND_MAX, out[key])
    out['min'] = _clamp_int(out['min'], SERVO_BOUND_MIN, SERVO_BOUND_MAX, SERVO_BOUND_MIN)
    out['max'] = _clamp_int(out['max'], SERVO_BOUND_MIN, SERVO_BOUND_MAX, SERVO_BOUND_MAX)
    if out['min'] > out['max']:
        out['min'], out['max'] = out['max'], out['min']
    out['center'] = max(out['min'], min(out['max'], out['center']))
    return out


def _channel_raw(container, ch):
    """Return one channel's raw values from a {"0": {...}} or {"0": 275} map."""
    if not isinstance(container, dict):
        return None
    for key in (str(ch), ch):
        if key in container:
            return container[key]
    return None


def _merge_servo_calibration(data):
    """Build the full {version, servos:{...}} structure from safe defaults
    (centre 300) overlaid with the stored file or an incoming POST body."""
    servos_in = {}
    if isinstance(data, dict):
        servos_in = data.get('servos') if isinstance(data.get('servos'), dict) else data
    result = {'version': SERVO_CAL_VERSION, 'servos': {}}
    for ch in SERVO_CHANNELS:
        raw = _channel_raw(servos_in, ch)
        if raw is None and isinstance(data, dict):
            raw = _channel_raw(data, ch)
        result['servos'][str(ch)] = _coerce_servo(raw, DEFAULT_SERVO)
    return result


def _load_json_file(path):
    try:
        with open(path, 'r') as f:
            loaded = json.load(f)
        return loaded if isinstance(loaded, (dict, list)) else None
    except (FileNotFoundError, ValueError, OSError):
        return None


def read_servo_calibration():
    """Stored calibration merged over safe defaults. The only source of truth is
    SERVO_CAL_FILE; if it does not exist yet, every servo defaults to centre 300.
    The file is created on the first save from the UI."""
    data = _load_json_file(SERVO_CAL_FILE)
    return _merge_servo_calibration(data)


def get_current_servo_calibration():
    """Fast, cached access for webServer.py (avoids a file read per use)."""
    global _servo_cal_cache
    if _servo_cal_cache is None:
        _servo_cal_cache = read_servo_calibration()
    return _servo_cal_cache


def register_servo_apply(callback):
    """webServer.py registers here so a save is pushed to the live servos."""
    global _servo_apply_cb
    _servo_apply_cb = callback


def write_servo_calibration(new_values):
    """Validate, merge and atomically persist calibration; returns the saved
    dict and notifies webServer.py so the change applies without a restart."""
    global _servo_cal_cache
    with _servo_cal_lock:
        current = read_servo_calibration()
        incoming = new_values.get('servos') if isinstance(new_values.get('servos'), dict) else new_values
        for ch in SERVO_CHANNELS:
            raw = _channel_raw(incoming, ch)
            if raw is None:
                continue
            current['servos'][str(ch)] = _coerce_servo(raw, current['servos'][str(ch)])
        current['version'] = SERVO_CAL_VERSION
        tmp = SERVO_CAL_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(current, f, indent=2)
        os.replace(tmp, SERVO_CAL_FILE)           # atomic swap, no partial writes
        _servo_cal_cache = current
    cb = _servo_apply_cb
    if cb is not None:
        try:
            cb(current)
        except Exception:
            pass
    return current


@app.route('/api/servo_calibration', methods=['GET'])
def get_servo_calibration():
    return jsonify(read_servo_calibration())


@app.route('/api/servo_calibration', methods=['POST'])
def post_servo_calibration():
    if request.content_length is not None and request.content_length > SERVO_CAL_MAX_BODY:
        return jsonify({'error': 'payload too large'}), 413
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'expected a JSON object'}), 400
    return jsonify(write_servo_calibration(data))


@app.route('/api/img/<path:filename>')
def sendimg(filename):
    return send_from_directory(dir_path+'/dist/img', filename)

@app.route('/js/<path:filename>')
def sendjs(filename):
    return send_from_directory(dir_path+'/dist/js', filename)

@app.route('/css/<path:filename>')
def sendcss(filename):
    return send_from_directory(dir_path+'/dist/css', filename)

@app.route('/api/img/icon/<path:filename>')
def sendicon(filename):
    return send_from_directory(dir_path+'/dist/img/icon', filename)

@app.route('/fonts/<path:filename>')
def sendfonts(filename):
    return send_from_directory(dir_path+'/dist/fonts', filename)

@app.route('/legacy')
def legacy():
    """Original Vue interface, kept intact for fallback."""
    return send_from_directory(dir_path+'/dist', 'index.html')

@app.route('/<path:filename>')
def sendgen(filename):
    return send_from_directory(dir_path+'/dist', filename)

@app.route('/')
def index():
    """Modern control console (server/ui/index.html)."""
    return send_from_directory(dir_path+'/ui', 'index.html')

class webapp:
    def __init__(self):
        self.camera = camera

    def modeselect(self, modeInput):
        Camera.modeSelect = modeInput

    def colorFindSet(self, H, S, V):
        camera.colorFindSet(H, S, V)

    def thread(self):
        app.run(host='0.0.0.0', threaded=True)

    def startthread(self):
        fps_threading=threading.Thread(target=self.thread)         #Define a thread for FPV and OpenCV
        fps_threading.setDaemon(False)                             #'True' means it is a front thread,it would close when the mainloop() closes
        fps_threading.start()                                     #Thread starts


