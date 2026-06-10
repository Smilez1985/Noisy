--- File: config_manager.py ---
import os
import json
import numpy as np
from multiprocessing import shared_memory

class ConfigManager:
    """
    Verwaltet die Konfiguration von Noisy (V0.8).
    Nutzt Shared Memory für Echtzeit-Updates und eine JSON-Datei zur Persistenz.
    Unterstützt nun Logging-Pfade und Hardware-Button-Konfiguration.
    """
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Shared Memory Name für UI-Parameter & Status
        self.shm_name = "noisy_vibe_params"
        
        try:
            # Versuche bestehenden Speicher zu öffnen
            self.shm = shared_memory.SharedMemory(name=self.shm_name)
        except FileNotFoundError:
            # Neuer Speicher (1024 Bytes genug für alle Parameter)
            self.shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=1024)
        
        # Initialisiere den Speicher mit aktuellen Werten
        self._sync_config_to_shm()

    def _load_config(self):
        """Lädt die Config von der Disk oder erstellt Defaults."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Standard-Konfiguration V0.8
            return {
                "display": {
                    "brightness_day": 255,
                    "brightness_night": 80,
                    "auto_dim": True,
                    "night_mode_start": "22:00",
                    "night_mode_end": "06:00"
                },
                "visuals": {
                    "animation_speed_multiplier": 1.0,
                    "idle_breath_speed": 0.8,
                    "mood_colors": {
                        "MUSIC": [255, 165, 0],
                        "LAUGH": [255, 255, 0],
                        "SCARED": [255, 0, 0],
                        "TIRED": [150, 150, 200],
                        "LISTEN": [0, 255, 255]
                    }
                },
                "models": {
                    "active_model_type": "sense-voice",
                    "paths": {
                        "tagging": "/home/noisy/models/sherpa-onnx-zipformer-small-audio-tagging-2024-04-15.onnx",
                        "sense": "/home/noisy/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17-int8.onnx"
                    },
                    "download_status": {"tagging": "ready", "sense": "ready"}
                },
                "system": {
                    "log_level": "INFO",
                    "debug_mode": False,
                    "last_save": "never",
                    "logging": {
                        "standard_path": "/var/log/noisy/noisy.log",
                        "dev_log_dir": "/var/log/noisy/dev_logs/"
                    },
                    "hardware": {
                        "dev_button_pin": 13,
                        "auto_start": True
                    }
                }
            }

    def _sync_config_to_shm(self):
        """Schreibt alle aktuellen Config-Werte in den Shared Memory Block."""
        # Index Mapping:
        # 0: brightness_day, 1: brightness_night, 2: speed_mult, 3: heartbeat, 4: dev_mode_active
        data = np.zeros(100, dtype=np.float32)
        data[0] = self.config["display"]["brightness_day"]
        data[1] = self.config["display"]["brightness_night"]
        data[2] = self.config["visuals"]["animation_speed_multiplier"]
        data[3] = 0.0  # Heartbeat (wird von Audio-Engine befüllt)
        data[4] = 1.0 if self.config["system"]["debug_mode"] else 0.0 # Dev Mode Flag
        
        self.shm.buf[:len(data)*4] = data.tobytes()

    def get_vibe_param(self, index):
        """Lies einen Wert aus dem Shared Memory."""
        return np.frombuffer(self.shm.buf, dtype=np.float32)[index]

    def set_vibe_param(self, index, value):
        """Schreibt Live-Wert in SHM und persistiert ihn in die JSON."""
        val = float(value)
        
        if index == 0: # brightness_day
            val = max(0, min(255, val))
            self.config["display"]["brightness_day"] = int(val)
        elif index == 1: # brightness_night
            val = max(0, min(255, val))
            self.config["display"]["brightness_night"] = int(val)
        elif index == 2: # animation_speed_multiplier
            val = max(0.1, min(3.0, val))
            self.config["visuals"]["animation_speed_multiplier"] = float(val)
        elif index == 4: # dev_mode_active (Flag für UI/Hardware)
            val = 1.0 if val > 0.5 else 0.0
            self.config["system"]["debug_mode"] = bool(val)
            
        data = np.frombuffer(self.shm.buf, dtype=np.float32)
        if index < len(data):
            data[index] = val
            
        # Persistenz auf Disk
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_full_config(self):
        """Gibt die komplette Config zurück (für Web-UI)."""
        return self.config

    def close(self):
        """Schließt den Shared Memory Block sauber."""
        try:
            self.shm.close()
        except:
            pass
