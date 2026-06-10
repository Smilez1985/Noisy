#!/usr/bin/env python3
"""
Noisy Audio Processor v5.0 (Schlank)
Nur: Mikrofon -> Gain -> Inferenz -> Raw-Daten in SHM

Entscheidungen (Mood, Fast-Track, Accumulator) macht der Orchestrator.
Dieser Prozess laeuft als Subprocess, isoliert vom Orchestrator.

SHM Layout (geschrieben von Audio):
  Byte 0:     Anzahl Labels in diesem Zyklus (0-10)
  Byte 1:     RMS-Intensity (0-255)
  Byte 2:     Beat-Speed (0-255)
  Byte 3:     Flags (Bit 0: Audio aktiv, Bit 1: Stille, Bit 2: Neue Daten bereit)
  Byte 4-end: Label-Daten (je 4 Bytes: 2 Label-ID + 2 Confidence*1000)
"""

import os
import sys
import time
import signal
import struct
import logging
import numpy as np
import pyaudio
import sherpa_onnx
from logging.handlers import RotatingFileHandler

from noisy_config import (
    MODEL_PATH, LABELS_PATH, AUDIO_LOG_FILE, LOG_LEVEL, DEBUG_MODE,
    SAMPLE_RATE, MODEL_RATE, CHUNK_SIZE, RMS_SILENCE,
    TARGET_RMS, GAIN_MIN, GAIN_MAX, GAIN_SMOOTHING, GAIN_START, GAIN_SILENCE_RESET,
    CONFIDENCE_MIN,
)

# ============================================================
# Konstanten
# ============================================================
SHM_AUDIO_NAME = 'noisy_audio'
SHM_AUDIO_SIZE = 128        # 4 Header + 10 Labels * 4 Bytes + Reserve
HEADER_SIZE = 4
LABEL_ENTRY_SIZE = 4         # 2 Bytes Label-ID + 2 Bytes Confidence
MAX_LABELS = 10

# ============================================================
# Logging
# ============================================================
os.makedirs(os.path.dirname(AUDIO_LOG_FILE), exist_ok=True)
handler = RotatingFileHandler(AUDIO_LOG_FILE, maxBytes=1024 * 1024, backupCount=3)
log_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    handlers=[handler],
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('noisy-audio')

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
# Label Name -> Index Lookup (fuer robuste SHM-Kodierung)
# ============================================================
def load_name_to_index():
    """Laedt class_labels_indices.csv als {display_name: index} dict."""
    import csv
    name2idx = {}
    try:
        with open(LABELS_PATH, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                idx = int(row['index'])
                name = row['display_name'].strip('"')
                name2idx[name] = idx
        log.info("Label-Index geladen: %d Labels", len(name2idx))
    except Exception as e:
        log.error("Label-Index laden fehlgeschlagen: %s", e)
    return name2idx

NAME_TO_INDEX = load_name_to_index()


# ============================================================
# Shared Memory (Audio -> Orchestrator)
# ============================================================
def _unregister_shm(name):
    """Verhindert dass Python 3.13 resource_tracker unser SHM loescht."""
    try:
        from multiprocessing import resource_tracker
        resource_tracker.unregister('/' + name, 'shared_memory')
    except Exception:
        pass

def create_audio_shm():
    from multiprocessing import shared_memory
    for attempt in range(10):
        try:
            shm = shared_memory.SharedMemory(
                name=SHM_AUDIO_NAME, create=True, size=SHM_AUDIO_SIZE
            )
            _unregister_shm(SHM_AUDIO_NAME)
            log.info("Audio-SHM erstellt: %s (%d Bytes)", SHM_AUDIO_NAME, SHM_AUDIO_SIZE)
            return shm
        except FileExistsError:
            try:
                old = shared_memory.SharedMemory(name=SHM_AUDIO_NAME)
                old.close()
                old.unlink()
            except Exception:
                pass
            time.sleep(0.5)
        except Exception as e:
            log.error("SHM Fehler (Versuch %d): %s", attempt + 1, e)
            time.sleep(1)
    log.critical("Audio-SHM konnte nicht erstellt werden!")
    sys.exit(1)


# ============================================================
# Mikrofon
# ============================================================
def open_microphone():
    pa = pyaudio.PyAudio()
    mic_index = None
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0 and 'usb' in info['name'].lower():
            mic_index = i
            log.info("USB Mikrofon: [%d] %s", i, info['name'])
            break
    if mic_index is None:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                mic_index = i
                log.info("Fallback Mikrofon: [%d] %s", i, info['name'])
                break
    if mic_index is None:
        log.critical("Kein Mikrofon gefunden!")
        sys.exit(1)
    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
        input=True, input_device_index=mic_index,
        frames_per_buffer=8000,
    )
    return pa, stream


# ============================================================
# Audio Tagger
# ============================================================
def create_tagger():
    if not os.path.exists(MODEL_PATH):
        log.critical("Modell nicht gefunden: %s", MODEL_PATH)
        sys.exit(1)
    if not os.path.exists(LABELS_PATH):
        log.critical("Labels nicht gefunden: %s", LABELS_PATH)
        sys.exit(1)
    config = sherpa_onnx.AudioTaggingConfig(
        model=sherpa_onnx.AudioTaggingModelConfig(
            zipformer=sherpa_onnx.OfflineZipformerAudioTaggingModelConfig(model=MODEL_PATH),
            num_threads=2,
        ),
        labels=LABELS_PATH,
        top_k=MAX_LABELS,
    )
    tagger = sherpa_onnx.AudioTagging(config=config)
    log.info("Tagger geladen (int8, 2 threads, top_k=%d)", MAX_LABELS)
    return tagger


# ============================================================
# Kalibrierung laden
# ============================================================
def load_calibration():
    try:
        import json
        from noisy_config import CALIBRATION_FILE
        if os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            val = data.get('rms_silence', RMS_SILENCE)
            log.info("Kalibrierung geladen: %.6f", val)
            return val
    except Exception as e:
        log.warning("Kalibrierung laden fehlgeschlagen: %s", e)
    return RMS_SILENCE


# ============================================================
# Beat-Detektor (RMS-Peak-Zaehlung)
# ============================================================
class BeatDetector:
    """Zaehlt RMS-Peaks pro Chunk fuer Beat-Geschwindigkeit."""

    def __init__(self, chunk_size, sample_rate):
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.sub_window = max(1, sample_rate // 20)  # 50ms Fenster
        self.last_beat_speed = 0

    def detect(self, samples):
        """Gibt Beat-Speed als 0-255 zurueck."""
        n_windows = len(samples) // self.sub_window
        if n_windows < 2:
            return self.last_beat_speed

        # RMS pro Sub-Window
        energies = []
        for i in range(n_windows):
            chunk = samples[i * self.sub_window:(i + 1) * self.sub_window]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            energies.append(rms)

        if not energies:
            return self.last_beat_speed

        # Peaks zaehlen (lokale Maxima)
        mean_e = np.mean(energies)
        peaks = 0
        for i in range(1, len(energies) - 1):
            if energies[i] > energies[i - 1] and energies[i] > energies[i + 1]:
                if energies[i] > mean_e * 1.2:
                    peaks += 1

        # Peaks/Sekunde -> BPM-aehnlich -> 0-255
        peaks_per_sec = peaks * (self.sample_rate / len(samples))
        # 0-10 Peaks/s -> 0-255
        speed = min(255, int(peaks_per_sec * 25.5))

        # Glaetten
        self.last_beat_speed = int(self.last_beat_speed * 0.6 + speed * 0.4)
        return self.last_beat_speed


# ============================================================
# SHM schreiben
# ============================================================
def write_shm(buf, results, rms_intensity, beat_speed, is_silence):
    """
    Schreibt Audio-Daten in Shared Memory.
    Header: [n_labels, rms_intensity, beat_speed, flags]
    Labels: je 4 Bytes [label_id_hi, label_id_lo, conf_hi, conf_lo]
    """
    n_labels = min(len(results), MAX_LABELS) if not is_silence else 0
    flags = 0
    if not is_silence:
        flags |= 0x01  # Audio aktiv
    else:
        flags |= 0x02  # Stille

    # Erst Daten schreiben (OHNE Ready-Flag)
    buf[0] = n_labels
    buf[1] = min(255, max(0, rms_intensity))
    buf[2] = min(255, max(0, beat_speed))

    # Label-Daten
    offset = HEADER_SIZE
    for i in range(n_labels):
        r = results[i]
        # Robustes Label-ID Lookup: Name -> Index (aus CSV)
        # Fallback auf r.index, letzter Fallback 0 (statt Loop-Index)
        label_id = NAME_TO_INDEX.get(r.name, getattr(r, 'index', 0))
        conf = int(r.prob * 1000)
        buf[offset] = (label_id >> 8) & 0xFF
        buf[offset + 1] = label_id & 0xFF
        buf[offset + 2] = (conf >> 8) & 0xFF
        buf[offset + 3] = conf & 0xFF
        offset += LABEL_ENTRY_SIZE

    # ZULETZT: Ready-Flag setzen (0x04) - signalisiert dem Orchestrator
    # dass neue Daten komplett bereit sind
    flags |= 0x04
    buf[3] = flags


# ============================================================
# Main
# ============================================================
def main():
    log.info("=" * 50)
    log.info("Noisy Audio Processor v5.0 (Schlank)")
    log.info("=" * 50)

    shm = create_audio_shm()
    buf = shm.buf

    tagger = create_tagger()
    pa, stream = open_microphone()
    beat_detector = BeatDetector(CHUNK_SIZE, SAMPLE_RATE)

    rms_silence = load_calibration()
    log.info("Stille-Schwelle: %.6f", rms_silence)

    current_gain = GAIN_START
    silence_cycles = 0
    inference_count = 0
    last_gain_log = round(current_gain)
    last_status = time.time()

    log.info("Auto-Gain: Target=%.2f, Range=%.0f-%.0fx, Start=%.0fx",
             TARGET_RMS, GAIN_MIN, GAIN_MAX, GAIN_START)

    try:
        while running:
            # Audio lesen
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception as e:
                log.warning("Audio Read Fehler: %s", e)
                time.sleep(0.5)
                continue

            samples_raw = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            rms_raw = float(np.sqrt(np.mean(samples_raw ** 2)))

            # RMS -> Intensity (0-255)
            rms_intensity = min(255, int(rms_raw * 5000))

            # === STILLE ===
            if rms_raw < rms_silence:
                silence_cycles += 1
                if silence_cycles >= 3:
                    current_gain = GAIN_SILENCE_RESET

                # Beat bleibt 0 bei Stille
                write_shm(buf, [], rms_intensity, 0, is_silence=True)
                continue

            # === AUDIO AKTIV ===
            silence_cycles = 0

            # Auto-Gain
            if rms_raw > 0.0001:
                ideal_gain = TARGET_RMS / rms_raw
                ideal_gain = max(GAIN_MIN, min(GAIN_MAX, ideal_gain))
                current_gain = current_gain * (1.0 - GAIN_SMOOTHING) + ideal_gain * GAIN_SMOOTHING

            samples_boosted = np.clip(samples_raw * current_gain, -1.0, 1.0)

            # Gain-Log
            gain_rounded = round(current_gain)
            if gain_rounded != last_gain_log:
                log.info("GAIN: %dx -> %dx | RMS: %.6f", last_gain_log, gain_rounded, rms_raw)
                last_gain_log = gain_rounded

            # Beat-Detection (auf rohen Samples, vor Resampling)
            beat_speed = beat_detector.detect(samples_boosted)

            # Resampling 44100 -> 16000
            target_len = int(len(samples_boosted) * MODEL_RATE / SAMPLE_RATE)
            samples_16k = np.interp(
                np.linspace(0, len(samples_boosted), target_len, endpoint=False),
                np.arange(len(samples_boosted)),
                samples_boosted
            ).astype(np.float32)

            # Inferenz
            tag_stream = tagger.create_stream()
            tag_stream.accept_waveform(MODEL_RATE, samples_16k)
            results = tagger.compute(tag_stream)
            inference_count += 1

            # In SHM schreiben
            write_shm(buf, results, rms_intensity, beat_speed, is_silence=False)

            # Puffer-Flush
            try:
                avail = stream.get_read_available()
                if avail > 0:
                    stream.read(avail, exception_on_overflow=False)
            except Exception:
                pass

            # Status-Log
            if inference_count % 30 == 0:
                top = results[0] if results else None
                top_name = top.name if top else "?"
                top_prob = top.prob if top else 0
                log.info("Audio #%d | %s (%.0f%%) | Gain: %.0fx | RMS: %.4f | Beat: %d",
                         inference_count, top_name, top_prob * 100,
                         current_gain, rms_raw, beat_speed)

            # Heartbeat
            if time.time() - last_status > 120:
                log.info("Audio Heartbeat: #%d Inferenzen, Gain=%.0fx", inference_count, current_gain)
                last_status = time.time()

    except Exception as e:
        log.error("Audio Fehler: %s", e, exc_info=True)
    finally:
        log.info("Audio raeume auf...")
        try:
            stream.stop_stream()
            stream.close()
            pa.terminate()
        except Exception:
            pass
        try:
            shm.close()
            shm.unlink()
        except Exception:
            pass
        log.info("Audio Processor beendet.")


if __name__ == "__main__":
    main()
