#!/usr/bin/env python3
"""
Noisy Beacon v5.1 - BLE Beacon via btmgmt
Strahlt Noisy's Personality-Zustand als BLE Advertisement aus.
Sichtbar mit nRF Connect App auf dem Handy.

Nutzt btmgmt (BlueZ) via subprocess - kein pip install noetig.

Payload Format (12 Bytes Manufacturer Specific Data):
  Byte 0-1:  "NO" (0x4E 0x4F) - Noisy-Signatur
  Byte 2:    Protocol Version (0x01)
  Byte 3-4:  Noisy-ID (16-bit, Big Endian)
  Byte 5:    Current Mood-ID
  Byte 6:    Energy (0-255)
  Byte 7:    Cheerful (0-255)
  Byte 8:    Shy (0-255)
  Byte 9:    Affection (0-255)
  Byte 10:   Age-Days (0-255, gedeckelt)
  Byte 11:   Reserved (0x00)
"""

import logging
import os
import subprocess
import threading
import time

from noisy_config import BLE_BEACON_INTERVAL

log = logging.getLogger('noisy-beacon')

PROTOCOL_VERSION = 0x01
ADV_INSTANCE = 1


def _find_btmgmt():
    """Sucht btmgmt Binary (Pfad variiert je nach Distribution)."""
    for path in ('/usr/bin/btmgmt', '/usr/sbin/btmgmt', '/usr/local/bin/btmgmt'):
        if os.path.exists(path):
            return path
    # Fallback: PATH durchsuchen lassen
    return 'btmgmt'


# Einmal beim Import ermitteln
_BTMGMT = _find_btmgmt()


def _run_btmgmt(*args):
    """Fuehrt btmgmt-Befehl aus. Gibt (success, output) zurueck."""
    cmd = ['sudo', _BTMGMT] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            log.warning("btmgmt %s fehlgeschlagen: %s", args[0], result.stderr.strip())
            return False, result.stderr
        return True, result.stdout
    except FileNotFoundError:
        log.error("btmgmt nicht gefunden - bluez installiert?")
        return False, "btmgmt not found"
    except subprocess.TimeoutExpired:
        log.error("btmgmt %s Timeout", args[0])
        return False, "timeout"
    except Exception as e:
        log.error("btmgmt %s Fehler: %s", args[0], e)
        return False, str(e)


def _build_payload(noisy_id, mood_id, energy, cheerful, shy, affection, age_days):
    """Baut 12-Byte Manufacturer Specific Data Payload."""
    return bytes([
        0x4E, 0x4F,                         # "NO" Signatur
        PROTOCOL_VERSION,                    # Protocol Version
        (noisy_id >> 8) & 0xFF,              # Noisy-ID High
        noisy_id & 0xFF,                     # Noisy-ID Low
        int(mood_id) & 0xFF,                 # Mood-ID
        int(energy * 255) & 0xFF,            # Energy
        int(cheerful * 255) & 0xFF,          # Cheerful
        int(shy * 255) & 0xFF,               # Shy
        int(affection * 255) & 0xFF,         # Affection
        min(255, int(age_days)) & 0xFF,      # Age Days (gedeckelt)
        0x00,                                # Reserved
    ])


def _adv_data_from_payload(payload):
    """
    Baut vollstaendiges AD Structure fuer Manufacturer Specific Data.
    Format: Length(1) + Type(0xFF)(1) + Company(2) + Payload
    Company ID 0xFFFF = Reserved/Testing.
    """
    # AD Type 0xFF = Manufacturer Specific Data
    # Company ID: 0xFFFF (Testing/Unregistered)
    company_lo = 0xFF
    company_hi = 0xFF
    ad_data = bytes([len(payload) + 3, 0xFF, company_lo, company_hi]) + payload
    return ad_data


def start_beacon():
    """Schaltet BLE ein und bereitet Advertising vor."""
    log.info("BLE Beacon: Starte...")
    ok, _ = _run_btmgmt('power', 'on')
    if not ok:
        log.error("BLE Beacon: power on fehlgeschlagen")
        return False
    log.info("BLE Beacon: Bluetooth eingeschaltet")
    return True


def update_beacon(noisy_id, mood_id, energy, cheerful, shy, affection, age_days):
    """Aktualisiert BLE Advertisement mit neuen Personality-Daten."""
    payload = _build_payload(noisy_id, mood_id, energy, cheerful, shy, affection, age_days)
    ad_data = _adv_data_from_payload(payload)
    ad_hex = ''.join('%02x' % b for b in ad_data)

    # Altes Advertisement entfernen (ignoriere Fehler falls keins existiert)
    _run_btmgmt('rm-adv', str(ADV_INSTANCE))

    # Neues Advertisement setzen
    ok, out = _run_btmgmt('add-adv', '-d', ad_hex, str(ADV_INSTANCE))
    if ok:
        log.debug("BLE Beacon: Update OK (Mood=%d E=%.0f%% C=%.0f%% S=%.0f%% A=%.0f%%)",
                  mood_id, energy * 100, cheerful * 100, shy * 100, affection * 100)
    else:
        log.warning("BLE Beacon: add-adv fehlgeschlagen: %s", out)
    return ok


def stop_beacon():
    """Stoppt BLE Advertisement und schaltet Bluetooth aus."""
    log.info("BLE Beacon: Stoppe...")
    _run_btmgmt('rm-adv', str(ADV_INSTANCE))
    _run_btmgmt('power', 'off')
    log.info("BLE Beacon: Gestoppt")


class BeaconThread(threading.Thread):
    """
    Background-Thread der den BLE Beacon periodisch aktualisiert.
    Liest aktuelle Werte vom Orchestrator.
    """

    def __init__(self, orchestrator):
        super().__init__(daemon=True)
        self.orch = orchestrator
        self._stop_event = threading.Event()

    def run(self):
        if not start_beacon():
            log.error("BLE Beacon: Konnte nicht gestartet werden")
            return

        log.info("BLE Beacon: Thread laeuft (Intervall %ds)", BLE_BEACON_INTERVAL)

        while not self._stop_event.is_set():
            try:
                p = self.orch.personality
                update_beacon(
                    noisy_id=p.noisy_id,
                    mood_id=self.orch.current_mood,
                    energy=p.energy,
                    cheerful=p.cheerful,
                    shy=p.shy,
                    affection=p.affection,
                    age_days=p.get_age_days(),
                )
            except Exception as e:
                log.error("BLE Beacon: Update-Fehler: %s", e)

            self._stop_event.wait(BLE_BEACON_INTERVAL)

        stop_beacon()
        log.info("BLE Beacon: Thread beendet")

    def stop(self):
        """Signalisiert dem Thread sich zu beenden."""
        self._stop_event.set()
