#!/usr/bin/env python3
import os
import time
import math
import threading
import subprocess
from multiprocessing import shared_memory
import numpy as np
import st7789
from PIL import Image, ImageDraw
from datetime import datetime

# Importe
try:
    from config_manager import ConfigManager
except ImportError:
    print("Fehler: config_manager.py nicht gefunden!")
    exit(1)

# --- Konfiguration ---
DISPLAY_RES = 240
CONFIG_PATH = "config.json"

# Initialisiere Manager (Konfig + UI-Parameter)
config = ConfigManager(CONFIG_PATH)

# Initialisiere Status-Buffer (Audio-Daten von audio_processor.py)
try:
    status_shm = shared_memory.SharedMemory(name="noisy_status_buffer")
    status_buf = np.frombuffer(status_shm.buf, dtype=np.float32)
except FileNotFoundError:
    # Erstelle es, falls der Audio-Proz noch nicht läuft (Fallback auf 0)
    status_shm = shared_memory.SharedMemory(name="noisy_status_buffer", create=True, size=1024)
    status_buf = np.frombuffer(status_shm.buf, dtype=np.float32)

# Hardware Setup
DISPLAY = st7789.ST7789(
    port=0, cs=0, dc=25, backlight=None,
    width=DISPLAY_RES, height=DISPLAY_RES, rotation=270,
    spi_speed_hz=40000000
)
DISPLAY.begin()

class NoisyBrain:
    def __init__(self):
        self.temp = 0.0
        self.mood = "IDLE"
        self.is_running = True
        self.cpu_freq_mode = "low"
        self.last_audio_event = None
        self.event_timestamp = 0
        
    def get_temp(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return int(f.read()) / 1000.0
        except: return 40.0

    def set_cpu_freq(self, mode):
        if mode == self.cpu_freq_mode: return
        freq = "200MHz" if mode == "low" else "1000MHz"
        try:
            subprocess.run(["sudo", "cpufreq-set", "-u", freq], capture_output=True)
        except: pass
        self.cpu_freq_mode = mode

def thermal_personality_worker(brain):
    while brain.is_running:
        temp = brain.get_temp()
        if temp > 70.0:
            brain.mood = "TIRED"
            brain.set_cpu_freq("low")
        elif temp < 60.0 and brain.mood == "TIRED":
            brain.mood = "IDLE"
        
        time.sleep(2.0)

def draw_mochi(draw, frame, temp):
    # --- WERTE AUS DEN BUFFERN HOLES ---
    # Von Config-Manager (Shared Memory 1)
    brightness_day = config.get_vibe_param(0)      
    brightness_night = config.get_vibe_param(1)     
    speed_mult = config.get_vibe_param(2)           
    
    # Von Audio-Status (Shared Memory 2)
    mood_id = int(status_buf[0])
    confidence = status_buf[1]
    volume = status_buf[2]

    cx, cy = 120, 115
    base_r = 50
    
    # Tag/Nacht Logik
    now = datetime.now().strftime("%H:%M")
    start = config.config["display"]["night_mode_start"]
    end = config.config["display"]["night_mode_end"]
    is_night = False
    if start < end: 
        is_night = now >= start or now <= end
    else: 
        is_night = now >= start or now <= end

    current_brightness = brightness_night if is_night else brightness_day
    norm_bright = current_brightness / 255.0

    # Animation-Parameter (Dynamisch über Speed Multiplier)
    breath = math.sin(frame * 0.15 * speed_mult) * 5
    
    # Mood Mapping Logik
    color = [c * norm_bright for c in [200, 220, 255]] # Default Weiß-Blau

    if mood_id == 1: # MUSIC
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("MUSIC", [255, 165, 0])]
        breath = math.sin(frame * 0.3 * speed_mult) * 15
    elif mood_id == 2: # LAUGH
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("LAUGH", [255, 255, 0])]
        breath = math.sin(frame * 0.4 * speed_mult) * 10
    elif mood_id == 3: # SCARED
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("SCARED", [255, 0, 0])]
        breath = math.sin(frame * 0.5 * speed_mult) * 8
    elif mood_id == 4: # LISTEN
        color = [int(c * norm_bright) for c in config.config["visuals"]["mood_colors"].get("LISTEN", [0, 255, 255])]

    # Thermal-Hack & Drawing
    tiredness = max(0, (temp - 60) / 20) if temp > 60 else 0
    
    # Körper zeichnen
    draw.ellipse([cx-(base_r+breath), cy-(base_r+breath)*0.8, 
                  cx+(base_r+breath), cy+(base_r+breath)], fill=color)
    
    # Augen (Thermal-Einfluss)
    eye_y = cy - 5
    eye_h = 8 * (1.0 - tiredness)
    draw.ellipse([cx-20, eye_y-eye_h, cx-12, eye_y+eye_h], fill=(40,40,50))
    draw.ellipse([cx+12, eye_y-eye_h, cx+20, eye_y+eye_h], fill=(40,40,50))

def main_loop():
    brain = NoisyBrain()
    thermal_thread = threading.Thread(target=thermal_personality_worker, args=(brain,))
    thermal_thread.daemon = True
    thermal_thread.start()
    
    frame = 0
    fps_timer = time.time()
    print("Noisy Main-System gestartet...")
    
    try:
        while True:
            img = Image.new('RGB', (DISPLAY_RES, DISPLAY_RES), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Zeichnen mit Daten aus beiden Shared Memory Buffern
            draw_mochi(draw, None, frame, brain.temp)
            
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
            DISPLAY.display(img)
            
            frame += 1
            if frame % 30 == 0:
                now = time.time()
                print(f"FPS: {30/(now-fps_timer):.1f} | MoodID: {status_buf[0]} | Conf: {status_buf[1]:.2f} | Temp: {brain.temp}°C")
                fps_timer = now
            
    except KeyboardInterrupt:
        print("Beendet.")

if __name__ == "__main__":
    try:
        os.sched_setaffinity(0, {0})
    except: pass
    main_loop()
