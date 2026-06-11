#!/usr/bin/env python3
"""
Noisy Web UI - Flask-Dashboard (laeuft als Thread im Orchestrator)

Teilt sich die RuntimeConfig-Instanz mit Orchestrator und Renderer:
Slider-Aenderungen landen direkt im gemeinsamen Objekt, der Renderer
liest sie beim naechsten Frame. Keine zusaetzliche IPC noetig.

Routen:
  GET  /                Dashboard
  POST /update_param    Live-Slider (brightness, speed) -> sofort + persist
  POST /save            Nacht-Fenster + Auto-Dim persistieren
  GET  /models          Liste der registrierten Modelle (JSON)
  POST /download        Modell-URL validieren, laden, entpacken, registrieren
  POST /select_model    Aktives Modell setzen -> orch.switch_model()

Erwartete Orchestrator-Schnittstelle:
  orch.switch_model()   Startet den Audio-Subprocess mit dem aktiven Modell neu.
"""

import os
import shutil
import logging
import tarfile
import threading
import urllib.request
from urllib.parse import urlparse

from flask import Flask, request, jsonify, render_template_string

from noisy_config import MODEL_DIR

log = logging.getLogger('noisy-web')

# Basis-Verzeichnis fuer Modelle (Elternverzeichnis des Default-Modells)
MODELS_BASE_DIR = os.path.dirname(MODEL_DIR)

# Maximale Download-Groesse (Schutz vor Endlos-Downloads): 500 MB
MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024


# ============================================================
# HTML Dashboard
# ============================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Noisy Control Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --bg: #0f0f0f;
            --card: #1a1a1a;
            --accent: #ffb74d;
            --text: #e0e0e0;
            --subtext: #888;
        }
        body {
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }
        .card {
            background: var(--card);
            padding: 35px;
            border-radius: 24px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.8);
            width: 100%;
            max-width: 460px;
            border: 1px solid #333;
            margin-bottom: 20px;
        }
        h1 { color: var(--accent); margin: 0 0 10px 0; font-size: 2rem; }
        h2 { color: var(--accent); margin: 0 0 20px 0; font-size: 1.2rem; }
        p { color: var(--subtext); margin-bottom: 25px; }
        .control-group { margin-bottom: 25px; }
        label { display: block; margin-bottom: 12px; font-weight: bold; color: #bbb; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;}
        input[type="range"] { width: 100%; accent-color: var(--accent); cursor: pointer; }
        .val-display { float: right; color: var(--accent); font-family: monospace; font-size: 1.1rem; }
        input[type="text"], input[type="time"], select {
            width: 100%;
            padding: 12px;
            background: #2a2a2a;
            border: 1px solid #444;
            color: white;
            border-radius: 8px;
            box-sizing: border-box;
            margin-bottom: 8px;
        }
        .row { display: flex; gap: 10px; }
        .row > * { flex: 1; }
        .toggle-row { display: flex; align-items: center; justify-content: space-between; }
        .toggle-row label { margin: 0; }
        input[type="checkbox"] { width: 22px; height: 22px; accent-color: var(--accent); cursor: pointer; }
        button {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s ease;
            margin-top: 6px;
        }
        .btn-save { background: var(--accent); color: #000; }
        .btn-secondary { background: #444; color: white; }
        button:hover { opacity: 0.9; transform: translateY(-2px); }
        button:active { transform: scale(0.98); }
        hr { border: 0; border-top: 1px solid #333; margin: 28px 0; }
        .status { font-size: 0.82em; color: var(--subtext); margin-top: 18px; text-align: center; min-height: 18px; }
        .model-list { list-style: none; padding: 0; margin: 0 0 18px 0; }
        .model-list li { padding: 10px 12px; background: #222; border-radius: 8px; margin-bottom: 6px; font-size: 0.9rem; display: flex; justify-content: space-between; align-items: center; }
        .badge { font-size: 0.7rem; padding: 2px 8px; border-radius: 6px; }
        .badge-active { background: var(--accent); color: #000; }
        .badge-builtin { background: #355; color: #cfe; }
        .badge-missing { background: #533; color: #fcc; }
    </style>
</head>
<body>
    <h1>Noisy</h1>
    <p>Atmosphaerisches Dashboard fuer deinen Mochi-Blob.</p>

    <!-- ANZEIGE -->
    <div class="card">
        <h2>Anzeige</h2>

        <div class="control-group">
            <label>Tag Helligkeit <span id="day_val" class="val-display">{{ disp.brightness_day }}</span></label>
            <input type="range" id="brightness_day" min="0" max="255" value="{{ disp.brightness_day }}">
        </div>

        <div class="control-group">
            <label>Nacht Helligkeit <span id="night_val" class="val-display">{{ disp.brightness_night }}</span></label>
            <input type="range" id="brightness_night" min="0" max="255" value="{{ disp.brightness_night }}">
        </div>

        <div class="control-group">
            <label>Animation Speed <span id="speed_val" class="val-display">{{ vis.animation_speed_multiplier }}</span></label>
            <input type="range" id="speed_mult" min="0.1" max="3.0" step="0.1" value="{{ vis.animation_speed_multiplier }}">
        </div>

        <hr>

        <div class="control-group toggle-row">
            <label>Auto-Dim (Nachtmodus)</label>
            <input type="checkbox" id="auto_dim" {% if disp.auto_dim %}checked{% endif %}>
        </div>

        <div class="control-group">
            <label>Nachtmodus Fenster</label>
            <div class="row">
                <input type="time" id="night_start" value="{{ disp.night_mode_start }}">
                <input type="time" id="night_end" value="{{ disp.night_mode_end }}">
            </div>
        </div>

        <button class="btn-save" onclick="saveSettings()">EINSTELLUNGEN SPEICHERN</button>
        <div class="status" id="status_display">Ready.</div>
    </div>

    <!-- MODELLE -->
    <div class="card">
        <h2>KI-Modell</h2>

        <div class="control-group">
            <label>Verfuegbare Modelle</label>
            <ul class="model-list" id="model_list"></ul>
            <select id="model_select"></select>
            <button class="btn-secondary" onclick="selectModel()">AKTIVES MODELL SETZEN</button>
        </div>

        <hr>

        <div class="control-group">
            <label>Neues Modell laden (.tar.bz2)</label>
            <input type="text" id="model_url" placeholder="https://.../sherpa-onnx-...tar.bz2">
            <button class="btn-secondary" onclick="downloadModel()">VALIDIEREN &amp; LADEN</button>
        </div>
        <div class="status" id="status_model">Ready.</div>
    </div>

    <script>
        // ---- Live Slider Updates ----
        const liveSliders = ['brightness_day', 'brightness_night', 'speed_mult'];
        liveSliders.forEach(id => {
            const valMap = { brightness_day: 'day_val', brightness_night: 'night_val', speed_mult: 'speed_val' };
            document.getElementById(id).oninput = function() {
                document.getElementById(valMap[id]).innerText = this.value;
                fetch('/update_param', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id: id, value: parseFloat(this.value) })
                });
            };
        });

        // ---- Persistente Einstellungen ----
        async function saveSettings() {
            const data = {
                auto_dim: document.getElementById('auto_dim').checked,
                night_mode_start: document.getElementById('night_start').value,
                night_mode_end: document.getElementById('night_end').value
            };
            const res = await fetch('/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            document.getElementById('status_display').innerText =
                res.ok ? "Gespeichert." : "Fehler beim Speichern.";
        }

        // ---- Modelle laden / rendern ----
        async function loadModels() {
            try {
                const res = await fetch('/models');
                const models = await res.json();
                const list = document.getElementById('model_list');
                const sel = document.getElementById('model_select');
                list.innerHTML = '';
                sel.innerHTML = '';
                models.forEach(m => {
                    let badges = '';
                    if (m.active)  badges += '<span class="badge badge-active">aktiv</span> ';
                    if (m.builtin) badges += '<span class="badge badge-builtin">builtin</span> ';
                    if (!m.ready)  badges += '<span class="badge badge-missing">fehlt</span>';
                    const li = document.createElement('li');
                    li.innerHTML = '<span>' + m.name + '</span><span>' + badges + '</span>';
                    list.appendChild(li);

                    const opt = document.createElement('option');
                    opt.value = m.key;
                    opt.textContent = m.name + (m.ready ? '' : ' (fehlt)');
                    if (m.active) opt.selected = true;
                    sel.appendChild(opt);
                });
            } catch (e) {
                document.getElementById('status_model').innerText = "Modell-Liste nicht ladbar.";
            }
        }

        async function selectModel() {
            const key = document.getElementById('model_select').value;
            document.getElementById('status_model').innerText = "Wechsle Modell...";
            const res = await fetch('/select_model', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ key: key })
            });
            const r = await res.json();
            document.getElementById('status_model').innerText = r.message;
            loadModels();
        }

        async function downloadModel() {
            const url = document.getElementById('model_url').value;
            document.getElementById('status_model').innerText = "Lade und validiere... (kann dauern)";
            try {
                const res = await fetch('/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: url })
                });
                const r = await res.json();
                document.getElementById('status_model').innerText = r.message;
                if (r.success) {
                    document.getElementById('model_url').value = '';
                    loadModels();
                }
            } catch(e) {
                document.getElementById('status_model').innerText = "Fehler bei der Anfrage.";
            }
        }

        loadModels();
    </script>
</body>
</html>
"""


# ============================================================
# Modell-Download (sicher)
# ============================================================
def _safe_extract(tar, dest):
    """Entpackt ein Tar-Archiv und verhindert Path-Traversal (../)."""
    dest_abs = os.path.abspath(dest)
    for member in tar.getmembers():
        member_path = os.path.abspath(os.path.join(dest, member.name))
        if member_path != dest_abs and not member_path.startswith(dest_abs + os.sep):
            raise ValueError("Unsicherer Pfad im Archiv: %s" % member.name)
    tar.extractall(dest)


def download_and_register_model(url, rt):
    """
    Laedt ein Sherpa-Tagging-Modell (.tar.bz2), validiert es und
    registriert es in der RuntimeConfig. Gibt {success, message} zurueck.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return {"success": False, "message": "Nur http/https-URLs sind erlaubt."}
    if not url.endswith('.tar.bz2'):
        return {"success": False, "message": "Nur .tar.bz2 Sherpa-Archive werden unterstuetzt."}

    fname = os.path.basename(parsed.path)
    dirname = fname[:-len('.tar.bz2')]
    if not dirname:
        return {"success": False, "message": "URL enthaelt keinen gueltigen Dateinamen."}

    archive_path = os.path.join(MODELS_BASE_DIR, fname)
    extract_dir = os.path.join(MODELS_BASE_DIR, dirname)

    if rt.has_model(dirname):
        return {"success": False, "message": "Modell '%s' ist bereits registriert." % dirname}

    try:
        os.makedirs(MODELS_BASE_DIR, exist_ok=True)

        # Download (mit Groessen-Limit)
        req = urllib.request.Request(url, headers={'User-Agent': 'Noisy'})
        with urllib.request.urlopen(req, timeout=60) as resp, open(archive_path, 'wb') as f:
            downloaded = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Datei groesser als erlaubt (%d MB)."
                                     % (MAX_DOWNLOAD_BYTES // (1024 * 1024)))
                f.write(chunk)

        # Entpacken (path-traversal-sicher)
        with tarfile.open(archive_path, 'r:bz2') as tar:
            _safe_extract(tar, MODELS_BASE_DIR)
        os.remove(archive_path)

    except Exception as e:
        log.warning("Modell-Download fehlgeschlagen: %s", e)
        for path in (archive_path,):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        return {"success": False, "message": "Download/Entpacken fehlgeschlagen: %s" % e}

    # Validierung: Modell + Labels vorhanden?
    model_path = None
    for cand in ('model.int8.onnx', 'model.onnx'):
        candidate = os.path.join(extract_dir, cand)
        if os.path.exists(candidate):
            model_path = candidate
            break
    labels_path = os.path.join(extract_dir, 'class_labels_indices.csv')

    if not model_path or not os.path.exists(labels_path):
        shutil.rmtree(extract_dir, ignore_errors=True)
        return {"success": False,
                "message": "Archiv enthaelt kein gueltiges Sherpa-Tagging-Modell "
                           "(model.onnx + class_labels_indices.csv)."}

    rt.add_model(dirname, dirname, model_path, labels_path)
    log.info("Modell registriert: %s", dirname)
    return {"success": True, "message": "Modell '%s' geladen und registriert." % dirname}


# ============================================================
# Flask App Factory
# ============================================================
def create_app(orch, rt):
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template_string(
            HTML_TEMPLATE,
            disp=rt.get_display(),
            vis=rt.get_visuals(),
        )

    @app.route('/update_param', methods=['POST'])
    def update_param():
        data = request.get_json(silent=True) or {}
        pid = data.get('id')
        val = data.get('value')
        if pid == 'brightness_day':
            rt.set_brightness_day(val)
        elif pid == 'brightness_night':
            rt.set_brightness_night(val)
        elif pid == 'speed_mult':
            rt.set_speed(val)
        else:
            return jsonify(ok=False, message="Unbekannter Parameter."), 400
        return jsonify(ok=True)

    @app.route('/save', methods=['POST'])
    def save():
        data = request.get_json(silent=True) or {}
        if 'auto_dim' in data:
            rt.set_auto_dim(data.get('auto_dim'))
        start = data.get('night_mode_start')
        end = data.get('night_mode_end')
        if start is not None and end is not None:
            rt.set_night_window(start, end)
        return jsonify(ok=True)

    @app.route('/models')
    def models():
        return jsonify(rt.list_models())

    @app.route('/download', methods=['POST'])
    def download():
        data = request.get_json(silent=True) or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify(success=False, message="Keine URL angegeben.")
        return jsonify(download_and_register_model(url, rt))

    @app.route('/select_model', methods=['POST'])
    def select_model():
        data = request.get_json(silent=True) or {}
        key = data.get('key')
        if not key or not rt.has_model(key):
            return jsonify(ok=False, message="Modell nicht gefunden."), 404
        rt.set_active_model(key)
        try:
            orch.switch_model()
            return jsonify(ok=True, message="Modell aktiviert und Audio neu gestartet.")
        except Exception as e:
            log.error("Modellwechsel fehlgeschlagen: %s", e)
            return jsonify(ok=False, message="Modell gesetzt, Neustart fehlgeschlagen: %s" % e), 500

    return app


# ============================================================
# Web-UI Thread
# ============================================================
class WebUIThread(threading.Thread):
    """Startet das Flask-Dashboard als Daemon-Thread im Orchestrator."""

    def __init__(self, orchestrator, runtime_config, host='0.0.0.0', port=8080):
        super().__init__(daemon=True)
        self.orch = orchestrator
        self.rt = runtime_config
        self.host = host
        self.port = port

    def run(self):
        # Flask/Werkzeug-Logging daempfen (sonst spammt es das Noisy-Log)
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        try:
            app = create_app(self.orch, self.rt)
            log.info("Web-UI startet auf http://%s:%d", self.host, self.port)
            app.run(host=self.host, port=self.port,
                    threaded=True, use_reloader=False, debug=False)
        except Exception as e:
            log.error("Web-UI Thread abgestuerzt: %s", e)
