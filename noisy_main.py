#!/usr/bin/env python3
import os
import time
import math
import random
import threading
import subprocess
from multiprocessing import shared_memory
import numpy as np
import st7789
from PIL import Image, ImageDraw
from datetime import datetime

# Importiere den neuen Config-Manager
try:
    from config_manager import ConfigManager
except ImportError:
    print("Fehler: config_manager.py nicht gefunden! Bitte erst erstellen.")
    exit(1)

# --- Konfiguration & Setup ---
DISPLAY_RES = 240
CONFIG_PATH = "config.json"

# Initialisiere den Config Manager (Liest RAM und JSON gleichzeitig)
config = ConfigManager(CONFIG_PATH)

# Hardware Setup (St7789 Display)
# Wir behalten deine ursprüngliche Konfiguration bei
DISPLAY = st7789.ST7789(
    port=0, cs=0, dc=25, backlight=None,
    width=DISPLAY_RES, height=DISPLAY_RES, rotation=270,
    spi_speed_hz=40000000
)
DISPLAY.begin()

class NoisyBrain:
    def __init__(self):
        self.temp = 0.0
        self.mood = "IDLE"  # IDLE, MUSIC, LAUGH, SCARED, TIRED
        self.is_running = True
        self.cpu_freq_mode = "low"
        self.last_audio_event = None
        self.event_timestamp = 0
        
    def get_temp(self):
        """Liest die CPU-Temperatur für die 'Thermal-Personality'."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read()) / 1000.0
                self.temp = temp
                return temp
        except:
            return 40.0

    def set_cpu_freq(self, mode):
        """Dynamisches Frequency-Capping."""
        if mode == self.cpu_freq_mode:
            return
        freq = "200MHz" if mode == "low" else "1000MHz"
        try:
            subprocess.run(["sudo", "cpufreq-set", "-u", freq], capture_output=True)
        except:
            pass
        self.cpu_freq_mode = mode

def thermal_personality_worker(brain):
    """Überwacht die Hitze und passt Noisys Zustand an."""
    while brain.is_running:
        temp = brain.get_temp()
        if temp > 70.0:
            brain.mood = "TIRED"
            brain.set_cpu_freq("low")
        elif temp < 60.0 and brain.mood == "TIRED":
            brain.mood = "IDLE"
        
        # Nur hochfahren, wenn Audio-Events erwartet werden
        if brain.last_audio_event and (time.time() - brain.event_timestamp < 5):
            brain.set_cpu_freq("high")
        else:
            brain.set_cpu_freq("low")
            
        time.sleep(2.0)

def draw_mochi(draw, mood, frame, temp):
    """Rendert den Mochi-Blob basierend auf Stimmung, Temperatur und UI-Config."""
    # ---werte aus dem Shared Memory / Config holen ---
    brightness_day = config.get_vibe_param(0)      # Index 0
    brightness_night = config.get_vibe_param(1)     # Index 1
    speed_mult = config.get_vibe_param(2)           # Index 2
    
    cx, cy = 120, 115
    base_r = 50
    
    # Tag/Nacht Logik bestimmen
    now = datetime.now().strftime("%H:%M")
    start = config.config["display"]["night_mode_start"]
    end = config.config["display"]["night_mode_end"]
    
    # Prüfen, ob wir im Nachtmodus sind
    is_night = False
    if start < end: # Normaler Fall (z.B. 22:00 - 06:00 -> hier ist die Logik leicht komplexer)
        if now >= start or now <= end:
            is_night = True
    else: # Übergang über Mitternacht (z.B. 23:00 - 05:00)
        if now >= start or now <= end:
            is_night = True

    current_brightness = brightness_night if is_night else brightness_day
    # Normalisierung auf 0.0 - 1.0
    norm_bright = current_brightness / 255.0

    # Thermal-Hack: Bei Hitze sinken die Augenlider
    tiredness = max(0, (temp - 60) / 20) if temp > 60 else 0
    
    # Animation-Parameter (mit Speed Multiplier aus Config)
    breath = math.sin(frame * 0.15 * speed_mult) * 5
    color = (200, 220, 255) # Standard Weiß-Blau

    if mood == "MUSIC":
        breath = math.sin(frame * 0.3 * speed_mult) * 15 
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("MUSIC", [255, 165, 0])]
    elif mood == "TIRED":
        breath = math.sin(frame * 0.05 * speed_mult) * 2 
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("TIRED", [150, 150, 200])]
    elif mood == "SCARED":
        breath = math.sin(frame * 0.5 * speed_mult) * 8
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("SCARED", [255, 0, 0])]
    elif mood == "LAUGH":
        breath = math.sin(frame * 0.4 * speed_mult) * 10
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("LAUGH", [255, 255, 0])]
    else:
        # Standard / Idle Farbe mit Brightness-Anpassung
        color = [int(c * norm_bright) for c in (200, 220, 255)]

    # Zeichne Körper (vereinfacht für Performance)
    draw.ellipse([cx-(base_r+breath), cy-(base_r+breath)*0.8, 
                  cx+(base_r+breath), cy+(base_r+breath)], fill=color)
    
    # Augen mit Thermal-Einfluss und Helligkeit
    eye_y = cy - 5
    eye_h = 8 * (1.0 - tiredness) # Augen schließen sich bei Hitze
    draw.ellipse([cx-20, eye_y-eye_h, cx-12, eye_y+eye_h], fill=(40,40,50))
    draw.ellipse([cx+12, eye_y-eye_h, cx+20, eye_y+eye_h], fill=(40,40,50))

def main_loop():
    brain = NoisyBrain()
    
    # Starte Thermal-Personality-Hack in eigenem Thread
    thermal_thread = threading.Thread(target=thermal_personality_worker, args=(brain,))
    thermal_thread.daemon = True # Sicherstellen, dass der Thread mit dem Programm stirbt
    thermal_thread.start()
    
    frame = 0
    fps_timer = time.time()
    
    print("Noisy Main-System gestartet...")
    print(f"Konfiguration geladen aus: {CONFIG_PATH}")
    
    try:
        while True:
            # 1. Erstelle leeres Bild
            img = Image.new('RGB', (DISPLAY_RES, DISPLAY_RES), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # 2. Zeichne Noisy (Mochi-Blob) mit den Config-Werten
            draw_mochi(draw, brain.mood, frame, brain.temp)
            
            # 3. Prisma-Flip: Horizontal spiegeln 
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
            
            # 4. Display-Output
            DISPLAY.display(img)
            
            frame += 1
            if frame % 30 == 0:
                now = time.time()
                print(f"FPS: {30/(now-fps_timer):.1f} | Temp: {brain.temp}°C | Mood: {brain.mood} | Brightness: {config.get_vibe_param(0)}")
                fps_timer = now
            
    except KeyboardInterrupt:
        brain.is_running = False
        DISPLAY.display(Image.new('RGB', (240, 240), (0, 0, 0)))
        print("Noisy wurde beendet.")

if __name__ == "__main__":
    # Core Pinning: Dieser Prozess (Renderer) auf Kern 1 fixieren
    try:
        os.sched_setaffinity(0, {0}) # Nutze Kern 0 oder wie in deiner Config bevorzugt
    except AttributeError:
        pass
        
    main_loop()
