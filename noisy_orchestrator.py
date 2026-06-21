#!/usr/bin/env python3
"""
Noisy Orchestrator - Masterprozess

Startet und ueberwacht:
  - noisy_audio.py als Subprocess (crash-isoliert)
  - NoisyRenderer als Thread (direkter Zugriff auf Mood-Daten)
  - Web-UI (Flask) als Thread (Live-Parameter + Modell-Management)

Entscheidet:
  - Fast-Track Impulse (SCARED, LAUGH, FART, EMPATHY)
  - Genre-Fingerprint Matching
  - Accumulator-basierte Mood-Glaettung
  - Kontext-Uebergaenge (SLEEP+Knall, WORK+Tippen, etc.)
  - Idle-Management mit Personality-skaliertem Timeout
  - Mood-Mindestdauer (Moods halten mindestens X Sekunden)
  - Smooth vs harte Uebergaenge (morph_speed)
  - Personality-Updates (Moflin A.E.I.)
"""

import os
import sys
import time
import signal
import random
import logging
import subprocess
import threading
import csv
import datetime
from collections import deque
from logging.handlers import RotatingFileHandler
from multiprocessing import shared_memory, resource_tracker

def _unregister_shm(name):
    """Verhindert dass Python 3.13 resource_tracker unser SHM loescht."""
    try:
        resource_tracker.unregister('/' + name, 'shared_memory')
    except Exception:
        pass

from noisy_config import (
    APP_DIR, LOG_FILE, LOG_LEVEL, LABELS_PATH, BLE_ENABLED_FILE, VERSION,
    SAMPLE_RATE, CONFIDENCE_MIN,
    BORED_TIMEOUT, SLEEP_TIMEOUT,
    ACCUMULATOR_WINDOW, GENRE_THRESHOLD, ACCUMULATOR_SILENCE_CLEAR,
    FAST_TRACK_CONFIDENCE, FINGERPRINT_BOOST,
    PERSONALITY_SAVE_INTERVAL,
    SHM_NAME, SHM_SIZE, DEBUG_MODE, THERMAL_PATH,
    TIME_MORNING, TIME_EVENING, TIME_NIGHT_START, TIME_NIGHT_END,
    SLEEP_TIMEOUT_NIGHT, BORED_TIMEOUT_NIGHT,
    THERMAL_WARM, THERMAL_HOT,
    RMS_SPIKE_THRESHOLD, RMS_SPIKE_HARD,
    CPU_FREQ_IDLE, CPU_FREQ_ACTIVE, CPU_FREQ_PATH,
    NIGHT_ANNOYED_DURATION,
    SOUND_MEMORY_TOP, SOUND_MEMORY_BOOST, SOUND_MEMORY_MIN_COUNT,
)

# Mood-System importieren (registriert alle Gruppen)
from moods import (
    get_mood_by_label, get_mood_name, get_mood_priority,
    is_fast_track, get_all_fingerprints, get_render_data,
    get_group_moods, get_mood,
)
from moods.emotionen import LISTEN, SCARED, LAUGH, SAD, EMPATHY, CURIOUS
from moods.koerper import SLEEP, FART, EAT, EXERCISE
from moods.umgebung import WORK, NATURE, WEATHER, TRAFFIC, HOUSE
from moods.idle import (
    BORED, JOINT, BONG, COFFEE, YAWN, STRETCH, DOZE,
    WATCH, TONGUE, DANCE, MEDITATE, GAME,
)
from moods.musik import MUSIC, ROCK, JAZZ, HIPHOP, REGGAE, PARTY, CHILL, CLASSIC

from noisy_personality import NoisyPersonality
from noisy_runtime import RuntimeConfig

try:
    from noisy_input import NoisyInput
    INPUT_AVAILABLE = True
except ImportError:
    INPUT_AVAILABLE = False

# ============================================================
# Audio-SHM Konstanten (muessen mit noisy_audio.py uebereinstimmen)
# ============================================================
SHM_AUDIO_NAME = 'noisy_audio'
SHM_AUDIO_SIZE = 128
HEADER_SIZE = 4
LABEL_ENTRY_SIZE = 4
MAX_LABELS = 10

# ============================================================
# Mood-Uebergangs-Geschwindigkeiten
# Wird pro Mood-Wechsel gesetzt, Renderer liest morph_speed.
# ============================================================
TRANSITION_INSTANT = 0.30       # Erschrecken, Impuls
TRANSITION_FAST = 0.15          # Lachen, aktive Reaktion
TRANSITION_NORMAL = 0.08        # Standard
TRANSITION_SLOW = 0.04          # Chillig, Musik-Wechsel
TRANSITION_GLACIAL = 0.02       # Einschlafen, Meditieren

# ============================================================
# Mood-Mindestdauer (Sekunden)
# Mood wird mindestens so lange gehalten, ausser ein
# staerkerer Impuls (hoeherer Priority) ueberschreibt ihn.
# ============================================================
MOOD_MIN_DURATION = {
    SCARED: 3.0,
    LAUGH: 4.0,
    FART: 5.0,
    EMPATHY: 4.0,
    SAD: 5.0,
    CURIOUS: 3.0,
    ROCK: 3.0,
    JAZZ: 3.0,
    HIPHOP: 3.0,
    REGGAE: 3.0,
    PARTY: 3.0,
    CHILL: 4.0,
    CLASSIC: 3.0,
    MUSIC: 2.0,
    WORK: 5.0,
    NATURE: 5.0,
    WEATHER: 4.0,
    EAT: 4.0,
    EXERCISE: 3.0,
    SLEEP: 5.0,
}
DEFAULT_MIN_DURATION = 2.0

# ============================================================
# Uebergangs-Geschwindigkeit pro Mood (wie schnell morph)
# ============================================================
TRANSITION_SPEED = {
    # Hart/Instant
    SCARED: TRANSITION_INSTANT,
    FART: TRANSITION_FAST,
    LAUGH: TRANSITION_FAST,
    EMPATHY: TRANSITION_FAST,
    # Normal
    ROCK: TRANSITION_NORMAL,
    HIPHOP: TRANSITION_NORMAL,
    PARTY: TRANSITION_NORMAL,
    EXERCISE: TRANSITION_NORMAL,
    CURIOUS: TRANSITION_NORMAL,
    SAD: TRANSITION_NORMAL,
    LISTEN: TRANSITION_NORMAL,
    # Smooth/Langsam
    JAZZ: TRANSITION_SLOW,
    REGGAE: TRANSITION_SLOW,
    CHILL: TRANSITION_SLOW,
    CLASSIC: TRANSITION_SLOW,
    MUSIC: TRANSITION_SLOW,
    NATURE: TRANSITION_SLOW,
    WEATHER: TRANSITION_SLOW,
    WORK: TRANSITION_SLOW,
    EAT: TRANSITION_SLOW,
    HOUSE: TRANSITION_SLOW,
    TRAFFIC: TRANSITION_SLOW,
    # Ganz langsam
    SLEEP: TRANSITION_GLACIAL,
    BORED: TRANSITION_GLACIAL,
}

# ============================================================
# Logging
# ============================================================
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3)
log_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    handlers=[handler],
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('noisy-orchestrator')
if DEBUG_MODE:
    log.info("=== DEBUG MODE AKTIV (Log auf SD-Karte) ===")
else:
    log.info("Privacy-Logging: /tmp (Ramdisk, stirbt bei Reboot)")

# ============================================================
# Shutdown
# ============================================================
running = True


def signal_handler(sig, frame):
    global running
    log.info("Shutdown-Signal empfangen")
    running = False


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# ============================================================
# Label-Index laden (Index -> Name Mapping)
# ============================================================
def load_label_index(labels_path):
    """Laedt class_labels_indices.csv: {index: display_name}"""
    labels = {}
    try:
        with open(labels_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                idx = int(row['index'])
                name = row['display_name'].strip('"')
                labels[idx] = name
    except Exception as e:
        log.error("Labels laden fehlgeschlagen: %s", e)
    log.info("Label-Index geladen: %d Labels", len(labels))
    return labels


# ============================================================
# Genre Accumulator
# ============================================================
class GenreAccumulator:
    def __init__(self, window_size):
        self.window = deque(maxlen=window_size)

    def add_cycle(self, mood_scores):
        if mood_scores:
            self.window.append(mood_scores)

    def clear(self):
        self.window.clear()

    def get_accumulated(self):
        totals = {}
        for cycle_scores in self.window:
            for mood, score in cycle_scores.items():
                totals[mood] = totals.get(mood, 0) + score
        return totals

    def get_best_mood(self, default=LISTEN):
        totals = self.get_accumulated()
        if not totals:
            return default
        best = max(totals, key=totals.get)
        if totals[best] < GENRE_THRESHOLD:
            return default
        return best


# ============================================================
# Audio-SHM lesen
# ============================================================
def read_audio_shm(buf, label_index):
    """
    Liest Raw-Daten aus Audio-SHM.
    Gibt zurueck: (labels_list, rms_intensity, beat_speed, is_silence)
    oder None wenn keine neuen Daten bereit sind (Ready-Flag 0x04 nicht gesetzt).
    """
    flags = buf[3]

    # Nur lesen wenn Audio neue Daten signalisiert hat (Ready-Flag 0x04)
    if not (flags & 0x04):
        return None

    # Ready-Flag loeschen (Orchestrator hat die Daten abgeholt)
    buf[3] = flags & ~0x04

    n_labels = buf[0]
    rms_intensity = buf[1]
    beat_speed = buf[2]

    is_silence = bool(flags & 0x02)
    labels = []

    if not is_silence and n_labels > 0:
        offset = HEADER_SIZE
        for i in range(min(n_labels, MAX_LABELS)):
            label_id = (buf[offset] << 8) | buf[offset + 1]
            conf = ((buf[offset + 2] << 8) | buf[offset + 3]) / 1000.0
            offset += LABEL_ENTRY_SIZE

            name = label_index.get(label_id, "Unknown_%d" % label_id)
            if conf >= CONFIDENCE_MIN:
                labels.append((name, conf))

    return labels, rms_intensity, beat_speed, is_silence


# ============================================================
# Mood-Scoring (aus Labels)
# ============================================================
def score_labels(labels):
    """
    Berechnet Mood-Scores aus erkannten Labels.
    Gibt zurueck: (cycle_scores, top_label, top_prob, fast_track_mood)
    """
    cycle_scores = {}
    top_label = "Unknown"
    top_prob = 0.0
    fast_track_mood = None
    detected_labels = {}

    for name, prob in labels:
        if prob > top_prob:
            top_label = name
            top_prob = prob
        detected_labels[name] = prob

        mood_id = get_mood_by_label(name)
        if mood_id is None:
            continue

        priority = get_mood_priority(mood_id)
        score = priority * prob
        cycle_scores[mood_id] = cycle_scores.get(mood_id, 0) + score

        # Fast-Track Check
        if is_fast_track(mood_id) and prob > FAST_TRACK_CONFIDENCE:
            if fast_track_mood is None or priority > get_mood_priority(fast_track_mood):
                fast_track_mood = mood_id

    # Genre-Fingerprint Boost
    fingerprints = get_all_fingerprints()
    for genre_id, fp in fingerprints.items():
        hint_count = sum(1 for h in fp["hints"]
                         if detected_labels.get(h, 0) > CONFIDENCE_MIN)
        if hint_count >= fp.get("min_hints", 1):
            old_score = cycle_scores.get(genre_id, 0)
            if old_score > 0:
                boost = old_score * fp["boost"]
            else:
                boost = get_mood_priority(genre_id) * 0.5
            cycle_scores[genre_id] = cycle_scores.get(genre_id, 0) + boost

    return cycle_scores, top_label, top_prob, fast_track_mood


# ============================================================
# Orchestrator
# ============================================================
class NoisyOrchestrator:
    def __init__(self):
        # Laufzeit-Config (Web-UI): Helligkeit, Speed, aktives Modell.
        # Wird mit Renderer (self.orch.rt) und Web-UI geteilt.
        self.rt = RuntimeConfig()
        active = self.rt.get_active_model()

        # Label-Index passend zum AKTIVEN Modell laden
        self.label_index = load_label_index(active['labels'])
        self.personality = NoisyPersonality(logger=log)
        self.accumulator = GenreAccumulator(ACCUMULATOR_WINDOW)

        # State
        self.current_mood = LISTEN
        self.last_mood = LISTEN
        self.mood_start_time = time.time()
        self.silence_start = time.time()
        self.silence_cycles = 0
        self.last_personality_save = time.time()
        self.last_status_log = time.time()
        self.cycle_count = 0

        # Idle-Management (zeitbasiert in Sekunden!)
        self.idle_change_time = time.time() + random.randint(30, 300)
        self.idle_pool = [m for m in get_group_moods("idle") if m != BORED]
        self.current_idle = BORED

        # Thermal
        self.cpu_temp = 45.0
        self.temp_read_counter = 0

        # CPU Frequency Capping
        self.current_cpu_freq = 0

        # Night Gesture
        self.night_annoyed_until = 0

        # Sound Memory (taegliches Kurzzeitgedaechtnis)
        self.sound_memory = {}       # {label_name: count}
        self.sound_memory_day = None # Aktueller Tag (fuer Reset)

        # Genre Affinity Feedback (fuer Renderer)
        self.favorite_playing = False

        # Renderer-Daten (Thread-safe durch GIL)
        self.render_mood_id = LISTEN
        self.render_data = get_render_data(LISTEN)
        self.render_intensity = 0
        self.render_beat = 0
        self.render_morph_speed = TRANSITION_NORMAL

        # Audio Subprocess
        self.audio_process = None
        self.audio_shm = None

        # Mood-SHM (Kompatibilitaet mit externen Prozessen)
        self.mood_shm = None

        # Input Handler (GPIO Buttons)
        self.input_handler = None
        self.show_identity = False      # Fuer Renderer: Identity HUD an/aus
        self.is_muted = False           # Mute/Privacy Modus
        self.is_debug = False           # Debug-Mode (roter Rahmen)
        self.cube_mode = True           # Cube Mode (Display gespiegelt fuer Prism)
        self.is_social = False          # Social Mode (BLE Beacon)
        self.reset_warning_until = 0.0   # Web-UI Passwort-Reset Warnung (Renderer-Overlay)
        self.beacon_thread = None       # BLE Beacon Thread

        # Web-UI (Flask Dashboard)
        self.web_thread = None          # Web-UI Thread
        self.model_switch_requested = False  # Web-UI: Audio mit neuem Modell neu starten

    # ----------------------------------------------------------
    # Mood-Mindestdauer + Priority-Override
    # ----------------------------------------------------------
    def can_change_mood(self, new_mood):
        """
        Prueft ob der aktuelle Mood abgeloest werden darf.
        - Gleicher Mood: kein Wechsel noetig
        - Staerkerer Priority: immer erlaubt (Override)
        - Mindestdauer nicht erreicht: blockiert
        """
        if new_mood == self.current_mood:
            return False

        elapsed = time.time() - self.mood_start_time
        min_dur = MOOD_MIN_DURATION.get(self.current_mood, DEFAULT_MIN_DURATION)

        if elapsed < min_dur:
            new_priority = get_mood_priority(new_mood)
            current_priority = get_mood_priority(self.current_mood)
            if new_priority > current_priority:
                return True
            return False

        return True

    # ----------------------------------------------------------
    # Mood setzen (zentrale Stelle)
    # ----------------------------------------------------------
    def set_mood(self, new_mood, reason=""):
        """Setzt den neuen Mood und aktualisiert alle Render-Daten."""
        old_name = get_mood_name(self.current_mood)
        new_name = get_mood_name(new_mood)

        self.last_mood = self.current_mood
        self.current_mood = new_mood
        self.mood_start_time = time.time()

        # Render-Daten aktualisieren
        self.render_mood_id = new_mood
        self.render_data = get_render_data(new_mood)
        self.render_morph_speed = TRANSITION_SPEED.get(new_mood, TRANSITION_NORMAL)
        self.update_mood_shm()

        log.info("MOOD: %s -> %s | %s", old_name, new_name, reason)

    # ----------------------------------------------------------
    # Audio Subprocess Management
    # ----------------------------------------------------------
    def start_audio(self):
        """Startet noisy_audio.py als Subprocess."""
        audio_script = os.path.join(APP_DIR, 'noisy_audio.py')
        if not os.path.exists(audio_script):
            log.critical("Audio-Script nicht gefunden: %s", audio_script)
            sys.exit(1)

        log.info("Starte Audio-Subprocess: %s", audio_script)
        self.audio_process = subprocess.Popen(
            [sys.executable, audio_script],
            cwd=APP_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("Audio-PID: %d", self.audio_process.pid)

        # Warte auf Audio-SHM
        for attempt in range(30):
            try:
                self.audio_shm = shared_memory.SharedMemory(name=SHM_AUDIO_NAME)
                _unregister_shm(SHM_AUDIO_NAME)
                log.info("Audio-SHM verbunden")
                return True
            except FileNotFoundError:
                time.sleep(0.5)

        log.error("Audio-SHM nicht gefunden nach 15s!")
        return False

    def check_audio(self):
        """Prueft ob Audio-Subprocess noch laeuft, neustart wenn noetig."""
        if self.audio_process is None:
            return False
        ret = self.audio_process.poll()
        if ret is not None:
            log.warning("Audio-Subprocess beendet (Code %s), Neustart...", ret)
            if self.audio_shm:
                try:
                    self.audio_shm.close()
                except Exception:
                    pass
                self.audio_shm = None
            time.sleep(1)
            return self.start_audio()
        return True

    def stop_audio(self):
        """Stoppt Audio-Subprocess."""
        if self.audio_process:
            self.audio_process.terminate()
            try:
                self.audio_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.audio_process.kill()
            log.info("Audio-Subprocess gestoppt")
        if self.audio_shm:
            try:
                self.audio_shm.close()
            except Exception:
                pass

    # ----------------------------------------------------------
    # Modellwechsel (von Web-UI angefordert)
    # ----------------------------------------------------------
    def switch_model(self):
        """
        Fordert einen KI-Modellwechsel an (von der Web-UI aufgerufen).
        Das aktive Modell wurde von der Web-UI bereits in runtime_config.json
        gesetzt. Der eigentliche Audio-Neustart passiert im Haupt-Thread
        (run-Loop), um Thread-Races auf dem Audio-SHM zu vermeiden, das sonst
        gleichzeitig von process_cycle() gelesen wuerde.
        """
        self.model_switch_requested = True
        log.info("Modellwechsel angefordert (deferred auf Haupt-Thread)")

    # ----------------------------------------------------------
    # Mood-SHM (fuer externe Prozesse)
    # ----------------------------------------------------------
    def create_mood_shm(self):
        """Erstellt Mood-SHM fuer externe Nutzung."""
        for attempt in range(10):
            try:
                self.mood_shm = shared_memory.SharedMemory(
                    name=SHM_NAME, create=True, size=SHM_SIZE
                )
                _unregister_shm(SHM_NAME)
                self.mood_shm.buf[0] = LISTEN & 0xFF
                log.info("Mood-SHM erstellt: %s (%d Bytes)", SHM_NAME, SHM_SIZE)
                return True
            except FileExistsError:
                try:
                    old = shared_memory.SharedMemory(name=SHM_NAME)
                    old.close()
                    old.unlink()
                except Exception:
                    pass
                time.sleep(0.5)
        return False

    def update_mood_shm(self):
        """Schreibt aktuellen Mood in SHM (8 Bytes)."""
        if self.mood_shm:
            self.mood_shm.buf[0] = int(self.current_mood) & 0xFF
            self.mood_shm.buf[1] = 0  # Variante (fuer spaeter)
            self.mood_shm.buf[2] = int(self.render_intensity) & 0xFF
            self.mood_shm.buf[3] = int(self.render_beat) & 0xFF
            # Byte 4: Transition-Speed Indikator (0-255)
            speed_byte = min(255, max(0, int(self.render_morph_speed * 850)))
            self.mood_shm.buf[4] = speed_byte
            # Bytes 5-7: Reserved

    # ----------------------------------------------------------
    # Idle-Management (zeitbasiert!)
    # ----------------------------------------------------------
    def update_idle(self):
        """Waehlt random Idle-Animation (zeitbasiert). Timer in echten Sekunden."""
        now = time.time()
        if now >= self.idle_change_time:
            pool = self.get_time_biased_idle_pool()
            if pool:
                self.current_idle = random.choice(pool)
            next_delay = random.randint(30, 300)
            self.idle_change_time = now + next_delay
            tod = self.get_time_of_day()
            log.info("Idle-Wechsel: %s (%s, naechster in %ds)",
                     get_mood_name(self.current_idle), tod, next_delay)

    def get_dynamic_bored_timeout(self):
        """Personality-skalierter BORED_TIMEOUT, nachts kuerzer."""
        affection = self.personality.affection
        scale = 0.5 + affection * 2.0
        base = BORED_TIMEOUT_NIGHT if self.get_time_of_day() == "night" else BORED_TIMEOUT
        return base * scale

    def get_dynamic_sleep_timeout(self):
        """SLEEP_TIMEOUT, nachts kuerzer."""
        if self.get_time_of_day() == "night":
            return SLEEP_TIMEOUT_NIGHT
        return SLEEP_TIMEOUT

    # ----------------------------------------------------------
    # Tageszeit-Bewusstsein
    # ----------------------------------------------------------
    def get_time_of_day(self):
        """Gibt Tageszeit zurueck: morning, evening, night, day."""
        hour = datetime.datetime.now().hour
        if TIME_MORNING[0] <= hour < TIME_MORNING[1]:
            return "morning"
        elif TIME_EVENING[0] <= hour < TIME_EVENING[1]:
            return "evening"
        elif hour >= TIME_NIGHT_START or hour < TIME_NIGHT_END:
            return "night"
        return "day"

    def get_time_biased_idle_pool(self):
        """Idle-Pool nach Tageszeit gewichtet."""
        all_idle = [m for m in get_group_moods("idle") if m != BORED]
        tod = self.get_time_of_day()

        if tod == "morning":
            # Morgens: verschlafen, gaehnen, strecken, Kaffee
            favs = [YAWN, STRETCH, COFFEE, DOZE]
        elif tod == "evening":
            # Abends: ruhig, meditativ, entspannt
            favs = [MEDITATE, DOZE, JOINT, BONG, WATCH]
        elif tod == "night":
            # Nachts: sehr muede, minimal
            favs = [DOZE, MEDITATE]
        else:
            return all_idle

        pool = [m for m in favs if m in all_idle]
        return pool if pool else all_idle

    # ----------------------------------------------------------
    # Thermal
    # ----------------------------------------------------------
    def read_temperature(self):
        """Liest CPU-Temperatur (alle 30 Zyklen)."""
        self.temp_read_counter += 1
        if self.temp_read_counter % 30 == 0:
            try:
                with open(THERMAL_PATH, 'r') as f:
                    self.cpu_temp = int(f.read()) / 1000.0
            except Exception:
                self.cpu_temp = 45.0

    # ----------------------------------------------------------
    # CPU Frequency Capping
    # ----------------------------------------------------------
    def set_cpu_freq(self, freq):
        """Setzt CPU Maximalfrequenz (Frequency Capping)."""
        if freq == self.current_cpu_freq:
            return
        try:
            with open(CPU_FREQ_PATH, 'w') as f:
                f.write(str(freq))
            self.current_cpu_freq = freq
            log.info("CPU Freq: %dMHz", freq // 1000)
        except Exception:
            pass

    # ----------------------------------------------------------
    # Night Annoyed (genervtes Aufwachen)
    # ----------------------------------------------------------
    @property
    def night_annoyed(self):
        """True wenn Noisy gerade nachts genervt aufgewacht ist."""
        return time.time() < self.night_annoyed_until

    # ----------------------------------------------------------
    # Passwort-Reset Warnung (Web-UI -> Display-Overlay)
    # ----------------------------------------------------------
    @property
    def reset_warning(self):
        """True solange die Reset-Warnung auf dem Display laeuft."""
        return time.time() < self.reset_warning_until

    def show_reset_warning(self, seconds):
        """Zeigt eine Passwort-Reset-Warnung mit Countdown auf dem Display.

        Wird vom Web-UI aufgerufen, sobald ein Passwort-Reset bestaetigt
        wurde. Der Renderer liest reset_warning_until und zeichnet das
        Overlay (orange pulsierender Rahmen + Countdown).
        """
        self.reset_warning_until = time.time() + float(seconds)
        log.warning("Display: Passwort-Reset-Warnung fuer %ss", seconds)

    # ----------------------------------------------------------
    # Sound Memory (taegliches Kurzzeitgedaechtnis)
    # ----------------------------------------------------------
    def update_sound_memory(self, top_label):
        """Merkt sich die haeufigsten Sounds des Tages."""
        today = datetime.date.today()
        if self.sound_memory_day != today:
            if self.sound_memory:
                log.info("SOUND MEMORY: Tagesreset (%d verschiedene Sounds gestern)",
                         len(self.sound_memory))
            self.sound_memory.clear()
            self.sound_memory_day = today

        self.sound_memory[top_label] = self.sound_memory.get(top_label, 0) + 1

    def get_sound_memory_boost(self, top_label):
        """Gibt Score-Boost zurueck wenn Sound bekannt ist (Top N heute)."""
        count = self.sound_memory.get(top_label, 0)
        if count < SOUND_MEMORY_MIN_COUNT:
            return 1.0  # Kein Boost

        # Ist der Sound in den Top N?
        if len(self.sound_memory) <= SOUND_MEMORY_TOP:
            return SOUND_MEMORY_BOOST

        sorted_sounds = sorted(self.sound_memory.items(), key=lambda x: -x[1])
        top_names = {name for name, _ in sorted_sounds[:SOUND_MEMORY_TOP]}
        if top_label in top_names:
            return SOUND_MEMORY_BOOST
        return 1.0

    # ----------------------------------------------------------
    # Kontext-Uebergaenge
    # ----------------------------------------------------------
    def apply_context(self, mood_id, top_label, top_prob, rms_intensity):
        """
        Kontextbasierte Mood-Anpassung.
        Beruecksichtigt aktuellen Mood, Personality und Umgebung.
        """
        prev = self.current_mood

        # ----- SCHLAF-UNTERBRECHUNG -----
        # Schlafend + lautes/schreckhaftes Geraeusch = erschrocken aufwachen
        if prev == SLEEP and mood_id in (SCARED, LAUGH, FART):
            log.info("KONTEXT: Aufgewacht durch %s!", top_label)
            self.accumulator.clear()
            # Nachts: genervt statt erschrocken
            if self.get_time_of_day() == "night":
                self.night_annoyed_until = time.time() + NIGHT_ANNOYED_DURATION
                log.info("NIGHT: Genervt aufgewacht (Psst!)")
            return SCARED

        # Schlafend + normales Geraeusch = sanft aufwachen
        if prev == SLEEP and mood_id not in (SLEEP, BORED):
            log.info("KONTEXT: Sanft aufgewacht (%s)", top_label)
            self.accumulator.clear()
            # Nachts: auch genervt bei sanftem Aufwachen
            if self.get_time_of_day() == "night":
                self.night_annoyed_until = time.time() + NIGHT_ANNOYED_DURATION
                log.info("NIGHT: Genervt aufgewacht (leise)")
            return LISTEN

        # ----- WORK-KONTEXT -----
        # Tippen waehrend WORK = Stolz-Boost fuer Personality
        if prev == WORK and mood_id == WORK:
            self.personality.energy = self.personality.clamp(
                self.personality.energy + 0.0003
            )
            self.personality.cheerful = self.personality.clamp(
                self.personality.cheerful + 0.0002
            )

        # WORK + Schreck = unterbrochen
        if prev == WORK and mood_id == SCARED:
            log.info("KONTEXT: Bei der Arbeit erschrocken!")
            return SCARED

        # ----- RMS-SPIKE (ploetzlich laut) -----
        if rms_intensity > RMS_SPIKE_THRESHOLD:
            if prev in (LISTEN, NATURE, WEATHER, CHILL, WORK, SLEEP):
                if mood_id not in (SCARED, LAUGH, FART):
                    # Sehr laut: immer erschrecken. Maessig laut: nur wenn scheu
                    if rms_intensity > RMS_SPIKE_HARD or self.personality.shy > 0.4:
                        log.info("KONTEXT: RMS-Spike (%d) -> SCARED", rms_intensity)
                        return SCARED

        # ----- NATUR-KONTEXT -----
        # Regen + Natur passen zusammen, nicht flippen
        if prev == NATURE and mood_id == WEATHER:
            return NATURE
        if prev == WEATHER and mood_id == NATURE:
            return NATURE

        # ----- ANGST-NACHKLANG -----
        # Nach SCARED erst beruhigen
        if prev == SCARED and mood_id != SCARED:
            elapsed = time.time() - self.mood_start_time
            if elapsed < 2.0:
                return SCARED
            # Nach dem Schreck erstmal zuhoeren
            if mood_id not in (LISTEN, LAUGH):
                log.info("KONTEXT: Nach Schreck beruhigen")
                return LISTEN

        # ----- SAD-TROST -----
        # Lachen waehrend SAD = Aufheiterung
        if prev == SAD and mood_id == LAUGH:
            log.info("KONTEXT: Aufgeheitert durch Lachen!")
            self.personality.cheerful = self.personality.clamp(
                self.personality.cheerful + 0.002
            )
            return LAUGH

        # ----- EMPATHY-NACHSORGE -----
        # Nach Empathie (Husten/Niesen) kurz besorgt bleiben
        if prev == EMPATHY and mood_id not in (EMPATHY, SCARED, LAUGH):
            elapsed = time.time() - self.mood_start_time
            if elapsed < 3.0:
                return EMPATHY

        # ----- CURIOUS-KONTEXT -----
        # Unbekanntes Geraeusch waehrend LISTEN = neugierig (wenn nicht zu scheu)
        if prev == LISTEN and mood_id == CURIOUS:
            if self.personality.shy < 0.6:
                return CURIOUS
            else:
                return LISTEN

        # ----- FEUERZEUG/FEUER -> JOINT (Gelegenheitsraucher) -----
        # Sherpa kennt kein "Lighter" - Feuerzeug wird als Clicking/Finger snapping erkannt.
        # Fire/Crackle = echtes Feuer/Kamin. Nur abends/nachts bei Idle -> Noisy raucht mit.
        idle_group = tuple(get_group_moods("idle"))
        fire_labels = ("Fire", "Crackle", "Clicking", "Finger snapping")
        if top_label in fire_labels and prev in idle_group:
            tod = self.get_time_of_day()
            if tod in ("evening", "night"):
                log.info("KONTEXT: Feuerzeug/Feuer (%s, %s) -> Gelegenheitsraucher!",
                         top_label, tod)
                return JOINT

        # ----- PROST (Flasche/Dose oeffnen) -----
        # Burst/pop oder Pour waehrend Idle/LISTEN = Prost-Moment
        if top_label in ("Burst, pop", "Pour", "Fill (with liquid)"):
            if prev in (LISTEN,) + idle_group:
                log.info("KONTEXT: Prost! (%s)", top_label)
                self.personality.cheerful = self.personality.clamp(
                    self.personality.cheerful + 0.002
                )
                return PARTY

        # ----- HORRORFILM (Scary music -> SCARED) -----
        # Scary music waehrend ruhigem Mood = Horrorfilm-Reaktion
        if top_label == "Scary music" and prev in (LISTEN, CHILL, WATCH):
            if self.personality.shy > 0.3:
                log.info("KONTEXT: Horrorfilm! Scary music -> SCARED")
                return SCARED

        # ----- MUSIK-KONTEXT -----
        musik_moods = (MUSIC, ROCK, JAZZ, HIPHOP, REGGAE, PARTY, CHILL, CLASSIC)

        # Verkehr soll Musik nicht unterbrechen
        if prev in musik_moods and mood_id == TRAFFIC:
            return prev

        # ----- HAUSHALT-KONTEXT -----
        # Kochen + Haushalt = bei EAT bleiben
        if prev == EAT and mood_id == HOUSE:
            return EAT

        # ----- IDLE-KONTEXT -----
        # Idle-Moods nicht von niedrigprioritaeren Moods unterbrechen
        idle_moods = tuple(get_group_moods("idle"))
        if prev in idle_moods and mood_id in (HOUSE, TRAFFIC):
            return prev

        return mood_id

    # ----------------------------------------------------------
    # BLE Beacon (Social Mode)
    # ----------------------------------------------------------
    def _start_beacon(self):
        """Startet BLE Beacon Thread."""
        if self.beacon_thread and self.beacon_thread.is_alive():
            return
        try:
            from noisy_beacon import BeaconThread
            self.beacon_thread = BeaconThread(self)
            self.beacon_thread.start()
            log.info("BLE Beacon gestartet")
        except Exception as e:
            log.error("BLE Beacon Start fehlgeschlagen: %s", e)
            self.beacon_thread = None

    def _stop_beacon(self):
        """Stoppt BLE Beacon Thread."""
        if self.beacon_thread:
            self.beacon_thread.stop()
            self.beacon_thread.join(timeout=5)
            self.beacon_thread = None
            log.info("BLE Beacon gestoppt")

    # ----------------------------------------------------------
    # Hauptschleife: Ein Zyklus
    # ----------------------------------------------------------
    def process_cycle(self):
        """Liest Audio-SHM, entscheidet Mood, aktualisiert alles."""
        if not self.audio_shm:
            time.sleep(0.1)
            return

        # === INPUT VERARBEITUNG ===
        if self.input_handler:
            inp = self.input_handler.process()
            self.show_identity = inp['show_identity']
            self.is_muted = inp['is_muted']
            self.is_debug = inp['is_debug']
            self.cube_mode = inp['cube_mode']

            # Social Mode (BLE Beacon)
            new_social = inp.get('is_social', False)
            if new_social != self.is_social:
                self.is_social = new_social
                if self.is_social:
                    self._start_beacon()
                else:
                    self._stop_beacon()

            # Mute: Noisy schlaeft, keine Inferenz-Verarbeitung
            if self.is_muted:
                if self.current_mood != SLEEP:
                    self.set_mood(SLEEP, "MUTE - Privacy Mode")
                return

            # Flush: Accumulator sofort leeren
            if inp['flush']:
                self.accumulator.clear()
                self.set_mood(LISTEN, "VIBE-CHECK - Accumulator geflusht")
                log.info("Vibe-Check: Accumulator geleert, Neustart")

            # Boost: Stimmungs-Impuls (cheerful + energy kurz hoch)
            if inp['boost']:
                self.personality.cheerful = self.personality.clamp(
                    self.personality.cheerful + 0.01
                )
                self.personality.energy = self.personality.clamp(
                    self.personality.energy + 0.01
                )
                self.personality.affection = self.personality.clamp(
                    self.personality.affection + 0.005
                )
                log.info("Mood-Boost! C=%.2f E=%.2f A=%.2f",
                         self.personality.cheerful, self.personality.energy,
                         self.personality.affection)

        # Audio-Daten lesen (nur wenn neue Daten bereit sind)
        audio_data = read_audio_shm(self.audio_shm.buf, self.label_index)
        if audio_data is None:
            return  # Keine neuen Daten, nichts zu tun

        labels, rms_intensity, beat_speed, is_silence = audio_data

        self.render_intensity = rms_intensity
        self.render_beat = beat_speed
        self.cycle_count += 1

        # === STILLE ===
        if is_silence:
            self.silence_cycles += 1
            silence_duration = time.time() - self.silence_start
            self.set_cpu_freq(CPU_FREQ_IDLE)

            if self.silence_cycles >= ACCUMULATOR_SILENCE_CLEAR:
                self.accumulator.clear()

            bored_timeout = self.get_dynamic_bored_timeout()

            if silence_duration > self.get_dynamic_sleep_timeout():
                new_mood = SLEEP
            elif silence_duration > bored_timeout:
                self.update_idle()
                new_mood = self.current_idle
            else:
                new_mood = self.current_mood

            self.personality.update(new_mood, 0)

            if self.can_change_mood(new_mood):
                if new_mood == SLEEP:
                    self.set_mood(new_mood,
                                  "Eingeschlafen (%.0fs Stille)" % silence_duration)
                elif new_mood != self.current_mood:
                    self.set_mood(new_mood,
                                  "Idle: %s" % get_mood_name(new_mood))
            return

        # === AUDIO AKTIV ===
        self.silence_start = time.time()
        self.silence_cycles = 0
        self.set_cpu_freq(CPU_FREQ_ACTIVE)

        # Scoring
        cycle_scores, top_label, top_prob, fast_track_mood = score_labels(labels)

        # Debug: Top-Labels loggen (nur im Debug-Mode)
        if DEBUG_MODE and labels:
            top3 = labels[:3]
            labels_str = ", ".join("%s(%.0f%%)" % (n, p * 100) for n, p in top3)
            log.debug("LABELS: %s", labels_str)

        # === SOUND MEMORY (taegliches Kurzzeitgedaechtnis) ===
        if top_label != "Unknown":
            self.update_sound_memory(top_label)
            boost = self.get_sound_memory_boost(top_label)
            if boost > 1.0:
                # Bekannten Sound boosten (Score-Multiplikator)
                for mood_id in cycle_scores:
                    cycle_scores[mood_id] *= boost

        # === FAST-TRACK (Impuls-Reaktion) ===
        if fast_track_mood is not None:
            new_mood = self.apply_context(
                fast_track_mood, top_label, top_prob, rms_intensity
            )
            self.accumulator.clear()
            self.accumulator.add_cycle(cycle_scores)

            if new_mood != self.current_mood:
                acc = self.accumulator.get_accumulated()
                scores_str = " ".join(
                    "%s=%.1f" % (get_mood_name(m), s)
                    for m, s in sorted(acc.items(), key=lambda x: -x[1])[:3]
                    if s > 0.5
                )
                self.set_mood(new_mood,
                              "FAST-TRACK %s (%.0f%%) [%s]" % (
                                  top_label, top_prob * 100, scores_str))
        else:
            # === ACCUMULATOR (normaler Weg) ===
            self.accumulator.add_cycle(cycle_scores)
            new_mood = self.accumulator.get_best_mood(default=self.current_mood)
            new_mood = self.apply_context(
                new_mood, top_label, top_prob, rms_intensity
            )

            if self.can_change_mood(new_mood):
                acc = self.accumulator.get_accumulated()
                scores_str = " ".join(
                    "%s=%.1f" % (get_mood_name(m), s)
                    for m, s in sorted(acc.items(), key=lambda x: -x[1])[:4]
                    if s > 0.5
                )
                self.set_mood(new_mood,
                              "%s (%.0f%%) Beat=%d [%s]" % (
                                  top_label, top_prob * 100,
                                  beat_speed, scores_str))

        # Personality
        self.personality.update(self.current_mood, rms_intensity / 255.0)

        # === GENRE AFFINITY (Langzeitgedaechtnis) ===
        self.personality.update_genre_affinity(self.current_mood)
        self.personality.decay_genre_affinity()

        # Lieblingsgenre-Erkennung (fuer Renderer)
        if self.personality.is_favorite_genre(self.current_mood):
            if not self.favorite_playing:
                self.favorite_playing = True
                affinity = self.personality.get_genre_affinity(self.current_mood)
                log.info("FAVORITE: %s (Affinitaet %.0f%%) - Noisy liebt das!",
                         get_mood_name(self.current_mood), affinity * 100)
                # Extra Freude-Boost bei Lieblingsgenre
                self.personality.cheerful = self.personality.clamp(
                    self.personality.cheerful + 0.003
                )
                self.personality.affection = self.personality.clamp(
                    self.personality.affection + 0.001
                )
        else:
            self.favorite_playing = False

        # Thermal-Effekt auf Personality
        self.read_temperature()
        if self.cpu_temp > THERMAL_HOT:
            self.personality.energy = self.personality.clamp(
                self.personality.energy - 0.0005
            )
        elif self.cpu_temp > THERMAL_WARM:
            self.personality.energy = self.personality.clamp(
                self.personality.energy - 0.0002
            )

        # Personality speichern
        if time.time() - self.last_personality_save > PERSONALITY_SAVE_INTERVAL:
            self.personality.save()
            self.last_personality_save = time.time()
            log.info("Personality: E=%.2f C=%.2f S=%.2f A=%.2f | Age: %.1f days",
                     self.personality.energy, self.personality.cheerful,
                     self.personality.shy, self.personality.affection,
                     self.personality.get_age_days())
            # Genre-Affinitaet loggen
            favs = self.personality.get_favorite_genres()
            if favs:
                fav_str = ", ".join("%s=%.0f%%" % (get_mood_name(m), s * 100)
                                    for m, s in favs)
                log.info("Favorites: %s", fav_str)

        # Status-Log
        if time.time() - self.last_status_log > 60:
            log.info("Status: Cycle=%d | Mood=%s | Beat=%d | RMS=%d | "
                     "Trait=%s | %s | %.0fC | Sounds=%d",
                     self.cycle_count, get_mood_name(self.current_mood),
                     beat_speed, rms_intensity,
                     self.personality.get_dominant_trait(),
                     self.get_time_of_day(), self.cpu_temp,
                     len(self.sound_memory))
            self.last_status_log = time.time()

    # ----------------------------------------------------------
    # Run
    # ----------------------------------------------------------
    def run(self):
        log.info("=" * 50)
        log.info("Noisy Orchestrator v%s", VERSION)
        log.info("=" * 50)
        log.info("Personality: Tag %.1f, %d Interaktionen, Trait: %s",
                 self.personality.get_age_days(),
                 self.personality.total_interactions,
                 self.personality.get_dominant_trait())

        # Mood-SHM erstellen
        if not self.create_mood_shm():
            log.critical("Mood-SHM konnte nicht erstellt werden!")
            sys.exit(1)

        # Audio starten
        if not self.start_audio():
            log.critical("Audio konnte nicht gestartet werden!")
            sys.exit(1)

        # Input-Handler starten (GPIO Buttons)
        if INPUT_AVAILABLE:
            try:
                self.input_handler = NoisyInput(self)
                log.info("Input-Handler gestartet (GPIO Buttons)")
            except Exception as e:
                log.warning("Input-Handler fehlgeschlagen: %s", e)
                self.input_handler = None
        else:
            log.info("Input-Handler nicht verfuegbar (kein gpiozero)")

        # Social Mode wiederherstellen (falls social.flag existiert)
        if os.path.exists(BLE_ENABLED_FILE):
            self.is_social = True
            self._start_beacon()
            log.info("Social Mode wiederhergestellt (social.flag vorhanden)")

        # Renderer als Thread starten
        renderer_thread = None
        renderer = None
        try:
            from noisy_render import NoisyRenderer
            renderer = NoisyRenderer(self)
            renderer_thread = threading.Thread(target=renderer.run, daemon=True)
            renderer_thread.start()
            log.info("Renderer-Thread gestartet")
        except Exception as e:
            log.error("Renderer konnte nicht gestartet werden: %s", e)
            log.info("Orchestrator laeuft ohne Renderer (headless)")

        # Web-UI als Thread starten (Flask Dashboard, Port 8080)
        try:
            from web_ui import WebUIThread
            self.web_thread = WebUIThread(self, self.rt)
            self.web_thread.start()
            log.info("Web-UI-Thread gestartet (http://<pi>:8080)")
        except Exception as e:
            log.error("Web-UI konnte nicht gestartet werden: %s", e)
            log.info("Orchestrator laeuft ohne Web-UI weiter")
            self.web_thread = None

        # Health-Check Timer
        last_audio_check = time.time()
        last_renderer_check = time.time()

        try:
            while running:
                # Modellwechsel (von Web-UI angefordert) im Haupt-Thread ausfuehren.
                # Hier statt im Flask-Thread, damit keine Race auf dem Audio-SHM
                # mit process_cycle() entsteht.
                if self.model_switch_requested:
                    self.model_switch_requested = False
                    active = self.rt.get_active_model()
                    log.info("Modellwechsel: Audio neu starten -> %s", active['name'])
                    self.label_index = load_label_index(active['labels'])
                    self.stop_audio()
                    self.audio_shm = None
                    time.sleep(1)
                    if not self.start_audio():
                        log.error("Audio-Neustart nach Modellwechsel fehlgeschlagen!")
                    last_audio_check = time.time()

                self.process_cycle()

                now = time.time()

                # Audio-Subprocess alle 10s pruefen
                if now - last_audio_check > 10:
                    self.check_audio()
                    last_audio_check = now

                # Renderer Health-Check alle 30s
                if renderer_thread and now - last_renderer_check > 30:
                    last_renderer_check = now
                    if not renderer_thread.is_alive():
                        log.warning("Renderer-Thread gestorben! Neustart...")
                        try:
                            from noisy_render import NoisyRenderer
                            renderer = NoisyRenderer(self)
                            renderer_thread = threading.Thread(
                                target=renderer.run, daemon=True
                            )
                            renderer_thread.start()
                            log.info("Renderer-Thread neu gestartet")
                        except Exception as e:
                            log.error("Renderer-Neustart fehlgeschlagen: %s", e)
                            renderer_thread = None

                # Kurze Pause (Audio liefert ~1 Zyklus/Sekunde)
                time.sleep(0.1)

        except KeyboardInterrupt:
            log.info("Keyboard Interrupt")
        except Exception as e:
            log.error("Orchestrator Fehler: %s", e, exc_info=True)
        finally:
            log.info("Orchestrator raeume auf...")
            self._stop_beacon()
            self.personality.save()
            self.stop_audio()
            if self.input_handler:
                self.input_handler.cleanup()
            if self.mood_shm:
                try:
                    self.mood_shm.close()
                    self.mood_shm.unlink()
                except Exception:
                    pass
            log.info("Orchestrator beendet.")


# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    NoisyOrchestrator().run()
