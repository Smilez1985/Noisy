#!/usr/bin/env python3
"""
Noisy Moods: Umgebung-Gruppe v5.0
Arbeitsgeraeusche, Natur, Verkehr, Haushalt.
"""

from moods import register_group, register_ignored_labels

# ============================================================
# Mood-IDs (Umgebung-Gruppe: 40-49)
# ============================================================
WORK     = 40
NATURE   = 41
WEATHER  = 42
TRAFFIC  = 43
HOUSE    = 44

# ============================================================
# Ignorierte Umgebungs-Labels
# ============================================================
IGNORED_ENV_LABELS = [
    "Inside, small room",
    "Inside, large room or hall",
    "Inside, public space",
    "Outside, urban or manmade",
    "Outside, rural or natural",
    "Reverberation",
    "Echo",
    "Noise",
    "Environmental noise",
    "Static",
    "Mains hum",
    "Sidetone",
    "Cacophony",
    "White noise",
    "Pink noise",
    "Throbbing",
    "Vibration",
    "Silence",
    "Sine wave",
    "Harmonic",
    "Chirp tone",
    "Sound effect",
    "Pulse",
    "Field recording",
    "Sonar",
    "Arrow",
    "Electronic tuner",
    "Effects unit",
    "Chorus effect",
    "Hum",
]

# ============================================================
# Mood-Definitionen
# ============================================================
UMGEBUNG_MOODS = [
    # ----------------------------------------------------------
    # WORK (Buero, Tippen, Werkzeug)
    # ----------------------------------------------------------
    {
        "id": WORK,
        "name": "WORK",
        "group": "umgebung",
        "priority": 45,
        "fast_track": False,
        "labels": {
            "Typing": WORK,
            "Computer keyboard": WORK,
            "Typewriter": WORK,
            "Writing": WORK,
            "Sawing": WORK,
            "Filing (rasp)": WORK,
            "Sanding": WORK,
            "Drill": WORK,
            "Hammer": WORK,
            "Jackhammer": WORK,
            "Tools": WORK,
            "Sewing machine": WORK,
            "Cash register": WORK,
            "Ratchet, pawl": WORK,
            "Gears": WORK,
            "Pulleys": WORK,
            "Mechanical fan": WORK,
        },
        "body": {
            "color": (100, 160, 220),
            "glow": (50, 80, 120),
        },
        "mouth": {"style": "focused"},
        "accessory": {"type": "keyboard"},
    },

    # ----------------------------------------------------------
    # NATURE (Wasser, Tiere, Wald)
    # ----------------------------------------------------------
    {
        "id": NATURE,
        "name": "NATURE",
        "group": "umgebung",
        "priority": 35,
        "fast_track": False,
        "labels": {
            "Water": NATURE,
            "Stream": NATURE,
            "Waterfall": NATURE,
            "Ocean": NATURE,
            "Waves, surf": NATURE,
            "Wind": NATURE,
            "Rustling leaves": NATURE,
            "Gurgling": NATURE,
            "Crackle": NATURE,
        },
        "body": {
            "color": (50, 180, 120),
            "glow": (25, 100, 60),
        },
        "physics": {
            "sway_speed": 0.04,
            "sway_amp": 3,
        },
        "mouth": {"style": "smile"},
    },

    # ----------------------------------------------------------
    # WEATHER (Regen, Sturm)
    # ----------------------------------------------------------
    {
        "id": WEATHER,
        "name": "WEATHER",
        "group": "umgebung",
        "priority": 35,
        "fast_track": False,
        "labels": {
            "Rain": WEATHER,
            "Raindrop": WEATHER,
            "Rain on surface": WEATHER,
            "Steam": WEATHER,
            "Wind noise (microphone)": WEATHER,
        },
        "body": {
            "color": (80, 100, 160),
            "glow": (40, 50, 90),
        },
        "physics": {
            "sway_speed": 0.06,
            "sway_amp": 4,
        },
    },

    # ----------------------------------------------------------
    # TRAFFIC (Fahrzeuge, Motoren)
    # ----------------------------------------------------------
    {
        "id": TRAFFIC,
        "name": "TRAFFIC",
        "group": "umgebung",
        "priority": 30,
        "fast_track": False,
        "labels": {
            "Vehicle": TRAFFIC,
            "Motor vehicle (road)": TRAFFIC,
            "Car": TRAFFIC,
            "Car alarm": TRAFFIC,
            "Car passing by": TRAFFIC,
            "Race car, auto racing": TRAFFIC,
            "Truck": TRAFFIC,
            "Bus": TRAFFIC,
            "Emergency vehicle": TRAFFIC,
            "Motorcycle": TRAFFIC,
            "Traffic noise, roadway noise": TRAFFIC,
            "Rail transport": TRAFFIC,
            "Train": TRAFFIC,
            "Railroad car, train wagon": TRAFFIC,
            "Train wheels squealing": TRAFFIC,
            "Subway, metro, underground": TRAFFIC,
            "Aircraft": TRAFFIC,
            "Aircraft engine": TRAFFIC,
            "Jet engine": TRAFFIC,
            "Propeller, airscrew": TRAFFIC,
            "Helicopter": TRAFFIC,
            "Fixed-wing aircraft, airplane": TRAFFIC,
            "Engine": TRAFFIC,
            "Light engine (high frequency)": TRAFFIC,
            "Medium engine (mid frequency)": TRAFFIC,
            "Heavy engine (low frequency)": TRAFFIC,
            "Engine knocking": TRAFFIC,
            "Engine starting": TRAFFIC,
            "Idling": TRAFFIC,
            "Accelerating, revving, vroom": TRAFFIC,
            "Skidding": TRAFFIC,
            "Tire squeal": TRAFFIC,
            "Air brake": TRAFFIC,
            "Air horn, truck horn": TRAFFIC,
            "Reversing beeps": TRAFFIC,
            "Power windows, electric windows": TRAFFIC,
            "Lawn mower": TRAFFIC,
            "Chainsaw": TRAFFIC,
            "Dental drill, dentist's drill": TRAFFIC,
            "Steam whistle": TRAFFIC,
        },
        "body": {
            "color": (150, 150, 150),
            "glow": (80, 80, 80),
        },
    },

    # ----------------------------------------------------------
    # HOUSE (Haushalt, Kueche, Bad)
    # ----------------------------------------------------------
    {
        "id": HOUSE,
        "name": "HOUSE",
        "group": "umgebung",
        "priority": 30,
        "fast_track": False,
        "labels": {
            "Cupboard open or close": HOUSE,
            "Drawer open or close": HOUSE,
            "Dishes, pots, and pans": HOUSE,
            "Cutlery, silverware": HOUSE,
            "Chopping (food)": HOUSE,
            "Frying (food)": HOUSE,
            "Microwave oven": HOUSE,
            "Blender": HOUSE,
            "Water tap, faucet": HOUSE,
            "Sink (filling or washing)": HOUSE,
            "Bathtub (filling or washing)": HOUSE,
            "Hair dryer": HOUSE,
            "Toilet flush": HOUSE,
            "Toothbrush": HOUSE,
            "Electric toothbrush": HOUSE,
            "Vacuum cleaner": HOUSE,
            "Electric shaver, electric razor": HOUSE,
            "Shuffling cards": HOUSE,
            "Air conditioning": HOUSE,
            "Clock": HOUSE,
            "Tick": HOUSE,
            "Tick-tock": HOUSE,
            "Liquid": HOUSE,
            "Slosh": HOUSE,
            "Squish": HOUSE,
            "Trickle, dribble": HOUSE,
            "Gush": HOUSE,
            "Spray": HOUSE,
            "Pump (liquid)": HOUSE,
            "Wood": HOUSE,
            "Chop": HOUSE,
            "Splinter": HOUSE,
            "Crack": HOUSE,
            "Glass": HOUSE,
            "Chink, clink": HOUSE,
            "Crushing": HOUSE,
            "Crumpling, crinkling": HOUSE,
            "Tearing": HOUSE,
            "Rub": HOUSE,
            "Mechanisms": HOUSE,
            "Rowboat, canoe, kayak": HOUSE,
        },
        "body": {
            "color": (180, 160, 120),
            "glow": (100, 80, 60),
        },
    },
]

# ============================================================
# Registrierung
# ============================================================
register_ignored_labels(IGNORED_ENV_LABELS)
register_group(UMGEBUNG_MOODS)
