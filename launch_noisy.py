--- File: launch_noisy.py ---
import multiprocessing
import time
import sys
import os
import logging

# Konfiguration für das Logging des Launchers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAUNCHER] - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/noisy/launcher.log"),
        logging.StreamHandler()
    ]
)

# Importe der Module
try:
    from audio_processor import AudioEngine
    import noisy_main
except ImportError as e:
    print(f"Fehler beim Laden der Module: {e}")
    sys.exit(1)

def run_audio():
    """Startet die Audio-Engine in einem eigenen Prozess."""
    try:
        engine = AudioEngine()
        engine.run()
    except Exception as e:
        logging.critical(f"Audio Engine Prozess abgestürzt: {e}")

def run_ui():
    """Startet die UI/Main-Loop im Hauptprozess."""
    try:
        noisy_main.main_loop()
    except Exception as e:
        logging.critical(f"UI Prozess abgestürzt: {e}")

if __name__ == "__main__":
    # Verzeichnis anpassen, damit imports funktionieren
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    logging.info("Noisy V0.8 Systemstart...")
    logging.info("Initialisiere Audio-Engine Prozess...")

    # Wir nutzen multiprocessing für maximale Stabilität auf dem Pi
    p_audio = multiprocessing.Process(target=run_audio, name="AudioEngine")
    p_ui = multiprocessing.Process(target=run_ui, name="NoisyUI")

    # Prozesse starten
    p_audio.start()
    time.sleep(1) # Kurzer Puffer für Shared Memory Erstellung
    p_ui.start()

    logging.info("Beide Engines erfolgreich gestartet.")

    try:
        # Warten, bis die Prozesse laufen
        while True:
            if not p_audio.is_alive() or not p_ui.is_alive():
                break
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Manueller Abbruch durch User.")
    finally:
        # Sauberes Herunterfahren aller Prozesse
        p_audio.terminate()
        p_ui.terminate()
        logging.info("System beendet.")
