#!/usr/bin/env python3
"""
Noisy Input v5.1 - GPIO Button Handler (GamePi13)
Polling-basiert mit lgpio (robust, keine toten Callbacks).

Wird vom Orchestrator alle 100ms aufgerufen (process()).
Erkennt Flanken (HIGH->LOW = gedrueckt) mit Software-Debounce.

Hardware-Pinout GamePi13 (BCM, Waveshare Wiki verifiziert):
  Up=5, Down=6, Left=16, Right=13
  A=21, B=20, X=15, Y=12
  Start=26, Select=19, L=23, R=14

  Display: DC=25, RST=27, CS=8, SCLK=11, MOSI=10
  Audio: PWM=18

Noisy Button-Belegung:
  Y (12)      - Identity HUD Toggle
  B (20)      - Mute / Privacy Toggle
  X (15)      - Vibe-Check (Accumulator Flush)
  A (21)      - Mood-Boost (Stimmungs-Impuls)
  Start (26)  - Debug-Mode Toggle
  Select (19) - Cube Mode Toggle (Display-Flip fuer Prism)
  L (23)      - Reserved
  R (14)      - Reserved
"""

import os
import time
import logging

log = logging.getLogger('noisy-input')

# ============================================================
# GPIO Pin-Definitionen (BCM, Waveshare GamePi13 Wiki)
# ============================================================
PIN_Y = 12          # Identity HUD
PIN_B = 20          # Mute / Privacy
PIN_X = 15          # Vibe-Check (Flush)
PIN_A = 21          # Mood-Boost
PIN_START = 26      # Debug-Mode Toggle
PIN_SELECT = 19     # Cube Mode Toggle
PIN_L = 23          # Reserved
PIN_R = 14          # Reserved
PIN_UP = 5          # Reserved
PIN_DOWN = 6        # Reserved
PIN_LEFT = 16       # Reserved
PIN_RIGHT = 13      # Reserved

# Debounce in Sekunden
DEBOUNCE = 0.25

# Debug-Flag Datei (gleiche wie in noisy_config.py)
DEBUG_FLAG_FILE = '/home/noisy/noisy-app/debug.flag'

# Social-Flag Datei (BLE Beacon)
SOCIAL_FLAG_FILE = '/home/noisy/noisy-app/social.flag'

# lgpio Chip (RPi hat normalerweise Chip 0, Pi5 hat Chip 4)
GPIO_CHIP = 0


# ============================================================
# Input Handler (lgpio Polling)
# ============================================================
class NoisyInput:
    """
    GPIO Button Handler fuer GamePi13.
    Nutzt lgpio direkt mit Polling statt gpiozero Callbacks.
    process() wird vom Orchestrator alle ~100ms aufgerufen.
    """

    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.handle = None

        # === FLAGS ===
        self.show_identity = False
        self.is_muted = False
        self.is_debug = os.path.exists(DEBUG_FLAG_FILE)
        self.cube_mode = True
        self.flush_requested = False
        self.boost_requested = False
        self.is_social = os.path.exists(SOCIAL_FLAG_FILE)

        # Mute-Tracking
        self.mute_start_time = 0

        # Button-Definitionen: (name, pin, action)
        self.button_defs = [
            ("Y",      PIN_Y,      "identity"),
            ("B",      PIN_B,      "mute"),
            ("X",      PIN_X,      "flush"),
            ("A",      PIN_A,      "boost"),
            ("Start",  PIN_START,  "debug"),
            ("Select", PIN_SELECT, "cube"),
            ("Left",   PIN_LEFT,   "cube"),    # Fallback: Cube Mode auch auf Left
            ("Up",     PIN_UP,     "social"),
            ("Down",   PIN_DOWN,   "reserved"),
            ("Right",  PIN_RIGHT,  "reserved"),
        ]

        # State-Tracking fuer Edge-Detection
        self.prev_state = {}    # pin -> letzer Zustand (0=LOW/gedrueckt, 1=HIGH)
        self.last_press = {}    # pin -> Zeitpunkt des letzten Drueckens (Debounce)
        self.active_pins = {}   # pin -> (name, action)

        self._setup_gpio()

    def _setup_gpio(self):
        """Oeffnet GPIO-Chip und konfiguriert Buttons als Input mit Pull-Up."""
        try:
            import lgpio
            self.lgpio = lgpio
        except ImportError:
            log.warning("lgpio nicht verfuegbar - GPIO Input deaktiviert")
            return

        try:
            self.handle = lgpio.gpiochip_open(GPIO_CHIP)
        except Exception as e:
            log.error("GPIO Chip %d oeffnen fehlgeschlagen: %s", GPIO_CHIP, e)
            return

        ok = []
        fail = []
        for name, pin, action in self.button_defs:
            try:
                lgpio.gpio_claim_input(self.handle, pin, lgpio.SET_PULL_UP)
                state = lgpio.gpio_read(self.handle, pin)
                self.prev_state[pin] = state
                self.last_press[pin] = 0
                self.active_pins[pin] = (name, action)
                ok.append(name)
            except Exception as e:
                log.warning("Button %s (Pin %d) nicht verfuegbar: %s", name, pin, e)
                fail.append(name)

        log.info("Buttons OK: %s", ", ".join(ok) if ok else "keine")
        if fail:
            log.warning("Buttons NICHT verfuegbar: %s (Kernel/Overlay belegt?)",
                        ", ".join(fail))

    # ----------------------------------------------------------
    # Button-Aktionen
    # ----------------------------------------------------------
    def _handle_action(self, name, action):
        """Fuehrt die Aktion fuer einen Button-Druck aus."""

        if action == "identity":
            self.show_identity = not self.show_identity
            state = "AN" if self.show_identity else "AUS"
            log.info("BUTTON Y: Identity HUD %s", state)

        elif action == "mute":
            self.is_muted = not self.is_muted
            if self.is_muted:
                self.mute_start_time = time.time()
                log.info("BUTTON B: MUTE AN - Privacy Mode")
            else:
                duration = time.time() - self.mute_start_time
                log.info("BUTTON B: MUTE AUS (war %.0fs stumm)", duration)

        elif action == "flush":
            self.flush_requested = True
            log.info("BUTTON X: Vibe-Check")

        elif action == "boost":
            self.boost_requested = True
            log.info("BUTTON A: Mood-Boost")

        elif action == "debug":
            self.is_debug = not self.is_debug
            if self.is_debug:
                try:
                    with open(DEBUG_FLAG_FILE, 'w') as f:
                        f.write('debug')
                    log.info("BUTTON Start: DEBUG AN (Log auf SD-Karte)")
                except Exception as e:
                    log.error("Debug-Flag erstellen fehlgeschlagen: %s", e)
            else:
                try:
                    os.remove(DEBUG_FLAG_FILE)
                    log.info("BUTTON Start: DEBUG AUS (Log in /tmp)")
                except FileNotFoundError:
                    pass
                except Exception as e:
                    log.error("Debug-Flag loeschen fehlgeschlagen: %s", e)

        elif action == "cube":
            self.cube_mode = not self.cube_mode
            state = "AN (Prism)" if self.cube_mode else "AUS (Normal)"
            log.info("BUTTON Select: Cube Mode %s", state)

        elif action == "social":
            self.is_social = not self.is_social
            if self.is_social:
                try:
                    with open(SOCIAL_FLAG_FILE, 'w') as f:
                        f.write('social')
                    log.info("BUTTON Up: Social Mode AN (BLE Beacon)")
                except Exception as e:
                    log.error("Social-Flag erstellen fehlgeschlagen: %s", e)
            else:
                try:
                    os.remove(SOCIAL_FLAG_FILE)
                    log.info("BUTTON Up: Social Mode AUS")
                except FileNotFoundError:
                    pass
                except Exception as e:
                    log.error("Social-Flag loeschen fehlgeschlagen: %s", e)

        elif action == "reserved":
            log.info("BUTTON %s: Reserved (noch keine Funktion)", name)

    # ----------------------------------------------------------
    # Process (Orchestrator ruft das pro Zyklus auf)
    # ----------------------------------------------------------
    def process(self):
        """
        Pollt alle Buttons, erkennt Flanken, fuehrt Aktionen aus.
        Gibt dict mit aktuellen States zurueck.
        """
        # GPIO Polling (Flanken-Erkennung mit Debounce)
        if self.handle is not None:
            now = time.time()
            for pin, (name, action) in self.active_pins.items():
                try:
                    state = self.lgpio.gpio_read(self.handle, pin)
                except Exception:
                    continue

                # Fallende Flanke: HIGH (1) -> LOW (0) = Button gedrueckt
                if self.prev_state.get(pin, 1) == 1 and state == 0:
                    if now - self.last_press.get(pin, 0) > DEBOUNCE:
                        self.last_press[pin] = now
                        self._handle_action(name, action)

                self.prev_state[pin] = state

        result = {
            'show_identity': self.show_identity,
            'is_muted': self.is_muted,
            'is_debug': self.is_debug,
            'cube_mode': self.cube_mode,
            'is_social': self.is_social,
            'flush': False,
            'boost': False,
        }

        if self.flush_requested:
            self.flush_requested = False
            result['flush'] = True

        if self.boost_requested:
            self.boost_requested = False
            result['boost'] = True

        return result

    def cleanup(self):
        """GPIO aufraeumen."""
        if self.handle is not None:
            try:
                for pin in self.active_pins:
                    self.lgpio.gpio_free(self.handle, pin)
                self.lgpio.gpiochip_close(self.handle)
            except Exception:
                pass
        log.info("GPIO Input bereinigt")
