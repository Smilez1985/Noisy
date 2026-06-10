import os
import time
import numpy as np
from multiprocessing import shared_memory
import pyaudio
import threading
import librosa
from config_manager import ConfigManager

# Konfiguration
SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # Kleinerer Chunk für minimale Latenz beim Fast-Path
MOOD_MAP = {
    "MUSIC": 1,      # Musik -> Mode 1
    "LAUGH": 2,      # Lachen -> Mode 2
    "SCARED": 3,     # Schreie/Angst -> Mode 3
    "LISTEN": 4,     # Ambient/Regen -> Mode 4
    "IDLE": 0        # Default -> Mode 0
}

class AudioEngine:
    def __init__(self):
        # Shared Memory für Status-Updates (Mood ID, Confidence, Volume)
        try:
            self.shm = shared_memory.SharedMemory(name="noisy_status_buffer")
        except FileNotFoundError:
            self.shm = shared_memory.SharedMemory(name="noisy_status_buffer", create=True, size=1024)
        
        # status_buf[0] = Mood ID (float32)
        # status_buf[1] = Confidence (float32)
        # status_buf[2] = Volume (RMS)
        self.status_buf = np.frombuffer(self.shm.buf, dtype=np.float32)

        # Laden der Konfiguration für Modelle
        self.config = ConfigManager("config.json")
        self.model_paths = self.config.get_full_config()["models"]["paths"]

        # Audio Setup
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                                    input=True, frames_per_buffer=CHUNK_SIZE)
        
        # Interne Puffer für den Kontext-Pfad (KI)
        self.context_buffer = []
        self.current_mood = 0.0
        self.confidence = 0.0
        self.volume = 0.0

    def get_fast_path_reaction(self, audio_np):
        """Reagiert sofort auf plötzliche Signale (Niesen, Schreie)."""
        rms = np.max(np.abs(audio_np)) / 32768.0
        
        # Schwellenwert für 'SCARED' (Schrei/Niesen) - sehr schnell reagierend
        if rms > 0.6: # Extrem laut
            return MOOD_MAP["SCARED"], 0.95
        
        # Mittelmäßiger Tonbereich -> Musik-Proxy
        elif rms > 0.2:
            return MOOD_MAP["MUSIC"], 0.7
        
        else:
            return MOOD_MAP["IDLE"], 1.0

    def process_audio(self):
        print("🎧 Audio Engine aktiv (Fast-Path & Context-Inferenz)...")
        
        while True:
            try:
                # 1. Rohdaten lesen
                data, _ = self.stream.read(CHUNK_SIZE)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                
                # 2. Fast-Path Analyse (Sofortige Reaktion)
                fast_mood, fast_conf = self.get_fast_path_reaction(audio_np)
                self.volume = np.max(np.abs(audio_np)) / 32768.0
                
                # Wir schreiben den Fast-Path direkt in den Speicher für die sofortige Reaktion
                # Aber wir halten die KI-Logik im Hintergrund laufen
                self.status_buf[0] = fast_mood
                self.status_buf[1] = fast_conf
                self.status_buf[2] = self.volume

                # 3. Kontext-Pfad (KI-Inferenz im Hintergrund)
                # Wir sammeln Daten für ein 1-Sekunden-Fenster zur KI-Analyse
                self.context_buffer.append(audio_np)
                if len(self.context_buffer) > (SAMPLE_RATE // CHUNK_SIZE):
                    # Konvertiere Buffer zu einem großen Array
                    full_chunk = np.concatenate(self.context_buffer)
                    
                    # Hier wird später Sherpa-ONNX aufgeführt:
                    # result = sherpa_model.predict(full_chunk)
                    # self.current_mood = result.mood_id
                    # selbst wenn die KI noch nicht perfekt ist, 
                    # sammelt dieser Pfad jetzt die Daten für die Musikerkennung.
                    
                    self.context_buffer = [] # Buffer leeren nach Analyse

            except Exception as e:
                print(f"Audio Error: {e}")
                time.sleep(0.1)

    def run(self):
        # Starte den Audio-Prozessor in einem dedizierten Thread
        threading.Thread(target=self.process_audio, daemon=True).start()
        while True:
            time.sleep(1)

if __name__ == "__main__":
    engine = AudioEngine()
    engine.run()
