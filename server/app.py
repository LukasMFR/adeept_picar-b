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
    'invertLEDs': False,
}
_ALLOWED_BOOL_KEYS = ('invertThrottle', 'invertSteering', 'invertLEDs')
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


