#!/usr/bin/env python3
"""
Noisy Debug Tool v5.0
Live-Analyse per SSH: zeigt KI-Labels, Scores, Fast-Track,
Accumulator, Beat, Personality, System-Monitor.

Nutzt das V5 Mood-System (moods/ Paket) und noisy_config.

Starten:  python3 noisy_debug.py
          noisy stop   (vorher Noisy stoppen, sonst kaempfen
                        beide um das Mikrofon!)
STRG+C zum Beenden.
"""

import os
import sys
import time
import numpy as np
import pyaudio
import sherpa_onnx
from collections import deque
from datetime import datetime

from noisy_config import (
    APP_DIR, LOG_FILE,
    MODEL_PATH, LABELS_PATH,
    SAMPLE_RATE, MODEL_RATE, CHUNK_SIZE, RMS_SILENCE, CONFIDENCE_MIN,
    TARGET_RMS, GAIN_MIN, GAIN_MAX, GAIN_SMOOTHING, GAIN_START, GAIN_SILENCE_RESET,
    ACCUMULATOR_WINDOW, GENRE_THRESHOLD, ACCUMULATOR_SILENCE_CLEAR,
    FAST_TRACK_CONFIDENCE, PERSONALITY_FILE,
    BORED_TIMEOUT, SLEEP_TIMEOUT,
)

# V5 Mood-System importieren (registriert alle Gruppen)
from moods import (
    get_mood_by_label, get_mood_name, get_mood_priority,
    is_fast_track, get_all_fingerprints, get_render_data,
    get_all_moods, get_all_groups, get_group_moods,
    _LABEL_MAP, _IGNORE_LABELS,
)
from moods.emotionen import LISTEN, SCARED, LAUGH, SAD, EMPATHY, CURIOUS
from moods.koerper import SLEEP, FART, EAT, EXERCISE
from moods.umgebung import WORK, NATURE, WEATHER, TRAFFIC, HOUSE
from moods.idle import BORED
from moods.musik import MUSIC, ROCK, JAZZ, HIPHOP, REGGAE, PARTY, CHILL, CLASSIC

from noisy_calibrate import load_calibration

# ============================================================
# Terminal-Farben
# ============================================================
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
GRAY = "\033[90m"
WHITE = "\033[97m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Debug-Log (immer auf SD, nicht Ramdisk - ist ja ein Debug-Tool)
DEBUG_LOG = os.path.join(APP_DIR, 'debug.log')


# ============================================================
# System-Monitoring
# ============================================================
class SystemMonitor:
    def __init__(self):
        self.last_cpu_idle = 0
        self.last_cpu_total = 0
        self.cpu_percent = 0.0
        self.cpu_temp = 0.0
        self.ram_used_mb = 0
        self.ram_total_mb = 0
        self.ram_percent = 0.0

    def update(self):
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                self.cpu_temp = int(f.read()) / 1000.0
        except Exception:
            self.cpu_temp = -1
        try:
            with open('/proc/stat', 'r') as f:
                parts = f.readline().split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])
            diff_idle = idle - self.last_cpu_idle
            diff_total = total - self.last_cpu_total
            if diff_total > 0:
                self.cpu_percent = 100.0 * (1.0 - diff_idle / diff_total)
            self.last_cpu_idle = idle
            self.last_cpu_total = total
        except Exception:
            self.cpu_percent = -1
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            mem = {}
            for line in lines[:5]:
                key, val = line.split(':')
                mem[key.strip()] = int(val.split()[0])
            self.ram_total_mb = mem.get('MemTotal', 0) // 1024
            available = mem.get('MemAvailable', 0) // 1024
            self.ram_used_mb = self.ram_total_mb - available
            if self.ram_total_mb > 0:
                self.ram_percent = 100.0 * self.ram_used_mb / self.ram_total_mb
        except Exception:
            pass

    def format(self):
        temp_color = RED if self.cpu_temp > 70 else YELLOW if self.cpu_temp > 60 else GREEN
        ram_color = RED if self.ram_percent > 85 else YELLOW if self.ram_percent > 70 else GREEN
        return (f"CPU: {self.cpu_percent:.0f}% | "
                f"Temp: {temp_color}{self.cpu_temp:.1f}C{RESET} | "
                f"RAM: {ram_color}{self.ram_used_mb}/{self.ram_total_mb}MB "
                f"({self.ram_percent:.0f}%){RESET}")


# ============================================================
# Inkrementelles Log
# ============================================================
class ChangeLogger:
    def __init__(self, filepath):
        self.filepath = filepath
        self.last_sys_str = ""
        self.f = open(filepath, 'a')
        self.log("=== Noisy Debug v5.0 gestartet ===")

    def ts(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, msg):
        self.f.write("[%s] %s\n" % (self.ts(), msg))
        self.f.flush()

    def log_mood_change(self, old_mood, new_mood, reason, top_label, top_prob, gain, accum_scores):
        old_name = get_mood_name(old_mood)
        new_name = get_mood_name(new_mood)
        scores_str = " ".join(
            "%s=%.1f" % (get_mood_name(m), s)
            for m, s in sorted(accum_scores.items(), key=lambda x: -x[1])[:4]
            if s > 0.5
        )
        self.log("MOOD: %s -> %s | %s | Top: %s (%.0f%%) | Gain: %.1fx | [%s]"
                 % (old_name, new_name, reason, top_label, top_prob * 100, gain, scores_str))

    def log_gain_change(self, old_gain, new_gain, rms_raw):
        self.log("GAIN: %.0fx -> %.0fx | RMS_raw: %.6f" % (old_gain, new_gain, rms_raw))

    def log_system(self, sys_str):
        # Strip ANSI codes for log file
        clean = sys_str
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', clean)
        if clean != self.last_sys_str:
            self.log("SYS: %s" % clean)
            self.last_sys_str = clean

    def close(self):
        self.log("=== Noisy Debug beendet ===")
        self.f.close()


# ============================================================
# Genre Accumulator (identisch mit Orchestrator)
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
            return default, totals
        best = max(totals, key=totals.get)
        if totals[best] < GENRE_THRESHOLD:
            return default, totals
        return best, totals


# ============================================================
# Beat-Detektor (identisch mit noisy_audio.py)
# ============================================================
class BeatDetector:
    def __init__(self, chunk_size, sample_rate):
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.sub_window = max(1, sample_rate // 20)
        self.last_beat_speed = 0

    def detect(self, samples):
        n_windows = len(samples) // self.sub_window
        if n_windows < 2:
            return self.last_beat_speed
        energies = []
        for i in range(n_windows):
            chunk = samples[i * self.sub_window:(i + 1) * self.sub_window]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            energies.append(rms)
        if not energies:
            return self.last_beat_speed
        mean_e = np.mean(energies)
        peaks = 0
        for i in range(1, len(energies) - 1):
            if energies[i] > energies[i - 1] and energies[i] > energies[i + 1]:
                if energies[i] > mean_e * 1.2:
                    peaks += 1
        peaks_per_sec = peaks * (self.sample_rate / len(samples))
        speed = min(255, int(peaks_per_sec * 25.5))
        self.last_beat_speed = int(self.last_beat_speed * 0.6 + speed * 0.4)
        return self.last_beat_speed


# ============================================================
# Scoring (V5 - nutzt Mood-Registry)
# ============================================================
def score_labels(results):
    """
    Berechnet Mood-Scores aus Sherpa-Results.
    Gibt zurueck: (cycle_scores, top_label, top_prob, fast_track_mood)
    Identisch mit Orchestrator-Logik.
    """
    cycle_scores = {}
    top_label = "Unknown"
    top_prob = 0.0
    fast_track_mood = None
    detected_labels = {}

    for r in results:
        name = r.name
        prob = r.prob

        if prob > top_prob:
            top_label = name
            top_prob = prob
        detected_labels[name] = prob

        if prob < CONFIDENCE_MIN:
            continue

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
# Personality anzeigen
# ============================================================
def show_personality():
    """Laedt und zeigt die aktuelle Personality."""
    try:
        import json
        with open(PERSONALITY_FILE, 'r') as f:
            data = json.load(f)
        age = (time.time() - data.get('birth_time', time.time())) / 86400
        total = data.get('total_interactions', 0)
        e = data.get('energy', 0.5)
        c = data.get('cheerful', 0.5)
        s = data.get('shy', 0.5)
        a = data.get('affection', 0.5)

        def bar(v, width=15):
            filled = int(v * width)
            return "%s%s" % ("#" * filled, "." * (width - filled))

        print("  %sPersonality:%s E=%.2f [%s] C=%.2f [%s] S=%.2f [%s] A=%.2f [%s]"
              % (DIM, RESET, e, bar(e), c, bar(c), s, bar(s), a, bar(a)))
        print("  %sAlter: %.1f Tage | Interaktionen: %d%s"
              % (DIM, age, total, RESET))
    except Exception as ex:
        print("  %sPersonality nicht lesbar: %s%s" % (YELLOW, ex, RESET))


# ============================================================
# Mood-Registry anzeigen
# ============================================================
def show_mood_registry():
    """Zeigt die registrierten Moods und Label-Coverage."""
    total_moods = len(get_all_moods())
    mapped = len(_LABEL_MAP)
    ignored = len(_IGNORE_LABELS)

    print("  %sMoods: %d in %d Gruppen | Labels: %d mapped + %d ignoriert = %d/527%s"
          % (DIM, total_moods, len(get_all_groups()), mapped, ignored, mapped + ignored, RESET))

    for g in get_all_groups():
        ids = get_group_moods(g)
        names = [get_mood_name(i) for i in ids]
        ft = [get_mood_name(i) for i in ids if is_fast_track(i)]
        ft_str = " %s[FT: %s]%s" % (RED, ", ".join(ft), RESET) if ft else ""
        print("  %s  %-12s: %s%s%s" % (DIM, g, ", ".join(names), RESET, ft_str))


# ============================================================
# RMS-Bar zeichnen
# ============================================================
def rms_bar(rms, threshold, width=30):
    """Zeichnet eine visuelle RMS-Anzeige mit Schwelle."""
    level = min(1.0, rms * 200)  # Skaliert fuer Sichtbarkeit
    filled = int(level * width)
    thresh_pos = min(width - 1, int(threshold * 200 * width))

    bar_chars = []
    for i in range(width):
        if i < filled:
            if i >= thresh_pos:
                bar_chars.append("%s#%s" % (GREEN, RESET))
            else:
                bar_chars.append("%s#%s" % (RED, RESET))
        elif i == thresh_pos:
            bar_chars.append("%s|%s" % (YELLOW, RESET))
        else:
            bar_chars.append("%s.%s" % (GRAY, RESET))

    return "".join(bar_chars)


# ============================================================
# Main
# ============================================================
def main():
    print()
    print("%s%s=== Noisy Debug Tool v5.0 ===%s" % (BOLD, CYAN, RESET))
    print("%sLive KI-Analyse | Fast-Track | Accumulator | Beat | System%s" % (BOLD, RESET))
    print()

    # Pruefe ob Noisy laeuft
    try:
        import subprocess
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "noisy.service"],
            capture_output=True
        )
        if result.returncode == 0:
            print("%s%s  WARNUNG: Noisy Service laeuft noch!%s" % (BOLD, RED, RESET))
            print("  Beide kaempfen um das Mikrofon. Stoppe mit: noisy stop")
            print()
    except Exception:
        pass

    if not os.path.exists(MODEL_PATH):
        print("%sFEHLER: Modell nicht gefunden: %s%s" % (RED, MODEL_PATH, RESET))
        sys.exit(1)

    # Mood-Registry
    show_mood_registry()
    print()

    # Personality
    show_personality()
    print()

    # Tagger laden
    print("  Lade Modell...")
    model_config = sherpa_onnx.AudioTaggingModelConfig(
        zipformer=sherpa_onnx.OfflineZipformerAudioTaggingModelConfig(model=MODEL_PATH),
        num_threads=2,
    )
    config = sherpa_onnx.AudioTaggingConfig(model=model_config, labels=LABELS_PATH, top_k=10)
    tagger = sherpa_onnx.AudioTagging(config=config)
    print("  %sTagger OK (int8, 2 threads)%s" % (GREEN, RESET))

    # Mikrofon
    pa = pyaudio.PyAudio()
    mic_index = None
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0 and 'usb' in info['name'].lower():
            mic_index = i
            print("  USB Mikrofon: [%d] %s" % (i, info['name']))
            break
    if mic_index is None:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                mic_index = i
                print("  Fallback Mikrofon: [%d] %s" % (i, info['name']))
                break
    if mic_index is None:
        print("%sKein Mikrofon!%s" % (RED, RESET))
        sys.exit(1)

    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
        input=True, input_device_index=mic_index,
        frames_per_buffer=8000,
    )
    print("  %sMikrofon OK @ %dHz%s" % (GREEN, SAMPLE_RATE, RESET))

    # Init
    sysmon = SystemMonitor()
    sysmon.update()
    logger = ChangeLogger(DEBUG_LOG)
    accumulator = GenreAccumulator(ACCUMULATOR_WINDOW)
    beat_detector = BeatDetector(CHUNK_SIZE, SAMPLE_RATE)
    current_gain = GAIN_START
    last_mood = LISTEN
    last_gain_rounded = round(current_gain)
    cycle = 0
    silence_cycles = 0
    silence_start = time.time()

    # Kalibrierung laden
    rms_silence = load_calibration(fallback=RMS_SILENCE)
    cal_info = "(kalibriert)" if rms_silence != RMS_SILENCE else "(Fallback)"

    print()
    print("  %sConfig:%s" % (DIM, RESET))
    print("    Auto-Gain: Ziel=%.2f, Range=%.0f-%.0fx, Start=%.0fx"
          % (TARGET_RMS, GAIN_MIN, GAIN_MAX, GAIN_START))
    print("    Accumulator: Window=%d, Threshold=%.1f, Silence-Clear=%d"
          % (ACCUMULATOR_WINDOW, GENRE_THRESHOLD, ACCUMULATOR_SILENCE_CLEAR))
    print("    Fast-Track: Confidence > %.0f%%" % (FAST_TRACK_CONFIDENCE * 100))
    print("    Stille-Schwelle: %.6f %s" % (rms_silence, cal_info))
    print("    Bored: %ds | Sleep: %ds" % (BORED_TIMEOUT, SLEEP_TIMEOUT))
    print("    System: %s" % sysmon.format())
    print("    Log: %s" % DEBUG_LOG)

    logger.log("Config: Gain=%.0fx, Window=%d, Threshold=%.1f, FT=%.2f"
               % (current_gain, ACCUMULATOR_WINDOW, GENRE_THRESHOLD, FAST_TRACK_CONFIDENCE))
    logger.log("System: %s" % sysmon.format())

    print()
    print("%s%s" % (BOLD, "=" * 74))
    print("LIVE ANALYSE - STRG+C zum Beenden")
    print("=" * 74 + RESET)
    print()
    print("  Legende:")
    print("    %s>>>%s = Mood-Wechsel  |  %sFT!%s = Fast-Track  |  %s---%s = Nicht gemappt"
          % (CYAN, RESET, RED, RESET, GRAY, RESET))
    print("    RMS-Bar: %s#%s = unter Schwelle  %s|%s = Schwelle  %s#%s = ueber Schwelle"
          % (RED, RESET, YELLOW, RESET, GREEN, RESET))
    print()

    try:
        while True:
            cycle += 1

            # Audio lesen
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception as e:
                print("%s  Audio Read Fehler: %s%s" % (RED, e, RESET))
                time.sleep(0.5)
                continue

            samples_raw = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            rms_raw = float(np.sqrt(np.mean(samples_raw ** 2)))
            rms_intensity = min(255, int(rms_raw * 5000))

            # === STILLE ===
            if rms_raw < rms_silence:
                silence_cycles += 1
                silence_duration = time.time() - silence_start

                # Gain Reset
                if silence_cycles >= 3:
                    if round(current_gain) != round(GAIN_SILENCE_RESET):
                        old_g = round(current_gain)
                        current_gain = GAIN_SILENCE_RESET
                        last_gain_rounded = round(current_gain)
                        logger.log_gain_change(old_g, current_gain, rms_raw)

                # Accumulator Clear
                if silence_cycles == ACCUMULATOR_SILENCE_CLEAR:
                    accumulator.clear()

                # Stille-Status alle 10 Zyklen anzeigen
                if silence_cycles % 10 == 1:
                    ts = datetime.now().strftime("%H:%M:%S")
                    bar = rms_bar(rms_raw, rms_silence)
                    state = "SLEEP" if silence_duration > SLEEP_TIMEOUT else \
                            "BORED" if silence_duration > BORED_TIMEOUT else "STILLE"
                    print("%s  [%s] #%d | %s [%s] | RMS: %.6f (I=%d) | %s %.0fs | Gain: %.0fx%s"
                          % (GRAY, ts, cycle, bar, state, rms_raw, rms_intensity,
                             state, silence_duration, current_gain, RESET))

                continue

            # === AUDIO AKTIV ===
            silence_cycles = 0
            silence_start = time.time()

            # Auto-Gain
            if rms_raw > 0.0001:
                ideal_gain = TARGET_RMS / rms_raw
                ideal_gain = max(GAIN_MIN, min(GAIN_MAX, ideal_gain))
                current_gain = current_gain * (1.0 - GAIN_SMOOTHING) + ideal_gain * GAIN_SMOOTHING

            samples_boosted = np.clip(samples_raw * current_gain, -1.0, 1.0)

            # Gain-Aenderung loggen
            gain_rounded = round(current_gain)
            if gain_rounded != last_gain_rounded:
                logger.log_gain_change(last_gain_rounded, current_gain, rms_raw)
                last_gain_rounded = gain_rounded

            # Beat-Detection
            beat_speed = beat_detector.detect(samples_boosted)

            # Resampling 44100 -> 16000
            target_len = int(len(samples_boosted) * MODEL_RATE / SAMPLE_RATE)
            samples_16k = np.interp(
                np.linspace(0, len(samples_boosted), target_len, endpoint=False),
                np.arange(len(samples_boosted)),
                samples_boosted
            ).astype(np.float32)

            # KI Inferenz
            t_start = time.time()
            tag_stream = tagger.create_stream()
            tag_stream.accept_waveform(MODEL_RATE, samples_16k)
            results = tagger.compute(tag_stream)
            inf_time = time.time() - t_start

            # V5 Scoring
            cycle_scores, top_label, top_prob, fast_track_mood = score_labels(results)

            # Accumulator
            accumulator.add_cycle(cycle_scores)
            acc_mood, acc_totals = accumulator.get_best_mood(default=last_mood)

            # Fast-Track ueberschreibt Accumulator
            reason = "ACCUM"
            if fast_track_mood is not None:
                acc_mood = fast_track_mood
                reason = "FAST-TRACK"
                accumulator.clear()
                accumulator.add_cycle(cycle_scores)

            mood_changed = acc_mood != last_mood

            # === IMMER ANZEIGEN (das ist ein Debug-Tool!) ===
            ts = datetime.now().strftime("%H:%M:%S")

            # Zeile 1: Header
            bar = rms_bar(rms_raw, rms_silence)
            ft_marker = "%s FT!%s" % (RED, RESET) if fast_track_mood else "    "
            mood_marker = "%s%s>>>%s" % (BOLD, CYAN, RESET) if mood_changed else "   "
            beat_bar = "#" * min(20, beat_speed // 13) if beat_speed > 0 else ""

            print("%s [%s] #%d | %s | RMS: %.4f (I=%d) x%.0f | %s%.2fs%s | Beat: %d %s%s%s"
                  % (mood_marker, ts, cycle, bar, rms_raw, rms_intensity,
                     current_gain, DIM, inf_time, RESET,
                     beat_speed, MAGENTA, beat_bar, RESET))

            # Zeile 2: Mood-Wechsel
            if mood_changed:
                old_name = get_mood_name(last_mood)
                new_name = get_mood_name(acc_mood)
                rd = get_render_data(acc_mood)
                color = rd["body"].get("color", (0, 0, 0))
                print("    %s%sMOOD: %s -> %s [%s] | Farbe: RGB(%d,%d,%d)%s"
                      % (BOLD, CYAN, old_name, new_name, reason,
                         color[0], color[1], color[2], RESET))

            # Zeile 3: Top-5 Labels
            for rank, r in enumerate(results[:5], 1):
                mood_id = get_mood_by_label(r.name)

                if mood_id is not None:
                    mname = get_mood_name(mood_id)
                    ft = is_fast_track(mood_id)
                    ft_tag = " %s[FT]%s" % (RED, RESET) if ft else ""

                    if r.prob >= CONFIDENCE_MIN:
                        # Gemappt + ueber Schwelle = aktiv
                        print("    %s%d. %-35s %6.1f%%  -> %s%s%s%s"
                              % (GREEN, rank, r.name, r.prob * 100, mname, ft_tag, RESET, ""))
                    else:
                        # Gemappt aber zu leise
                        print("    %s%d. %-35s %6.1f%%  -> %s (zu leise)%s"
                              % (YELLOW, rank, r.name, r.prob * 100, mname, RESET))
                elif r.name in _IGNORE_LABELS:
                    # Explizit ignoriert
                    print("    %s%d. %-35s %6.1f%%  -> [ignoriert]%s"
                          % (GRAY, rank, r.name, r.prob * 100, RESET))
                else:
                    # Nicht gemappt
                    print("    %s%d. %-35s %6.1f%%  -> ---%s"
                          % (GRAY, rank, r.name, r.prob * 100, RESET))

            # Zeile 4: Accumulator-Stand
            acc_str = " | ".join(
                "%s=%.1f" % (get_mood_name(m), s)
                for m, s in sorted(acc_totals.items(), key=lambda x: -x[1])[:5]
                if s > 0.5
            )
            if acc_str:
                print("    %sAccum: [%s]%s" % (DIM, acc_str, RESET))

            # Warnung: Labels ueber Schwelle aber nicht gemappt
            unmapped = [r for r in results
                        if r.name not in _LABEL_MAP
                        and r.name not in _IGNORE_LABELS
                        and r.prob >= 0.10]
            if unmapped:
                names = ", ".join('"%s"(%.0f%%)' % (r.name, r.prob * 100) for r in unmapped)
                print("    %sUNMAPPED >10%%: %s%s" % (YELLOW, names, RESET))

            # System alle 30 Zyklen
            if cycle % 30 == 0:
                sysmon.update()
                print("    %s%s%s" % (DIM, sysmon.format(), RESET))

            # Mood loggen
            if mood_changed:
                logger.log_mood_change(last_mood, acc_mood, reason,
                                       top_label, top_prob, current_gain, acc_totals)
                last_mood = acc_mood

            # System-Log alle 60 Zyklen
            if cycle % 60 == 0:
                sysmon.update()
                logger.log_system(sysmon.format())

            # Puffer-Flush
            try:
                avail = stream.get_read_available()
                if avail > 0:
                    stream.read(avail, exception_on_overflow=False)
            except Exception:
                pass

            print()

    except KeyboardInterrupt:
        print()
        print("%s%sDebug beendet nach %d Zyklen.%s" % (BOLD, CYAN, cycle, RESET))
        sysmon.update()
        print("  %s" % sysmon.format())
        print()
        show_personality()
        print()
    finally:
        logger.close()
        try:
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
