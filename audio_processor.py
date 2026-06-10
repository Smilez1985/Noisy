import os
import time
import numpy as np
from multiprocessing import shared_memory
import librosa
import pyaudio
import threading

# Konfiguration für die Audio-Erkennung
SAMPLE_RATE = 16000
CHUNK_SIZE = 4096 # Ca. 0.25 Sekunden
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

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                                    input=True, frames_per_buffer=CHUNK_SIZE)
        
        self.current_mood = 0.0
        self.confidence = 0.0
        self.volume = 0.0

    def process_audio(self):
        print("🎧 Audio Engine aktiv...")
        while True:
            try:
                data, _ = self.stream.read(CHUNK_SIZE)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                
                # 1. Volume berechnen (RMS)
                self.volume = np.max(np.abs(audio_np)) / 32768.0
                
                # 2. Vereinfachte Logik (Hier später Sherpa-ONNX integrieren)
                # Aktuell: Reagiert auf Lautstärke und Frequenz als Proxy
                if self.volume > 0.5: # Sehr laut
                    self.current_mood = MOOD_MAP["SCARED"]
                    self.confidence = 0.9
                elif self.volume > 0.2: # Normaler Ton
                    # Hier würde die KI-Inferenz laufen
                    self.current_mood = MOOD_MAP["MUSIC"]
                    self.confidence = 0.7
                else:
                    self.current_mood = MOOD_MAP["IDLE"]
                    self.confidence = 1.0

                # 3. In Shared Memory schreiben
                self.status_buf[0] = self.current_mood
                self.status_buf[1] = self.confidence
                self.status_buf[2] = self.volume

            except Exception as e:
                print(f"Audio Error: {e}")
                time.sleep(0.1)

    def run(self):
        threading.Thread(target=self.process_audio, daemon=True).start()
        while True:
            time.sleep(1)

if __name__ == "__main__":
    engine = AudioEngine()
    engine.run()
