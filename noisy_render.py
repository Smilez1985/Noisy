#!/usr/bin/env python3
"""
Noisy Face Renderer (Komponentenbasiert)
Laeuft als Thread im Orchestrator, liest Mood-Daten direkt.

Der Avatar wird aus wiederverwendbaren Komponenten zusammengebaut.
Jeder Mood bringt nur seine ABWEICHUNGEN mit (Overrides).
Default-Augen, Default-Mund etc. werden immer gleich gezeichnet
wenn der Mood nichts anderes sagt.

Live-Parameter (Web-UI) aus orch.rt:
  - Software-Dimming (Tag/Nacht-Helligkeit, Auto-Dim, Nacht-Fenster)
  - Animationsgeschwindigkeit (Speed-Multiplikator)

Komponenten:
  1. Glow (5 Layer)
  2. Kopfhoerer-Buegel (hinter Body, nur bei Musik)
  3. Body (Ellipse)
  4. Kopfhoerer-Muscheln (vor Body, nur bei Musik)
  5. Frisur (immer, wippt bei Musik)
  6. Accessoires (Rasta-Hut, Goldkette, Joint, etc.)
  7. Augen (mit Blink-Engine)
  8. Mund
  9. SAD-Traene
  10. Partikel (vorderster Layer)
"""

import os
import sys
import time
import math
import random
import numpy as np
import st7789
from datetime import datetime
from PIL import Image, ImageDraw, ImageEnhance

from noisy_config import (
    WIDTH, HEIGHT, TARGET_FPS, FRAME_TIME, THERMAL_PATH,
)
from moods import (
    DEFAULT_BODY, DEFAULT_EYES, DEFAULT_MOUTH, DEFAULT_HAIR,
    DEFAULT_PHYSICS, DEFAULT_PARTICLES, DEFAULT_ACCESSORY,
    get_render_data, get_mood_name,
    BLACK, WHITE, GOLD, EYE_COLOR,
)
from moods.emotionen import LISTEN, LAUGH, SAD, SCARED, EMPATHY, CURIOUS
from moods.koerper import SLEEP, FART
from moods.idle import BORED
from moods.musik import ROCK, JAZZ, HIPHOP, REGGAE, PARTY

# ============================================================
# Farb-Interpolation
# ============================================================
def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


# ============================================================
# Partikel-System (NumPy-vektorisiert)
# ============================================================
class ParticleSystem:
    """Vektorisiertes Partikel-System mit NumPy Arrays."""

    def __init__(self, max_particles=30):
        self.max = max_particles
        # Spalten: x, y, vx, vy, life, type_id
        # type_id: 0=note, 1=zzz, 2=exclamation, 3=heart, 4=star, 5=smoke, 6=sweat, 7=stink
        self.data = np.zeros((0, 6), dtype=np.float32)
        self.colors = []

    def spawn(self, x, y, p_type, color):
        """Spawnt ein einzelnes Partikel."""
        if len(self.data) >= self.max:
            return

        type_map = {"note": 0, "zzz": 1, "exclamation": 2, "heart": 3,
                     "star": 4, "smoke": 5, "sweat": 6, "stink": 7}
        tid = type_map.get(p_type, 0)

        if tid == 1:  # zzz
            vx = random.uniform(0.5, 1.5)
            vy = random.uniform(-1.5, -0.5)
            life = random.randint(40, 80)
        elif tid == 2:  # exclamation
            vx = random.uniform(-3, 3)
            vy = random.uniform(-3, 3)
            life = random.randint(10, 25)
        elif tid == 5:  # smoke
            vx = random.uniform(-0.5, 0.5)
            vy = random.uniform(-1.5, -0.5)
            life = random.randint(20, 50)
        elif tid == 7:  # stink
            vx = random.uniform(-1, 1)
            vy = random.uniform(-0.5, 0.5)
            life = random.randint(15, 35)
        else:  # note, heart, star, sweat
            vx = random.uniform(-1.5, 1.5)
            vy = random.uniform(-2.5, -1)
            life = random.randint(30, 60)

        new = np.array([[x, y, vx, vy, life, tid]], dtype=np.float32)
        self.data = np.vstack([self.data, new]) if len(self.data) > 0 else new
        self.colors.append(color)

    def update(self):
        """Update alle Partikel (vektorisiert)."""
        if len(self.data) == 0:
            return
        # Position updaten
        self.data[:, 0] += self.data[:, 2]  # x += vx
        self.data[:, 1] += self.data[:, 3]  # y += vy
        self.data[:, 4] -= 1                 # life -= 1
        # Tote entfernen
        alive = self.data[:, 4] > 0
        self.data = self.data[alive]
        self.colors = [c for c, a in zip(self.colors, alive) if a]

    def draw(self, draw_ctx):
        """Zeichnet alle Partikel."""
        symbols = {0: None, 1: "z", 2: "!", 3: "<3", 4: "*", 5: "~", 6: ".", 7: "~"}
        for i in range(len(self.data)):
            x, y, _, _, life, tid = self.data[i]
            alpha = max(0.2, life / 60.0)
            c = self.colors[i] if i < len(self.colors) else WHITE
            c = (int(c[0] * alpha), int(c[1] * alpha), int(c[2] * alpha))
            ix, iy = int(x), int(y)
            tid = int(tid)

            sym = symbols.get(tid)
            if sym:
                draw_ctx.text((ix, iy), sym, fill=c)
            else:
                # Note
                draw_ctx.ellipse([ix, iy, ix + 5, iy + 4], fill=c)
                draw_ctx.line([ix + 4, iy + 2, ix + 4, iy - 8], fill=c, width=2)


# ============================================================
# Renderer
# ============================================================
class NoisyRenderer:
    def __init__(self, orchestrator):
        self.orch = orchestrator
        self.frame = 0.0
        self.particles = ParticleSystem(max_particles=30)

        # Display Init (im Konstruktor statt Modul-Level)
        try:
            self.display = st7789.ST7789(
                port=0, cs=0, dc=25, backlight=None,
                width=WIDTH, height=HEIGHT, rotation=90,
                spi_speed_hz=40000000,
            )
            self.display.begin()
            print("Display initialisiert (ST7789, 240x240, SPI)")
        except Exception as e:
            print(f"DISPLAY FEHLER: {e}")
            print("SPI aktiviert? dtoverlay=lcd1inch3_ST7789 in config.txt?")
            raise

        # Blink-Engine
        self.blink_timer = 0
        self.blink_duration = 0
        self.is_blinking = False
        self.next_blink = random.randint(50, 150)

        # Smooth Color Morphing
        self.current_body_color = DEFAULT_BODY["color"]
        self.current_glow_color = DEFAULT_BODY["glow"]
        self.morph_speed = 0.08

        # Thermal
        self.cpu_temp = 45.0
        self.temp_read_counter = 0

        # SAD Traene
        self.tear_y = 0

    # ----------------------------------------------------------
    # Thermal
    # ----------------------------------------------------------
    def read_temperature(self):
        self.temp_read_counter += 1
        if self.temp_read_counter % 30 == 0:
            try:
                with open(THERMAL_PATH, "r") as f:
                    self.cpu_temp = int(f.read()) / 1000.0
            except Exception:
                self.cpu_temp = 45.0

    # ----------------------------------------------------------
    # Brightness / Night-Window (Web-UI Live-Parameter)
    # ----------------------------------------------------------
    def _is_night(self, disp):
        """True wenn die aktuelle Uhrzeit im Nacht-Fenster liegt."""
        now = datetime.now().strftime("%H:%M")
        start = disp.get("night_mode_start", "22:00")
        end = disp.get("night_mode_end", "06:00")
        if start <= end:
            return start <= now < end
        # Fenster ueber Mitternacht (z.B. 22:00 - 06:00)
        return now >= start or now < end

    def _apply_brightness(self, img):
        """Software-Dimming: skaliert das Bild nach Tag-/Nacht-Helligkeit."""
        rt = getattr(self.orch, 'rt', None)
        if rt is None:
            return img
        disp = rt.get_display()
        if disp.get("auto_dim", True) and self._is_night(disp):
            brightness = disp.get("brightness_night", 80)
        else:
            brightness = disp.get("brightness_day", 255)
        factor = max(0.0, min(1.0, brightness / 255.0))
        if factor >= 0.999:
            return img
        return ImageEnhance.Brightness(img).enhance(factor)

    # ----------------------------------------------------------
    # Glow
    # ----------------------------------------------------------
    def draw_glow(self, draw, cx, cy, r_w, r_h, color, mood_id):
        pulse = 1.0
        if mood_id == ROCK:
            pulse = 0.65 + 0.35 * math.sin(self.frame * 0.45)
        for i in range(5, 0, -1):
            gw = r_w + i * 10
            gh = r_h + i * 10
            f = (6 - i) * 0.25 * pulse
            g = (int(color[0] * f), int(color[1] * f), int(color[2] * f))
            draw.ellipse([cx - gw, cy - gh * 0.85, cx + gw, cy + gh * 0.95], fill=g)

    # ----------------------------------------------------------
    # Body
    # ----------------------------------------------------------
    def draw_body(self, draw, cx, cy, r_w, r_h, color):
        draw.ellipse([cx - r_w, cy - r_h * 0.85, cx + r_w, cy + r_h * 0.95], fill=color)

    # ----------------------------------------------------------
    # Kopfhoerer
    # ----------------------------------------------------------
    def draw_headphones(self, draw, cx, cy, r_w, r_h, before_body=True):
        if before_body:
            draw.arc([cx - r_w - 8, cy - r_h - 18, cx + r_w + 8, cy + 3],
                     180, 0, fill=WHITE, width=10)
            draw.arc([cx - r_w - 6, cy - r_h - 16, cx + r_w + 6, cy + 1],
                     180, 0, fill=(35, 35, 45), width=8)
        else:
            draw.ellipse([cx - r_w - 13, cy - 16, cx - r_w + 9, cy + 26],
                         fill=(35, 35, 45), outline=WHITE, width=2)
            draw.ellipse([cx + r_w - 9, cy - 16, cx + r_w + 13, cy + 26],
                         fill=(35, 35, 45), outline=WHITE, width=2)

    # ----------------------------------------------------------
    # Frisur (immer sichtbar, wippt bei Musik)
    # ----------------------------------------------------------
    def draw_hair(self, draw, cx, cy, r_w, physics, hair_data):
        if not hair_data.get("visible", True):
            return

        color = hair_data.get("color", (139, 90, 43))
        dark = hair_data.get("color_dark", (110, 70, 30))
        light = hair_data.get("color_light", (165, 110, 55))

        # Wobble bei Musik (Traegheits-Nachwipp)
        ho_x, ho_y = 0, 0
        if hair_data.get("wobble", False):
            hs = physics.get("headbang_speed", 0)
            ha = physics.get("headbang_amp", 0)
            bs = physics.get("bounce_speed", 0)
            if hs > 0:
                body_phase = math.sin(self.frame * hs) * ha
                hair_phase = math.sin(self.frame * hs - 0.6) * ha * 1.2
                ho_y = hair_phase - body_phase
                ho_x = math.sin(self.frame * hs - 0.4) * 8
            elif bs > 0:
                ho_y = math.sin(self.frame * bs - 0.5) * 5
                ho_x = math.sin(self.frame * bs - 0.3) * 3

        hx = cx + 10 + ho_x
        hy = cy - r_w * 0.95 + ho_y

        # Stufe 1: Breite Basis
        draw.ellipse([cx - r_w - 2, hy + 6, cx + r_w + 2, hy + 24], fill=color)
        # Stufe 2: Mitte (breit, rechts versetzt)
        draw.ellipse([hx - 30, hy - 10, hx + 34, hy + 12], fill=color)
        # Stufe 3: Oben
        draw.ellipse([hx - 8, hy - 26, hx + 24, hy - 2], fill=color)
        # Spitze (rechts)
        tip_x = hx + 24 + ho_x * 0.6
        tip_y = hy - 30 + ho_y * 0.3
        draw.ellipse([tip_x - 9, tip_y - 7, tip_x + 9, tip_y + 7], fill=color)

        # Schatten + Glanz
        draw.arc([cx - r_w - 2, hy + 6, cx - 10, hy + 24], 90, 270, fill=dark, width=3)
        draw.arc([hx - 30, hy - 10, hx - 6, hy + 12], 90, 270, fill=dark, width=3)
        draw.arc([hx + 10, hy - 22, hx + 22, hy - 6], 270, 90, fill=light, width=2)

    # ----------------------------------------------------------
    # Augen (Default + Overrides)
    # ----------------------------------------------------------
    def draw_eyes(self, draw, cx, cy, r, blink_progress, eye_data):
        eye_y = cy - r * 0.12
        spacing = r * 0.38
        ew = r * 0.13 * eye_data.get("scale_w", 1.0)
        eh = r * 0.16 * eye_data.get("scale_h", 1.0)
        look_offset = eye_data.get("look_offset", 0)

        if eye_data.get("droopy", False):
            eh *= 0.18

        if blink_progress > 0:
            eh *= max(0.05, 1.0 - blink_progress)

        for s in [-1, 1]:
            ex = cx + s * spacing + look_offset
            draw.ellipse([ex - ew, eye_y - eh, ex + ew, eye_y + eh], fill=EYE_COLOR)
            if eh > r * 0.08 and blink_progress < 0.3:
                gr = ew * 0.35
                gx = ex - ew * 0.3
                gy = eye_y - eh * 0.3
                draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=WHITE)

    # ----------------------------------------------------------
    # Mund (Default + Overrides)
    # ----------------------------------------------------------
    def draw_mouth(self, draw, cx, cy, r, mouth_data, mood_id):
        my = cy + r * 0.22
        style = mouth_data.get("style", "smile")
        w = mouth_data.get("width", 1.0)
        mw = r * 0.15 * w

        if style == "grin":
            draw.chord([cx - 18, my - 5, cx + 18, my + 22], 0, 180, fill=EYE_COLOR)
        elif style == "open_round":
            draw.ellipse([cx - 8, my + 2, cx + 8, my + 18], fill=EYE_COLOR)
        elif style == "frown":
            draw.arc([cx - 12, my + 5, cx + 12, my + 20], 180, 360, fill=EYE_COLOR, width=4)
        elif style == "line":
            draw.line([cx - 8, my + 8, cx + 8, my + 8], fill=EYE_COLOR, width=3)
        elif style == "smirk":
            draw.arc([cx - 10, my, cx + 10, my + 12], 0, 180, fill=EYE_COLOR, width=3)
            draw.line([cx + 12, my + 4, cx + 18, my + 2], fill=(255, 100, 200), width=2)
        elif style == "yawn":
            draw.ellipse([cx - 12, my, cx + 12, my + 28], fill=EYE_COLOR)
        elif style == "tongue":
            draw.arc([cx - 15, my, cx + 15, my + 20], 0, 180, fill=EYE_COLOR, width=4)
            draw.ellipse([cx - 6, my + 12, cx + 6, my + 24], fill=(220, 80, 80))
        elif style == "sip":
            sz = 3 + int(math.sin(self.frame * 0.2) * 2)
            draw.ellipse([cx - sz, my + 5, cx + sz, my + 5 + sz * 2], fill=EYE_COLOR)
        elif style == "chewing":
            phase = math.sin(self.frame * 0.4)
            mh = int(6 + phase * 4)
            draw.ellipse([cx - 8, my + 2, cx + 8, my + 2 + mh], fill=EYE_COLOR)
        elif style == "focused":
            draw.line([cx - 10, my + 8, cx + 10, my + 8], fill=EYE_COLOR, width=3)
            draw.line([cx - 6, my + 5, cx - 6, my + 11], fill=EYE_COLOR, width=2)
        elif style == "concerned":
            draw.arc([cx - 10, my + 3, cx + 10, my + 18], 200, 340, fill=EYE_COLOR, width=3)
        elif style == "neutral":
            draw.line([cx - 8, my + 8, cx + 8, my + 8], fill=EYE_COLOR, width=2)
        else:  # smile (default)
            draw.arc([cx - mw, my - mw * 0.4, cx + mw, my + mw * 0.4],
                     0, 180, fill=EYE_COLOR, width=4)

    # ----------------------------------------------------------
    # Accessoires
    # ----------------------------------------------------------
    def draw_accessory(self, draw, cx, cy, r_w, r_h, acc_type, mood_id):
        if acc_type is None:
            return

        if acc_type == "rasta_hat":
            r = r_w
            draw.ellipse([cx - r - 16, cy - r - 42, cx + r + 16, cy - r + 12],
                         fill=(255, 0, 0))
            draw.rectangle([cx - r - 9, cy - r - 26, cx + r + 9, cy - r - 11],
                           fill=(255, 255, 0))
            draw.rectangle([cx - r - 9, cy - r - 11, cx + r + 9, cy - r + 6],
                           fill=(0, 180, 0))
            for i in range(-3, 4):
                dx = cx + i * 22
                sway = math.sin(self.frame * 0.1) * 13
                draw.line([dx, cy - r + 6, dx + sway, cy + r + 12],
                          fill=(50, 40, 30), width=9)

        elif acc_type == "gold_chain":
            swing = math.sin(self.frame * 0.4) * 18
            draw.arc([cx - r_w - 5, cy + 12, cx + r_w + 5, cy + r_w + 22],
                     0, 180, fill=GOLD, width=4)
            mx = cx + swing
            my = cy + r_w + 16
            draw.ellipse([mx - 10, my - 10, mx + 10, my + 10], fill=GOLD, outline=WHITE)
            draw.text((mx - 4, my - 7), "$", fill=BLACK)

        elif acc_type == "keyboard":
            for i in range(4):
                kx = cx - 45 + i * 28
                ky = cy + 42
                pressed = (int(self.frame) + i * 4) % 16 < 5
                yoff = 3 if pressed else 0
                draw.rectangle([kx, ky + yoff, kx + 22, ky + 10 + yoff],
                               outline=WHITE, width=2)

        elif acc_type == "joint":
            draw.rectangle([cx + 22, cy + 15, cx + 55, cy + 24], fill=WHITE)
            draw.ellipse([cx + 53, cy + 13, cx + 62, cy + 26], fill=(255, 80, 0))

        elif acc_type == "bong":
            draw.ellipse([cx + 25, cy + 18, cx + 55, cy + 48], outline=WHITE, width=3)
            draw.rectangle([cx + 35, cy - 15, cx + 45, cy + 22],
                           fill=(200, 200, 255), outline=WHITE)

        elif acc_type == "coffee":
            draw.rectangle([cx + 24, cy + 8, cx + 48, cy + 30],
                           fill=(240, 240, 240), outline=WHITE)
            draw.arc([cx + 46, cy + 12, cx + 58, cy + 24], -90, 90, fill=WHITE, width=2)
            if int(self.frame) % 12 < 6:
                draw.text((cx + 30, cy - 8), "~", fill=(200, 200, 200))

        elif acc_type == "watch":
            draw.line([cx + 28, cy + 22, cx + 48, cy + 8], fill=WHITE, width=3)
            draw.ellipse([cx + 42, cy + 2, cx + 56, cy + 16], fill=WHITE)
            draw.line([cx + 49, cy + 9, cx + 49, cy + 4], fill=BLACK, width=1)
            draw.line([cx + 49, cy + 9, cx + 53, cy + 9], fill=BLACK, width=1)

        elif acc_type == "gamepad":
            draw.rectangle([cx - 20, cy + 35, cx + 20, cy + 50],
                           fill=(50, 50, 60), outline=WHITE, width=2)
            draw.ellipse([cx - 12, cy + 38, cx - 6, cy + 44], fill=(200, 50, 50))
            draw.ellipse([cx + 6, cy + 38, cx + 12, cy + 44], fill=(50, 50, 200))

    # ----------------------------------------------------------
    # SAD Traene
    # ----------------------------------------------------------
    def draw_sad_tear(self, draw, cx, cy, r):
        self.tear_y = (self.tear_y + 1) % 35
        tear_x = cx - r * 0.38 - 5
        tear_start_y = cy - r * 0.05
        ty = tear_start_y + self.tear_y
        draw.ellipse([tear_x, ty, tear_x + 6, ty + 8], fill=(100, 200, 255))

    # ----------------------------------------------------------
    # Identity HUD Overlay (Taste Y)
    # ----------------------------------------------------------
    def draw_identity_overlay(self, draw):
        """
        Semi-transparentes Overlay ueber Noisy.
        Zeigt AEI-Werte, Mood, Alter, Interaktionen.
        240x240px, Lesbarkeit first.
        """
        # Hintergrund (dunkel, semi-transparent simuliert)
        draw.rectangle([10, 10, 230, 230], fill=(0, 0, 0))
        draw.rectangle([12, 12, 228, 228], outline=GOLD, width=2)

        # Header
        draw.text((20, 18), "IDENTITY: NOISY", fill=GOLD)

        # AEI-Balken
        personality = self.orch.personality
        bars = [
            ("E", personality.energy, (255, 100, 50)),     # Orange
            ("C", personality.cheerful, (255, 220, 50)),   # Gelb
            ("S", personality.shy, (100, 150, 255)),       # Blau
            ("A", personality.affection, (255, 100, 180)), # Rosa
        ]

        y_start = 50
        bar_height = 18
        bar_spacing = 28
        bar_left = 35
        bar_right = 215
        bar_width = bar_right - bar_left

        for i, (label, value, color) in enumerate(bars):
            by = y_start + i * bar_spacing

            # Label
            draw.text((18, by + 2), label, fill=WHITE)

            # Rahmen
            draw.rectangle([bar_left, by, bar_right, by + bar_height],
                           outline=(80, 80, 80), width=1)

            # Fuell-Balken
            fill_w = int(bar_width * value)
            if fill_w > 0:
                draw.rectangle([bar_left, by, bar_left + fill_w, by + bar_height],
                               fill=color)

            # Wert rechts
            draw.text((bar_right - 32, by + 2), "%.0f%%" % (value * 100), fill=WHITE)

        # Mood + Info
        info_y = y_start + 4 * bar_spacing + 8
        mood_name = get_mood_name(self.orch.render_mood_id)
        draw.text((20, info_y), "VIBE:", fill=(150, 150, 150))
        draw.text((60, info_y), mood_name, fill=GOLD)

        # Alter
        age_days = personality.get_age_days()
        draw.text((20, info_y + 22), "AGE:", fill=(150, 150, 150))
        if age_days < 1:
            age_str = "%.0f Std" % (age_days * 24)
        else:
            age_str = "%.1f Tage" % age_days
        draw.text((60, info_y + 22), age_str, fill=WHITE)

        # Interaktionen
        draw.text((20, info_y + 44), "INT:", fill=(150, 150, 150))
        draw.text((60, info_y + 44), "%d" % personality.total_interactions, fill=WHITE)

        # Dominant Trait
        trait = personality.get_dominant_trait()
        draw.text((20, info_y + 66), "TRAIT:", fill=(150, 150, 150))
        draw.text((72, info_y + 66), trait.upper(), fill=GOLD)

        # Mute-Status
        if self.orch.is_muted:
            draw.text((140, info_y + 66), "[MUTED]", fill=(255, 50, 50))

    # ----------------------------------------------------------
    # Night Gesture (Psst! nachts genervt aufgewacht)
    # ----------------------------------------------------------
    def draw_night_gesture(self, draw, cx, cy, r):
        """
        Zeichnet Nacht-Geste: Psst-Finger, genervte Augen-Balken,
        kleine Uhr (zeigt auf die Uhrzeit).
        """
        # Psst-Finger (vertikaler Strich vor dem Mund)
        fx = cx + 2
        fy = cy + r * 0.18
        # Finger (hautfarben)
        draw.rectangle([fx - 3, fy - 12, fx + 3, fy + 8], fill=(220, 180, 150))
        # Fingerspitze (rund)
        draw.ellipse([fx - 4, fy - 16, fx + 4, fy - 10], fill=(220, 180, 150))

        # "Shh" Text (pulsierend)
        if int(self.frame) % 20 < 14:
            draw.text((cx + 18, fy - 8), "shh!", fill=(200, 200, 255))

        # Genervte Augenbrauen (schraeg nach innen)
        eye_y = cy - r * 0.12
        spacing = r * 0.38
        for s in [-1, 1]:
            ex = cx + s * spacing
            # Augenbraue: aussen hoch, innen runter (genervt)
            brow_outer_y = eye_y - 14
            brow_inner_y = eye_y - 8
            if s == -1:
                draw.line([ex - 10, brow_outer_y, ex + 8, brow_inner_y],
                          fill=EYE_COLOR, width=3)
            else:
                draw.line([ex - 8, brow_inner_y, ex + 10, brow_outer_y],
                          fill=EYE_COLOR, width=3)

        # Kleine Uhr (rechts oben, Noisy zeigt auf die Zeit)
        clock_x = cx + r + 20
        clock_y = cy - r - 5
        clock_r = 12
        draw.ellipse([clock_x - clock_r, clock_y - clock_r,
                      clock_x + clock_r, clock_y + clock_r],
                     outline=WHITE, width=2)
        # Zeiger
        draw.line([clock_x, clock_y, clock_x, clock_y - 8], fill=WHITE, width=2)
        draw.line([clock_x, clock_y, clock_x + 6, clock_y], fill=WHITE, width=1)
        # "Zzz" daneben
        draw.text((clock_x + 14, clock_y - 6), "z", fill=(150, 150, 200))

    # ----------------------------------------------------------
    # RENDER
    # ----------------------------------------------------------
    def render(self):
        self.read_temperature()

        # Laufzeit-Parameter (Speed) vom Orchestrator
        rt = getattr(self.orch, 'rt', None)
        speed = rt.get_speed() if rt is not None else 1.0

        # Mood-Daten vom Orchestrator lesen (Thread-safe durch GIL)
        mood_id = self.orch.render_mood_id
        rd = self.orch.render_data
        intensity = self.orch.render_intensity
        beat = self.orch.render_beat

        body = rd["body"]
        eyes = rd["eyes"]
        mouth = rd["mouth"]
        hair = rd["hair"]
        physics = rd["physics"]
        particles = rd["particles"]
        accessory = rd["accessory"]

        # --- BLINK ENGINE ---
        blink_progress = 0.0
        if self.is_blinking:
            self.blink_timer += 1
            half = self.blink_duration / 2
            if self.blink_timer <= half:
                blink_progress = self.blink_timer / half
            else:
                blink_progress = 1.0 - (self.blink_timer - half) / half
            if self.blink_timer >= self.blink_duration:
                self.is_blinking = False
                self.next_blink = random.randint(45, 130)
        else:
            self.next_blink -= 1
            if self.next_blink <= 0:
                self.is_blinking = True
                self.blink_timer = 0
                self.blink_duration = random.randint(3, 7)

        # --- THERMAL VISUALS ---
        thermal_droopy = 0.0
        self.thermal_sweat = False
        if self.cpu_temp > 70:
            thermal_droopy = min(0.5, (self.cpu_temp - 70) / 20.0)
            self.thermal_sweat = True
        elif self.cpu_temp > 60:
            thermal_droopy = min(0.2, (self.cpu_temp - 60) / 50.0)
        self.thermal_droopy = thermal_droopy

        # --- SMOOTH COLOR MORPHING ---
        # morph_speed kommt vom Orchestrator (Transition-Geschwindigkeit)
        morph = self.orch.render_morph_speed
        target_body = body.get("color", DEFAULT_BODY["color"])
        target_glow = body.get("glow", DEFAULT_BODY["glow"])
        self.current_body_color = lerp_color(self.current_body_color, target_body, morph)
        self.current_glow_color = lerp_color(self.current_glow_color, target_glow, morph)

        # --- CANVAS ---
        img = Image.new('RGB', (WIDTH, HEIGHT), BLACK)
        draw = ImageDraw.Draw(img)

        cx, cy = 120, 118
        base_r = 55

        # --- BREATHING & SWAY ---
        breath = math.sin(self.frame * 0.12) * 2.5
        sway_speed = physics.get("sway_speed", 0.05)
        sway_amp = physics.get("sway_amp", 2.2)
        cx += math.sin(self.frame * sway_speed) * sway_amp
        r_w = base_r + breath
        r_h = base_r + breath

        # --- PHYSICS ---
        headbang_speed = physics.get("headbang_speed", 0)
        headbang_amp = physics.get("headbang_amp", 0)
        bounce_speed = physics.get("bounce_speed", 0)
        bounce_amp = physics.get("bounce_amp", 0)
        shake_x = physics.get("shake_x", 0)
        shake_y = physics.get("shake_y", 0)

        if headbang_speed > 0:
            cy += math.sin(self.frame * headbang_speed) * headbang_amp
        if bounce_speed > 0:
            cy -= abs(math.sin(self.frame * bounce_speed) * bounce_amp)
        if shake_x > 0:
            cx += random.randint(-shake_x, shake_x)
        if shake_y > 0:
            cy += random.randint(-shake_y, shake_y)

        # Stretch (Idle)
        r_w += physics.get("stretch_w", 0)
        r_h += physics.get("stretch_h", 0)

        # =======================================================
        # DRAWING LAYERS
        # =======================================================

        # Layer 1: Glow
        self.draw_glow(draw, cx, cy, r_w, r_h, self.current_glow_color, mood_id)

        # Layer 2: Kopfhoerer-Buegel (nur bei headphones Accessoire)
        acc_type = accessory.get("type")
        has_headphones = acc_type == "headphones"
        if has_headphones:
            self.draw_headphones(draw, cx, cy, r_w, r_h, before_body=True)

        # Layer 3: Body
        self.draw_body(draw, cx, cy, r_w, r_h, self.current_body_color)

        # Layer 4: Kopfhoerer-Muscheln
        if has_headphones:
            self.draw_headphones(draw, cx, cy, r_w, r_h, before_body=False)

        # Layer 5: Frisur
        self.draw_hair(draw, cx, cy, r_w, physics, hair)

        # Layer 6: Accessoires (nicht headphones, die sind schon gezeichnet)
        if acc_type and acc_type != "headphones":
            self.draw_accessory(draw, cx, cy, r_w, r_h, acc_type, mood_id)

        # Layer 7: Augen (mit Thermal-Droopy)
        if self.thermal_droopy > 0:
            eyes = dict(eyes)
            eyes["scale_h"] = eyes.get("scale_h", 1.0) * (1.0 - self.thermal_droopy)
        self.draw_eyes(draw, cx, cy, base_r, blink_progress, eyes)

        # Layer 8: Mund
        self.draw_mouth(draw, cx, cy, base_r, mouth, mood_id)

        # Layer 9: SAD Traene
        if mood_id == SAD:
            self.draw_sad_tear(draw, cx, cy, base_r)

        # Layer 10: Partikel
        p_type = particles.get("type")
        p_rate = particles.get("rate", 0)
        p_color = particles.get("color") or self.current_body_color
        if p_type and random.random() < p_rate:
            px = cx + random.randint(-45, 45)
            py = cy - 40
            self.particles.spawn(px, py, p_type, p_color)

        # Thermal-Schweiss (bei >70°C, unabhaengig vom Mood)
        if self.thermal_sweat and int(self.frame) % 15 == 0:
            sx = cx + random.randint(-25, 25)
            self.particles.spawn(sx, cy - 35, "sweat", (100, 200, 255))

        # Lieblingsgenre: Herz-Partikel + Augen-Funkeln
        if self.orch.favorite_playing and int(self.frame) % 10 == 0:
            hx = cx + random.randint(-35, 35)
            self.particles.spawn(hx, cy - 45, "heart", (255, 100, 180))

        self.particles.update()
        self.particles.draw(draw)

        # Lieblingsgenre: Augen-Funkeln (kleine Sterne in den Augen)
        if self.orch.favorite_playing:
            eye_y = cy - base_r * 0.12
            spacing = base_r * 0.38
            sparkle = int(200 + 55 * math.sin(self.frame * 0.5))
            for s in [-1, 1]:
                sx = cx + s * spacing - 3
                sy = eye_y - 5
                draw.text((int(sx), int(sy)), "*", fill=(sparkle, sparkle, 100))

        # Layer 11: Night Gesture (Psst! Finger + Uhr, genervte Augen)
        if self.orch.night_annoyed:
            self.draw_night_gesture(draw, cx, cy, base_r)

        # Layer 12: Identity HUD Overlay (Taste Y Toggle)
        if self.orch.show_identity:
            self.draw_identity_overlay(draw)

        # Layer 13: DEBUG-Rahmen (rot pulsierend, auffaellig!)
        if self.orch.is_debug:
            pulse = int(180 + 75 * math.sin(self.frame * 0.3))
            for i in range(6):
                draw.rectangle([i, i, WIDTH - 1 - i, HEIGHT - 1 - i],
                               outline=(pulse, 0, 0))
            draw.text((WIDTH // 2 - 20, 5), "DEBUG", fill=(255, 50, 50))

        # Layer 14: MUTE-Rahmen (grau) + Korken in den Ohren
        if self.orch.is_muted:
            for i in range(6):
                draw.rectangle([i, i, WIDTH - 1 - i, HEIGHT - 1 - i],
                               outline=(100, 100, 100))
            draw.text((WIDTH // 2 - 18, 5), "MUTE", fill=(150, 150, 150))
            # Korken in beiden Ohren
            ear_y = cy - base_r * 0.1
            for s in [-1, 1]:
                ex = cx + s * (r_w + 6)
                # Korken (kleiner brauner Zylinder)
                draw.rectangle([ex - 5, ear_y - 4, ex + 5, ear_y + 8],
                               fill=(180, 130, 60))
                draw.rectangle([ex - 6, ear_y - 5, ex + 6, ear_y - 2],
                               fill=(200, 150, 80))
                # Kleiner Schatten
                draw.line([ex - 3, ear_y + 1, ex + 3, ear_y + 1],
                          fill=(140, 100, 40), width=1)

        # Layer 15: SOCIAL-Rahmen (gruen pulsierend, BLE Beacon aktiv)
        if self.orch.is_social:
            pulse = int(140 + 115 * math.sin(self.frame * 0.3))
            for i in range(6):
                draw.rectangle([i, i, WIDTH - 1 - i, HEIGHT - 1 - i],
                               outline=(0, pulse, 0))
            draw.text((WIDTH // 2 - 12, 5), "BLE", fill=(0, 255, 0))

        # --- BRIGHTNESS / NIGHT-DIMMING ---
        img = self._apply_brightness(img)

        # --- DISPLAY ---
        if self.orch.cube_mode:
            # Prism/Cube: 180° Rotation (= gespiegelt + auf dem Kopf, Folded Optics)
            self.display.display(img.transpose(Image.ROTATE_180))
        else:
            # Normal: Direkte Anzeige (richtig herum)
            self.display.display(img)
        self.frame += speed

    # ----------------------------------------------------------
    # RUN (als Thread)
    # ----------------------------------------------------------
    def run(self):
        print("Noisy Renderer gestartet (Komponentenbasiert)")
        print(f"Target FPS: {TARGET_FPS}")

        fps_counter = 0
        fps_timer = time.time()

        try:
            while True:
                t_start = time.time()
                self.render()

                fps_counter += 1
                if time.time() - fps_timer >= 10.0:
                    actual_fps = fps_counter / (time.time() - fps_timer)
                    mood_name = get_mood_name(self.orch.render_mood_id)
                    print(f"FPS: {actual_fps:.1f} | Frame: {int(self.frame)} | "
                          f"Temp: {self.cpu_temp:.0f}C | Mood: {mood_name}")
                    fps_counter = 0
                    fps_timer = time.time()

                elapsed = time.time() - t_start
                sleep_time = FRAME_TIME - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            print(f"Renderer Fehler: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.display.display(Image.new('RGB', (WIDTH, HEIGHT), BLACK))
            print("Renderer beendet.")
