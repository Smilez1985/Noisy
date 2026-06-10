--- File: audio_processor.py ---
import os
import time
import numpy as np
from multiprocessing import shared_memory
import pyaudio
import threading
import logging
import subprocess
from config_manager import ConfigManager

# Konfiguration
SAMPLE_RATE = 16000
CHUNK_SIZE = 512  
MOOD_MAP = {
    "MUSIC": 1,      # Musik -> Mode 1
    "LAUGH": 2,      # Lachen -> Mode 2
    "SCARED": 3,     # Schreie/Angst -> Mode 3
    "LISTEN": 4,     # Ambient/Regen -> Mode 4
    "IDLE": 0        # Default -> Mode 0
}

class AudioEngine:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.get_full_config()
        
        # Logging Setup
        log_path = self.config["system"]["logging"]["standard_path"]
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        logging.basicConfig(
            filename=log_path,
            level=self.config["system"]["log_level"],
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        # Shared Memory Setup
        try:
            self.shm = shared_memory.SharedMemory(name="noisy_status_buffer")
        except FileNotFoundError:
            self.shm = shared_memory.SharedMemory(name="noisy_status_buffer", create=True, size=1024)
        
        self.status_buf = np.frombuffer(self.shm.buf, dtype=np.float32)

        # Audio Hardware Instanzien
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.reinitialize_audio() # Initialer Aufruf

        self.current_mood = 0.0
        self.confidence = 0.0
        self.volume = 0.0
        self.heartbeat_counter = 0
        self.running = True
        
        # Fehler-Handling Variablen
        self.consecutive_errors = 0
        self.max_retries = 5

    def reinitialize_audio(self):
        """Versucht den Audio-Stream sauber zu öffnen oder neu zu verbinden."""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            
            self.stream = self.p.open(
                format=pyaudio.paInt16, 
                channels=1, 
                rate=SAMPLE_RATE,
                input=True, 
                frames_per_buffer=CHUNK_SIZE,
                 options={'blocking': True}
            )
            logging.info("Audio Stream erfolgreich initialisiert.")
            return True
        except Exception as e:
            logging.error(f"Fehler bei der Audio-Initialisierung: {e}")
            return False

    def get_fast_path_reaction(self, audio_np):
        """Reagiert sofort auf plötzliche Signale (Niesen/Schreien)."""
        rms = np.max(np.abs(audio_np)) / 32768.0
        if rms > 0.6: 
            return MOOD_MAP["SCARED"], 0.95
        return None, 0.0

    def _analyze_audio(self, audio_np):
        """Platzhalter für ML-Analyse."""
        rms = np.max(np.abs(audio_np)) / 32768.0
        self.volume = rms
        if rms > 0.1:
            if rms > 0.4: return MOOD_MAP["LAUGH"], 0.8
            else: return MOOD_MAP["MUSIC"], 0.6
        return MOOD_MAP["IDLE"], 1.0

    def run(self):
        """Hauptschleife mit Fehler-Recovery."""
        logging.info("Audio Engine Loop gestartet.")
        
        while self.running:
            try:
                if not self.stream or not self.stream.is_active():
                    if not self.reinitialize_audio():
                        raise ConnectionError("Kein aktiver Audio-Stream verfügbar.")

                # Daten lesen
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                # Processing
                mood, conf = self.get_fast_path_reaction(audio_np)
                if mood is None:
                    mood, conf = self._analyze_audio(audio_np)

                self.current_mood = float(mood)
                self.confidence = conf
                self.heartbeat_counter += 1

                # Shared Memory Update
                self.status_buf[0] = self.current_mood
                self.status_buf[1] = self.confidence
                self.status_buf[2] = self.volume
                self.status_buf[3] = float(self.heartbeat_counter % 1000)

                time.sleep(0.001)
                # Bei Erfolg Fehler-Counter zurücksetzen
                self.consecutive_errors = 0

            except Exception as e:
                logging.error(f"Loop-Fehler erkannt: {e}")
                self.consecutive_errors += 1
                
                if self.consecutive_errors >= self.max_retries:
                    logging.critical("Maximaler Fehlerlimit erreicht. Starte Silent Reboot...")
                    self._silent_reboot()
                else:
                    logging.info(f"Versuche Stream-Recovery ({self.consecutive_errors}/{self.max_retries})...")
                    time.sleep(2) # Backoff vor Retry
                    self.reinitialize_audio()

    def _silent_reboot(self):
        """Triggert einen System-Reboot als letzte Instanz."""
        try:
            # Schreibt ein kurzes Signal in das Log, bevor es rebootet
            logging.critical("SYSTEM REBOOT TRIGGERED DUE TO PERSISTENT AUDIO FAILURE.")
            # Nutzt sudo reboot für echten Hardware-Restart
            subprocess.run(["sudo", "reboot"], check=True)
        except Exception as fatal_e:
            logging.error(f"Reboot fehlgeschlagen: {fatal_e}")

    def cleanup(self):
        """Sauberes Schließen."""
        self.running = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except: pass
        if hasattr(self, 'p'):
            self.p.terminate()
        try:
            self.shm.close()
        except: pass

if __name__ == "__main__":
    engine = AudioEngine()
    t = threading.Thread(target=engine.run)
    t.daemon = True
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Beendet.")
