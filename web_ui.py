import os
import json
import threading
import requests
from flask import Flask, request, jsonify, render_template_string
from config_manager import ConfigManager

app = Flask(__name__)
# Initialisiere den globalen Konfigurations-Manager
config = ConfigManager("config.json")

# --- HTML & CSS Template (Das Dashboard) ---
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
            max-width: 450px;
            border: 1px solid #333;
        }
        h1 { color: var(--accent); margin: 0 0 10px 0; font-size: 2rem; }
        p { color: var(--subtext); margin-bottom: 35px; }
        .control-group { margin-bottom: 25px; }
        label { display: block; margin-bottom: 12px; font-weight: bold; color: #bbb; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;}
        input[type="range"] { width: 100%; accent-color: var(--accent); cursor: pointer; margin-bottom: 5px; }
        .val-display { float: right; color: var(--accent); font-family: monospace; font-size: 1.1rem; }
        input[type="text"], input[type="time"] {
            width: 100%;
            padding: 12px;
            background: #2a2a2a;
            border: 1px solid #444;
            color: white;
            border-radius: 8px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 12px;
            font-weight: bold;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-save { background: var(--accent); color: #000; margin-top: 10px; }
        .btn-download { background: #444; color: white; margin-bottom: 10px;}
        button:hover { opacity: 0.9; transform: translateY(-2px); }
        button:active { transform: scale(0.98); }
        hr { border: 0; border-top: 1px solid #333; margin: 30px 0; }
        .status { font-size: 0.8em; color: var(--subtext); margin-top: 25px; text-align: center; height: 20px; }
    </style>
</head>
<body>
    <h1>Noisy</h1>
    <p>Atmosphärisches Dashboard für deinen Mochi-Blob.</p>

    <div class="card">
        <!-- Live Preview Sektion -->
        <div class="control-group">
            <label>Tag Helligkeit <span id="day_val" class="val-display">{{ config.display.brightness_day }}</span></label>
            <input type="range" id="brightness_day" min="0" max="255" value="{{ config.display.brightness_day }}">
        </div>

        <div class="control-group">
            <label>Nacht Helligkeit <span id="night_val" class="val-display">{{ config.display.brightness_night }}</span></label>
            <input type="range" id="brightness_night" min="0" max="255" value="{{ config.display.brightness_night }}">
        </div>

        <div class="control-group">
            <label>Animation Speed <span id="speed_val" class="val-display">{{ config.visuals.animation_speed_multiplier }}</span></label>
            <input type="range" id="speed_mult" min="0.1" max="3.0" step="0.1" value="{{ config.visuals.animation_speed_multiplier }}">
        </div>

        <hr>

        <!-- Persistente Einstellungen -->
        <div class="control-group">
            <label>Nachtmodus Fenster</label>
            <input type="time" id="night_start" value="{{ config.display.night_mode_start }}">
            <input type="time" id="night_end" value="{{ config.display.night_mode_end }}">
        </div>

        <div class="control-group">
            <label>Modell URL (Optional)</label>
            <input type="text" id="model_url" placeholder="https://github.com/..." value="{{ config.models.paths.sense }}">
            <button class="btn-download" onclick="downloadModel()">Validiere & Lade Modell</button>
        </div>

        <button class="btn-save" onclick="saveSettings()">EINSTELLUNGEN SPEICHERN</button>
        <div class="status" id="status_msg">Ready.</div>
    </div>

    <script>
        // Live Slider Updates (Realtime Preview)
        const liveSliders = ['brightness_day', 'brightness_night', 'speed_mult'];
        liveSliders.forEach(id => {
            document.getElementById(id).oninput = function() {
                let val = parseFloat(this.value);
                document.getElementById(id + '_val').innerText = this.value;
                // Schicke sofort an den Shared Memory (Live Update)
                fetch('/update_param', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id: id, value: val })
                });
            };
        });

        // Save Logic
        async function saveSettings() {
            const data = {
                brightness_day: document.getElementById('brightness_day').value,
                brightness_night: document.getElementById('brightness_night').value,
                animation_speed_multiplier: document.getElementById('speed_mult').value,
                night_mode_start: document.getElementById('night_start').value,
                night_mode_end: document.getElementById('night_end').value
            };
            const res = await fetch('/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            if (res.ok) document.getElementById('status_msg').innerText = "Speicherung erfolgreich!";
        }

        // Download Logic
        async function downloadModel() {
            const url = document.getElementById('model_url').value;
            document.getElementById('status_msg').innerText = "Prüfe URL...";
            try {
                const res = await fetch('/download', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: url })
                });
                const result = await res.json();
                document.getElementById('status_msg').innerText = result.message;
            } catch(e) {
                document.getElementById('status_msg').innerText = "Fehler bei der Anfrage.";
            }
        }
    </script>
</body>
</html>
