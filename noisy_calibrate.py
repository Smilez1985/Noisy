#!/usr/bin/env python3
"""
Noisy Calibrate v4.0 - Raumkalibrierung
Nimmt 15 Sekunden Grundrauschen auf und speichert den RMS-Schwellenwert.
Wird bei der Installation automatisch aufgerufen, kann aber auch
manuell per 'noisy-calibrate' gestartet werden.

Erzeugt: calibration.json mit noise_floor und rms_silence
"""

import os
import sys
import json
import time
import numpy as np
import pyaudio
from noisy_config import APP_DIR, SAMPLE_RATE, CHUNK_SIZE

# ============================================================
# Konfiguration
# ============================================================
CALIBRATION_FILE = os.path.join(APP_DIR, 'calibration.json')
CALIBRATION_SECONDS = 15
NOISE_MARGIN = 1.5  # Schwelle = Peak-RMS * Margin


def find_microphone():
    """USB-Mikrofon suchen, Fallback auf erstes verfuegbares."""
    pa = pyaudio.PyAudio()
    mic_index = None

    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0 and 'usb' in info['name'].lower():
            mic_index = i
            print(f"  Mikrofon: [{i}] {info['name']}")
            break

    if mic_index is None:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                mic_index = i
                print(f"  Mikrofon (Fallback): [{i}] {info['name']}")
                break

    if mic_index is None:
        print("FEHLER: Kein Mikrofon gefunden!")
        pa.terminate()
        sys.exit(1)

    return pa, mic_index


def calibrate(silent=False):
    """
    Fuehrt die Kalibrierung durch.
    silent=True: Keine interaktive Ausgabe (fuer Install-Script)
    Gibt den rms_silence Wert zurueck.
    """
    if not silent:
        print("")
        print("=" * 50)
        print("  Noisy Raumkalibrierung")
        print("=" * 50)
        print("")
        print("  Noisy wird jetzt 15 Sekunden lang zuhoeren.")
        print("  Bitte sei so LEISE wie moeglich!")
        print("  Kein Reden, keine Musik, nicht bewegen.")
        print("")
        input("  Druecke ENTER wenn du bereit bist...")
        print("")

    pa, mic_index = find_microphone()

    stream = pa.open(
        format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
        input=True, input_device_index=mic_index,
        frames_per_buffer=8000,
    )

    # Erste Sekunde verwerfen (Mic-Einschaltknacks)
    stream.read(CHUNK_SIZE, exception_on_overflow=False)

    rms_values = []
    peak_rms = 0.0

    if not silent:
        print(f"  Aufnahme laeuft... ({CALIBRATION_SECONDS}s)")

    for i in range(CALIBRATION_SECONDS):
        data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(samples ** 2)))
        rms_values.append(rms)

        if rms > peak_rms:
            peak_rms = rms

        if not silent:
            bar_len = int(min(rms * 5000, 40))
            bar = "#" * bar_len
            print(f"  [{i+1:2d}/{CALIBRATION_SECONDS}] RMS: {rms:.6f} {bar}")

    stream.stop_stream()
    stream.close()
    pa.terminate()

    # Auswertung
    avg_rms = float(np.mean(rms_values))
    std_rms = float(np.std(rms_values))
    rms_silence = round(peak_rms * NOISE_MARGIN, 6)

    # Speichern
    cal_data = {
        'noise_floor_avg': round(avg_rms, 6),
        'noise_floor_peak': round(peak_rms, 6),
        'noise_floor_std': round(std_rms, 6),
        'noise_margin': NOISE_MARGIN,
        'rms_silence': rms_silence,
        'samples': CALIBRATION_SECONDS,
        'calibrated_at': time.time(),
    }

    with open(CALIBRATION_FILE, 'w') as f:
        json.dump(cal_data, f, indent=2)

    if not silent:
        print("")
        print(f"  Ergebnis:")
        print(f"    Durchschnitt:  {avg_rms:.6f}")
        print(f"    Peak:          {peak_rms:.6f}")
        print(f"    Streuung:      {std_rms:.6f}")
        print(f"    Schwelle:      {rms_silence:.6f} (Peak x {NOISE_MARGIN})")
        print("")
        print(f"  Gespeichert: {CALIBRATION_FILE}")
        print("")
    else:
        print(f"  Kalibriert: noise_floor={peak_rms:.6f}, "
              f"rms_silence={rms_silence:.6f} (x{NOISE_MARGIN})")

    return rms_silence


def load_calibration(fallback=0.002):
    """
    Laedt den kalibrierten rms_silence Wert.
    Wird von noisy_audio.py und noisy_debug.py beim Start aufgerufen.
    Fallback wenn keine Kalibrierung vorhanden.
    """
    try:
        if os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            return data.get('rms_silence', fallback)
    except Exception:
        pass
    return fallback


if __name__ == "__main__":
    calibrate(silent=False)
