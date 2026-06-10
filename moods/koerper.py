#!/usr/bin/env python3
"""
Noisy Moods: Koerper-Gruppe v5.0
Koerpergeraeusche und physische Zustaende.
"""

from moods import register_group, register_ignored_labels

# ============================================================
# Mood-IDs (Koerper-Gruppe: 30-39)
# ============================================================
FART     = 30
SLEEP    = 31
EAT      = 32
EXERCISE = 33

# ============================================================
# Ignorierte Koerper-Labels (zu generisch)
# ============================================================
IGNORED_BODY_LABELS = [
    "Breathing",
    "Run",
    "Shuffle",
    "Walk, footsteps",
    "Pant",
]

# ============================================================
# Mood-Definitionen
# ============================================================
KOERPER_MOODS = [
    # ----------------------------------------------------------
    # FART
    # ----------------------------------------------------------
    {
        "id": FART,
        "name": "FART",
        "group": "koerper",
        "priority": 80,
        "fast_track": True,
        "labels": {
            "Fart": FART,
            "Burping, eructation": FART,
            "Oink": FART,
            "Stomach rumble": FART,
            "Snort": FART,
            "Hiccup": FART,
        },
        "body": {
            "color": (100, 180, 50),
            "glow": (50, 100, 25),
        },
        "eyes": {"look_offset": 14},
        "mouth": {"style": "smirk"},
        "particles": {"type": "stink", "rate": 0.20, "color": (120, 180, 60)},
    },

    # ----------------------------------------------------------
    # SLEEP (Stille-Timeout -> Schlaf)
    # ----------------------------------------------------------
    {
        "id": SLEEP,
        "name": "SLEEP",
        "group": "koerper",
        "priority": 10,
        "fast_track": False,
        "labels": {
            "Snoring": SLEEP,
            "Purr": SLEEP,
        },
        "body": {
            "color": (40, 40, 80),
            "glow": (20, 20, 50),
        },
        "eyes": {"scale_h": 0.18, "droopy": True},
        "mouth": {"style": "line"},
        "physics": {
            "sway_speed": 0.03,
            "sway_amp": 1.5,
        },
        "particles": {"type": "zzz", "rate": 0.08, "color": (180, 180, 200)},
    },

    # ----------------------------------------------------------
    # EAT (Essen/Trinken)
    # ----------------------------------------------------------
    {
        "id": EAT,
        "name": "EAT",
        "group": "koerper",
        "priority": 35,
        "fast_track": False,
        "labels": {
            "Chewing, mastication": EAT,
            "Biting": EAT,
            "Gargling": EAT,
            "Sizzle": EAT,
            "Stir": EAT,
            "Pour": EAT,
            "Boiling": EAT,
            "Fill (with liquid)": EAT,
        },
        "body": {
            "color": (200, 150, 80),
            "glow": (120, 80, 40),
        },
        "mouth": {"style": "chewing"},
    },

    # ----------------------------------------------------------
    # EXERCISE (Bewegung, Sport)
    # ----------------------------------------------------------
    {
        "id": EXERCISE,
        "name": "EXERCISE",
        "group": "koerper",
        "priority": 40,
        "fast_track": False,
        "labels": {
            "Basketball bounce": EXERCISE,
            "Bouncing": EXERCISE,
            "Whip": EXERCISE,
            "Slap, smack": EXERCISE,
            "Whack, thwack": EXERCISE,
        },
        "body": {
            "color": (255, 140, 0),
            "glow": (180, 80, 0),
        },
        "physics": {
            "bounce_speed": 0.5,
            "bounce_amp": 10,
        },
        "particles": {"type": "sweat", "rate": 0.15, "color": (100, 200, 255)},
    },
]

# ============================================================
# Registrierung
# ============================================================
register_ignored_labels(IGNORED_BODY_LABELS)
register_group(KOERPER_MOODS)
