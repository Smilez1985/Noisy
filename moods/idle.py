#!/usr/bin/env python3
"""
Noisy Moods: Idle-Gruppe v5.0
Bored-Zustand und alle Idle-Animationen.
Der Orchestrator waehlt random aus der Idle-Gruppe.
"""

from moods import register_group, register_ignored_labels

# ============================================================
# Mood-IDs (Idle-Gruppe: 50-69)
# ============================================================
BORED    = 50
JOINT    = 51
BONG     = 52
COFFEE   = 53
YAWN     = 54
STRETCH  = 55
DOZE     = 56
WATCH    = 57
TONGUE   = 58
DANCE    = 59
MEDITATE = 60
GAME     = 61

# ============================================================
# Ignorierte Labels (Speech und generisches)
# ============================================================
IGNORED_IDLE_LABELS = [
    "Speech",
    "Male speech, man speaking",
    "Female speech, woman speaking",
    "Child speech, kid speaking",
    "Conversation",
    "Narration, monologue",
    "Babbling",
    "Speech synthesizer",
    "Whispering",
    "Chatter",
    "Hubbub, speech noise, speech babble",
    "Groan",
    "Grunt",
]

# ============================================================
# Mood-Definitionen
# ============================================================
IDLE_MOODS = [
    # ----------------------------------------------------------
    # BORED (Basis-Idle, wird im Orchestrator zum Idle-Verteiler)
    # ----------------------------------------------------------
    {
        "id": BORED,
        "name": "BORED",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (60, 60, 80),
            "glow": (30, 30, 45),
        },
        "eyes": {"look_offset": 14},
        "mouth": {"style": "neutral"},
    },

    # ----------------------------------------------------------
    # JOINT (Idle-Animation: raucht)
    # ----------------------------------------------------------
    {
        "id": JOINT,
        "name": "JOINT",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (60, 70, 60),
            "glow": (30, 40, 30),
        },
        "eyes": {"scale_h": 0.6, "droopy": True},
        "mouth": {"style": "smile"},
        "accessory": {"type": "joint"},
        "particles": {"type": "smoke", "rate": 0.15, "color": (140, 140, 140)},
    },

    # ----------------------------------------------------------
    # BONG (Idle-Animation: Bong rauchen)
    # ----------------------------------------------------------
    {
        "id": BONG,
        "name": "BONG",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (50, 70, 80),
            "glow": (25, 35, 45),
        },
        "eyes": {"scale_h": 0.5, "droopy": True},
        "accessory": {"type": "bong"},
        "particles": {"type": "smoke", "rate": 0.20, "color": (160, 160, 160)},
    },

    # ----------------------------------------------------------
    # COFFEE
    # ----------------------------------------------------------
    {
        "id": COFFEE,
        "name": "COFFEE",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (140, 100, 60),
            "glow": (80, 50, 30),
        },
        "mouth": {"style": "sip"},
        "accessory": {"type": "coffee"},
        "particles": {"type": "smoke", "rate": 0.08, "color": (200, 200, 200)},
    },

    # ----------------------------------------------------------
    # YAWN
    # ----------------------------------------------------------
    {
        "id": YAWN,
        "name": "YAWN",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (80, 80, 100),
            "glow": (40, 40, 55),
        },
        "mouth": {"style": "yawn"},
    },

    # ----------------------------------------------------------
    # STRETCH
    # ----------------------------------------------------------
    {
        "id": STRETCH,
        "name": "STRETCH",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (80, 120, 100),
            "glow": (40, 60, 50),
        },
        "physics": {
            "stretch_h": 20,
            "stretch_w": -12,
        },
    },

    # ----------------------------------------------------------
    # DOZE (Eindoesen)
    # ----------------------------------------------------------
    {
        "id": DOZE,
        "name": "DOZE",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (50, 50, 70),
            "glow": (25, 25, 40),
        },
        "eyes": {"scale_h": 0.18, "droopy": True},
        "particles": {"type": "zzz", "rate": 0.06, "color": (180, 180, 200)},
    },

    # ----------------------------------------------------------
    # WATCH (Uhr anschauen)
    # ----------------------------------------------------------
    {
        "id": WATCH,
        "name": "WATCH",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (70, 70, 90),
            "glow": (35, 35, 50),
        },
        "eyes": {"look_offset": -10},
        "accessory": {"type": "watch"},
    },

    # ----------------------------------------------------------
    # TONGUE (Zunge rausstrecken)
    # ----------------------------------------------------------
    {
        "id": TONGUE,
        "name": "TONGUE",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (80, 80, 100),
            "glow": (40, 40, 55),
        },
        "mouth": {"style": "tongue"},
    },

    # ----------------------------------------------------------
    # DANCE (Idle-Tanz)
    # ----------------------------------------------------------
    {
        "id": DANCE,
        "name": "DANCE",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (180, 100, 200),
            "glow": (90, 50, 110),
        },
        "physics": {
            "bounce_speed": 0.4,
            "bounce_amp": 12,
            "sway_speed": 0.3,
            "sway_amp": 8,
        },
    },

    # ----------------------------------------------------------
    # MEDITATE (Idle-Meditation)
    # ----------------------------------------------------------
    {
        "id": MEDITATE,
        "name": "MEDITATE",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (100, 80, 160),
            "glow": (60, 40, 100),
        },
        "eyes": {"scale_h": 0.3},
        "mouth": {"style": "neutral"},
        "physics": {
            "sway_speed": 0.02,
            "sway_amp": 1,
        },
    },

    # ----------------------------------------------------------
    # GAME (Idle-Spielen, zocken)
    # ----------------------------------------------------------
    {
        "id": GAME,
        "name": "GAME",
        "group": "idle",
        "priority": 5,
        "fast_track": False,
        "labels": {},
        "body": {
            "color": (50, 200, 50),
            "glow": (25, 120, 25),
        },
        "eyes": {"scale_w": 0.9, "scale_h": 0.8},
        "accessory": {"type": "gamepad"},
    },
]

# ============================================================
# Registrierung
# ============================================================
register_ignored_labels(IGNORED_IDLE_LABELS)
register_group(IDLE_MOODS)
