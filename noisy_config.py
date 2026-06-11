#!/usr/bin/env python3
"""
Noisy Config - Zentrale Konfiguration
Wird von allen Modulen importiert.
Aendern nur hier -> wirkt ueberall.

Privacy-Logging:
  Normalerweise: Log nach /tmp (Ramdisk, stirbt bei Reboot)
  Debug-Mode:    Log auf SD-Karte (persistent)
  Aktivierung:   NOISY_DEBUG=1 Umgebungsvariable
                 oder Datei /home/noisy/noisy-app/debug.flag existiert
"""

import os
import json

# ============================================================
# Debug-Mode Erkennung
# ============================================================
APP_DIR = '/home/noisy/noisy-app'
DEBUG_FLAG_FILE = os.path.join(APP_DIR, 'debug.flag')
DEBUG_MODE = (
    os.environ.get('NOISY_DEBUG', '0') == '1'
    or os.path.exists(DEBUG_FLAG_FILE)
)

# ============================================================
# Version (Single Source of Truth: manifest.json)
# ============================================================
def _load_version():
    """Liest die Version aus manifest.json - alleinige Versionsquelle."""
    try:
        with open(os.path.join(APP_DIR, 'manifest.json'), 'r') as f:
            return json.load(f).get('version', '0.0.0')
    except Exception:
        return '0.0.0'

VERSION = _load_version()

# ============================================================
# Pfade
# ============================================================
MODEL_DIR = '/home/noisy/models/sherpa-onnx-zipformer-small-audio-tagging-2024-04-15'
MODEL_PATH = os.path.join(MODEL_DIR, 'model.int8.onnx')
LABELS_PATH = os.path.join(MODEL_DIR, 'class_labels_indices.csv')
PERSONALITY_FILE = os.path.join(APP_DIR, 'personality.json')
CALIBRATION_FILE = os.path.join(APP_DIR, 'calibration.json')
MOODS_DIR = os.path.join(APP_DIR, 'moods')

# ============================================================
# Logging (Privacy-First)
# Normal:  /tmp/noisy.log (Ramdisk, weg bei Reboot, schont SD)
# Debug:   /home/noisy/noisy-app/noisy.log (persistent auf SD)
# ============================================================
if DEBUG_MODE:
    LOG_FILE = os.path.join(APP_DIR, 'noisy.log')
    AUDIO_LOG_FILE = os.path.join(APP_DIR, 'noisy_audio.log')
    LOG_LEVEL = 'DEBUG'
else:
    LOG_FILE = '/tmp/noisy.log'
    AUDIO_LOG_FILE = '/tmp/noisy_audio.log'
    LOG_LEVEL = 'INFO'

# ============================================================
# IPC (Shared Memory: 8 Bytes)
# Byte 0:   Mood-ID (0-255)
# Byte 1:   Mood-Variante (0-255, fuer spaeter)
# Byte 2:   Intensity (0-255, RMS-basiert)
# Byte 3:   Beat-Speed (0-255, Peaks/Sek skaliert)
# Byte 4:   Transition-Speed (0-255)
# Byte 5-7: Reserved (Kontext, Flags)
# ============================================================
SHM_NAME = 'noisy_mood'
SHM_SIZE = 8

# ============================================================
# Audio (USB-Mic native 44100, KI braucht 16000)
# ============================================================
SAMPLE_RATE = 44100
MODEL_RATE = 16000
CHUNK_SECONDS = 1
CHUNK_SIZE = SAMPLE_RATE * CHUNK_SECONDS
RMS_SILENCE = 0.002
CONFIDENCE_MIN = 0.05

# ============================================================
# Stille-Timeouts (Sekunden, Basis-Werte)
# Orchestrator skaliert BORED_TIMEOUT mit Personality.affection
# ============================================================
BORED_TIMEOUT = 25
SLEEP_TIMEOUT = 60

# ============================================================
# Auto-Gain
# ============================================================
TARGET_RMS = 0.08
GAIN_MIN = 1.0
GAIN_MAX = 30.0
GAIN_SMOOTHING = 0.15
GAIN_START = 10.0
GAIN_SILENCE_RESET = 5.0

# ============================================================
# Accumulator (Orchestrator nutzt diese Werte)
# ============================================================
ACCUMULATOR_WINDOW = 5
GENRE_THRESHOLD = 2.0
ACCUMULATOR_SILENCE_CLEAR = 5

# ============================================================
# Fast-Track Impuls (Orchestrator)
# High-Priority Moods ueberspringen den Accumulator wenn
# Confidence ueber diesem Schwellenwert liegt.
# ============================================================
FAST_TRACK_CONFIDENCE = 0.40

# ============================================================
# Genre-Fingerprint
# ============================================================
FINGERPRINT_BOOST = 2.0

# ============================================================
# Moflin A.E.I.
# ============================================================
PERSONALITY_SAVE_INTERVAL = 300
PERSONALITY_DECAY_RATE = 0.00003      # War 0.0001 (zu aggressiv, Personality vergass zu schnell)

# ============================================================
# Tageszeit-Bewusstsein (Stunden, 24h Format)
# ============================================================
TIME_MORNING = (6, 10)      # Noisy ist verschlafen, gaehnt, streckt sich
TIME_EVENING = (20, 23)     # Noisy wird ruhiger, meditiert, chillt
TIME_NIGHT_START = 23       # Noisy will schlafen, reagiert genervt auf Laerm
TIME_NIGHT_END = 6
SLEEP_TIMEOUT_NIGHT = 30    # Nachts schneller einschlafen (statt 60s)
BORED_TIMEOUT_NIGHT = 15    # Nachts schneller gelangweilt

# ============================================================
# Thermal-Personality (CPU-Temperatur beeinflusst Noisy)
# ============================================================
THERMAL_WARM = 60.0         # Ab hier: leicht muede, Energie sinkt langsam
THERMAL_HOT = 70.0          # Ab hier: sichtbar muede, Schweiss-Partikel

# ============================================================
# RMS-Spike (ploetzlich laut -> SCARED)
# ============================================================
RMS_SPIKE_THRESHOLD = 150   # Ab hier: pruefen ob Schreck-Reaktion
RMS_SPIKE_HARD = 200        # Ab hier: immer erschrecken (unabhaengig von shy)

# ============================================================
# CPU Frequency Capping (Pi Zero 2 W: 600MHz-1000MHz)
# Spart Strom/Hitze bei Stille, volle Leistung bei Audio
# ============================================================
CPU_FREQ_IDLE = 600000      # 600MHz bei Stille/Idle
CPU_FREQ_ACTIVE = 1000000   # 1GHz bei Audio-Aktivitaet
CPU_FREQ_PATH = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq'

# ============================================================
# Night Gesture (genervtes Aufwachen nachts)
# ============================================================
NIGHT_ANNOYED_DURATION = 5  # Sekunden: Psst-Geste nach naechtlichem Aufwachen

# ============================================================
# Sound Memory (taegliches Kurzzeitgedaechtnis)
# Noisy merkt sich die haeufigsten Sounds des Tages.
# Bekannte Sounds bekommen Score-Boost -> schnellere Reaktion.
# ============================================================
SOUND_MEMORY_TOP = 5          # Top N Sounds merken
SOUND_MEMORY_BOOST = 1.3      # Score-Multiplikator fuer bekannte Sounds
SOUND_MEMORY_MIN_COUNT = 3    # Mindestens X mal gehoert bevor Boost greift

# ============================================================
# Genre Affinity (langfristiges Gedaechtnis in Personality)
# Noisy entwickelt Vorlieben fuer Musikgenres ueber Tage/Wochen.
# Lieblingsgenres loesen staerkere Reaktionen aus (Herzen, Freude).
# ============================================================
GENRE_AFFINITY_GAIN = 0.002       # Pro Zyklus mit aktivem Genre
GENRE_AFFINITY_DECAY = 0.0003     # Pro Zyklus fuer ALLE Genres (langsam)
GENRE_AFFINITY_THRESHOLD = 0.3    # Ab hier: Lieblingsgenre-Reaktion
GENRE_AFFINITY_MAX = 1.0          # Maximale Affinitaet

# ============================================================
# BLE Beacon (Social Mode)
# ============================================================
BLE_ENABLED_FILE = os.path.join(APP_DIR, 'social.flag')
BLE_BEACON_INTERVAL = 10      # Sekunden zwischen Beacon-Updates
BLE_NOISY_SIGNATURE = b'NO'   # 2-Byte Signatur zum Erkennen

# ============================================================
# Renderer
# ============================================================
WIDTH = 240
HEIGHT = 240
TARGET_FPS = 15
FRAME_TIME = 1.0 / TARGET_FPS
THERMAL_PATH = '/sys/class/thermal/thermal_zone0/temp'
