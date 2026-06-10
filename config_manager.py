import os
import json
import numpy as np
from multiprocessing import shared_memory

class ConfigManager:
    """
    Verwaltet die Konfiguration von Noisy.
    Nutzt Shared Memory für Echtzeit-Updates über die Web-UI 
    und eine JSON-Datei zur dauerhaften Speicherung (Persistenz).
    V0.7 - Enthält nun Input-Validierung und Heartbeat-Support.
    """
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Shared Memory Name für UI-Parameter
        self.shm_name = "noisy_vibe_params"
        
        try:
            # Versuche, bestehenden Speicher zu öffnen (WebUI ist bereits offen)
            self.shm = shared_memory.SharedMemory(name=self.shm_name)
        except FileNotFoundError:
            # Wenn nicht vorhanden -> neuen erstellen
            # Wir reservieren 1024 Bytes für UI-Parameter
            self.shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=1024)
        
        # Initialisiere den Speicher mit aktuellen Werten aus der Config
        self._sync_config_to_shm()

    def _load_config(self):
        """Lädt die Config von der Disk oder erstellt Defaults."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        else:
            # Standard-Konfiguration falls Datei fehlt
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
                    "last_save": "never"
                }
            }

    def _sync_config_to_shm(self):
        """Schreibt alle aktuellen Config-Werte in den Shared Memory Block."""
        # Wir nutzen ein Array aus Float32 Werten im Speicher:
        data = np.zeros(100, dtype=np.float32)
        data[0] = self.config["display"]["brightness_day"]
        data[1] = self.config["display"]["brightness_night"]
        data[2] = self.config["visuals"]["animation_speed_multiplier"]
        # Index 3 ist der Heartbeat-Counter für die Audio-Engine
        data[3] = 0.0
        
        # Daten in den Speicher schreiben
        self.shm.buf[:len(data)*4] = data.tobytes()

    def get_vibe_param(self, index):
        """Lies einen Wert aus dem Shared Memory."""
        return np.frombuffer(self.shm.buf, dtype=np.float32)[index]

    def set_vibe_param(self, index, value):
        """Schreibt einen Wert in den Shared Memory (Live) UND speichert ihn in der JSON (Disk).
        Inklusive Input-Validierung (Clamping)."""
        # 1. Update im RAM für sofortige Reaktion von Noisy mit Validierung
        if index == 0: # brightness_day
            value = max(0, min(255, float(value)))
            self.config["display"]["brightness_day"] = int(value)
        elif index == 1: # brightness_night
            value = max(0, min(255, float(value)))
            self.config["display"]["brightness_night"] = int(value)
        elif index == 2: # animation_speed_multiplier
            value = max(0.1, min(3.0, float(value)))
            self.config["visuals"]["animation_speed_multiplier"] = float(value)
        # Index 3 (Heartbeat) wird nicht validiert/gespeichert, da es ein Live-Counter ist
            
        data = np.frombuffer(self.shm.buf, dtype=np.float32)
        if index < len(data):
            data[index] = value
            
        # 2. Update in der Config-Struktur & auf Disk schreiben (nur für persistente Werte)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def get_full_config(self):
        """Gibt die komplette Config zurück (für Web-UI oder Debug)."""
        return self.config

    def close(self):
        """Schließt den Shared Memory Block sauber."""
        try:
            self.shm.close()
        except:
            pass
