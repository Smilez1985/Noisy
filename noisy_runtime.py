#!/usr/bin/env python3
"""
Noisy Runtime Config - Live-aenderbare Parameter (Web-UI)

Getrennt von den statischen Konstanten in noisy_config.py:
Hier liegen nur Werte, die der User zur Laufzeit ueber das
Web-Dashboard aendern darf und die einen Reboot ueberleben sollen.

Persistenz: runtime_config.json in APP_DIR.
Thread-Safety: RLock, da Orchestrator, Renderer und Flask-Thread
parallel lesen/schreiben. Speichern erfolgt atomar (tmp + os.replace).

Enthaelt:
  - display:  Helligkeit Tag/Nacht, Auto-Dim, Nacht-Zeitfenster
  - visuals:  Animationsgeschwindigkeit
  - server:   HTTPS an/aus (Self-Signed, greift nach Service-Neustart)
  - models:   Registry verfuegbarer KI-Modelle + aktives Modell
"""

import os
import json
import threading

from noisy_config import APP_DIR, MODEL_DIR

RUNTIME_CONFIG_FILE = os.path.join(APP_DIR, 'runtime_config.json')

# ============================================================
# Default-Modell (der mitgelieferte Zipformer-Tagger)
# ============================================================
DEFAULT_MODEL_KEY = "zipformer-audio-tagging"

_DEFAULT_MODELS = {
    DEFAULT_MODEL_KEY: {
        "name": "Zipformer Audio-Tagging (int8)",
        "model": os.path.join(MODEL_DIR, 'model.int8.onnx'),
        "labels": os.path.join(MODEL_DIR, 'class_labels_indices.csv'),
        "builtin": True,
    }
}

# ============================================================
# Default-Konfiguration
# ============================================================
DEFAULTS = {
    "display": {
        "brightness_day": 255,
        "brightness_night": 80,
        "auto_dim": True,
        "night_mode_start": "22:00",
        "night_mode_end": "06:00",
    },
    "visuals": {
        "animation_speed_multiplier": 1.0,
    },
    "server": {
        "https": False,
    },
    "models": {
        "active": DEFAULT_MODEL_KEY,
        "registry": _DEFAULT_MODELS,
    },
}


def _deep_merge(base, override):
    """Merged override in base (rekursiv) und gibt eine neue Struktur zurueck."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _valid_time(s):
    """Prueft HH:MM (24h). Gibt True/False zurueck."""
    try:
        parts = str(s).split(":")
        if len(parts) != 2:
            return False
        h, m = int(parts[0]), int(parts[1])
        return 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        return False


class RuntimeConfig:
    """Thread-sichere Laufzeit-Konfiguration mit JSON-Persistenz."""

    def __init__(self, path=RUNTIME_CONFIG_FILE):
        self.path = path
        self._lock = threading.RLock()
        self._data = self._load()

    # ----------------------------------------------------------
    # Laden / Speichern
    # ----------------------------------------------------------
    def _load(self):
        """Laedt die Config von Disk und merged sie ueber die Defaults."""
        data = {
            "display": dict(DEFAULTS["display"]),
            "visuals": dict(DEFAULTS["visuals"]),
            "server": dict(DEFAULTS["server"]),
            "models": {
                "active": DEFAULTS["models"]["active"],
                "registry": dict(DEFAULTS["models"]["registry"]),
            },
        }
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r') as f:
                    on_disk = json.load(f)
                data = _deep_merge(data, on_disk)
        except Exception:
            pass

        # Sicherstellen, dass die server-Sektion existiert (Forward-Compat)
        if "server" not in data or not isinstance(data["server"], dict):
            data["server"] = dict(DEFAULTS["server"])
        if "https" not in data["server"]:
            data["server"]["https"] = DEFAULTS["server"]["https"]

        # Das eingebaute Default-Modell muss IMMER vorhanden sein
        if DEFAULT_MODEL_KEY not in data["models"]["registry"]:
            data["models"]["registry"][DEFAULT_MODEL_KEY] = dict(
                _DEFAULT_MODELS[DEFAULT_MODEL_KEY]
            )

        # Aktives Modell validieren -> Fallback auf Default
        if data["models"]["active"] not in data["models"]["registry"]:
            data["models"]["active"] = DEFAULT_MODEL_KEY

        return data

    def save(self):
        """Schreibt die Config atomar auf Disk."""
        with self._lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, 'w') as f:
                    json.dump(self._data, f, indent=2)
                os.replace(tmp, self.path)
            except Exception:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass

    # ----------------------------------------------------------
    # Display-Parameter
    # ----------------------------------------------------------
    def get_display(self):
        with self._lock:
            return dict(self._data["display"])

    def set_brightness_day(self, value):
        with self._lock:
            self._data["display"]["brightness_day"] = int(max(0, min(255, value)))
            self.save()

    def set_brightness_night(self, value):
        with self._lock:
            self._data["display"]["brightness_night"] = int(max(0, min(255, value)))
            self.save()

    def set_auto_dim(self, value):
        with self._lock:
            self._data["display"]["auto_dim"] = bool(value)
            self.save()

    def set_night_window(self, start, end):
        """Setzt Nacht-Start/Ende (HH:MM). Ungueltige Werte werden ignoriert."""
        with self._lock:
            if _valid_time(start):
                self._data["display"]["night_mode_start"] = str(start)
            if _valid_time(end):
                self._data["display"]["night_mode_end"] = str(end)
            self.save()

    def get_brightness_day(self):
        with self._lock:
            return self._data["display"]["brightness_day"]

    def get_brightness_night(self):
        with self._lock:
            return self._data["display"]["brightness_night"]

    def get_auto_dim(self):
        with self._lock:
            return self._data["display"]["auto_dim"]

    def get_night_window(self):
        with self._lock:
            d = self._data["display"]
            return d["night_mode_start"], d["night_mode_end"]

    # ----------------------------------------------------------
    # Visuals
    # ----------------------------------------------------------
    def get_visuals(self):
        with self._lock:
            return dict(self._data["visuals"])

    def set_speed(self, value):
        with self._lock:
            try:
                v = float(value)
            except (TypeError, ValueError):
                return
            self._data["visuals"]["animation_speed_multiplier"] = max(0.1, min(3.0, v))
            self.save()

    def get_speed(self):
        with self._lock:
            return self._data["visuals"]["animation_speed_multiplier"]

    # ----------------------------------------------------------
    # Server (HTTPS-Toggle)
    # Greift erst nach Neustart des Web-Servers/Service, da TLS beim
    # Start gebunden wird (vgl. WebUIThread).
    # ----------------------------------------------------------
    def get_server(self):
        with self._lock:
            return dict(self._data["server"])

    def get_https(self):
        with self._lock:
            return bool(self._data["server"].get("https", False))

    def set_https(self, value):
        with self._lock:
            self._data["server"]["https"] = bool(value)
            self.save()
            return self._data["server"]["https"]

    # ----------------------------------------------------------
    # Modell-Registry
    # ----------------------------------------------------------
    def list_models(self):
        """Gibt eine Liste der registrierten Modelle zurueck (fuer Dropdown)."""
        with self._lock:
            active = self._data["models"]["active"]
            out = []
            for key, m in self._data["models"]["registry"].items():
                out.append({
                    "key": key,
                    "name": m.get("name", key),
                    "builtin": m.get("builtin", False),
                    "active": key == active,
                    "ready": os.path.exists(m.get("model", "")),
                })
            return out

    def add_model(self, key, name, model_path, labels_path):
        """Registriert ein neues Modell. Ueberschreibt bestehende gleichen Keys."""
        with self._lock:
            self._data["models"]["registry"][key] = {
                "name": name,
                "model": model_path,
                "labels": labels_path,
                "builtin": False,
            }
            self.save()

    def remove_model(self, key):
        """Entfernt ein nicht-eingebautes Modell. Aktives faellt auf Default zurueck."""
        with self._lock:
            reg = self._data["models"]["registry"]
            if key in reg and not reg[key].get("builtin", False):
                del reg[key]
                if self._data["models"]["active"] == key:
                    self._data["models"]["active"] = DEFAULT_MODEL_KEY
                self.save()
                return True
            return False

    def set_active_model(self, key):
        """Setzt das aktive Modell, falls registriert. Gibt True bei Erfolg zurueck."""
        with self._lock:
            if key in self._data["models"]["registry"]:
                self._data["models"]["active"] = key
                self.save()
                return True
            return False

    def get_active_model(self):
        """Gibt {key, name, model, labels} des aktiven Modells zurueck."""
        with self._lock:
            key = self._data["models"]["active"]
            m = self._data["models"]["registry"].get(
                key, _DEFAULT_MODELS[DEFAULT_MODEL_KEY]
            )
            return {
                "key": key,
                "name": m.get("name", key),
                "model": m.get("model"),
                "labels": m.get("labels"),
            }

    def has_model(self, key):
        with self._lock:
            return key in self._data["models"]["registry"]
