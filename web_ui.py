#!/usr/bin/env python3
"""
Noisy Web UI - Flask-Dashboard (laeuft als Thread im Orchestrator)

Teilt sich die RuntimeConfig-Instanz mit Orchestrator und Renderer:
Slider-Aenderungen landen direkt im gemeinsamen Objekt, der Renderer
liest sie beim naechsten Frame. Keine zusaetzliche IPC noetig.

Sicherheit (siehe noisy_auth.py / noisy_netsec.py):
  - Admin-Login auf ALLEN Routen (Session-Cookie, SameSite=Strict)
  - First-Login setzt das Passwort; "Passwort vergessen" (Reset-Phrase
    ins Passwort-Feld) loescht NUR das Passwort nach Countdown
  - /download SSRF-/Symlink-/Disk-gehaertet
  - HTTPS (Self-Signed) per Web-UI + CLI umschaltbar (greift nach Neustart)

Routen:
  GET  /                Dashboard (login noetig)
  GET/POST /setup       First-Login: Passwort setzen
  GET/POST /login       Login (Reset-Phrase -> Reset-Flow)
  GET  /logout          Abmelden
  POST /reset/confirm   Passwort-Reset bestaetigen
  GET/POST /change_password   Passwort aendern (login noetig)
  POST /update_param    Live-Slider (brightness, speed)
  POST /save            Nacht-Fenster + Auto-Dim persistieren
  GET  /models          Liste der registrierten Modelle (JSON)
  POST /download        Modell-URL validieren, laden, entpacken (gehaertet)
  POST /select_model    Aktives Modell setzen -> orch.switch_model()
  POST /toggle_https    HTTPS an/aus -> Service-Neustart
"""

import os
import time
import logging
import threading
import subprocess
from functools import wraps

from flask import (
    Flask, request, jsonify, session, redirect, url_for,
    render_template_string,
)

from noisy_config import (
    MODEL_DIR, WEB_HOST, WEB_PORT,
    TLS_CERT_FILE, TLS_KEY_FILE,
    RESET_COUNTDOWN_SECONDS,
)
from noisy_auth import AuthManager, is_reset_phrase
import noisy_netsec

log = logging.getLogger('noisy-web')

# Basis-Verzeichnis fuer Modelle (Elternverzeichnis des Default-Modells)
MODELS_BASE_DIR = os.path.dirname(MODEL_DIR)

SERVICE_NAME = 'noisy.service'


# ============================================================
# Service-Neustart (verzoegert, damit die HTTP-Antwort noch rausgeht)
# ============================================================
def schedule_service_restart(delay=1.5):
    """Startet den noisy.service nach kurzer Verzoegerung neu (Daemon-Thread)."""
    def _restart():
        time.sleep(delay)
        try:
            subprocess.Popen(['sudo', 'systemctl', 'restart', SERVICE_NAME])
        except Exception as e:
            log.error("Service-Neustart fehlgeschlagen: %s", e)
    threading.Thread(target=_restart, daemon=True).start()


# ============================================================
# Aufraeum-Helfer
# ============================================================
def _cleanup(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _cleanup_dir(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


# ============================================================
# Modell-Download (gehaertet, nutzt noisy_netsec)
# ============================================================
def download_and_register_model(url, rt):
    """
    Laedt ein Sherpa-Tagging-Modell (.tar.bz2), validiert es SSRF-/Symlink-
    sicher und registriert es in der RuntimeConfig. Gibt {success, message}.
    """
    if not url:
        return {"success": False, "message": "Keine URL angegeben."}
    if not url.endswith('.tar.bz2'):
        return {"success": False, "message": "Nur .tar.bz2 Sherpa-Archive werden unterstuetzt."}

    from urllib.parse import urlparse
    fname = os.path.basename(urlparse(url).path)
    dirname = fname[:-len('.tar.bz2')] if fname.endswith('.tar.bz2') else ''
    if not dirname:
        return {"success": False, "message": "URL enthaelt keinen gueltigen Dateinamen."}

    archive_path = os.path.join(MODELS_BASE_DIR, fname)
    extract_dir = os.path.join(MODELS_BASE_DIR, dirname)

    if rt.has_model(dirname):
        return {"success": False, "message": "Modell '%s' ist bereits registriert." % dirname}

    try:
        # URL pruefen (Schema, Endung, Allowlist, oeffentliche IP)
        noisy_netsec.validate_download_url(url)
        os.makedirs(MODELS_BASE_DIR, exist_ok=True)

        # Download (Redirects Hop-fuer-Hop validiert, Groesse/Disk gecheckt)
        noisy_netsec.download_to_file(url, archive_path)

        # Entpacken (Symlink-/Traversal-fest via tar-Filter 'data')
        noisy_netsec.safe_extract_bz2(archive_path, MODELS_BASE_DIR)
        os.remove(archive_path)

    except noisy_netsec.SecurityError as e:
        _cleanup(archive_path)
        _cleanup_dir(extract_dir)
        log.warning("Download abgelehnt (Security): %s", e)
        return {"success": False, "message": "Abgelehnt: %s" % e}
    except Exception as e:
        _cleanup(archive_path)
        _cleanup_dir(extract_dir)
        log.warning("Modell-Download fehlgeschlagen: %s", e)
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
        _cleanup_dir(extract_dir)
        return {"success": False,
                "message": "Archiv enthaelt kein gueltiges Sherpa-Tagging-Modell "
                           "(model.onnx + class_labels_indices.csv)."}

    rt.add_model(dirname, dirname, model_path, labels_path)
    log.info("Modell registriert: %s", dirname)
    return {"success": True, "message": "Modell '%s' geladen und registriert." % dirname}


# ============================================================
# HTML Templates
# ============================================================
_STYLE = """
<style>
  :root { --bg:#0f0f0f; --card:#1a1a1a; --accent:#ffb74d; --text:#e0e0e0; --subtext:#888; }
  body { font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif; background:var(--bg);
         color:var(--text); margin:0; display:flex; flex-direction:column; align-items:center; padding:40px 20px; }
  .card { background:var(--card); padding:35px; border-radius:24px; box-shadow:0 15px 40px rgba(0,0,0,.8);
          width:100%; max-width:460px; border:1px solid #333; margin-bottom:20px; box-sizing:border-box; }
  h1 { color:var(--accent); margin:0 0 10px 0; font-size:2rem; }
  h2 { color:var(--accent); margin:0 0 20px 0; font-size:1.2rem; }
  p { color:var(--subtext); margin-bottom:25px; }
  label { display:block; margin-bottom:12px; font-weight:bold; color:#bbb; font-size:.85rem; text-transform:uppercase; letter-spacing:1px; }
  input[type="range"] { width:100%; accent-color:var(--accent); cursor:pointer; }
  .val-display { float:right; color:var(--accent); font-family:monospace; font-size:1.1rem; }
  input[type="text"],input[type="time"],input[type="password"],select {
    width:100%; padding:12px; background:#2a2a2a; border:1px solid #444; color:#fff;
    border-radius:8px; box-sizing:border-box; margin-bottom:8px; }
  .row { display:flex; gap:10px; } .row > * { flex:1; }
  .control-group { margin-bottom:25px; }
  .toggle-row { display:flex; align-items:center; justify-content:space-between; }
  .toggle-row label { margin:0; }
  input[type="checkbox"] { width:22px; height:22px; accent-color:var(--accent); cursor:pointer; }
  button { width:100%; padding:14px; border:none; border-radius:12px; font-weight:bold; font-size:.95rem;
           cursor:pointer; transition:all .2s ease; margin-top:6px; }
  .btn-save { background:var(--accent); color:#000; }
  .btn-secondary { background:#444; color:#fff; }
  .btn-danger { background:#7a2b2b; color:#fff; }
  button:hover { opacity:.9; transform:translateY(-2px); } button:active { transform:scale(.98); }
  hr { border:0; border-top:1px solid #333; margin:28px 0; }
  .status { font-size:.82em; color:var(--subtext); margin-top:18px; text-align:center; min-height:18px; }
  .err { color:#ff8a80; font-size:.9em; margin-bottom:14px; min-height:16px; }
  .muted { color:var(--subtext); font-size:.82em; }
  a { color:var(--accent); }
  .model-list { list-style:none; padding:0; margin:0 0 18px 0; }
  .model-list li { padding:10px 12px; background:#222; border-radius:8px; margin-bottom:6px; font-size:.9rem; display:flex; justify-content:space-between; align-items:center; }
  .badge { font-size:.7rem; padding:2px 8px; border-radius:6px; }
  .badge-active { background:var(--accent); color:#000; }
  .badge-builtin { background:#355; color:#cfe; }
  .badge-missing { background:#533; color:#fcc; }
</style>
"""

LOGIN_TEMPLATE = """<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<title>Noisy Login</title><meta name="viewport" content="width=device-width, initial-scale=1">__STYLE__</head>
<body><h1>Noisy</h1><div class="card"><h2>Anmelden</h2>
<div class="err">{{ error }}</div>
<form method="POST" action="{{ url_for('login') }}">
  <label>Benutzer</label><input type="text" name="username" value="admin" autocomplete="username">
  <label>Passwort</label><input type="password" name="password" autocomplete="current-password" autofocus>
  <button class="btn-save" type="submit">EINLOGGEN</button>
</form>
<p class="muted" style="margin-top:18px;">Passwort vergessen? Gib eine der Reset-Phrasen ins Passwort-Feld ein
(z.&nbsp;B. <code>forgot password</code>) und bestaetige den Reset.</p>
</div></body></html>"""

SETUP_TEMPLATE = """<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<title>Noisy Setup</title><meta name="viewport" content="width=device-width, initial-scale=1">__STYLE__</head>
<body><h1>Noisy</h1><div class="card"><h2>Erst-Einrichtung</h2>
<p>Lege ein Admin-Passwort fest. Es schuetzt das Dashboard im Netzwerk.</p>
<div class="err">{{ error }}</div>
<form method="POST" action="{{ url_for('setup') }}">
  <label>Neues Passwort</label><input type="password" name="password" autocomplete="new-password" autofocus>
  <label>Passwort wiederholen</label><input type="password" name="password2" autocomplete="new-password">
  <button class="btn-save" type="submit">PASSWORT SETZEN</button>
</form></div></body></html>"""

CHANGE_PW_TEMPLATE = """<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<title>Noisy - Passwort aendern</title><meta name="viewport" content="width=device-width, initial-scale=1">__STYLE__</head>
<body><h1>Noisy</h1><div class="card"><h2>Passwort aendern</h2>
<div class="err">{{ error }}</div>
<form method="POST" action="{{ url_for('change_password') }}">
  <label>Aktuelles Passwort</label><input type="password" name="old" autocomplete="current-password" autofocus>
  <label>Neues Passwort</label><input type="password" name="new" autocomplete="new-password">
  <label>Neues Passwort wiederholen</label><input type="password" name="new2" autocomplete="new-password">
  <button class="btn-save" type="submit">AENDERN</button>
</form><p style="margin-top:16px;"><a href="{{ url_for('index') }}">Zurueck</a></p></div></body></html>"""

RESET_CONFIRM_TEMPLATE = """<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<title>Noisy - Passwort zuruecksetzen</title><meta name="viewport" content="width=device-width, initial-scale=1">__STYLE__</head>
<body><h1>Noisy</h1><div class="card"><h2>Passwort zuruecksetzen?</h2>
<p>Es wird <b>nur das Passwort</b> geloescht. Personality, Kalibrierung, Modelle
und Einstellungen bleiben erhalten. Danach startet Noisy neu und du legst ein
neues Passwort fest.</p>
<form method="POST" action="{{ url_for('reset_confirm') }}">
  <button class="btn-danger" type="submit">JA, PASSWORT ZURUECKSETZEN</button>
</form>
<p style="margin-top:16px;"><a href="{{ url_for('login') }}">Abbrechen</a></p></div></body></html>"""

RESET_DONE_TEMPLATE = """<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<title>Noisy - Reset</title><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{{ wait_plus }}; url={{ url_for('index') }}">__STYLE__</head>
<body><h1>Noisy</h1><div class="card"><h2>Passwort wird zurueckgesetzt</h2>
<p>Reset in <b>{{ countdown }}</b> Sekunden, danach startet Noisy neu.
Auf dem Display erscheint eine Warnung. Diese Seite leitet anschliessend
automatisch zur Neu-Einrichtung weiter.</p>
<p class="muted">Falls nicht automatisch: nach dem Neustart einfach die Adresse neu laden.</p>
</div></body></html>"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8">
<title>Noisy Control Panel</title><meta name="viewport" content="width=device-width, initial-scale=1">__STYLE__</head>
<body>
<h1>Noisy</h1>
<p>Atmosphaerisches Dashboard fuer deinen Mochi-Blob.</p>

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
    <input type="text" id="model_url" placeholder="https://github.com/k2-fsa/...tar.bz2">
    <button class="btn-secondary" onclick="downloadModel()">VALIDIEREN &amp; LADEN</button>
    <p class="muted">Erlaubt sind nur Modell-Hosts der Allowlist (GitHub-Releases, Hugging Face).</p>
  </div>
  <div class="status" id="status_model">Ready.</div>
</div>

<div class="card">
  <h2>System</h2>
  <div class="control-group toggle-row">
    <label>HTTPS (Self-Signed)</label>
    <input type="checkbox" id="https_toggle" {% if srv.https %}checked{% endif %}>
  </div>
  <p class="muted">Beim Umschalten startet Noisy neu. Danach unter
  {{ 'http' if srv.https else 'https' }}://&lt;adresse&gt;:{{ port }} neu verbinden.</p>
  <button class="btn-secondary" onclick="applyHttps()">HTTPS ANWENDEN (NEUSTART)</button>
  <div class="status" id="status_system">Ready.</div>
  <hr>
  <button class="btn-secondary" onclick="location.href='{{ url_for('change_password') }}'">PASSWORT AENDERN</button>
  <button class="btn-secondary" onclick="location.href='{{ url_for('logout') }}'">ABMELDEN</button>
</div>

<script>
  const liveSliders = ['brightness_day','brightness_night','speed_mult'];
  liveSliders.forEach(id => {
    const valMap = { brightness_day:'day_val', brightness_night:'night_val', speed_mult:'speed_val' };
    document.getElementById(id).oninput = function() {
      document.getElementById(valMap[id]).innerText = this.value;
      fetch('/update_param', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ id:id, value: parseFloat(this.value) }) });
    };
  });

  async function saveSettings() {
    const data = { auto_dim: document.getElementById('auto_dim').checked,
      night_mode_start: document.getElementById('night_start').value,
      night_mode_end: document.getElementById('night_end').value };
    const res = await fetch('/save', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(data) });
    document.getElementById('status_display').innerText = res.ok ? "Gespeichert." : "Fehler beim Speichern.";
  }

  async function loadModels() {
    try {
      const res = await fetch('/models');
      const models = await res.json();
      const list = document.getElementById('model_list'); const sel = document.getElementById('model_select');
      list.innerHTML=''; sel.innerHTML='';
      models.forEach(m => {
        let badges='';
        if (m.active) badges += '<span class="badge badge-active">aktiv</span> ';
        if (m.builtin) badges += '<span class="badge badge-builtin">builtin</span> ';
        if (!m.ready) badges += '<span class="badge badge-missing">fehlt</span>';
        const li=document.createElement('li');
        li.innerHTML='<span>'+m.name+'</span><span>'+badges+'</span>'; list.appendChild(li);
        const opt=document.createElement('option'); opt.value=m.key;
        opt.textContent=m.name+(m.ready?'':' (fehlt)'); if (m.active) opt.selected=true; sel.appendChild(opt);
      });
    } catch(e) { document.getElementById('status_model').innerText="Modell-Liste nicht ladbar."; }
  }

  async function selectModel() {
    const key=document.getElementById('model_select').value;
    document.getElementById('status_model').innerText="Wechsle Modell...";
    const res=await fetch('/select_model',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({key:key})});
    const r=await res.json(); document.getElementById('status_model').innerText=r.message; loadModels();
  }

  async function downloadModel() {
    const url=document.getElementById('model_url').value;
    document.getElementById('status_model').innerText="Lade und validiere... (kann dauern)";
    try {
      const res=await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({url:url})});
      const r=await res.json(); document.getElementById('status_model').innerText=r.message;
      if (r.success) { document.getElementById('model_url').value=''; loadModels(); }
    } catch(e) { document.getElementById('status_model').innerText="Fehler bei der Anfrage."; }
  }

  async function applyHttps() {
    const on=document.getElementById('https_toggle').checked;
    document.getElementById('status_system').innerText="Speichere & starte neu...";
    try {
      const res=await fetch('/toggle_https',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({https:on})});
      const r=await res.json(); document.getElementById('status_system').innerText=r.message;
    } catch(e) { document.getElementById('status_system').innerText="Noisy startet neu - bitte neu verbinden."; }
  }

  loadModels();
</script>
</body></html>"""


def _t(tpl):
    """Bindet das gemeinsame Stylesheet in ein Template ein."""
    return tpl.replace('__STYLE__', _STYLE)


# ============================================================
# Flask App Factory
# ============================================================
def create_app(orch, rt, auth):
    app = Flask(__name__)
    app.secret_key = auth.get_secret()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Strict',
        SESSION_COOKIE_SECURE=bool(rt.get_https()),
    )

    # ---- Auth-Helfer ----
    def _ip():
        return request.remote_addr or 'unknown'

    def api_login_required(f):
        @wraps(f)
        def wrapper(*a, **k):
            if not session.get('authed'):
                return jsonify(ok=False, message="Nicht eingeloggt."), 401
            return f(*a, **k)
        return wrapper

    def page_login_required(f):
        @wraps(f)
        def wrapper(*a, **k):
            if not auth.is_password_set():
                return redirect(url_for('setup'))
            if not session.get('authed'):
                return redirect(url_for('login'))
            return f(*a, **k)
        return wrapper

    # ---- Seiten ----
    @app.route('/')
    @page_login_required
    def index():
        return render_template_string(
            _t(DASHBOARD_TEMPLATE),
            disp=rt.get_display(), vis=rt.get_visuals(),
            srv=rt.get_server(), port=WEB_PORT,
        )

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        if auth.is_password_set():
            # Schon eingerichtet -> nur ueber Login bzw. /change_password
            return redirect(url_for('index') if session.get('authed') else url_for('login'))
        error = ""
        if request.method == 'POST':
            pw = request.form.get('password', '')
            pw2 = request.form.get('password2', '')
            if pw != pw2:
                error = "Passwoerter stimmen nicht ueberein."
            else:
                ok, msg = auth.set_password(pw)
                if ok:
                    session['authed'] = True
                    return redirect(url_for('index'))
                error = msg
        return render_template_string(_t(SETUP_TEMPLATE), error=error)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if not auth.is_password_set():
            return redirect(url_for('setup'))
        if session.get('authed'):
            return redirect(url_for('index'))
        error = ""
        if request.method == 'POST':
            pw = request.form.get('password', '')
            # "Passwort vergessen": Reset-Phrase im Passwort-Feld
            if is_reset_phrase(pw):
                return render_template_string(_t(RESET_CONFIRM_TEMPLATE))
            ip = _ip()
            if auth.is_locked(ip):
                error = ("Zu viele Fehlversuche. Gesperrt fuer %d Sekunden."
                         % auth.seconds_until_unlock(ip))
            elif auth.verify_password(pw):
                auth.register_success(ip)
                session['authed'] = True
                return redirect(url_for('index'))
            else:
                auth.register_failure(ip)
                error = "Falsches Passwort."
        return render_template_string(_t(LOGIN_TEMPLATE), error=error)

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/change_password', methods=['GET', 'POST'])
    @page_login_required
    def change_password():
        error = ""
        if request.method == 'POST':
            old = request.form.get('old', '')
            new = request.form.get('new', '')
            new2 = request.form.get('new2', '')
            if not auth.verify_password(old):
                error = "Aktuelles Passwort falsch."
            elif new != new2:
                error = "Neue Passwoerter stimmen nicht ueberein."
            else:
                ok, msg = auth.set_password(new)
                if ok:
                    return redirect(url_for('index'))
                error = msg
        return render_template_string(_t(CHANGE_PW_TEMPLATE), error=error)

    @app.route('/reset/confirm', methods=['POST'])
    def reset_confirm():
        # Recovery-Pfad: ohne Login erreichbar (man ist ja ausgesperrt).
        if not auth.is_password_set():
            return redirect(url_for('setup'))

        def _do_reset():
            # Best-effort: Warnung auf dem Display anzeigen (falls Orchestrator es kann)
            try:
                if hasattr(orch, 'show_reset_warning'):
                    orch.show_reset_warning(RESET_COUNTDOWN_SECONDS)
            except Exception as e:
                log.warning("Display-Warnung fehlgeschlagen: %s", e)
            log.warning("PASSWORT-RESET angefordert - Reset in %d s", RESET_COUNTDOWN_SECONDS)
            time.sleep(RESET_COUNTDOWN_SECONDS)
            auth.reset_password()
            log.warning("PASSWORT geloescht - Service-Neustart")
            schedule_service_restart(delay=0.5)

        threading.Thread(target=_do_reset, daemon=True).start()
        return render_template_string(
            _t(RESET_DONE_TEMPLATE),
            countdown=RESET_COUNTDOWN_SECONDS,
            wait_plus=RESET_COUNTDOWN_SECONDS + 8,
        )

    # ---- API ----
    @app.route('/update_param', methods=['POST'])
    @api_login_required
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
    @api_login_required
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
    @api_login_required
    def models():
        return jsonify(rt.list_models())

    @app.route('/download', methods=['POST'])
    @api_login_required
    def download():
        data = request.get_json(silent=True) or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify(success=False, message="Keine URL angegeben.")
        return jsonify(download_and_register_model(url, rt))

    @app.route('/select_model', methods=['POST'])
    @api_login_required
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

    @app.route('/toggle_https', methods=['POST'])
    @api_login_required
    def toggle_https():
        data = request.get_json(silent=True) or {}
        want = bool(data.get('https'))
        rt.set_https(want)
        log.info("HTTPS auf %s gesetzt -> Service-Neustart", want)
        schedule_service_restart()
        scheme = 'https' if want else 'http'
        return jsonify(ok=True,
                       message="HTTPS %s. Noisy startet neu - bitte unter %s://...:%d neu verbinden."
                               % ("aktiviert" if want else "deaktiviert", scheme, WEB_PORT))

    return app


# ============================================================
# Web-UI Thread
# ============================================================
class WebUIThread(threading.Thread):
    """Startet das Flask-Dashboard als Daemon-Thread im Orchestrator."""

    def __init__(self, orchestrator, runtime_config, host=WEB_HOST, port=WEB_PORT):
        super().__init__(daemon=True)
        self.orch = orchestrator
        self.rt = runtime_config
        self.host = host
        self.port = port
        self.auth = AuthManager()

    def run(self):
        logging.getLogger('werkzeug').setLevel(logging.WARNING)

        ssl_context = None
        scheme = 'http'
        if self.rt.get_https():
            if noisy_netsec.ensure_self_signed_cert(TLS_CERT_FILE, TLS_KEY_FILE):
                ssl_context = (TLS_CERT_FILE, TLS_KEY_FILE)
                scheme = 'https'
            else:
                log.error("HTTPS aktiviert, aber Zertifikat-Erzeugung fehlgeschlagen "
                          "-> Fallback auf HTTP")

        try:
            app = create_app(self.orch, self.rt, self.auth)
            log.info("Web-UI startet auf %s://%s:%d", scheme, self.host, self.port)
            app.run(host=self.host, port=self.port, threaded=True,
                    use_reloader=False, debug=False, ssl_context=ssl_context)
        except Exception as e:
            log.error("Web-UI Thread abgestuerzt: %s", e)
