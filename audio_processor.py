--- File: audio_processor.py ---
import os
import time
import numpy as np
from multiprocessing import shared_memory
import pyaudio
import threading

# Konfiguration
SAMPLE_RATE = 16000
CHUNK_SIZE = 512  # Geringe Latenz für den Fast-Path
MOOD_MAP = {
    "MUSIC": 1,      # Musik -> Mode 1
    "LAUGH": 2,      # Lachen -> Mode 2
    "SCARED": 3,     # Schreie/Angst -> Mode 3
    "LISTEN": 4,     # Ambient/Regen -> Mode 4
    "IDLE": 0        # Default -> Mode 0
}

class AudioEngine:
    def __init__(self):
        # Shared Memory für Status-Updates (Mood ID, Confidence, Volume, Heartbeat)
        try:
            # Wir nutzen den Buffer von noisy_main.py als Quelle
            self.shm = shared_memory.SharedMemory(name="noisy_status_buffer")
        except FileNotFoundError:
            self.shm = shared_memory.SharedMemory(name="noisy_status_buffer", create=True, size=1024)
        
        # Status-Buffer Mapping (entsprechend noisy_main.py):
        # status_buf[0] = Mood ID (float32)
        # status_buf[1] = Confidence (float32)
        # status_buf[2] = Volume (RMS)
        # status_buf[3] = Heartbeat (Counter für Watchdog)
        self.status_buf = np.frombuffer(self.shm.buf, dtype=np.float32)

        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                                    input=True, frames_per_buffer=CHUNK_SIZE)
        
        self.current_mood = 0.0
        self.confidence = 0.0
        self.volume = 0.0
        self.heartbeat_counter = 0
        self.running = True

    def get_fast_path_reaction(self, audio_np):
        """Reagiert sofort auf plötzliche Signale (Niesen/Schreien) innerhalb von <30ms."""
        rms = np.max(np.abs(audio_np)) / 32768.0
        
        # Schwellenwert für 'SCARED' (Schrei/Niesen) - sehr schnell reagierend
        if rms > 0.6: # Extrem lauter Peak
            return MOOD_MAP["SCARED"], 0.95
        return None, 0.0

    def _analyze_audio(self, audio_np):
        """
        Hier wird später die eigentliche ML-Logik (Sense Voice / Tagging) eingebunden.
        Aktuell simulieren wir die Reaktion basierend auf der Lautstärke.
        """
        rms = np.max(np.abs(audio_np)) / 32768.0
        self.volume = rms

        if rms > 0.1:
            # Simulation: Je lauter, desto eher "LAUGH" oder "MUSIC"
            if rms > 0.4:
                return MOOD_MAP["LAUGH"], 0.8
            else:
                return MOOD_MAP["MUSIC"], 0.6
        return MOOD_MAP["IDLE"], 1.0

    def run(self):
        """Hauptschleife der Audio-Verarbeitung."""
        print("Audio Engine gestartet...")
        try:
            while self.running:
                # Daten vom Mikrofon lesen
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                # 1. Check Fast Path (Sofortreaktion)
                mood, conf = self.get_fast_path_reaction(audio_np)
                
                if mood is None:
                    # 2. Normaler Analyse-Pfad (Slow Path / ML)
                    mood, conf = self._analyze_audio(audio_np)

                # Update interne Variablen
                self.current_mood = float(mood)
                self.confidence = conf
                self.heartbeat_counter += 1

                # 3. Schreibt in den Shared Memory für noisy_main.py
                # Wir müssen vorsichtig sein, da status_buf direkt auf das SHM zugreift
                self.status_buf[0] = self.current_mood
                self.status_buf[1] = self.confidence
                self.status_buf[2] = self.volume
                self.status_buf[3] = float(self.heartbeat_counter % 1000) # Roll-over verhindern

                # Kleine Pause zur CPU-Schonung (da CHUNK_SIZE klein ist)
                time.sleep(0.001)

        except Exception as e:
            print(f"Audio Engine Error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        try:
            self.shm.close()
        except:
            pass

if __name__ == "__main__":
    engine = AudioEngine()
    # Startet die Engine in einem Thread, damit das Hauptprogramm nicht blockiert
    t = threading.Thread(target=engine.run)
    t.start()
    t.join()
